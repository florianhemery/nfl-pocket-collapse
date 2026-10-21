"""Defensive Sync Score (DSS) — metric computation.

Quantifies how synchronized a defensive secondary moves as a unit using
frame-by-frame tracking data. Three sub-scores:

  1. Velocity Alignment (VA)  — dot product of each DB's velocity vector
     vs. the group mean velocity vector. High = everyone moving together.
  2. Spacing Discipline (SD)  — inverse of the coefficient of variation of
     inter-DB distances. Low CV = formation maintained.
  3. Orientation Divergence (OD) — 1 minus the circular variance of body
     orientations. LOW coherence (DBs looking different directions) is BETTER
     for defense — it means each DB is tracking his own assignment, not all
     staring at the QB. This sub-score is inverted vs. raw coherence.

DSS = 100 * (0.40*VA + 0.30*SD + 0.30*OD), scale 0-100.
Higher = better-coordinated secondary (fewer completions allowed).

Key finding: orientation coherence (all DBs looking the same direction) is
COUNTER-productive — it correlates positively with completion rate. The DSS
inverts it so that divergent gaze (each DB on his man) scores higher.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────
FIELD_LENGTH = 120
FIELD_WIDTH = 53.3

# Positions that belong to the secondary (defensive backs)
SECONDARY_POSITIONS = {"CB", "FS", "SS", "DB"}

# PFF lined-up positions for coverage players (secondary + slot corners)
COVERAGE_PFF_POSITIONS = {
    "LCB", "RCB", "FS", "FSL", "FSR", "SS", "SSL", "SSR",
    "SCBL", "SCBR", "SCBiL", "SCBiR", "SCBoL", "SCBoR",
}


# ── Data loading ─────────────────────────────────────────────────────────
def load_metadata(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load the four metadata CSVs."""
    data_dir = Path(data_dir)
    return {
        "games": pd.read_csv(data_dir / "games.csv"),
        "plays": pd.read_csv(data_dir / "plays.csv"),
        "players": pd.read_csv(data_dir / "players.csv"),
        "scouting": pd.read_csv(data_dir / "pffScoutingData.csv"),
    }


def load_tracking_data(
    tracking_dir: str | Path,
    game_ids: list[int] | None = None,
    max_games: int | None = None,
) -> pd.DataFrame:
    """Load tracking CSVs, optionally filtered by game ID or capped."""
    tracking_dir = Path(tracking_dir)
    files = sorted(tracking_dir.glob("tracking_*.csv"))
    if game_ids:
        files = [f for f in files if any(str(gid) in f.stem for gid in game_ids)]
    if max_games:
        files = files[:max_games]
    frames = [pd.read_csv(f) for f in files]
    if not frames:
        raise FileNotFoundError(f"No tracking files found in {tracking_dir}")
    return pd.concat(frames, ignore_index=True)


# ── Secondary identification ────────────────────────────────────────────
def identify_secondary(
    tracking_df: pd.DataFrame,
    scouting_df: pd.DataFrame,
    players_df: pd.DataFrame,
) -> pd.DataFrame:
    """Identify which players on the defensive team are in coverage (secondary).

    Uses PFF scouting data (pff_role == 'Coverage') cross-referenced with
    player officialPosition to find defensive backs.
    """
    # Players who are DBs by official position
    db_player_ids = set(
        players_df.loc[
            players_df["officialPosition"].isin(SECONDARY_POSITIONS), "nflId"
        ]
    )

    # Scouting entries where role is Coverage
    coverage_scouting = scouting_df[scouting_df["pff_role"] == "Coverage"][
        ["gameId", "playId", "nflId", "pff_positionLinedUp"]
    ].copy()

    # Merge with tracking to keep only DBs in coverage on each play
    merged = tracking_df.merge(
        coverage_scouting,
        on=["gameId", "playId", "nflId"],
        how="inner",
    )

    # Further filter: player must be a DB by official position
    merged = merged[merged["nflId"].isin(db_player_ids)]

    return merged


