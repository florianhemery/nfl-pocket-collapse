"""Held-out validation of the DSS (protocol: docs/decisions/0006).

Models are fitted once on weeks 1-6 and scored on weeks 7-8. The only confirmatory result is
``delta_auc``: the AUC of baseline plus DSS minus the AUC of the baseline, with a paired
bootstrap over test games and the written decision rule. Everything else is exploratory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy import stats
from sklearn.linear_model import (  # pyright: ignore[reportMissingTypeStubs]
    LinearRegression,
    LogisticRegression,
)

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.intp]
Json = dict[str, Any]

DECIMALS = 4
TRAIN_LAST_WEEK = 6
TEST_WEEKS = (7, 8)
SPLIT_LABEL = "train weeks 1-6 / test weeks 7-8"
OUTCOME = "completed"
YARDS = "playResult"
#: Baseline inputs, in the order of ADR 0006.
BASELINE_FEATURES = [
    "frames_analyzed",
    "coverageType",
    "coverage",
    "down",
    "yardsToGo",
    "yardsToEndzone",
]
CATEGORICAL = frozenset({"coverageType", "coverage", "down"})
DSS_FEATURES = ["dss"]
SUBSCORE_FEATURES = ["va", "sd", "od"]
#: Columns the validation reads from the results table.
REQUIRED_COLUMNS = [
    *BASELINE_FEATURES,
    *DSS_FEATURES,
    *SUBSCORE_FEATURES,
    OUTCOME,
    YARDS,
    "week",
    "gameId",
]

LOGISTIC_C = 1.0
LOGISTIC_MAX_ITER = 1000
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261024
CI_LEVEL = 0.95
#: ``weak_signal`` needs a point gain in AUC above this value (ADR 0006).
WEAK_SIGNAL_MIN_DELTA_AUC = 0.005
LOG_LOSS_EPS = float(np.finfo(np.float64).eps)

DECISION_RULE = (
    "Confirmatory test (the only one): delta_auc is the test AUC of the model with the "
    "baseline plus DSS minus the test AUC of the baseline model, both fitted on weeks 1-6 and "
    "scored on weeks 7-8, with a 95% paired cluster bootstrap interval [lo, hi] over test "
    f"games ({BOOTSTRAP_RESAMPLES} resamples, fixed seed). Applied to the values written in "
    "this file: signal if lo > 0; weak_signal if lo <= 0 and delta_auc > "
    f"{WEAK_SIGNAL_MIN_DELTA_AUC}; no_signal otherwise, including a negative gain. Every other "
    "number in this object is exploratory and does not change the decision."
)


class ValidationError(RuntimeError):
    """The held-out comparison cannot be computed from the given results."""


@dataclass(frozen=True)
class Interval:
    """A closed interval, ``lo <= hi``."""

    lo: float
    hi: float


@dataclass(frozen=True)
class ScoredTest:
    """Test outcomes, the predictions of the two models and the game of each play."""

    y: FloatArray
    baseline: FloatArray
    candidate: FloatArray
    games: NDArray[Any]


@dataclass(frozen=True)
class BootstrapResult:
    """Paired bootstrap intervals of the AUC and Brier differences."""

    delta_auc: Interval
    delta_brier: Interval
    resamples: int


def r4(value: float) -> float:
    """Round to the contract precision, refusing NaN and infinities."""
    if not np.isfinite(value):
        raise ValidationError(f"non-finite value in validation: {value}")
    return round(float(value), DECIMALS)


def auc(y: FloatArray, p: FloatArray) -> float:
    """Area under the ROC curve (rank statistic, ties count one half). NaN with one class."""
    positives = int(y.sum())
    negatives = len(y) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = stats.rankdata(p)
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def brier(y: FloatArray, p: FloatArray) -> float:
    """Mean squared difference between the predicted probability and the outcome."""
    return float(np.mean((p - y) ** 2))


def log_loss(y: FloatArray, p: FloatArray) -> float:
    """Mean negative log likelihood, probabilities clipped to ``[eps, 1 - eps]``."""
    clipped = np.clip(p, LOG_LOSS_EPS, 1.0 - LOG_LOSS_EPS)
    return float(-np.mean(y * np.log(clipped) + (1.0 - y) * np.log(1.0 - clipped)))


def rmse(y: FloatArray, prediction: FloatArray) -> float:
    return float(np.sqrt(np.mean((prediction - y) ** 2)))


def r_squared(y: FloatArray, prediction: FloatArray) -> float:
    """Coefficient of determination against the mean of ``y`` (the test mean)."""
    total = float(np.sum((y - y.mean()) ** 2))
    if total == 0.0:
        raise ValidationError("R2 undefined: constant yards in the test set")
    return 1.0 - float(np.sum((y - prediction) ** 2)) / total


def design_matrices(
    train: pd.DataFrame, test: pd.DataFrame, features: list[str]
) -> tuple[FloatArray, FloatArray]:
    """Model inputs: standardized numbers and one indicator per category level.

    Means, standard deviations and category levels come from ``train`` only. A level that
    does not occur in ``train`` is all zeros in ``test``. A constant numeric column is only
    centered.
    """
    blocks: tuple[list[FloatArray], list[FloatArray]] = ([], [])
    for name in features:
        if name in CATEGORICAL:
            levels = sorted({str(v) for v in train[name]})
            for frame, out in zip((train, test), blocks, strict=True):
                labels = np.array([str(v) for v in frame[name]])
                out.extend((labels == level).astype(np.float64) for level in levels)
        else:
            x_train = train[name].to_numpy(dtype=np.float64)
            x_test = test[name].to_numpy(dtype=np.float64)
            spread = float(x_train.std())
            scale = spread if spread > 0 else 1.0
            blocks[0].append((x_train - x_train.mean()) / scale)
            blocks[1].append((x_test - x_train.mean()) / scale)
    return np.column_stack(blocks[0]), np.column_stack(blocks[1])


class _Classifier(Protocol):
    """The part of a scikit-learn classifier used here (the library ships no type stubs)."""

    n_iter_: NDArray[np.int32]

    def fit(self, x: FloatArray, y: FloatArray) -> object: ...

    def predict_proba(self, x: FloatArray) -> FloatArray: ...


class _Regressor(Protocol):
    def fit(self, x: FloatArray, y: FloatArray) -> object: ...

    def predict(self, x: FloatArray) -> FloatArray: ...


def fit_predict_proba(x_train: FloatArray, y_train: FloatArray, x_test: FloatArray) -> FloatArray:
    """Fit the logistic regression of ADR 0006 and return P(y = 1) on ``x_test``."""
    model = cast(
        "_Classifier",
        LogisticRegression(C=LOGISTIC_C, solver="lbfgs", max_iter=LOGISTIC_MAX_ITER),  # pyright: ignore[reportUnknownArgumentType]
    )
    model.fit(x_train, y_train)
    if int(np.max(model.n_iter_)) >= LOGISTIC_MAX_ITER:
        raise ValidationError("logistic regression did not converge")
    return np.asarray(model.predict_proba(x_test)[:, 1], dtype=np.float64)


def fit_predict_linear(x_train: FloatArray, y_train: FloatArray, x_test: FloatArray) -> FloatArray:
    """Fit ordinary least squares with an intercept and predict on ``x_test``."""
    model = cast("_Regressor", LinearRegression())  # pyright: ignore[reportUnknownArgumentType]
    model.fit(x_train, y_train)
    return np.asarray(model.predict(x_test), dtype=np.float64)


def cluster_resample(groups: list[IntArray], rng: np.random.Generator) -> IntArray:
    """Row indices of one cluster resample: whole groups drawn with replacement."""
    picks = rng.integers(0, len(groups), size=len(groups))
    return np.concatenate([groups[int(i)] for i in picks])


def game_groups(games: NDArray[Any]) -> list[IntArray]:
    """Row indices of each game, games in sorted order."""
    return [np.flatnonzero(games == g) for g in np.unique(games)]


def _interval(values: list[float]) -> Interval:
    tail = 100.0 * (1.0 - CI_LEVEL) / 2.0
    lo, hi = np.percentile(np.array(values, dtype=np.float64), [tail, 100.0 - tail])
    return Interval(float(lo), float(hi))


def paired_bootstrap(
    scored: ScoredTest, *, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED
) -> BootstrapResult:
    """Paired cluster bootstrap of ``candidate - baseline`` for AUC and Brier.

    Games are drawn with replacement and all plays of a drawn game are kept, so plays of one
    game never get separated. Both models are scored on the same resample. A resample with a
    single outcome class is skipped; ``resamples`` in the result counts the ones kept.
    """
    groups = game_groups(scored.games)
    rng = np.random.default_rng(seed)
    d_auc: list[float] = []
    d_brier: list[float] = []
    for _ in range(resamples):
        idx = cluster_resample(groups, rng)
        y, base, cand = scored.y[idx], scored.baseline[idx], scored.candidate[idx]
        base_auc = auc(y, base)
        if np.isnan(base_auc):
            continue
        d_auc.append(auc(y, cand) - base_auc)
        d_brier.append(brier(y, cand) - brier(y, base))
    if not d_auc:
        raise ValidationError("every bootstrap resample has a single outcome class")
    return BootstrapResult(_interval(d_auc), _interval(d_brier), len(d_auc))


def decide(delta_auc: float, lo: float) -> str:
    """Apply DECISION_RULE to the (rounded) AUC difference and its lower bound."""
    if lo > 0:
        return "signal"
    if delta_auc > WEAK_SIGNAL_MIN_DELTA_AUC:
        return "weak_signal"
    return "no_signal"


def split_by_week(results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Weeks 1-6 for training, weeks 7-8 for testing."""
    train = results.loc[results["week"] <= TRAIN_LAST_WEEK].reset_index(drop=True)
    test = results.loc[results["week"].isin(TEST_WEEKS)].reset_index(drop=True)
    if train.empty or test.empty:
        raise ValidationError(
            f"the split needs plays in weeks 1-{TRAIN_LAST_WEEK} and {TEST_WEEKS}"
        )
    for name, part in (("train", train), ("test", test)):
        if part[OUTCOME].nunique() < 2:
            raise ValidationError(f"the {name} set has a single outcome class")
    return train, test


