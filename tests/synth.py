"""Random synthetic tracking rows of a secondary, for equivalence tests."""

from __future__ import annotations

import numpy as np
import pandas as pd


def random_secondary(seed: int, n_plays: int) -> pd.DataFrame:
    """Secondary rows with varying roster size, dropouts, and a few unscorable plays."""
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float | int | str | None]] = []
    for play in range(n_plays):
        n_frames = int(rng.integers(4, 30))
        snap = int(rng.integers(1, 4))
        end = snap + int(rng.integers(-1, n_frames))
        roster = [int(i) for i in rng.choice(100, size=int(rng.integers(2, 8)), replace=False)]
        for frame in range(1, snap + n_frames + 3):
            present = [i for i in roster if rng.random() > 0.08]
            for nfl_id in present:
                rows.append(
                    {
                        "gameId": 1 + play // 7,
                        "playId": play,
                        "nflId": nfl_id,
                        "frameId": frame,
                        "x": float(rng.uniform(0, 120)),
                        "y": float(rng.uniform(0, 53)),
                        "s": float(rng.choice([0.0, rng.uniform(0, 10)])),
                        "o": float(rng.uniform(0, 360)),
                        "dir": float(rng.uniform(0, 360)),
                        "event": "ball_snap"
                        if frame == snap
                        else ("pass_forward" if frame == end else None),
                    }
                )
    return pd.DataFrame(rows)
