"""Property and edge-case tests of the vectorized sub-scores."""

from __future__ import annotations

import random

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nfl_dss import metrics
from nfl_dss.metrics import BoolArray, FloatArray, FrameBatch, frame_scores

speed = st.one_of(st.just(0.0), st.floats(min_value=0.1, max_value=12.0))
player = st.tuples(
    st.floats(min_value=-60, max_value=60),
    st.floats(min_value=-60, max_value=60),
    speed,
    st.floats(min_value=0, max_value=360),
    st.floats(min_value=0, max_value=360),
)
frame_players = st.lists(player, min_size=2, max_size=8)


def columns(players: list[tuple[float, ...]]) -> tuple[FloatArray, ...]:
    """One frame as five (1, n) arrays: x, y, s, dir, o."""
    arr = np.array(players, dtype=np.float64)
    return tuple(arr[:, i][None, :] for i in range(5))


def batch_of(arrays: list[FloatArray], mask: BoolArray) -> FrameBatch:
    x, y, s, d, o = arrays
    return FrameBatch(x, y, s, d, o, mask)


def scores(players: list[tuple[float, ...]]) -> tuple[float, float, float]:
    x, y, s, d, o = columns(players)
    mask = np.ones_like(x, dtype=np.bool_)
    out = frame_scores(FrameBatch(x, y, s, d, o, mask))
    return float(out.va[0]), float(out.sd[0]), float(out.od[0])


@given(frame_players)
def test_scores_are_in_unit_interval(players: list[tuple[float, ...]]) -> None:
    for value in scores(players):
        assert 0.0 <= value <= 1.0


@settings(max_examples=200)
@given(
    frame_players,
    st.floats(min_value=0, max_value=360),
    st.floats(min_value=-100, max_value=100),
    st.floats(min_value=-100, max_value=100),
)
def test_invariant_under_rotation_and_translation(
    players: list[tuple[float, ...]], theta_deg: float, tx: float, ty: float
) -> None:
    theta = np.radians(theta_deg)
    moved = [
        (
            x * np.cos(theta) - y * np.sin(theta) + tx,
            x * np.sin(theta) + y * np.cos(theta) + ty,
            s,
            d + theta_deg,
            o + theta_deg,
        )
        for x, y, s, d, o in players
    ]
    assert scores(moved) == pytest.approx(scores(players), abs=1e-7)


@given(frame_players, st.randoms(use_true_random=False))
def test_invariant_under_player_permutation(
    players: list[tuple[float, ...]], rnd: random.Random
) -> None:
    shuffled = list(players)
    rnd.shuffle(shuffled)
    assert scores(shuffled) == pytest.approx(scores(players), abs=1e-9)


@given(frame_players)
def test_padding_does_not_change_scores(players: list[tuple[float, ...]]) -> None:
    x, y, s, d, o = columns(players)
    mask = np.ones_like(x, dtype=np.bool_)
    padded = [np.concatenate([a, np.full((1, 3), 1e3)], axis=1) for a in (x, y, s, d, o)]
    padded_mask = np.concatenate([mask, np.zeros((1, 3), dtype=np.bool_)], axis=1)
    base = frame_scores(FrameBatch(x, y, s, d, o, mask))
    wide = frame_scores(batch_of(padded, padded_mask))
    assert (wide.va[0], wide.sd[0], wide.od[0]) == pytest.approx(
        (base.va[0], base.sd[0], base.od[0]), abs=1e-12
    )


def test_aligned_group_with_equal_orientation() -> None:
    players = [
        (0.0, 0.0, 5.0, 30.0, 90.0),
        (4.0, 0.0, 5.0, 30.0, 90.0),
        (8.0, 0.0, 5.0, 30.0, 90.0),
    ]
    va, _, od = scores(players)
    assert va == pytest.approx(1.0)
    assert od == pytest.approx(0.0, abs=1e-12)


def test_opposite_orientations_are_fully_divergent() -> None:
    players = [(0.0, 0.0, 1.0, 0.0, 0.0), (5.0, 0.0, 1.0, 0.0, 180.0)]
    assert scores(players)[2] == pytest.approx(1.0)


def test_stationary_group_is_trivially_aligned_and_collocated_is_disciplined() -> None:
    players = [(1.0, 1.0, 0.0, 10.0, 0.0), (1.0, 1.0, 0.0, 200.0, 0.0), (1.0, 1.0, 0.0, 90.0, 0.0)]
    va, sd, _ = scores(players)
    assert va == 1.0
    assert sd == 1.0


def test_opposite_velocities_give_trivial_alignment() -> None:
    players = [(0.0, 0.0, 5.0, 0.0, 0.0), (3.0, 0.0, 5.0, 180.0, 0.0)]
    assert scores(players)[0] == 1.0


def test_negative_cosine_is_clamped_to_zero() -> None:
    # Velocities (1, 0), (1, 0), (-10, 0): the mean velocity is (-8/3, 0), so the players'
    # cosines to it are -1, -1 and +1 and their mean is -1/3. VA must be clamped to 0.
    players = [(0.0, 0.0, 1.0, 0.0, 0.0), (3.0, 0.0, 1.0, 0.0, 0.0), (6.0, 0.0, 10.0, 180.0, 0.0)]
    x, _, s, d, _ = columns(players)
    mask = np.ones_like(x, dtype=np.bool_)
    assert metrics.velocity_alignment(s, d, mask)[0] == 0.0


def test_fewer_than_two_players_is_nan() -> None:
    x, y, s, d, o = columns([(0.0, 0.0, 1.0, 0.0, 0.0), (1.0, 1.0, 1.0, 0.0, 0.0)])
    mask = np.array([[True, False]])
    out = frame_scores(FrameBatch(x, y, s, d, o, mask))
    assert np.isnan([out.va[0], out.sd[0], out.od[0]]).all()


def test_nan_input_propagates() -> None:
    players = [(0.0, 0.0, 5.0, 0.0, 0.0), (3.0, np.nan, 5.0, 0.0, 0.0), (6.0, 1.0, 5.0, 0.0, 0.0)]
    _, sd, _ = scores(players)
    assert np.isnan(sd)


def test_chunked_scoring_matches_single_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    rng = np.random.default_rng(0)
    shape = (11, 5)
    arrays = [rng.uniform(0, 50, shape) for _ in range(5)]
    mask = rng.random(shape) > 0.2
    whole = frame_scores(batch_of(arrays, mask))
    monkeypatch.setattr(metrics, "CHUNK_FRAMES", 4)
    chunked = frame_scores(batch_of(arrays, mask))
    for a, b in zip(
        (whole.va, whole.sd, whole.od), (chunked.va, chunked.sd, chunked.od), strict=True
    ):
        np.testing.assert_array_equal(a, b)


def test_combine_uses_the_documented_weights() -> None:
    va, sd, od = (np.array([v]) for v in (1.0, 0.5, 0.0))
    assert metrics.combine(va, sd, od)[0] == pytest.approx(100 * (0.40 + 0.15))
