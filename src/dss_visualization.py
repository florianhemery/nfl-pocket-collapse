"""Visualizations for the Defensive Sync Score."""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
from pathlib import Path

# NFL field colors
FIELD_GREEN = "#1B5E20"
FIELD_DARK = "#0D3818"
LINE_WHITE = "white"
DB_COLOR = "#F44336"
QB_COLOR = "#FFD700"
WR_COLOR = "#2196F3"

FIELD_LENGTH = 120
FIELD_WIDTH = 53.3


def draw_field(ax) -> None:
    """Draw an NFL field on a matplotlib Axes."""
    ax.add_patch(patches.Rectangle((0, 0), FIELD_LENGTH, FIELD_WIDTH,
                                   facecolor=FIELD_GREEN, edgecolor=LINE_WHITE, lw=2))
    for x in range(10, 110, 10):
        ax.plot([x, x], [0, FIELD_WIDTH], color=LINE_WHITE, lw=1.5, alpha=0.7)
    ax.add_patch(patches.Rectangle((0, 0), 10, FIELD_WIDTH, facecolor="#2E7D32", alpha=0.5))
    ax.add_patch(patches.Rectangle((110, 0), 10, FIELD_WIDTH, facecolor="#2E7D32", alpha=0.5))
    ax.set_xlim(0, FIELD_LENGTH)
    ax.set_ylim(0, FIELD_WIDTH)
    ax.set_aspect("equal")
    ax.axis("off")


def animate_play_dss(
    secondary_df: pd.DataFrame,
    full_play_df: pd.DataFrame,
    dss_result: dict,
    output_path: str = "output/dss_animation.gif",
    title: str = "Defensive Sync Score",
) -> str:
    """Animate a single play showing DBs moving with a live DSS sync meter.

    secondary_df: tracking rows for the defensive secondary on this play
    full_play_df: all tracking rows for this play (for context — QB, WRs, etc.)
    dss_result: dict from compute_dss_for_play
    """
    from matplotlib.animation import FuncAnimation, PillowWriter

    frames_list = sorted(secondary_df["frameId"].unique())
    snap_frames = secondary_df[secondary_df["event"] == "ball_snap"]["frameId"].values
    snap_frame = snap_frames[0] if len(snap_frames) > 0 else frames_list[0]

    fig, (ax_field, ax_meter) = plt.subplots(1, 2, figsize=(14, 6),
                                              gridspec_kw={"width_ratios": [3, 1]})

    def update(frame_idx):
        ax_field.clear()
        ax_meter.clear()
        draw_field(ax_field)

        frame_id = frames_list[frame_idx]
        frame = secondary_df[secondary_df["frameId"] == frame_id]
        full_frame = full_play_df[full_play_df["frameId"] == frame_id]

        # Draw all players for context
        for _, row in full_frame.iterrows():
            if row["nflId"] in set(secondary_df["nflId"].unique()):
                color = DB_COLOR
                size = 100
                role = "DB"
            elif row.get("position") == "QB":
                color = QB_COLOR
                size = 120
                role = "QB"
            else:
                color = WR_COLOR
                size = 50
                role = ""

            ax_field.scatter(row["x"], row["y"], c=color, s=size, zorder=5,
                            edgecolors="white", lw=0.5)

            # Draw velocity vector for DBs
            if role == "DB":
                dir_rad = np.radians(row["dir"])
                vx = row["s"] * np.cos(dir_rad) * 2
                vy = row["s"] * np.sin(dir_rad) * 2
                ax_field.arrow(row["x"], row["y"], vx, vy,
                              head_width=0.8, head_length=0.5, fc=DB_COLOR, ec=DB_COLOR, zorder=6)

        phase = "Post-snap" if frame_id >= snap_frame else "Pre-snap"
        ax_field.set_title(f"{title} — {phase} (frame {frame_idx+1}/{len(frames_list)})",
                          fontsize=13, color="white", fontweight="bold")

        # Sync meter
        if frame_id >= snap_frame:
            va = dss_result.get("va", 0)
            sd = dss_result.get("sd", 0)
            od = dss_result.get("od", 0)
            dss = dss_result.get("dss", 0)
        else:
            va = sd = od = dss = 0

        ax_meter.set_xlim(0, 1)
        ax_meter.set_ylim(0, 4)
        ax_meter.axis("off")
        ax_meter.set_title("Sync Meter", fontsize=14, fontweight="bold")

        labels = ["DSS", "Velocity\nAlign", "Spacing\nDisc", "Orient\nDiverg"]
        values = [dss, va, sd, od]
        colors = ["#FF6F00", "#E91E63", "#9C27B0", "#3F51B5"]

        for i, (label, val, c) in enumerate(zip(labels, values, colors)):
            y = 3.5 - i * 0.9
            ax_meter.barh(y, val / 100, height=0.6, color=c, alpha=0.8)
            ax_meter.text(0.02, y, label, va="center", fontsize=9, color="white", fontweight="bold")
            ax_meter.text(val / 100 + 0.02, y, f"{val:.1f}", va="center", fontsize=9)

    anim = FuncAnimation(fig, update, frames=len(frames_list), interval=120)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PillowWriter(fps=8)
    anim.save(str(output_path), writer=writer)
    plt.close(fig)

    return str(output_path)


