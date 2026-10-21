"""Main pipeline: load data, compute DSS, generate visualizations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from dss import (
    load_metadata,
    load_tracking_data,
    identify_secondary,
    compute_dss_all_plays,
)
from dss_visualization import (
    animate_play_dss,
    plot_dss_team_ranking,
    plot_dss_vs_outcome,
    plot_dss_heatmap,
)

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def main():
    print("=" * 60)
    print("  Defensive Sync Score (DSS) Pipeline")
    print("=" * 60 + "\n")

    # 1. Load metadata
    print("[1/6] Loading metadata...")
    meta = load_metadata(DATA_DIR)
    games = meta["games"]
    plays = meta["plays"]
    players = meta["players"]
    scouting = meta["scouting"]
    print(f"  Games: {len(games)} | Plays: {len(plays)} | "
          f"Players: {len(players)} | Scouting rows: {len(scouting)}")

    # 2. Load tracking data
    print("\n[2/6] Loading tracking data...")
    tracking = load_tracking_data(DATA_DIR / "tracking")
    print(f"  Tracking rows: {len(tracking):,}")
    print(f"  Games: {tracking['gameId'].nunique()}")
    print(f"  Columns: {list(tracking.columns)}")

    # Add player positions to tracking
    tracking = tracking.merge(
        players[["nflId", "officialPosition"]].rename(
            columns={"officialPosition": "position"}
        ),
        on="nflId",
        how="left",
    )

    # 3. Compute DSS for all plays
    print("\n[3/6] Computing Defensive Sync Score...")
    dss_df = compute_dss_all_plays(tracking, scouting, players, plays, games)
    print(f"  Plays with DSS: {len(dss_df)}")
    print(f"  DSS range: {dss_df['dss'].min():.1f} — {dss_df['dss'].max():.1f}")
    print(f"  DSS mean: {dss_df['dss'].mean():.1f}")

    # 4. Analysis & validation
    print("\n[4/6] Statistical validation...")
    # Overall: DSS vs completion rate
    high_dss = dss_df[dss_df["dss"] >= dss_df["dss"].median()]
    low_dss = dss_df[dss_df["dss"] < dss_df["dss"].median()]
    print(f"  High DSS plays: completion rate = {high_dss['completed'].mean():.3f}")
    print(f"  Low DSS plays:  completion rate = {low_dss['completed'].mean():.3f}")

    # By coverage type
    for ct in ["Man", "Zone"]:
        subset = dss_df[dss_df["coverageType"] == ct]
        if len(subset) > 0:
            hi = subset[subset["dss"] >= subset["dss"].median()]
            lo = subset[subset["dss"] < subset["dss"].median()]
            print(f"  {ct}: High DSS comp={hi['completed'].mean():.3f}, "
                  f"Low DSS comp={lo['completed'].mean():.3f} (n={len(subset)})")

    # Correlation
    corr = dss_df["dss"].corr(dss_df["completed"])
    print(f"  Pearson(DSS, completed): {corr:.4f}")

    # 5. Generate visualizations
    print("\n[5/6] Generating visualizations...")

    team_chart = plot_dss_team_ranking(
        dss_df, output_path=str(OUTPUT_DIR / "dss_team_ranking.png")
    )
    print(f"  Team ranking: {team_chart}")

    outcome_chart = plot_dss_vs_outcome(
        dss_df, output_path=str(OUTPUT_DIR / "dss_vs_completion.png")
    )
    print(f"  DSS vs outcome: {outcome_chart}")

    heatmap_chart = plot_dss_heatmap(
        dss_df, output_path=str(OUTPUT_DIR / "dss_heatmap.png")
    )
    print(f"  Heatmap: {heatmap_chart}")

    # Animate the most synchronized play
    best_play = dss_df.loc[dss_df["dss"].idxmax()]
    print(f"\n  Best DSS play: {best_play['defensiveTeam']} "
          f"(DSS={best_play['dss']:.1f}, VA={best_play['va']:.1f}, "
          f"SD={best_play['sd']:.1f}, OD={best_play['od']:.1f})")

    # Rebuild secondary tracking for this play
    secondary_df = identify_secondary(tracking, scouting, players)
    best_sec = secondary_df[
        (secondary_df["gameId"] == best_play["gameId"])
        & (secondary_df["playId"] == best_play["playId"])
    ]
    best_full = tracking[
        (tracking["gameId"] == best_play["gameId"])
        & (tracking["playId"] == best_play["playId"])
    ]

    anim_path = animate_play_dss(
        best_sec, best_full, best_play.to_dict(),
        output_path=str(OUTPUT_DIR / "dss_best_sync.gif"),
        title=f"Best Secondary Sync — {best_play['defensiveTeam']} "
              f"({best_play['coverage']}, DSS={best_play['dss']:.1f})",
    )
    print(f"  Animation: {anim_path}")

    # 6. Save results
    print("\n[6/6] Saving results...")
    dss_df.to_csv(OUTPUT_DIR / "dss_results.csv", index=False)
    print(f"  Results CSV: {OUTPUT_DIR / 'dss_results.csv'}")

    print("\n" + "=" * 60)
    print("  Pipeline complete!")
    print("=" * 60)
    print(f"\n  Plays analyzed: {len(dss_df)}")
    print(f"  Teams ranked: {dss_df['defensiveTeam'].nunique()}")
    print(f"  DSS mean: {dss_df['dss'].mean():.1f} / 100")
    print(f"  Correlation DSS↔completion: {corr:.4f}")
    print(f"\n  Outputs in: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
