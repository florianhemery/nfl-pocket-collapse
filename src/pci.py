"""Pocket Collapse Index (PCI) — metric computation.

Computes how fast the QB pocket collapses on passing plays using
frame-by-frame tracking data from the NFL Big Data Bowl dataset.
"""

import pandas as pd
import numpy as np
from scipy.spatial import ConvexHull
from pathlib import Path

# Field constants
FIELD_LENGTH = 120  # yards (including endzones)
FIELD_WIDTH = 53.3  # yards


def load_tracking_data(tracking_dir: str | Path, game_ids: list[int] | None = None) -> pd.DataFrame:
    """Load tracking CSV files, optionally filtered by game ID."""
    tracking_dir = Path(tracking_dir)
    files = sorted(tracking_dir.glob("tracking_*.csv"))
    if game_ids:
        files = [f for f in files if any(str(gid) in f.stem for gid in game_ids)]
    frames = [pd.read_csv(f) for f in files]
    if not frames:
        raise FileNotFoundError(f"No tracking files found in {tracking_dir}")
    return pd.concat(frames, ignore_index=True)


def identify_qb(tracking_df: pd.DataFrame, plays_df: pd.DataFrame) -> pd.DataFrame:
    """Identify the quarterback on each play via PFF scouting data or position."""
    pass_play_ids = plays_df[plays_df["passResult"].isin(["C", "I", "S", "IN"])]
    merged = tracking_df.merge(
        pass_play_ids[["gameId", "playId"]].drop_duplicates(),
        on=["gameId", "playId"],
    )
    qb_mask = merged["position"] == "QB"
    return merged[qb_mask]


def compute_pocket_area(df_play: pd.DataFrame, qb_id: int, event: str = "ball_snap") -> float:
    """Compute the free area around the QB at a given event frame.
    
    Uses a convex hull of the QB position and nearest blockers to estimate
    the 'pocket'. Rushers inside this hull reduce the area.
    
    Returns the pocket area in square yards.
    """
    frame = df_play[df_play["event"] == event]
    if frame.empty:
        return np.nan
    
    qb_row = frame[frame["nflId"] == qb_id]
    if qb_row.empty:
        return np.nan
    qb_x, qb_y = float(qb_row["x"].iloc[0]), float(qb_row["y"].iloc[0])
    
    # Offensive players near QB (within ~7 yards)
    off_players = frame[frame["team"] == "off"]
    near_off = off_players[
        (off_players["x"] - qb_x).abs() < 7
        & (off_players["y"] - qb_y).abs() < 5
    ]
    
    # Defenders near QB
    def_players = frame[frame["team"] == "def"]
    near_def = def_players[
        (def_players["x"] - qb_x).abs() < 10
        & (def_players["y"] - qb_y).abs() < 8
    ]
    
    if len(near_off) < 2:
        return np.nan
    
    points = near_off[["x", "y"]].values
    try:
        hull = ConvexHull(points)
        return hull.volume  # 2D area
    except Exception:
        return np.nan


def compute_collapse_rate(
    df_play: pd.DataFrame,
    qb_id: int,
    snap_event: str = "ball_snap",
    end_event: str = "pass_forward",
) -> dict:
    """Compute the Pocket Collapse Index for a single play.
    
    PCI = rate of pocket area decrease from snap to pass release.
    Higher PCI = faster collapse = worse for offense.
    
    Returns dict with: initial_area, final_area, collapse_rate, time_to_throw, pci
    """
    snap_frame = df_play[df_play["event"] == snap_event]
    end_frame = df_play[df_play["event"] == end_event]
    
    if snap_frame.empty or end_frame.empty:
        return None
    
    snap_time = snap_frame["time"].iloc[0]
    end_time = end_frame["time"].iloc[0]
    time_to_throw = (end_time - snap_time).total_seconds()
    
    if time_to_throw <= 0:
        return None
    
    initial_area = compute_pocket_area(df_play, qb_id, snap_event)
    final_area = compute_pocket_area(df_play, qb_id, end_event)
    
    if np.isnan(initial_area) or np.isnan(final_area):
        return None
    
    collapse_rate = (initial_area - final_area) / time_to_throw  # sq yards / sec
    pci = collapse_rate / initial_area if initial_area > 0 else 0  # normalized
    
    return {
        "initial_area": round(initial_area, 2),
        "final_area": round(final_area, 2),
        "collapse_rate": round(collapse_rate, 2),
        "time_to_throw": round(time_to_throw, 2),
        "pci": round(pci, 4),
    }
