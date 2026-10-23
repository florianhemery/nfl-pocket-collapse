"""Frozen copy of the first, loop-based DSS implementation (src/dss.py at 1c9e489).

Kept only as an oracle: tests/test_equivalence.py checks that the vectorized code in
``nfl_dss.metrics`` and ``nfl_dss.pipeline`` returns the same values. Do not edit the math here.
Excluded from pyright and from lint on purpose (it is unchanged historical code).
"""

from typing import Optional

import numpy as np
import pandas as pd


# -- Sub-score 1: Velocity Alignment ------------------------------------
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
        # Group is nearly stationary - alignment is trivially high
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


# -- Sub-score 2: Spacing Discipline ------------------------------------
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

    # Map CV to [0, 1]: CV=0 -> 1, CV=1 -> 0.5, CV=2+ -> 0
    # Using a decay: score = 1 / (1 + cv)
    score = 1.0 / (1.0 + cv)
    return float(np.clip(score, 0, 1))


# -- Sub-score 3: Orientation Divergence ---------------------------------
def orientation_coherence(group_df: pd.DataFrame) -> float:
    """Circular variance of body orientations (o field).

    Returns the resultant length R in [0, 1].
    R=1 means all angles identical; R=0 means uniformly distributed.
    This is the RAW coherence - the DSS inverts it (see compute_dss_for_play).
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


# -- DSS computation ----------------------------------------------------
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
      OD: Orientation Divergence (0-1, higher = better - DBs tracking
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
        (secondary_df["frameId"] >= snap_frame) & (secondary_df["frameId"] <= end_frame)
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