def plot_dss_team_ranking(
    dss_df: pd.DataFrame,
    output_path: str = "output/dss_team_ranking.png",
) -> str:
    """Horizontal bar chart ranking defensive teams by average DSS."""
    agg = dss_df.groupby("defensiveTeam")["dss"].agg(["mean", "count"]).reset_index()
    agg = agg[agg["count"] >= 5].sort_values("mean", ascending=False)

    fig, ax = plt.subplots(figsize=(10, max(4, len(agg) * 0.35)))

    colors = plt.cm.RdYlGn(np.linspace(0.15, 0.85, len(agg)))
    ax.barh(agg["defensiveTeam"], agg["mean"], color=colors, edgecolor="white", lw=0.5)
    ax.set_xlabel("Defensive Sync Score (higher = more synchronized)", fontsize=11)
    ax.set_title("Defensive Sync Score — Team Ranking", fontsize=14, fontweight="bold")
    ax.invert_yaxis()

    for i, (val, cnt) in enumerate(zip(agg["mean"], agg["count"])):
        ax.text(val + 0.3, i, f"  {val:.1f} (n={cnt})", va="center", fontsize=9)

    plt.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return str(output_path)


def plot_dss_vs_outcome(
    dss_df: pd.DataFrame,
    output_path: str = "output/dss_vs_completion.png",
) -> str:
    """Scatter plot: DSS vs completion rate, with binned trend line."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: DSS vs completion (binned)
    ax = axes[0]
    bins = np.linspace(dss_df["dss"].min(), dss_df["dss"].max(), 15)
    dss_df = dss_df.copy()
    dss_df["dss_bin"] = pd.cut(dss_df["dss"], bins=bins, labels=False)
    binned = dss_df.groupby("dss_bin").agg(
        dss=("dss", "mean"),
        comp_rate=("completed", "mean"),
        count=("completed", "count"),
    ).reset_index()
    binned = binned[binned["count"] >= 5]

    ax.scatter(binned["dss"], binned["comp_rate"], s=binned["count"] * 3, alpha=0.7, c="#E91E63")
    z = np.polyfit(binned["dss"], binned["comp_rate"], 1)
    x_line = np.linspace(binned["dss"].min(), binned["dss"].max(), 100)
    ax.plot(x_line, np.polyval(z, x_line), "--", color="#333", lw=2)
    ax.set_xlabel("Defensive Sync Score (binned)", fontsize=11)
    ax.set_ylabel("Completion Rate", fontsize=11)
    ax.set_title("DSS vs Pass Completion Rate", fontsize=13, fontweight="bold")
    ax.grid(alpha=0.3)

    # Right: DSS by coverage type
    ax = axes[1]
    for ct in ["Man", "Zone"]:
        subset = dss_df[dss_df["coverageType"] == ct]
        if len(subset) > 0:
            bins2 = np.linspace(subset["dss"].min(), subset["dss"].max(), 12)
            subset = subset.copy()
            subset["dss_bin"] = pd.cut(subset["dss"], bins=bins2, labels=False)
            b = subset.groupby("dss_bin").agg(
                dss=("dss", "mean"),
                comp_rate=("completed", "mean"),
                count=("completed", "count"),
            ).reset_index()
            b = b[b["count"] >= 3]
            color = "#FF5722" if ct == "Man" else "#2196F3"
            ax.scatter(b["dss"], b["comp_rate"], s=b["count"] * 3, alpha=0.6, c=color, label=ct)
            if len(b) > 1:
                z2 = np.polyfit(b["dss"], b["comp_rate"], 1)
                ax.plot(np.linspace(b["dss"].min(), b["dss"].max(), 50),
                        np.polyval(z2, np.linspace(b["dss"].min(), b["dss"].max(), 50)),
                        "--", color=color, lw=2)

    ax.set_xlabel("DSS (binned)", fontsize=11)
    ax.set_ylabel("Completion Rate", fontsize=11)
    ax.set_title("DSS vs Completion — Man vs Zone", fontsize=13, fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return str(output_path)


def plot_dss_heatmap(
    dss_df: pd.DataFrame,
    output_path: str = "output/dss_heatmap.png",
) -> str:
    """Heatmap: average DSS by down x coverage type."""
    pivot = dss_df.pivot_table(
        values="dss",
        index="coverage",
        columns="down",
        aggfunc="mean",
    )

    fig, ax = plt.subplots(figsize=(8, max(4, len(pivot) * 0.5)))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn", interpolation="nearest")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{int(d)}down" for d in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("DSS by Coverage Type x Down", fontsize=13, fontweight="bold")

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.iloc[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=9,
                       color="white" if val < 50 else "black")

    plt.colorbar(im, ax=ax, label="DSS")
    plt.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return str(output_path)
