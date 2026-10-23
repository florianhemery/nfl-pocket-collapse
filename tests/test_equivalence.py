"""The vectorized code must agree with the frozen loop-based implementation."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from nfl_dss.metrics import FrameBatch, frame_scores
from nfl_dss.pipeline import score_plays
from tests import legacy_dss as _legacy
from tests.synth import random_secondary

TOLERANCE = 1e-9
legacy_dss: Any = _legacy


def test_frame_scores_match_legacy_on_random_frames() -> None:
    rng = np.random.default_rng(42)
    n_frames, width = 400, 8
    x, y = rng.uniform(0, 120, (n_frames, width)), rng.uniform(0, 53, (n_frames, width))
    s = np.where(rng.random((n_frames, width)) < 0.15, 0.0, rng.uniform(0, 10, (n_frames, width)))
    d, o = rng.uniform(0, 360, (2, n_frames, width))
    counts = rng.integers(2, width + 1, n_frames)
    mask = np.arange(width)[None, :] < counts[:, None]
    new = frame_scores(FrameBatch(x, y, s, d, o, mask))
    for i in range(n_frames):
        k = int(counts[i])
        frame = pd.DataFrame(
            {"x": x[i, :k], "y": y[i, :k], "s": s[i, :k], "dir": d[i, :k], "o": o[i, :k]}
        )
        assert new.va[i] == pytest.approx(legacy_dss.velocity_alignment(frame), abs=TOLERANCE)
        assert new.sd[i] == pytest.approx(legacy_dss.spacing_discipline(frame), abs=TOLERANCE)
        assert new.od[i] == pytest.approx(legacy_dss.orientation_divergence(frame), abs=TOLERANCE)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_play_scores_match_legacy_on_random_plays(seed: int) -> None:
    secondary = random_secondary(seed, n_plays=60)
    scored = score_plays(secondary, decimals=None).set_index(["gameId", "playId"])
    new = cast(dict[tuple[int, int], dict[str, float]], scored.to_dict("index"))
    expected = 0
    for raw_key, rows in secondary.groupby(["gameId", "playId"]):
        key = cast(tuple[int, int], raw_key)
        old: dict[str, float] | None = legacy_dss.compute_dss_for_play(rows)
        if old is None:
            assert key not in new
            continue
        expected += 1
        got = new[key]
        for name in ("dss", "va", "sd", "od"):
            assert round(float(got[name]), 2) == pytest.approx(old[name], abs=TOLERANCE)
        assert int(got["num_dbs"]) == old["num_dbs"]
        assert int(got["frames_analyzed"]) == old["frames_analyzed"]
    assert len(new) == expected
    assert expected > 10, "the generator should produce a meaningful number of scorable plays"
