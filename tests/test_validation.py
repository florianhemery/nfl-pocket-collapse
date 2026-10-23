"""Held-out validation: metric formulas, model inputs, cluster bootstrap and decision rule."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator
from sklearn import metrics as sk_metrics  # pyright: ignore[reportMissingTypeStubs]

from nfl_dss import validation
from nfl_dss.validation import ScoredTest, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs" / "site-data.schema.json").read_text(encoding="utf-8"))
COVERAGES = [("Cover-3", "Zone"), ("Cover-1", "Man"), ("Cover-2", "Zone"), ("Prevent", "Other")]


def synthetic(n: int = 1600, seed: int = 3, effect: float = 0.0) -> pd.DataFrame:
    """Plays over weeks 1-8, 4 games a week. ``effect`` is the weight of DSS in the logit."""
    rng = np.random.default_rng(seed)
    week = rng.integers(1, 9, n)
    cov = rng.integers(0, len(COVERAGES), n)
    frames = rng.integers(10, 60, n)
    dss = rng.normal(56, 8, n)
    logit = (
        0.4 - 0.03 * (frames - 30) + 0.3 * (cov % 2) + effect * (dss - 56) / 8
    )  # time to throw and coverage drive completion
    completed = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    columns: dict[str, Any] = {
        "dss": dss,
        "va": rng.uniform(5, 99, n),
        "sd": rng.normal(71, 3, n),
        "od": rng.uniform(1, 80, n),
        "frames_analyzed": frames,
        "week": week,
        "gameId": week * 10 + rng.integers(0, 4, n),
        "coverage": [COVERAGES[i][0] for i in cov],
        "coverageType": [COVERAGES[i][1] for i in cov],
        "completed": completed,
        "down": rng.integers(1, 5, n),
        "yardsToGo": rng.integers(1, 20, n),
        "yardsToEndzone": rng.integers(1, 100, n),
        "playResult": (0.1 * frames + 0.05 * (dss - 56) + rng.normal(0, 8, n)).round(),
    }
    return pd.DataFrame(columns)


def sk_auc(y: np.ndarray[Any, Any], p: np.ndarray[Any, Any]) -> float:
    return float(cast(Any, sk_metrics).roc_auc_score(y, p))


def sk_log_loss(y: np.ndarray[Any, Any], p: np.ndarray[Any, Any]) -> float:
    return float(cast(Any, sk_metrics).log_loss(y, p))


# -- metric formulas -------------------------------------------------------------------------


def test_metrics_match_hand_computation() -> None:
    y = np.array([0.0, 0.0, 1.0, 1.0])
    p = np.array([0.1, 0.4, 0.35, 0.8])
    assert validation.auc(y, p) == pytest.approx(0.75)
    assert validation.brier(y, p) == pytest.approx(0.158125)
    expected = -(np.log(0.9) + np.log(0.6) + np.log(0.35) + np.log(0.8)) / 4
    assert validation.log_loss(y, p) == pytest.approx(float(expected))


def test_auc_counts_ties_as_one_half_and_is_nan_with_one_class() -> None:
    assert validation.auc(np.array([0.0, 1.0]), np.array([0.5, 0.5])) == 0.5
    assert np.isnan(validation.auc(np.ones(3), np.array([0.1, 0.2, 0.3])))


def test_metrics_agree_with_scikit_learn_on_random_scores() -> None:
    rng = np.random.default_rng(11)
    y = (rng.random(400) < 0.6).astype(np.float64)
    p = np.round(rng.uniform(0.02, 0.98, 400), 2)  # rounding creates ties
    assert validation.auc(y, p) == pytest.approx(sk_auc(y, p), abs=1e-12)
    assert validation.log_loss(y, p) == pytest.approx(sk_log_loss(y, p), abs=1e-12)


def test_rmse_and_r2_against_the_test_mean() -> None:
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert validation.rmse(y, y + 2.0) == pytest.approx(2.0)
    assert validation.r_squared(y, y) == 1.0
    assert validation.r_squared(y, np.full(4, y.mean())) == pytest.approx(0.0)
    with pytest.raises(ValidationError, match="R2 undefined"):
        validation.r_squared(np.ones(3), np.ones(3))


def test_non_finite_values_are_refused() -> None:
    with pytest.raises(ValidationError, match="non-finite"):
        validation.r4(float("inf"))


# -- model inputs ---------------------------------------------------------------------------


def test_design_uses_training_statistics_and_levels_only() -> None:
    train = pd.DataFrame(
        {"frames_analyzed": [1.0, 3.0], "coverage": ["a", "b"], "yardsToGo": [5.0, 5.0]}
    )
    test = pd.DataFrame(
        {"frames_analyzed": [5.0, 1.0], "coverage": ["b", "z"], "yardsToGo": [6.0, 5.0]}
    )
    features = ["frames_analyzed", "coverage", "yardsToGo"]
    x_train, x_test = validation.design_matrices(train, test, features)
    # frames: mean 2, std 1. coverage: levels a, b, and the unseen level z is all zeros.
    # yardsToGo is constant in training: centered only.
    assert x_train.tolist() == [[-1.0, 1.0, 0.0, 0.0], [1.0, 0.0, 1.0, 0.0]]
    assert x_test.tolist() == [[3.0, 0.0, 1.0, 1.0], [-1.0, 0.0, 0.0, 0.0]]


def test_test_outcomes_never_reach_the_fit() -> None:
    results = synthetic()
    train, test = validation.split_by_week(results)
    features = validation.BASELINE_FEATURES
    before = validation._completion_scores(train, test, features)  # pyright: ignore[reportPrivateUsage]
    scrambled = test.assign(completed=1 - test["completed"], playResult=0)
    after = validation._completion_scores(train, scrambled, features)  # pyright: ignore[reportPrivateUsage]
    assert np.array_equal(before, after)


@pytest.mark.filterwarnings("ignore::sklearn.exceptions.ConvergenceWarning")
def test_logistic_regression_must_converge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validation, "LOGISTIC_MAX_ITER", 1)
    with pytest.raises(ValidationError, match="converge"):
        validation.model_comparison(synthetic())


# -- split ----------------------------------------------------------------------------------


def test_split_is_weeks_1_to_6_against_7_and_8() -> None:
    train, test = validation.split_by_week(synthetic())
    assert set(train["week"]) == {1, 2, 3, 4, 5, 6}
    assert set(test["week"]) == {7, 8}
    assert set(train["gameId"]).isdisjoint(set(test["gameId"]))


def test_split_refuses_missing_weeks_and_single_class() -> None:
    results = synthetic()
    with pytest.raises(ValidationError, match="split needs"):
        validation.split_by_week(results.loc[results["week"] <= 6])
    flat = results.assign(completed=np.where(results["week"] >= 7, 1, results["completed"]))
    with pytest.raises(ValidationError, match="single outcome class"):
        validation.split_by_week(flat)


def test_missing_columns_are_refused() -> None:
    with pytest.raises(ValidationError, match="missing columns: down"):
        validation.model_comparison(synthetic().drop(columns=["down"]))


# -- cluster bootstrap ----------------------------------------------------------------------


def test_cluster_resample_keeps_whole_games() -> None:
    games = np.repeat([10, 20, 30, 40], [3, 5, 2, 4])
    groups = validation.game_groups(games)
    rng = np.random.default_rng(1)
    for _ in range(200):
        idx = validation.cluster_resample(groups, rng)
        counts = np.bincount(idx, minlength=len(games))
        for rows in groups:
            assert len(set(counts[rows])) == 1  # every play of a game is drawn equally often
        assert counts.sum() == len(idx)


def test_bootstrap_resamples_games_not_plays(monkeypatch: pytest.MonkeyPatch) -> None:
    games = np.repeat(np.arange(7), 12)
    rng = np.random.default_rng(2)
    y = (rng.random(len(games)) < 0.5).astype(np.float64)
    scores = rng.random(len(games))
    seen: list[np.ndarray[Any, Any]] = []
    draws: list[Any] = []
    real = validation.cluster_resample

    def spy(groups: list[Any], generator: np.random.Generator) -> Any:
        draws.append(len(groups))
        out = real(groups, generator)
        seen.append(out)
        return out

    monkeypatch.setattr(validation, "cluster_resample", spy)
    result = validation.paired_bootstrap(ScoredTest(y, scores, scores, games), resamples=50)
    assert result.resamples == 50
    assert draws == [7] * 50  # a draw is one pick per game, never one per play
    for idx in seen:
        counts = np.bincount(idx, minlength=len(games)).reshape(7, 12)
        assert (
            counts == counts[:, :1]
        ).all()  # a game enters whole, every one of its plays equally


def test_bootstrap_of_two_equal_models_is_exactly_zero() -> None:
    rng = np.random.default_rng(3)
    games = np.repeat(np.arange(10), 20)
    y = (rng.random(200) < 0.5).astype(np.float64)
    p = rng.random(200)
    result = validation.paired_bootstrap(ScoredTest(y, p, p, games), resamples=100)
    assert (result.delta_auc.lo, result.delta_auc.hi) == (0.0, 0.0)
    assert (result.delta_brier.lo, result.delta_brier.hi) == (0.0, 0.0)


def test_bootstrap_is_paired_and_follows_a_real_gain() -> None:
    rng = np.random.default_rng(4)
    games = np.repeat(np.arange(30), 40)
    y = (rng.random(1200) < 0.5).astype(np.float64)
    weak = rng.random(1200)
    strong = np.clip(0.5 * weak + 0.5 * y + rng.normal(0, 0.1, 1200), 0, 1)
    result = validation.paired_bootstrap(ScoredTest(y, weak, strong, games), resamples=200)
    gain = validation.auc(y, strong) - validation.auc(y, weak)
    assert result.delta_auc.lo > 0
    assert result.delta_auc.lo < gain < result.delta_auc.hi
    assert result.delta_brier.hi < 0  # a better model has a lower Brier score


def test_bootstrap_is_deterministic_and_documented() -> None:
    games = np.repeat(np.arange(8), 15)
    rng = np.random.default_rng(5)
    y = (rng.random(120) < 0.5).astype(np.float64)
    a, b = rng.random(120), rng.random(120)
    scored = ScoredTest(y, a, b, games)
    assert validation.paired_bootstrap(scored, resamples=60) == validation.paired_bootstrap(
        scored, resamples=60
    )
    assert validation.paired_bootstrap(scored, resamples=60, seed=1) != validation.paired_bootstrap(
        scored, resamples=60, seed=2
    )
    assert validation.BOOTSTRAP_RESAMPLES == 2000
    assert validation.BOOTSTRAP_SEED == 20261024
    assert validation.CI_LEVEL == 0.95


def test_degenerate_resamples_are_skipped_or_refused() -> None:
    games = np.repeat(np.arange(4), 5)
    scores = np.linspace(0.1, 0.9, 20)
    with pytest.raises(ValidationError, match="single outcome class"):
        validation.paired_bootstrap(ScoredTest(np.zeros(20), scores, scores, games), resamples=10)
    # One game holds every positive: resamples that miss it are skipped, the rest are kept.
    y = np.zeros(20)
    y[:5] = 1.0
    result = validation.paired_bootstrap(ScoredTest(y, scores, scores, games), resamples=200)
    assert 0 < result.resamples < 200


# -- decision rule --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("delta", "lo", "expected"),
    [
        (0.02, 0.0001, "signal"),
        (0.0004, 0.0001, "signal"),  # the lower bound decides, whatever the size of the gain
        (0.02, 0.0, "weak_signal"),  # lo > 0 is strict
        (0.0051, -0.01, "weak_signal"),
        (0.005, -0.01, "no_signal"),  # delta > 0.005 is strict
        (0.0049, -0.01, "no_signal"),
        (0.0, 0.0, "no_signal"),
        (-0.02, -0.04, "no_signal"),
    ],
)
def test_decision_rule_boundaries(delta: float, lo: float, expected: str) -> None:
    assert validation.decide(delta, lo) == expected


def test_decision_rule_text_states_its_thresholds() -> None:
    assert str(validation.WEAK_SIGNAL_MIN_DELTA_AUC) == "0.005"
    for part in ("lo > 0", "0.005", "2000 resamples", "only one", "exploratory"):
        assert part in validation.DECISION_RULE


# -- the whole comparison -------------------------------------------------------------------


def test_comparison_is_deterministic_and_valid_against_the_schema() -> None:
    results = synthetic()
    first = validation.model_comparison(results)
    assert validation.model_comparison(results) == first
    contract = SCHEMA["properties"]["validation"]["properties"]["model_comparison"]
    Draft202012Validator(contract).validate(first)  # pyright: ignore[reportUnknownMemberType]
    assert first["split"] == "train weeks 1-6 / test weeks 7-8"
    assert first["baseline_features"] == validation.BASELINE_FEATURES
    assert (first["n_train"], first["n_test"]) == (
        int((results["week"] <= 6).sum()),
        int((results["week"] >= 7).sum()),
    )
    assert first["n_test_games"] == results.loc[results["week"] >= 7, "gameId"].nunique()
    assert first["bootstrap"] == {"unit": "game", "resamples": 2000, "seed": 20261024}


def test_schema_rejects_an_incomplete_or_unknown_comparison() -> None:
    contract = SCHEMA["properties"]["validation"]["properties"]["model_comparison"]
    good = validation.model_comparison(synthetic())
    missing = deepcopy(good)
    del missing["delta_brier_ci95"]
    extra = {**good, "surprise": 1}
    bad_decision = {**good, "decision": "great"}
    for broken in (missing, extra, bad_decision):
        with pytest.raises(Exception, match=r"delta_brier_ci95|surprise|great"):
            Draft202012Validator(contract).validate(broken)  # pyright: ignore[reportUnknownMemberType]


def assert_close(actual: Any, expected: Any, tol: float = 2e-4) -> None:
    """Equal structure; numbers within ``tol`` (the last digits of a fit can differ by platform)."""
    if isinstance(expected, dict):
        want_map = cast(dict[str, Any], expected)
        got_map = cast(dict[str, Any], actual)
        assert set(got_map) == set(want_map)
        for key, want in want_map.items():
            assert_close(got_map[key], want, tol)
    elif isinstance(expected, list):
        want_list = cast(list[Any], expected)
        got_list = cast(list[Any], actual)
        assert len(got_list) == len(want_list)
        for got, want in zip(got_list, want_list, strict=True):
            assert_close(got, want, tol)
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, abs=tol)
    else:
        assert actual == expected


GOLDEN_NULL: dict[str, Any] = {
    "split": "train weeks 1-6 / test weeks 7-8",
    "baseline_features": [
        "frames_analyzed",
        "coverageType",
        "coverage",
        "down",
        "yardsToGo",
        "yardsToEndzone",
    ],
    "n_train": 1242,
    "n_test": 358,
    "n_test_games": 8,
    "baseline_auc": 0.6083,
    "with_dss_auc": 0.6078,
    "delta_auc": -0.0004,
    "delta_auc_ci95": [-0.0019, 0.0013],
    "baseline_brier": 0.2244,
    "with_dss_brier": 0.2245,
    "delta_brier": 0.0001,
    "delta_brier_ci95": [-0.0001, 0.0002],
    "baseline_logloss": 0.6399,
    "with_dss_logloss": 0.6401,
    "subscores_auc": 0.5871,
    "delta_subscores_auc": -0.0211,
    "yards": {"baseline_rmse": 8.2605, "with_dss_rmse": 8.2449, "delta_r2": 0.0037},
    "bootstrap": {"unit": "game", "resamples": 2000, "seed": 20261024},
    "decision": "no_signal",
}
GOLDEN_SIGNAL: dict[str, Any] = {
    **GOLDEN_NULL,
    "n_train": 4540,
    "n_test": 1460,
    "baseline_auc": 0.5808,
    "with_dss_auc": 0.8223,
    "delta_auc": 0.2415,
    "delta_auc_ci95": [0.2037, 0.2746],
    "baseline_brier": 0.2402,
    "with_dss_brier": 0.17,
    "delta_brier": -0.0702,
    "delta_brier_ci95": [-0.0756, -0.0634],
    "baseline_logloss": 0.6732,
    "with_dss_logloss": 0.5094,
    "subscores_auc": 0.5788,
    "delta_subscores_auc": -0.002,
    "yards": {"baseline_rmse": 7.9623, "with_dss_rmse": 7.9419, "delta_r2": 0.005},
    "decision": "signal",
}


def test_golden_values_on_the_synthetic_dataset() -> None:
    out = validation.model_comparison(synthetic())
    out.pop("decision_rule")
    assert_close(out, GOLDEN_NULL)


def test_golden_values_when_dss_carries_signal() -> None:
    out = validation.model_comparison(synthetic(n=6000, seed=8, effect=1.5))
    out.pop("decision_rule")
    assert_close(out, GOLDEN_SIGNAL)


def test_comparison_agrees_with_an_independent_computation() -> None:
    """Scores from the helpers, recomputed here with scikit-learn metrics and plain numpy."""
    results = synthetic(n=2400, seed=21, effect=0.8)
    out = validation.model_comparison(results)
    train, test = validation.split_by_week(results)
    y = test["completed"].to_numpy(dtype=np.float64)
    base = validation._completion_scores(train, test, validation.BASELINE_FEATURES)  # pyright: ignore[reportPrivateUsage]
    both = validation._completion_scores(train, test, [*validation.BASELINE_FEATURES, "dss"])  # pyright: ignore[reportPrivateUsage]
    assert out["baseline_auc"] == pytest.approx(sk_auc(y, base), abs=5e-5)
    assert out["with_dss_auc"] == pytest.approx(sk_auc(y, both), abs=5e-5)
    assert out["baseline_logloss"] == pytest.approx(sk_log_loss(y, base), abs=5e-5)
    diff = base - y
    brier_reference = float(diff @ diff) / len(y)
    assert out["baseline_brier"] == pytest.approx(brier_reference, abs=5e-5)
    assert out["delta_auc"] == pytest.approx(sk_auc(y, both) - sk_auc(y, base), abs=5e-5)


def test_dss_that_drives_the_outcome_is_a_signal_and_noise_is_not() -> None:
    assert (
        validation.model_comparison(synthetic(n=6000, seed=8, effect=1.5))["decision"] == "signal"
    )
    null = validation.model_comparison(synthetic(n=3000, seed=1, effect=0.0))
    assert null["decision"] != "signal"
    assert null["delta_auc_ci95"][0] <= 0


def test_yards_summary_improves_when_dss_matters() -> None:
    yards = validation.model_comparison(synthetic(n=4000, seed=5))["yards"]
    assert yards["with_dss_rmse"] <= yards["baseline_rmse"]
    assert yards["delta_r2"] > 0
