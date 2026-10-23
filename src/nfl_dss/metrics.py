"""Vectorized DSS sub-scores.

All functions take 2-D arrays of shape ``(frames, players)`` plus a boolean ``mask`` marking
the real players of each frame (rows are padded to the widest frame). They are pure numpy and
have no I/O, so they can be tested on synthetic arrays.

Sub-scores, each in [0, 1], higher is better for the defense:

* VA, velocity alignment: mean cosine similarity between each moving player's velocity
  and the group mean velocity, clamped to [0, 1].
* SD, spacing discipline: ``1 / (1 + cv)`` where ``cv`` is the coefficient of variation
  (population standard deviation over mean) of the pairwise distances.
* OD, orientation divergence: ``1 - R`` where ``R`` is the resultant length of the body
  orientations (1 means everyone faces the same way).

``DSS = 100 * (0.40 * VA + 0.30 * SD + 0.30 * OD)``.

The math is kept identical to the first version of the project (loop-based, see
``tests/legacy_dss.py``); the only change is that OD is clipped to [0, 1] so that floating
point noise can no longer produce ``-1e-16``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

#: A speed or distance below this value is treated as zero.
EPSILON = 1e-6
#: Weights of (VA, SD, OD) in the DSS.
DEFAULT_WEIGHTS: tuple[float, float, float] = (0.40, 0.30, 0.30)
#: Frames are scored in chunks to bound the size of the (frames, N, N) distance tensor.
CHUNK_FRAMES = 50_000


@dataclass(frozen=True)
class FrameScores:
    """Per-frame sub-scores in [0, 1]. A frame with fewer than two players is NaN."""

    va: FloatArray
    sd: FloatArray
    od: FloatArray


def _padded(values: FloatArray, mask: BoolArray) -> FloatArray:
    """Zero the padding so that sums over players only see real players."""
    return np.where(mask, values, 0.0)


def _divide(numerator: FloatArray, denominator: FloatArray) -> FloatArray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return numerator / denominator


def velocity_alignment(s: FloatArray, direction_deg: FloatArray, mask: BoolArray) -> FloatArray:
    """Velocity alignment of each frame, shape ``(frames,)``."""
    n = mask.sum(axis=1).astype(np.float64)
    rad = np.radians(direction_deg)
    vx = _padded(s * np.cos(rad), mask)
    vy = _padded(s * np.sin(rad), mask)
    mean_vx = _divide(vx.sum(axis=1), n)
    mean_vy = _divide(vy.sum(axis=1), n)
    mean_mag = np.hypot(mean_vx, mean_vy)
    mag = np.hypot(vx, vy)
    # NaN speeds count as moving so that they propagate to the score instead of vanishing.
    moving = mask & ~(mag < EPSILON)
    dot = vx * mean_vx[:, None] + vy * mean_vy[:, None]
    cos = np.where(moving, _divide(dot, mag * mean_mag[:, None]), 0.0)
    n_moving = moving.sum(axis=1).astype(np.float64)
    mean_cos = _divide(cos.sum(axis=1), n_moving)
    # A stationary group, or one where nobody moves, is trivially aligned.
    trivial = (mean_mag < EPSILON) | (n_moving == 0)
    va = np.where(trivial, 1.0, np.clip(mean_cos, 0.0, 1.0))
    return np.where(n < 2, np.nan, va)


def spacing_discipline(x: FloatArray, y: FloatArray, mask: BoolArray) -> FloatArray:
    """Spacing discipline of each frame, shape ``(frames,)``."""
    n = mask.sum(axis=1)
    px = _padded(x, mask)
    py = _padded(y, mask)
    dist = np.hypot(px[:, :, None] - px[:, None, :], py[:, :, None] - py[:, None, :])
    width = mask.shape[1]
    upper = np.triu(np.ones((width, width), dtype=np.bool_), k=1)
    pair = mask[:, :, None] & mask[:, None, :] & upper[None, :, :]
    n_pairs = pair.sum(axis=(1, 2)).astype(np.float64)
    mean_d = _divide(np.where(pair, dist, 0.0).sum(axis=(1, 2)), n_pairs)
    centered = np.where(pair, dist - mean_d[:, None, None], 0.0)
    std_d = np.sqrt(_divide((centered**2).sum(axis=(1, 2)), n_pairs))
    cv = _divide(std_d, mean_d)
    sd = np.where(mean_d < EPSILON, 1.0, np.clip(1.0 / (1.0 + cv), 0.0, 1.0))
    return np.where(n < 2, np.nan, sd)


def orientation_coherence(o_deg: FloatArray, mask: BoolArray) -> FloatArray:
    """Resultant length R of the body orientations of each frame, in [0, 1]."""
    n = mask.sum(axis=1).astype(np.float64)
    rad = np.radians(o_deg)
    mean_sin = _divide(_padded(np.sin(rad), mask).sum(axis=1), n)
    mean_cos = _divide(_padded(np.cos(rad), mask).sum(axis=1), n)
    r = np.hypot(mean_sin, mean_cos)
    return np.where(n < 2, np.nan, r)


def orientation_divergence(o_deg: FloatArray, mask: BoolArray) -> FloatArray:
    """Orientation divergence ``1 - R`` of each frame, clipped to [0, 1]."""
    return np.clip(1.0 - orientation_coherence(o_deg, mask), 0.0, 1.0)


@dataclass(frozen=True)
class FrameBatch:
    """Padded ``(frames, players)`` arrays; ``mask`` marks the real players of each frame."""

    x: FloatArray
    y: FloatArray
    s: FloatArray
    direction_deg: FloatArray
    o_deg: FloatArray
    mask: BoolArray

    def window(self, start: int, stop: int) -> FrameBatch:
        """The frames ``start`` (included) to ``stop`` (excluded)."""
        return FrameBatch(
            self.x[start:stop],
            self.y[start:stop],
            self.s[start:stop],
            self.direction_deg[start:stop],
            self.o_deg[start:stop],
            self.mask[start:stop],
        )


def _score_batch(batch: FrameBatch) -> FrameScores:
    return FrameScores(
        va=velocity_alignment(batch.s, batch.direction_deg, batch.mask),
        sd=spacing_discipline(batch.x, batch.y, batch.mask),
        od=orientation_divergence(batch.o_deg, batch.mask),
    )


def frame_scores(batch: FrameBatch) -> FrameScores:
    """Compute VA, SD and OD for every frame of a padded batch."""
    n_frames = batch.mask.shape[0]
    if n_frames <= CHUNK_FRAMES:
        return _score_batch(batch)
    parts = [
        _score_batch(batch.window(i, i + CHUNK_FRAMES)) for i in range(0, n_frames, CHUNK_FRAMES)
    ]
    return FrameScores(
        va=np.concatenate([p.va for p in parts]),
        sd=np.concatenate([p.sd for p in parts]),
        od=np.concatenate([p.od for p in parts]),
    )


def combine(
    va: FloatArray,
    sd: FloatArray,
    od: FloatArray,
    weights: tuple[float, float, float] = DEFAULT_WEIGHTS,
) -> FloatArray:
    """DSS on the 0-100 scale from sub-scores in [0, 1]."""
    w_va, w_sd, w_od = weights
    return 100.0 * (w_va * va + w_sd * sd + w_od * od)