# ── Sub-score 1: Velocity Alignment ────────────────────────────────────
def velocity_alignment(group_df: pd.DataFrame) -> float:
    """Mean cosine similarity between each DB's velocity vector and the group mean.

    velocity vector from (s, dir): vx = s * cos(dir_rad), vy = s * sin(dir_rad)
    Returns value in [0, 1]. 1 = all moving in the same direction.
    """
    if len(group_df) < 2:
        return np.nan

    # Direction is in degrees, convert to radians
    dir_rad = np.radians(group_df["dir"].values)
    s = group_df["s"].values

    # Velocity vectors
    vx = s * np.cos(dir_rad)
    vy = s * np.sin(dir_rad)

    # Group mean velocity vector
    mean_vx, mean_vy = np.mean(vx), np.mean(vy)
    mean_mag = np.sqrt(mean_vx**2 + mean_vy**2)

    if mean_mag < 1e-6:
        # Group is nearly stationary — alignment is trivially high
        return 1.0

    # Cosine similarity of each individual vector vs mean
    cos_sims = []
    for i in range(len(vx)):
        indiv_mag = np.sqrt(vx[i] ** 2 + vy[i] ** 2)
        if indiv_mag < 1e-6:
            continue  # skip stationary players
        dot = vx[i] * mean_vx + vy[i] * mean_vy
        cos_sim = dot / (indiv_mag * mean_mag)
        cos_sims.append(cos_sim)

    if not cos_sims:
        return 1.0

    # Mean cosine similarity, clamped to [0, 1]
    # (cos sim can be negative if moving opposite direction)
    return float(np.clip(np.mean(cos_sims), 0, 1))


# ── Sub-score 2: Spacing Discipline ────────────────────────────────────
def spacing_discipline(group_df: pd.DataFrame) -> float:
    """Inverse of coefficient of variation of pairwise distances.

    Low CV = uniform spacing = high discipline.
    Returns value in [0, 1].
    """
    if len(group_df) < 2:
        return np.nan

    positions = group_df[["x", "y"]].values
    n = len(positions)

    # All pairwise distances
    dists = []
    for i in range(n):
        for j in range(i + 1, n):
            d = np.sqrt(np.sum((positions[i] - positions[j]) ** 2))
            dists.append(d)

    dists = np.array(dists)
    mean_d = np.mean(dists)
    if mean_d < 1e-6:
        return 1.0

    cv = np.std(dists) / mean_d  # coefficient of variation

    # Map CV to [0, 1]: CV=0 → 1, CV=1 → 0.5, CV=2+ → 0
    # Using a decay: score = 1 / (1 + cv)
    score = 1.0 / (1.0 + cv)
    return float(np.clip(score, 0, 1))


# ── Sub-score 3: Orientation Divergence ─────────────────────────────────
def orientation_coherence(group_df: pd.DataFrame) -> float:
    """Circular variance of body orientations (o field).

    Returns the resultant length R in [0, 1].
    R=1 means all angles identical; R=0 means uniformly distributed.
    This is the RAW coherence — the DSS inverts it (see compute_dss_for_play).
    """
    if len(group_df) < 2:
        return np.nan

    o_rad = np.radians(group_df["o"].values)

    mean_sin = np.mean(np.sin(o_rad))
    mean_cos = np.mean(np.cos(o_rad))
    R = np.sqrt(mean_sin**2 + mean_cos**2)

    return float(R)


def orientation_divergence(group_df: pd.DataFrame) -> float:
    """1 minus the orientation coherence.

    HIGH divergence (DBs looking different directions) is BETTER for defense:
    each DB is tracking his own assignment rather than all staring at the QB.
    Returns value in [0, 1]. 1 = all looking different directions (good).
    """
    oc = orientation_coherence(group_df)
    if np.isnan(oc):
        return np.nan
    return 1.0 - oc


