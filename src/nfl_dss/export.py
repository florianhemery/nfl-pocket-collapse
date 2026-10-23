"""Build ``site-data.json`` (contract: docs/CONTRACT.md, schema: docs/site-data.schema.json).

Every number is computed here from three files: ``output/dss_results.csv``, ``data/plays.csv``
and ``data/games.csv``. Nothing is typed by hand. Floats are rounded to 4 decimals.
"""

from __future__ import annotations

import hashlib
import json
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

SCHEMA_VERSION = "1.0"
DECIMALS = 4
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261023
CI_LEVEL = 0.95
QUINTILES = 5

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
    "descriptive correlation only; the held-out model comparison (model_comparison) is "
    "reported separately when available."
)

DATASET_NAME = "NFL Big Data Bowl 2023"
DATASET_LICENSE_NOTE = (
    "The terms of the 2023 competition were not verified by the producer of this file. "
    "Recent Big Data Bowl editions are published under CC BY-NC 4.0 according to secondary "
    "sources. The Kaggle files are not redistributed here: only derived statistics are."
)
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
    "gameId",
    "playId",
    "defensiveTeam",
    "passResult",
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
    """Paths of the three files the export is computed from."""

    results: Path
    plays: Path
    games: Path


def r4(value: float) -> float:
    """Round to the contract precision, refusing NaN and infinities."""
    if not np.isfinite(value):
        raise ExportError(f"non-finite value in export: {value}")
    return round(float(value), DECIMALS)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit(repo_dir: Path) -> str:
    """Short sha of ``HEAD`` in ``repo_dir``, or ``unknown`` outside a git checkout."""
    git = shutil.which("git")
    if git is None:
        return "unknown"
    proc = subprocess.run(  # noqa: S603
        [git, "-C", str(repo_dir), "rev-parse", "--short=7", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else "unknown"


def load_results(inputs: ExportInputs) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read and cross-check the results against plays.csv and games.csv.

    Returns the results and the games they cover. Fails if a play is unknown to plays.csv or
    if the outcome flag disagrees with ``passResult``.
    """
    for path in (inputs.results, inputs.plays, inputs.games):
        if not path.is_file():
            raise ExportError(f"missing input file: {path}")
    results = pd.read_csv(inputs.results)
    missing = [c for c in RESULT_COLUMNS if c not in results.columns]
    if missing:
        raise ExportError(f"{inputs.results} is missing columns: {', '.join(missing)}")
    if results.duplicated(["gameId", "playId"]).any():
        raise ExportError("duplicate (gameId, playId) rows in results")
    plays = pd.read_csv(inputs.plays, usecols=["gameId", "playId", "passResult", "defensiveTeam"])
    joined = results.merge(plays, on=["gameId", "playId"], how="left", suffixes=("", "_plays"))
    if joined["passResult_plays"].isna().any():
        raise ExportError("some results rows are absent from plays.csv")
    expected = (joined["passResult_plays"] == "C").astype(int)
    if (expected != joined["completed"]).any() or (
        joined["defensiveTeam"] != joined["defensiveTeam_plays"]
    ).any():
        raise ExportError("results disagree with plays.csv (completed or defensiveTeam)")
    games = pd.read_csv(inputs.games, usecols=["gameId", "season", "week"])
    games = games.loc[games["gameId"].isin(results["gameId"])]
    if games["gameId"].nunique() != results["gameId"].nunique():
        raise ExportError("some results games are absent from games.csv")
    return results, games


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
                "p_completed": r4(p),
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


def dataset_label(games: pd.DataFrame) -> str:
    seasons = sorted(games["season"].unique())
    if len(seasons) != 1:
        raise ExportError(f"expected one season, got {seasons}")
    return (
        f"{DATASET_NAME} ({seasons[0]} season, weeks {games['week'].min()}-{games['week'].max()})"
    )


def build_site_data(
    inputs: ExportInputs,
    *,
    commit: str,
    generated_at: datetime | None = None,
) -> Json:
    """Compute the whole export. ``generated_at`` is injectable for deterministic tests."""
    results, games = load_results(inputs)
    stamp = (generated_at or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    r, p = pearson(_col(results, "dss"), _col(results, "completed"))
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "pipeline_commit": commit,
            "generated_at": stamp,
            "dataset": dataset_label(games),
            "dataset_license_note": DATASET_LICENSE_NOTE,
            "input_sha256": {
                "dss_results.csv": sha256_file(inputs.results),
                "games.csv": sha256_file(inputs.games),
                "plays.csv": sha256_file(inputs.plays),
            },
            "plays_analyzed": len(results),
            "games": int(results["gameId"].nunique()),
            "teams": int(results["defensiveTeam"].nunique()),
        },
        "metric": {"formula": FORMULA, "subscores": subscore_stats(results)},
        "validation": {
            "outcome": "completed",
            "pearson_dss_completed": {"r": r4(r), "p": r4(p), "n": len(results)},
            "quintiles": quintile_table(results),
            "confounders": confounder_table(results),
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
