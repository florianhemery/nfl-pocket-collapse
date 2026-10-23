"""Build ``site-data.json`` (contract: docs/CONTRACT.md, schema: docs/site-data.schema.json).

Every number is computed here from three files: ``output/dss_results.csv``, ``data/plays.csv``
and ``data/games.csv``. Nothing is typed by hand. Floats are rounded to 4 decimals.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy import stats

SCHEMA_VERSION = "1.1"
DECIMALS = 4
#: p-values keep six decimals, floored at this value so that a tiny p is never written as 0.
P_DECIMALS = 6
P_FLOOR = 1e-6
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261023
CI_LEVEL = 0.95
QUINTILES = 5
#: Controls of the adjusted estimate: time to throw and the coverage family.
ADJUSTMENT_CONTROLS = ["frames_analyzed", "coverage_type"]
#: A coverage family needs this many plays to be read on its own (see READING_RULE).
READING_MIN_PLAYS = 500

#: Verdict thresholds. They are fixed before looking at results and written in VERDICT_RULE.
SIGNAL_ALPHA = 0.01
WEAK_SIGNAL_ALPHA = 0.05
SIGNAL_MIN_ABS_R = 0.10

VERDICT_RULE = (
    "Outcome: pass completed (1) or not (0). Let r be the Pearson correlation between DSS and "
    "the outcome over all analyzed plays. The hypothesis is that a higher DSS means fewer "
    f"completions, so only r < 0 counts. signal: p < {SIGNAL_ALPHA} and |r| >= "
    f"{SIGNAL_MIN_ABS_R}. weak_signal: p < {WEAK_SIGNAL_ALPHA}, r < 0, and not signal. "
    "no_signal: anything else, including a significant positive r. This rule looks at the "
    "descriptive correlation only and does not account for confounding (see "
    "validation.stratified); the held-out model comparison (model_comparison) is "
    "reported separately when available."
)

#: Written before looking at the stratified results; documented in docs/CONTRACT.md.
READING_RULE = (
    "A stratum is a coverage family (coverage_type) with at least "
    f"{READING_MIN_PLAYS} plays; smaller ones are reported but do not enter the reading. "
    "A correlation counts as an association when r < 0 and p < "
    f"{WEAK_SIGNAL_ALPHA}. reading is simpson when all the strata that enter the reading "
    "agree with each other on whether there is an association and the pooled correlation "
    "says the opposite. It is consistent in every other case."
)

DATASET_NAME = "NFL Big Data Bowl 2023"
DATASET_LICENSE_NOTE = (
    "The terms of the 2023 competition were not verified by the producer of this file. "
    "Recent Big Data Bowl editions are published under CC BY-NC 4.0 according to secondary "
    "sources. The raw Kaggle files are not tracked in this repository, but a row-level "
    "extract is: output/dss_results.csv holds, for each analyzed play, the game and play "
    "ids, the defensive team, the PFF coverage labels, the completion flag and the computed "
    "scores. Whether redistributing that extract is permitted has not been verified."
)
#: Path of the committed export, relative to the repository root.
EXPORT_PATH = "exports/site-data.json"
FORMULA = "DSS = 100 * (0.40*VA + 0.30*SD + 0.30*OD)"

SUBSCORES = [
    ("va", "Velocity Alignment"),
    ("sd", "Spacing Discipline"),
    ("od", "Orientation Divergence"),
]
RESULT_COLUMNS = [
    "dss",
    "va",
    "sd",
    "od",
    "frames_analyzed",
    "season",
    "week",
    "gameId",
    "playId",
    "defensiveTeam",
    "coverage",
    "coverageType",
    "completed",
]

FloatArray = NDArray[np.float64]
Json = dict[str, Any]


class ExportError(RuntimeError):
    """The inputs cannot produce a trustworthy export."""


@dataclass(frozen=True)
class ExportInputs:
    """Paths of the files the export is computed from.

    ``plays`` and ``games`` come together or not at all. With both, the results are
    cross-checked against the competition files. Without them (the results-only path, the one
    CI can run) the export is computed from ``results`` alone.
    """

    results: Path
    plays: Path | None = None
    games: Path | None = None

    def __post_init__(self) -> None:
        if (self.plays is None) != (self.games is None):
            raise ValueError("plays and games must be given together")


def r4(value: float) -> float:
    """Round to the contract precision, refusing NaN and infinities."""
    if not np.isfinite(value):
        raise ExportError(f"non-finite value in export: {value}")
    return round(float(value), DECIMALS)


def p6(value: float) -> float:
    """Round a p-value to six decimals, never to 0, refusing NaN."""
    if not np.isfinite(value):
        raise ExportError(f"non-finite p-value in export: {value}")
    return max(round(float(value), P_DECIMALS), P_FLOOR)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(git: str, repo_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [git, "-C", str(repo_dir), *args], capture_output=True, text=True, check=False
    )


def git_commit(repo_dir: Path) -> str:
    """Short sha of ``HEAD`` in ``repo_dir``, ``-dirty`` appended if the tree is modified.

    ``unknown`` outside a git checkout. The export itself is left out of the dirty check, so
    that regenerating it twice in a row gives the same answer.
    """
    git = shutil.which("git")
    if git is None:
        return "unknown"
    head = _git(git, repo_dir, "rev-parse", "--short=7", "HEAD")
    sha = head.stdout.strip()
    if head.returncode != 0 or not sha:
        return "unknown"
    status = _git(git, repo_dir, "status", "--porcelain", "--", ".", f":(exclude){EXPORT_PATH}")
    return f"{sha}-dirty" if status.returncode != 0 or status.stdout.strip() else sha


def _read_results(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise ExportError(f"missing input file: {path}")
    results = pd.read_csv(path)
    missing = [c for c in RESULT_COLUMNS if c not in results.columns]
    if missing:
        raise ExportError(f"{path} is missing columns: {', '.join(missing)}")
    if results.duplicated(["gameId", "playId"]).any():
        raise ExportError("duplicate (gameId, playId) rows in results")
    return results


def _check_against_plays(results: pd.DataFrame, plays_path: Path) -> None:
    if not plays_path.is_file():
        raise ExportError(f"missing input file: {plays_path}")
    plays = pd.read_csv(plays_path, usecols=["gameId", "playId", "passResult", "defensiveTeam"])
    joined = results.merge(plays, on=["gameId", "playId"], how="left", suffixes=("", "_plays"))
    if joined["passResult"].isna().any():
        raise ExportError("some results rows are absent from plays.csv")
    expected = (joined["passResult"] == "C").astype(int)
    if (expected != joined["completed"]).any() or (
        joined["defensiveTeam"] != joined["defensiveTeam_plays"]
    ).any():
        raise ExportError("results disagree with plays.csv (completed or defensiveTeam)")


def _check_against_games(results: pd.DataFrame, games_path: Path) -> None:
    if not games_path.is_file():
        raise ExportError(f"missing input file: {games_path}")
    games = pd.read_csv(games_path, usecols=["gameId", "season", "week"])
    seen = results[["gameId", "season", "week"]].drop_duplicates()
    joined = seen.merge(games, on="gameId", how="left", suffixes=("", "_games"))
    if joined["season_games"].isna().any():
        raise ExportError("some results games are absent from games.csv")
    if (joined["season"] != joined["season_games"]).any() or (
        joined["week"] != joined["week_games"]
    ).any():
        raise ExportError("results disagree with games.csv (season or week)")


def load_results(inputs: ExportInputs) -> pd.DataFrame:
    """Read the results and, when the competition files are given, cross-check them.

    Fails if a play or game is unknown to ``plays.csv`` / ``games.csv`` or if the outcome flag,
    the defensive team, the season or the week disagree with them.
    """
    results = _read_results(inputs.results)
    if inputs.plays is not None and inputs.games is not None:
        _check_against_plays(results, inputs.plays)
        _check_against_games(results, inputs.games)
    return results


def pearson(a: FloatArray, b: FloatArray) -> tuple[float, float]:
    """Pearson r and two-sided p-value, refusing constant inputs."""
    if np.std(a) == 0 or np.std(b) == 0:
        raise ExportError("correlation undefined: constant input")
    res = stats.pearsonr(a, b)
    return float(res.statistic), float(res.pvalue)


def _col(results: pd.DataFrame, name: str) -> FloatArray:
    return results[name].to_numpy(dtype=np.float64)


def subscore_stats(results: pd.DataFrame) -> list[Json]:
    """Mean, sample standard deviation and correlation with completion of each sub-score."""
    completed = _col(results, "completed")
    out: list[Json] = []
    for key, label in SUBSCORES:
        values = _col(results, key)
        r, p = pearson(values, completed)
        out.append(
            {
                "id": key,
                "label": label,
                "mean": r4(values.mean()),
                "sd": r4(values.std(ddof=1)),
                "r_completed": r4(r),
                "p_completed": p6(p),
            }
        )
    return out


def quintile_table(results: pd.DataFrame) -> list[Json]:
    """Five equal-sized groups by DSS (ties broken by game and play id), lowest first."""
    dss, completed = _col(results, "dss"), _col(results, "completed")
    order = np.lexsort((_col(results, "playId"), _col(results, "gameId"), dss))
    n = len(order)
    if n < QUINTILES:
        raise ExportError("not enough plays for quintiles")
    group = (np.arange(n) * QUINTILES) // n
    out: list[Json] = []
    for q in range(QUINTILES):
        idx = order[group == q]
        out.append(
            {
                "q": q + 1,
                "dss_min": r4(dss[idx].min()),
                "dss_max": r4(dss[idx].max()),
                "completion_rate": r4(completed[idx].mean()),
                "n": len(idx),
            }
        )
    return out


def confounder_table(results: pd.DataFrame) -> list[Json]:
    """Variables that may drive completion independently of coordination."""
    r, _ = pearson(_col(results, "frames_analyzed"), _col(results, "completed"))
    return [{"id": "frames_analyzed", "label": "Time to throw (frames)", "r_completed": r4(r)}]


def verdict(r: float, p: float) -> str:
    """Apply VERDICT_RULE to the DSS/completion correlation."""
    if p < SIGNAL_ALPHA and abs(r) >= SIGNAL_MIN_ABS_R and r < 0:
        return "signal"
    if p < WEAK_SIGNAL_ALPHA and r < 0:
        return "weak_signal"
    return "no_signal"


def partial_correlation(
    y: FloatArray, x: FloatArray, controls: FloatArray
) -> tuple[float, float, int]:
    """Partial correlation of ``y`` and ``x`` given the columns of ``controls``.

    Both variables are regressed on an intercept and the controls (least squares) and the
    residuals are correlated. The p-value uses ``n - k - 2`` degrees of freedom with ``k`` the
    number of control columns. Returns ``(r, p, n)``.
    """
    n = len(y)
    design = np.column_stack([np.ones(n), controls])
    dof = n - controls.shape[1] - 2
    if dof < 1:
        raise ExportError("not enough plays for the adjusted estimate")
    residuals: list[FloatArray] = []
    for column in (y, x):
        beta, *_ = np.linalg.lstsq(design, column, rcond=None)
        residuals.append(column - design @ beta)
    if np.std(residuals[0]) < 1e-12 or np.std(residuals[1]) < 1e-12:
        raise ExportError("partial correlation undefined: a variable is explained by the controls")
    r = float(np.corrcoef(residuals[0], residuals[1])[0, 1])
    t = abs(r) * math.sqrt(dof / (1.0 - r * r))
    return r, float(2.0 * stats.t.sf(t, dof)), n


def _median_split_rates(dss: FloatArray, completed: FloatArray) -> tuple[float, float]:
    """Completion rate of the plays with DSS at or above the median, then below it."""
    high = dss >= np.median(dss)
    if high.all() or not high.any():
        raise ExportError("median split undefined: constant DSS")
    return float(completed[high].mean()), float(completed[~high].mean())


def stratum_table(results: pd.DataFrame) -> list[Json]:
    """DSS/completion correlation and median split inside each coverage family, largest first.

    A family with fewer than 3 plays or with a constant outcome has no correlation and is left
    out.
    """
    kind = np.array([str(v) for v in results["coverageType"]])
    dss, completed = _col(results, "dss"), _col(results, "completed")
    out: list[Json] = []
    for name in sorted(set(kind.tolist())):
        pick = kind == name
        if pick.sum() < 3 or np.std(completed[pick]) == 0:
            continue
        r, p = pearson(dss[pick], completed[pick])
        high, low = _median_split_rates(dss[pick], completed[pick])
        out.append(
            {
                "stratum": name,
                "n": int(pick.sum()),
                "r": r4(r),
                "p": p6(p),
                "completion_high_dss": r4(high),
                "completion_low_dss": r4(low),
            }
        )
    return sorted(out, key=lambda row: (-row["n"], row["stratum"]))


def adjusted_estimate(results: pd.DataFrame) -> Json:
    """Partial correlation of DSS and completion given time to throw and coverage family."""
    kind = pd.Series([str(v) for v in results["coverageType"]])
    dummies = pd.get_dummies(kind, drop_first=True, dtype=np.float64)
    controls = np.column_stack([_col(results, "frames_analyzed"), dummies.to_numpy()])
    r, p, n = partial_correlation(_col(results, "dss"), _col(results, "completed"), controls)
    return {
        "method": (
            "partial correlation of DSS and completed controlling for "
            + " and ".join(ADJUSTMENT_CONTROLS)
        ),
        "controls": list(ADJUSTMENT_CONTROLS),
        "r": r4(r),
        "p": p6(p),
        "n": n,
    }


def reading(pooled_r: float, pooled_p: float, strata: list[Json]) -> str:
    """Apply READING_RULE: ``simpson`` when the strata and the pooled correlation disagree."""
    pooled = pooled_p < WEAK_SIGNAL_ALPHA and pooled_r < 0
    within = {
        row["p"] < WEAK_SIGNAL_ALPHA and row["r"] < 0
        for row in strata
        if row["n"] >= READING_MIN_PLAYS
    }
    return "simpson" if len(within) == 1 and within != {pooled} else "consistent"


def stratified_validation(results: pd.DataFrame, pooled_r: float, pooled_p: float) -> Json:
    """Within-coverage and adjusted estimates, to read next to the pooled correlation."""
    strata = stratum_table(results)
    return {
        "by": "coverage_type",
        "strata": strata,
        "adjusted": adjusted_estimate(results),
        "reading": reading(pooled_r, pooled_p, strata),
    }


def bootstrap_ci(values: FloatArray, rng: np.random.Generator) -> tuple[float, float]:
    """Percentile bootstrap interval of the mean."""
    idx = rng.integers(0, len(values), size=(BOOTSTRAP_RESAMPLES, len(values)))
    means = values[idx].mean(axis=1)
    tail = 100.0 * (1.0 - CI_LEVEL) / 2.0
    lo, hi = np.percentile(means, [tail, 100.0 - tail])
    return float(lo), float(hi)


def shrink_means(means: FloatArray, counts: FloatArray, variances: FloatArray) -> FloatArray:
    """Empirical-Bayes (normal-normal, method of moments) shrinkage towards the grand mean.

    Each team mean has sampling variance ``v_i = variance_i / n_i``. The between-team variance
    is ``tau2 = max(0, var(means) - mean(v_i))`` and the shrunk mean is
    ``grand + tau2 / (tau2 + v_i) * (mean_i - grand)`` with ``grand`` the play-weighted mean.
    """
    sampling = variances / counts
    grand = float(np.average(means, weights=counts))
    tau2 = max(0.0, float(np.var(means, ddof=1)) - float(sampling.mean()))
    weight = tau2 / (tau2 + sampling) if tau2 > 0 else np.zeros_like(sampling)
    return grand + weight * (means - grand)


def team_table(results: pd.DataFrame) -> list[Json]:
    """Per-team DSS with bootstrap 95% interval and shrunk mean, sorted by team."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    team_of = np.array([str(t) for t in results["defensiveTeam"]])
    dss, completed = _col(results, "dss"), _col(results, "completed")
    teams = sorted(set(team_of.tolist()))
    values = [dss[team_of == t] for t in teams]
    if any(len(v) < 2 for v in values):
        raise ExportError("a team has fewer than 2 plays")
    means = np.array([v.mean() for v in values])
    counts = np.array([len(v) for v in values], dtype=np.float64)
    variances = np.array([v.var(ddof=1) for v in values])
    shrunk = shrink_means(means, counts, variances)
    out: list[Json] = []
    for i, team in enumerate(teams):
        lo, hi = bootstrap_ci(values[i], rng)
        out.append(
            {
                "team": team,
                "n": len(values[i]),
                "dss_mean": r4(means[i]),
                "dss_ci95": [r4(lo), r4(hi)],
                "dss_shrunk": r4(shrunk[i]),
                "completion_rate": r4(completed[team_of == team].mean()),
            }
        )
    return out


