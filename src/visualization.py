"""Visualizations for the Pocket Collapse Index."""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from matplotlib.animation import FuncAnimation, PillowWriter
import imageio.v2 as imageio
from pathlib import Path


# NFL field dimensions
FIELD_LENGTH = 120  # yards (100 + 2x10 endzones)
FIELD_WIDTH = 53.3


def draw_field(ax) -> None:
    """Draw an NFL field on a matplotlib Axes."""
    # Green background
    ax.add_patch(patches.Rectangle((0, 0), FIELD_LENGTH, FIELD_WIDTH, 
                                   facecolor="#1B5E20", edgecolor="white", lw=2))
    
    # Yard lines every 10 yards
    for x in range(10, 110, 10):
        ax.plot([x, x], [0, FIELD_WIDTH], color="white", lw=1.5, alpha=0.7)
    
    # End zones
    ax.add_patch(patches.Rectangle((0, 0), 10, FIELD_WIDTH, facecolor="#2E7D32", alpha=0.5))
    ax.add_patch(patches.Rectangle((110, 0), 10, FIELD_WIDTH, facecolor="#2E7D32", alpha=0.5))
    
    ax.set_xlim(0, FIELD_LENGTH)
    ax.set_ylim(0, FIELD_WIDTH)
    ax.set_aspect("equal")
    ax.axis("off")


def animate_play(
    df_play: pd.DataFrame,
    qb_id: int,
    output_path: str = "output/play_animation.gif",
    title: str = "Pocket Collapse",
) -> str:
    """Animate a single play showing pocket area shrinking over time.
    
    Returns the path to the saved GIF.
    """
    frames_list = sorted(df_play["frameId"].unique())
    
    fig, ax = plt.subplots(figsize=(12, 6.5))
    
    def update(frame_idx):
        ax.clear()
        draw_field(ax)
        
        frame = df_play[df_play["frameId"] == frames_list[frame_idx]]
        if frame.empty:
            return
        
        # Determine snap frame to start tracking
        snap_frames = df_play[df_play["event"] == "ball_snap"]["frameId"].values
        if len(snap_frames) > 0 and frames_list[frame_idx] < snap_frames[0]:
            ax.set_title(f"{title} — Pre-snap", fontsize=14, color="white")
        else:
            ax.set_title(f"{title} — Frame {frame_idx+1}/{len(frames_list)}", 
                        fontsize=14, color="white")
        
        # Plot offensive players (blue) and defensive players (red)
        for _, row in frame.iterrows():
            color = "#2196F3" if row["team"] == "off" else "#F44336"
            size = 120 if row["nflId"] == qb_id else 60
            ax.scatter(row["x"], row["y"], c=color, s=size, zorder=5, edgecolors="white", lw=0.5)
            if row["nflId"] == qb_id:
                ax.annotate("QB", (row["x"], row["y"]), textcoords="offset points",
                           xytext=(5, 5), color="white", fontsize=8, fontweight="bold")
        
        # Draw convex hull of offensive players near QB (the "pocket")
        qb_row = frame[frame["nflId"] == qb_id]
        if not qb_row.empty:
            qb_x, qb_y = float(qb_row["x"].iloc[0]), float(qb_row["y"].iloc[0])
            off_near = frame[
                (frame["team"] == "off")
                & ((frame["x"] - qb_x).abs() < 7)
                & ((frame["y"] - qb_y).abs() < 5)
            ]
            if len(off_near) >= 3:
                points = off_near[["x", "y"]].values
                try:
                    hull = ConvexHull(points)
                    hull_pts = points[hull.vertices]
                    hull_pts = np.append(hull_pts, [hull_pts[0]], axis=0)
                    ax.fill(hull_pts[:, 0], hull_pts[:, 1], alpha=0.25, color="#FFD700", zorder=4)
                    ax.plot(hull_pts[:, 0], hull_pts[:, 1], color="#FFD700", lw=2, zorder=4)
                except Exception:
                    pass
    
    anim = FuncAnimation(fig, update, frames=len(frames_list), interval=100)
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    writer = PillowWriter(fps=10)
    anim.save(str(output_path), writer=writer)
    plt.close(fig)
    
    return str(output_path)


def plot_pci_ranking(
    pci_df: pd.DataFrame,
    output_path: str = "output/pci_ranking.png",
    group_by: str = "team",
    title: str = "Pocket Collapse Index — Team Ranking",
) -> str:
    """Bar chart ranking teams or players by average PCI."""
    agg = pci_df.groupby(group_by)["pci"].agg(["mean", "count"]).reset_index()
    agg = agg[agg["count"] >= 3].sort_values("mean", ascending=True)
    
    fig, ax = plt.subplots(figsize=(10, max(4, len(agg) * 0.4)))
    
    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(agg)))
    ax.barh(agg[group_by], agg["mean"], color=colors, edgecolor="white", lw=0.5)
    ax.set_xlabel("Pocket Collapse Index (lower = better OL)", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.invert_yaxis()
    
    for i, (val, cnt) in enumerate(zip(agg["mean"], agg["count"])):
        ax.text(val + 0.002, i, f"  {val:.3f} (n={cnt})", va="center", fontsize=9)
    
    plt.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    
    return str(output_path)
