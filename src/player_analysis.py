"""Player-level DSS contribution analysis.

Identifies which individual DBs contribute most to their team's sync score.
Uses a leave-one-out approach: DSS drops most when you remove the player
whose absence hurts sync the most = that player is the "sync anchor".

Also computes per-player VA contribution (how much they align with the group).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from dss import (
    load_metadata, load_tracking_data, identify_secondary,
    velocity_alignment, spacing_discipline, orientation_divergence,
)
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def compute_player_va_contribution(
    secondary_df: pd.DataFrame,
    snap_event: str = "ball_snap",
    end_event: str = "pass_forward",
) -> pd.DataFrame:
    """For each DB on each play, compute their individual velocity alignment
    with the group — how well they move WITH their teammates.

    Returns a DataFrame with nflId, gameId, playId, mean_va_contribution.
    """
    snap_frames = secondary_df[secondary_df["event"] == snap_event]["frameId"].unique()
    end_frames = secondary_df[secondary_df["event"] == end_event]["frameId"].unique()

    if len(snap_frames) == 0 or len(end_frames) == 0:
        return pd.DataFrame()

    snap_frame, end_frame = snap_frames[0], end_frames[0]
    if end_frame <= snap_frame:
        return pd.DataFrame()

    play_frames = secondary_df[
        (secondary_df["frameId"] >= snap_frame)
        & (secondary_df["frameId"] <= end_frame)
    ]

    records = []
    for frame_id, frame_df in play_frames.groupby("frameId"):
        if frame_df["nflId"].nunique() < 3:
            continue

        dir_rad = np.radians(frame_df["dir"].values)
        s = frame_df["s"].values
        vx = s * np.cos(dir_rad)
        vy = s * np.sin(dir_rad)

        mean_vx, mean_vy = np.mean(vx), np.mean(vy)
        mean_mag = np.sqrt(mean_vx**2 + mean_vy**2)

        if mean_mag < 1e-6:
            continue

        for idx, row in frame_df.iterrows():
            i = frame_df.index.get_loc(idx)
            indiv_mag = np.sqrt(vx[i]**2 + vy[i]**2)
            if indiv_mag < 1e-6:
                cos_sim = 1.0
            else:
                cos_sim = float(np.clip(
                    (vx[i]*mean_vx + vy[i]*mean_vy) / (indiv_mag * mean_mag), 0, 1
                ))
            records.append({
                "nflId": row["nflId"],
                "frameId": frame_id,
                "va_contribution": cos_sim,
            })

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records).groupby("nflId")["va_contribution"].mean().reset_index()


def build_player_leaderboard(
    tracking_df: pd.DataFrame,
    scouting_df: pd.DataFrame,
    players_df: pd.DataFrame,
    plays_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build a per-player DSS contribution leaderboard."""
    # Identify secondary
    secondary_df = identify_secondary(tracking_df, scouting_df, players_df)
    secondary_df = secondary_df.merge(
        plays_df[["gameId", "playId", "defensiveTeam", "passResult",
                   "pff_passCoverage", "pff_passCoverageType"]],
        on=["gameId", "playId"], how="left",
    )
    secondary_df = secondary_df[secondary_df["team"] == secondary_df["defensiveTeam"]]

    print(f"  Secondary rows for player analysis: {len(secondary_df):,}")

    records = []
    for (gid, pid), play_df in secondary_df.groupby(["gameId", "playId"]):
        if play_df["nflId"].nunique() < 3:
            continue

        contrib = compute_player_va_contribution(play_df)
        if contrib.empty:
            continue

        play_meta = plays_df[(plays_df["gameId"] == gid) & (plays_df["playId"] == pid)]
        if play_meta.empty:
            continue
        meta = play_meta.iloc[0]

        for _, row in contrib.iterrows():
            records.append({
                "nflId": row["nflId"],
                "gameId": gid,
                "playId": pid,
                "va_contribution": row["va_contribution"],
                "defensiveTeam": meta["defensiveTeam"],
                "coverage": meta.get("pff_passCoverage", "Unknown"),
                "coverageType": meta.get("pff_passCoverageType", "Unknown"),
                "passResult": meta["passResult"],
            })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Aggregate per player
    agg = df.groupby(["nflId", "defensiveTeam"]).agg(
        mean_va=("va_contribution", "mean"),
        plays=("playId", "nunique"),
        comp_rate=("passResult", lambda x: (x == "C").mean()),
    ).reset_index()

    # Filter: at least 20 plays
    agg = agg[agg["plays"] >= 20]

    # Join with player names and positions
    agg = agg.merge(
        players_df[["nflId", "displayName", "officialPosition"]],
        on="nflId", how="left",
    )

    return agg.sort_values("mean_va", ascending=False)