# ── DSS computation ────────────────────────────────────────────────────
def compute_dss_for_play(
    secondary_df: pd.DataFrame,
    snap_event: str = "ball_snap",
    end_event: str = "pass_forward",
    weights: tuple[float, float, float] = (0.40, 0.30, 0.30),
) -> Optional[dict]:
    """Compute the Defensive Sync Score for a single play.

    Averages the three sub-scores across all post-snap frames
    (from ball_snap to pass_forward).

    Sub-scores:
      VA: Velocity Alignment (0-1, higher = better)
      SD: Spacing Discipline (0-1, higher = better)
      OD: Orientation Divergence (0-1, higher = better — DBs tracking
          different assignments instead of all staring at QB)

    DSS = 100 * (0.40*VA + 0.30*SD + 0.30*OD)

    Returns dict with per-play DSS and sub-scores, or None if insufficient data.
    """
    w_va, w_sd, w_od = weights

    # Find frame range
    events = secondary_df["event"].dropna().unique()
    snap_frames = secondary_df[secondary_df["event"] == snap_event]["frameId"].unique()
    end_frames = secondary_df[secondary_df["event"] == end_event]["frameId"].unique()

    if len(snap_frames) == 0 or len(end_frames) == 0:
        return None

    snap_frame = snap_frames[0]
    end_frame = end_frames[0]

    if end_frame <= snap_frame:
        return None

    # Filter to post-snap frames
    play_frames = secondary_df[
        (secondary_df["frameId"] >= snap_frame)
        & (secondary_df["frameId"] <= end_frame)
    ]

    # Need at least 3 DBs per frame for meaningful sync
    frame_counts = play_frames.groupby("frameId")["nflId"].nunique()
    valid_frames = frame_counts[frame_counts >= 3].index

    if len(valid_frames) < 3:
        return None

    play_frames = play_frames[play_frames["frameId"].isin(valid_frames)]

    # Compute sub-scores per frame
    va_scores = []
    sd_scores = []
    od_scores = []

    for frame_id, frame_df in play_frames.groupby("frameId"):
        if frame_df["nflId"].nunique() < 3:
            continue
        va = velocity_alignment(frame_df)
        sd = spacing_discipline(frame_df)
        od = orientation_divergence(frame_df)
        if not np.isnan(va):
            va_scores.append(va)
        if not np.isnan(sd):
            sd_scores.append(sd)
        if not np.isnan(od):
            od_scores.append(od)

    if len(va_scores) < 2:
        return None

    mean_va = float(np.mean(va_scores))
    mean_sd = float(np.mean(sd_scores)) if sd_scores else 0.5
    mean_od = float(np.mean(od_scores)) if od_scores else 0.5

    dss = 100.0 * (w_va * mean_va + w_sd * mean_sd + w_od * mean_od)

    return {
        "dss": round(dss, 2),
        "va": round(100 * mean_va, 2),
        "sd": round(100 * mean_sd, 2),
        "od": round(100 * mean_od, 2),
        "num_dbs": int(frame_counts.get(snap_frame, 0)),
        "frames_analyzed": len(va_scores),
    }


def compute_dss_all_plays(
    tracking_df: pd.DataFrame,
    scouting_df: pd.DataFrame,
    players_df: pd.DataFrame,
    plays_df: pd.DataFrame,
    games_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute DSS for all pass plays in the dataset.

    Returns a DataFrame with one row per play: DSS, sub-scores, and play metadata.
    """
    # Identify secondary tracking data
    print("  Identifying secondary players...")
    secondary_df = identify_secondary(tracking_df, scouting_df, players_df)
    print(f"  Secondary tracking rows: {len(secondary_df):,}")

    # Determine defensive team per play
    # In tracking, 'team' is 3-letter abbr. The defensive team is NOT possessionTeam.
    secondary_df = secondary_df.merge(
        plays_df[["gameId", "playId", "possessionTeam", "defensiveTeam",
                   "passResult", "playResult", "pff_passCoverage",
                   "pff_passCoverageType", "down", "yardsToGo",
                   "absoluteYardlineNumber"]],
        on=["gameId", "playId"],
        how="left",
    )

    # Verify these players are on the defensive team
    secondary_df = secondary_df[secondary_df["team"] == secondary_df["defensiveTeam"]]

    print(f"  After defensive team filter: {len(secondary_df):,}")
    print(f"  Unique plays with secondary data: {secondary_df[['gameId','playId']].drop_duplicates().shape[0]}")

    # Compute DSS per play
    print("  Computing DSS per play...")
    results = []
    play_groups = secondary_df.groupby(["gameId", "playId"])

    total = len(play_groups)
    for idx, ((gid, pid), play_df) in enumerate(play_groups):
        if idx % 500 == 0:
            print(f"    Progress: {idx}/{total} plays...")

        result = compute_dss_for_play(play_df)
        if result is None:
            continue

        # Get play metadata
        play_meta = plays_df[(plays_df["gameId"] == gid) & (plays_df["playId"] == pid)]
        if play_meta.empty:
            continue
        meta = play_meta.iloc[0]

        result["gameId"] = gid
        result["playId"] = pid
        result["defensiveTeam"] = meta["defensiveTeam"]
        result["offensiveTeam"] = meta["possessionTeam"]
        result["passResult"] = meta["passResult"]
        result["playResult"] = meta["playResult"]
        result["coverage"] = meta.get("pff_passCoverage", "Unknown")
        result["coverageType"] = meta.get("pff_passCoverageType", "Unknown")
        result["down"] = meta["down"]
        result["yardsToGo"] = meta["yardsToGo"]

        # Binary outcome: 1 = completion, 0 = incompletion/INT
        result["completed"] = 1 if meta["passResult"] == "C" else 0
        result["sacked"] = 1 if meta["passResult"] == "S" else 0

        results.append(result)

    return pd.DataFrame(results)