def coverage_table(results: pd.DataFrame) -> list[Json]:
    """Per coverage scheme DSS and completion rate, most frequent first."""
    cov = np.array([str(v) for v in results["coverage"]])
    kind = np.array([str(v) for v in results["coverageType"]])
    dss, completed = _col(results, "dss"), _col(results, "completed")
    out: list[Json] = []
    for name, type_ in sorted(set(zip(cov.tolist(), kind.tolist(), strict=True))):
        pick = (cov == name) & (kind == type_)
        out.append(
            {
                "coverage": name,
                "coverage_type": type_,
                "n": int(pick.sum()),
                "dss_mean": r4(dss[pick].mean()),
                "completion_rate": r4(completed[pick].mean()),
            }
        )
    return sorted(out, key=lambda row: (-row["n"], row["coverage"]))


def dataset_label(results: pd.DataFrame) -> str:
    seasons = sorted(int(v) for v in results["season"].unique())
    if len(seasons) != 1:
        raise ExportError(f"expected one season, got {seasons}")
    first, last = int(results["week"].min()), int(results["week"].max())
    return f"{DATASET_NAME} ({seasons[0]} season, weeks {first}-{last})"


def _input_hashes(inputs: ExportInputs) -> dict[str, str]:
    paths = {"dss_results.csv": inputs.results}
    if inputs.plays is not None and inputs.games is not None:
        paths.update({"games.csv": inputs.games, "plays.csv": inputs.plays})
    return {name: sha256_file(path) for name, path in sorted(paths.items())}