def _completion_scores(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> FloatArray:
    x_train, x_test = design_matrices(train, test, features)
    y_train = train[OUTCOME].to_numpy(dtype=np.float64)
    return fit_predict_proba(x_train, y_train, x_test)


def _yards_scores(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> FloatArray:
    x_train, x_test = design_matrices(train, test, features)
    return fit_predict_linear(x_train, train[YARDS].to_numpy(dtype=np.float64), x_test)


def _yards_summary(train: pd.DataFrame, test: pd.DataFrame) -> Json:
    y = test[YARDS].to_numpy(dtype=np.float64)
    base = _yards_scores(train, test, BASELINE_FEATURES)
    with_dss = _yards_scores(train, test, [*BASELINE_FEATURES, *DSS_FEATURES])
    return {
        "baseline_rmse": r4(rmse(y, base)),
        "with_dss_rmse": r4(rmse(y, with_dss)),
        "delta_r2": r4(r_squared(y, with_dss) - r_squared(y, base)),
    }


def model_comparison(results: pd.DataFrame) -> Json:
    """The ``validation.model_comparison`` object of the export (contract v1.2)."""
    missing = [c for c in REQUIRED_COLUMNS if c not in results.columns]
    if missing:
        raise ValidationError(f"results are missing columns: {', '.join(missing)}")
    train, test = split_by_week(results)
    y = test[OUTCOME].to_numpy(dtype=np.float64)
    base = _completion_scores(train, test, BASELINE_FEATURES)
    with_dss = _completion_scores(train, test, [*BASELINE_FEATURES, *DSS_FEATURES])
    with_sub = _completion_scores(train, test, [*BASELINE_FEATURES, *SUBSCORE_FEATURES])
    games = test["gameId"].to_numpy()
    boot = paired_bootstrap(ScoredTest(y, base, with_dss, games))
    delta_auc = r4(auc(y, with_dss) - auc(y, base))
    lower = r4(boot.delta_auc.lo)
    return {
        "split": SPLIT_LABEL,
        "baseline_features": list(BASELINE_FEATURES),
        "n_train": len(train),
        "n_test": len(test),
        "n_test_games": len(game_groups(games)),
        "baseline_auc": r4(auc(y, base)),
        "with_dss_auc": r4(auc(y, with_dss)),
        "delta_auc": delta_auc,
        "delta_auc_ci95": [lower, r4(boot.delta_auc.hi)],
        "baseline_brier": r4(brier(y, base)),
        "with_dss_brier": r4(brier(y, with_dss)),
        "delta_brier": r4(brier(y, with_dss) - brier(y, base)),
        "delta_brier_ci95": [r4(boot.delta_brier.lo), r4(boot.delta_brier.hi)],
        "baseline_logloss": r4(log_loss(y, base)),
        "with_dss_logloss": r4(log_loss(y, with_dss)),
        "subscores_auc": r4(auc(y, with_sub)),
        "delta_subscores_auc": r4(auc(y, with_sub) - auc(y, base)),
        "yards": _yards_summary(train, test),
        "bootstrap": {"unit": "game", "resamples": boot.resamples, "seed": BOOTSTRAP_SEED},
        "decision_rule": DECISION_RULE,
        "decision": decide(delta_auc, lower),
    }
