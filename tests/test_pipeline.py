"""Pipeline edge cases."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dss.pipeline import (
    FALLBACK_SUBSCORE,
    RESULT_COLUMNS,
    aggregate_plays,
    build_results,
    score_plays,
    write_results,
)
from nfl_dss.secondary import PLAY_KEY
from tests.synth import random_secondary


def test_no_scorable_play_gives_an_empty_table() -> None:
    secondary = random_secondary(1, 3).assign(event=None)
    assert score_plays(secondary).empty


def test_rounding_is_applied_when_requested() -> None:
    secondary = random_secondary(5, 20)
    rounded = score_plays(secondary, decimals=2)
    exact = score_plays(secondary, decimals=None)
    assert (rounded["dss"] != exact["dss"]).any()
    assert (rounded["dss"] * 100 - (rounded["dss"] * 100).round()).abs().max() < 1e-6


def test_duplicate_tracking_rows_do_not_change_scores() -> None:
    secondary = random_secondary(9, 15)
    doubled = pd.concat([secondary, secondary.iloc[::3]], ignore_index=True)
    pd.testing.assert_frame_equal(score_plays(doubled), score_plays(secondary))


def test_results_round_trip_through_csv(tiny_data: Path, tmp_path: Path) -> None:
    results = build_results(tiny_data, tiny_data / "tracking")
    path = tmp_path / "nested" / "r.csv"
    write_results(results, path)
    back = pd.read_csv(path)
    assert list(back.columns) == RESULT_COLUMNS
    pd.testing.assert_frame_equal(back, results, check_dtype=False)


def test_undefined_spacing_and_orientation_fall_back_to_the_neutral_score() -> None:
    frames = pd.DataFrame(
        {
            "gameId": 1,
            "playId": 1,
            "frameId": [1, 2, 3, 4],
            "va": [0.5, 0.6, 0.7, 0.6],
            "sd": np.nan,
            "od": np.nan,
        }
    )
    num_dbs = pd.Series([3], index=pd.MultiIndex.from_tuples([(1, 1)], names=PLAY_KEY))
    row = aggregate_plays(frames, num_dbs, decimals=None).iloc[0]
    assert FALLBACK_SUBSCORE == 0.5
    assert row["va"] == pytest.approx(60.0)
    assert row["sd"] == 50.0
    assert row["od"] == 50.0
    assert row["dss"] == pytest.approx(100 * (0.40 * 0.6 + 0.30 * 0.5 + 0.30 * 0.5))
    assert row["frames_analyzed"] == 4