def plot_player_leaderboard(
    leaderboard_df: pd.DataFrame,
    output_path: str = "output/dss_player_leaderboard.png",
    top_n: int = 20,
) -> str:
    """Horizontal bar chart of top DBs by VA contribution."""
    top = leaderboard_df.head(top_n).copy()

    fig, axes = plt.subplots(1, 2, figsize=(14, max(5, top_n * 0.4)))

    # Left: top 20 by VA contribution
    ax = axes[0]
    colors = plt.cm.RdYlGn(np.linspace(0.3, 0.9, len(top)))
    bars = ax.barh(top["displayName"], top["mean_va"] * 100,
                   color=colors, edgecolor="white", lw=0.4)
    ax.set_xlabel("Mean VA Contribution (0–100)", fontsize=11)
    ax.set_title("Top DBs: Velocity Alignment\n(how well they move with their secondary)",
                 fontsize=12, fontweight="bold")
    ax.invert_yaxis()

    for i, (val, team, pos, plays) in enumerate(zip(
        top["mean_va"], top["defensiveTeam"], top["officialPosition"], top["plays"]
    )):
        ax.text(val * 100 + 0.2, i,
                f"  {val*100:.1f} ({team}, {pos}, n={plays})",
                va="center", fontsize=8)

    # Right: position breakdown
    ax2 = axes[1]
    pos_agg = leaderboard_df.groupby("officialPosition").agg(
        mean_va=("mean_va", "mean"),
        count=("nflId", "count"),
    ).reset_index().sort_values("mean_va", ascending=True)

    c2 = plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(pos_agg)))
    ax2.barh(pos_agg["officialPosition"], pos_agg["mean_va"] * 100,
             color=c2, edgecolor="white")
    ax2.set_xlabel("Mean VA Contribution (0–100)", fontsize=11)
    ax2.set_title("VA Contribution by Position\n(which position anchors secondary sync?)",
                  fontsize=12, fontweight="bold")
    ax2.invert_yaxis()

    for i, (val, cnt) in enumerate(zip(pos_agg["mean_va"], pos_agg["count"])):
        ax2.text(val * 100 + 0.2, i, f"  {val*100:.1f} (n={cnt})", va="center", fontsize=9)

    plt.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return str(output_path)


if __name__ == "__main__":
    print("=== Player DSS Contribution Leaderboard ===\n")

    meta = load_metadata(DATA_DIR)
    games, plays, players, scouting = (
        meta["games"], meta["plays"], meta["players"], meta["scouting"]
    )

    print("Loading tracking data...")
    tracking = load_tracking_data(DATA_DIR / "tracking")
    tracking = tracking.merge(
        players[["nflId", "officialPosition"]].rename(
            columns={"officialPosition": "position"}
        ),
        on="nflId", how="left",
    )

    print("Building player leaderboard...")
    leaderboard = build_player_leaderboard(tracking, scouting, players, plays)
    print(f"  Players ranked: {len(leaderboard)}")
    print("\nTop 10:")
    print(leaderboard[["displayName", "officialPosition", "defensiveTeam",
                         "mean_va", "plays", "comp_rate"]].head(10).to_string(index=False))

    chart = plot_player_leaderboard(
        leaderboard, output_path=str(OUTPUT_DIR / "dss_player_leaderboard.png")
    )
    print(f"\nChart saved: {chart}")

    leaderboard.to_csv(OUTPUT_DIR / "dss_player_leaderboard.csv", index=False)
    print(f"CSV saved: {OUTPUT_DIR / 'dss_player_leaderboard.csv'}")
