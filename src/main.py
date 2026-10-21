"""Main pipeline: load data, compute PCI, generate visualizations."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from pci import load_tracking_data, identify_qb, compute_collapse_rate
from visualization import animate_play, plot_pci_ranking

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def main():
    print("=== Pocket Collapse Index (PCI) Pipeline ===\n")

    # 1. Load metadata
    print("Loading metadata...")
    games = pd.read_csv(DATA_DIR / "games.csv")
    plays = pd.read_csv(DATA_DIR / "plays.csv")
    players = pd.read_csv(DATA_DIR / "players.csv")
    print(f"  Games: {len(games)} | Plays: {len(plays)} | Players: {len(players)}")

    # 2. Load tracking data
    print("Loading tracking data...")
    tracking = load_tracking_data(DATA_DIR / "tracking")
    print(f"  Tracking rows: {len(tracking):,}")
    print(f"  Games in tracking: {tracking['gameId'].nunique()}")
    print(f"  Columns: {list(tracking.columns)}")

    # 3. Filter to pass plays
    print("\nFiltering to pass plays...")
    pass_results = ["C", "I", "S", "IN"]
    pass_plays = plays[plays["passResult"].isin(pass_results)]
    print(f"  Pass plays: {len(pass_plays)}")

    # Merge tracking with play info to get possessionTeam
    tracking_merged = tracking.merge(
        pass_plays[["gameId", "playId", "possessionTeam", "defensiveTeam",
                     "down", "yardsToGo", "passResult", "playResult"]],
        on=["gameId", "playId"],
        how="inner",
    )
    print(f"  Tracking rows on pass plays: {len(tracking_merged):,}")

    # 4. Determine offensive/defensive team per frame
    games_merge = games[["gameId", "homeTeamAbbr", "visitorTeamAbbr"]]
    tracking_merged = tracking_merged.merge(games_merge, on="gameId", how="left")

    tracking_merged["offDefTeam"] = np.where(
        tracking_merged["possessionTeam"] == tracking_merged["homeTeamAbbr"],
        "home", "away"
    )
    tracking_merged["teamRole"] = np.where(
        tracking_merged["team"] == tracking_merged["offDefTeam"],
        "off", "def"
    )

    # 5. Compute PCI for each play
    print("\nComputing Pocket Collapse Index...")
    results = []

    for (gid, pid), play_df in tracking_merged.groupby(["gameId", "playId"]):
        qb_rows = play_df[play_df["position"] == "QB"]
        if qb_rows.empty:
            continue
        qb_id = qb_rows["nflId"].iloc[0]

        result = compute_collapse_rate(play_df, qb_id)
        if result is None:
            continue

        play_info = pass_plays[
            (pass_plays["gameId"] == gid) & (pass_plays["playId"] == pid)
        ].iloc[0]

        result["gameId"] = gid
        result["playId"] = pid
        result["team"] = play_info["possessionTeam"]
        result["opponent"] = play_info["defensiveTeam"]
        result["passResult"] = play_info["passResult"]
        result["playResult"] = play_info["playResult"]
        results.append(result)

    pci_df = pd.DataFrame(results)
    print(f"  Plays with PCI computed: {len(pci_df)}")

    if len(pci_df) == 0:
        print("  WARNING: No plays could be computed. Check event names in data.")
        print(f"  Unique events: {tracking_merged['event'].unique()}")
        return

    # 6. Generate visualizations
    print("\nGenerating visualizations...")

    team_chart = plot_pci_ranking(
        pci_df,
        output_path=str(OUTPUT_DIR / "pci_ranking.png"),
        group_by="team",
        title="Pocket Collapse Index - Team Ranking (lower = better pass protection)",
    )
    print(f"  Team ranking saved: {team_chart}")

    # Animate the worst pocket collapse play
    worst_play = pci_df.loc[pci_df["pci"].idxmax()]
    worst_play_df = tracking_merged[
        (tracking_merged["gameId"] == worst_play["gameId"])
        & (tracking_merged["playId"] == worst_play["playId"])
    ]
    qb_id = worst_play_df[worst_play_df["position"] == "QB"]["nflId"].iloc[0]

    anim_path = animate_play(
        worst_play_df,
        qb_id,
        output_path=str(OUTPUT_DIR / "worst_collapse.gif"),
        title=f"Worst Pocket Collapse - {worst_play['team']} (PCI={worst_play['pci']:.3f})",
    )
    print(f"  Animation saved: {anim_path}")

    # 7. Save results
    pci_df.to_csv(OUTPUT_DIR / "pci_results.csv", index=False)
    print(f"\nResults saved to {OUTPUT_DIR / 'pci_results.csv'}")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
