"""Pinned values for the resampling and shrinkage helpers.

Property-style checks (``lo < mean < hi``) let a changed seed, resample count or interval level
slip through, so these tests pin numbers: golden values for a fixed seed, a comparison with the
normal approximation, and a hand computation for the shrinkage.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pytest

from nfl_dss import export


class SpyGenerator(np.random.Generator):
    """A generator that records the shape of every ``integers`` request."""

    def __init__(self, seed: int) -> None:
        super().__init__(np.random.PCG64(seed))
        self.shapes: list[Any] = []

    def integers(self, *args: Any, **kwargs: Any) -> Any:  # pyright: ignore[reportIncompatibleMethodOverride]
        self.shapes.append(kwargs.get("size"))
        return cast(Any, super().integers(*args, **kwargs))  # pyright: ignore[reportUnknownMemberType]


def test_bootstrap_ci_golden_values_for_a_fixed_seed() -> None:
    values = np.arange(1.0, 41.0)
    lo, hi = export.bootstrap_ci(values, np.random.default_rng(123))
    assert lo == pytest.approx(17.05, abs=1e-9)
    assert hi == pytest.approx(24.000625, abs=1e-9)


def test_bootstrap_ci_is_a_95_percent_interval_close_to_the_normal_one() -> None:
    rng = np.random.default_rng(7)
    values = rng.normal(55.0, 9.0, 5000)
    lo, hi = export.bootstrap_ci(values, np.random.default_rng(99))
    half_width = 1.959964 * values.std(ddof=1) / np.sqrt(len(values))
    assert lo == pytest.approx(values.mean() - half_width, abs=0.03)
    assert hi == pytest.approx(values.mean() + half_width, abs=0.03)


def test_bootstrap_draws_the_documented_number_of_resamples() -> None:
    spy = SpyGenerator(5)
    values = np.arange(30.0)
    export.bootstrap_ci(values, spy)
    assert export.BOOTSTRAP_RESAMPLES == 2000
    assert spy.shapes == [(2000, 30)]


def test_bootstrap_seed_and_level_are_the_documented_ones() -> None:
    assert export.BOOTSTRAP_SEED == 20261023
    assert export.CI_LEVEL == 0.95


def test_shrink_means_matches_a_hand_computation() -> None:
    # Three teams, unequal sizes. Sampling variances v_i = 100 / n_i = 10, 5, 100/70.
    means = np.array([10.0, 20.0, 30.0])
    counts = np.array([10.0, 20.0, 70.0])
    variances = np.array([100.0, 100.0, 100.0])
    sampling = [100.0 / 10, 100.0 / 20, 100.0 / 70]
    grand = (10 * 10.0 + 20 * 20.0 + 70 * 30.0) / 100  # play-weighted: 26, not the plain 20
    tau2 = 100.0 - sum(sampling) / 3  # sample variance (ddof=1) of the means is 100
    expected = [
        grand + tau2 / (tau2 + v) * (m - grand) for m, v in zip(means, sampling, strict=True)
    ]
    shrunk = export.shrink_means(means, counts, variances)
    assert shrunk == pytest.approx(expected, abs=1e-9)
    assert shrunk == pytest.approx([11.53075171, 20.30143541, 29.94044665], abs=1e-8)