def build_site_data(
    inputs: ExportInputs,
    *,
    commit: str,
    generated_at: datetime | None = None,
) -> Json:
    """Compute the whole export. ``generated_at`` is injectable for deterministic tests."""
    results = load_results(inputs)
    stamp = (generated_at or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    r, p = pearson(_col(results, "dss"), _col(results, "completed"))
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "pipeline_commit": commit,
            "generated_at": stamp,
            "dataset": dataset_label(results),
            "dataset_license_note": DATASET_LICENSE_NOTE,
            "input_sha256": _input_hashes(inputs),
            "plays_analyzed": len(results),
            "games": int(results["gameId"].nunique()),
            "teams": int(results["defensiveTeam"].nunique()),
        },
        "metric": {"formula": FORMULA, "subscores": subscore_stats(results)},
        "validation": {
            "outcome": "completed",
            "pearson_dss_completed": {"r": r4(r), "p": p6(p), "n": len(results)},
            "quintiles": quintile_table(results),
            "confounders": confounder_table(results),
            "stratified": stratified_validation(results, r, p),
            "model_comparison": None,
            "verdict": verdict(r, p),
            "verdict_rule": VERDICT_RULE,
        },
        "teams": team_table(results),
        "coverages": coverage_table(results),
        "replays": [],
    }


def dump_site_data(data: Json) -> str:
    """Canonical serialization: 2-space indent, UTF-8, trailing newline."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_site_data(data: Json, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_site_data(data), encoding="utf-8")
