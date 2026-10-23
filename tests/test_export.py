"""Export contract: schema, determinism, size, and the statistics themselves."""

from __future__ import annotations

import itertools
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator
from scipy import stats

from nfl_dss import export
from nfl_dss.export import ExportError, ExportInputs, build_site_data, dump_site_data

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs" / "site-data.schema.json").read_text(encoding="utf-8"))
COMMITTED = ROOT / "exports" / "site-data.json"
FIXED_TIME = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
COVERAGES = [("Cover-3", "Zone"), ("Cover-1", "Man"), ("Cover-2", "Zone"), ("Prevent", "Other")]


def make_inputs(
    tmp_path: Path, n_teams: int = 8, n_plays: int = 1200, seed: int = 7
) -> ExportInputs:
    """Synthetic results, plays and games files that are consistent with each other."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(n_teams)]
    play_id = np.arange(n_plays)
    cov = rng.integers(0, len(COVERAGES), n_plays)
    result = rng.choice(["C", "I", "IN", "S"], n_plays, p=[0.6, 0.3, 0.05, 0.05])
    columns: dict[str, Any] = {
        "dss": rng.normal(56, 8, n_plays).round(2).clip(20, 90),
        "va": rng.uniform(5, 99, n_plays).round(2),
        "sd": rng.normal(71, 3, n_plays).round(2),
        "od": rng.uniform(1, 80, n_plays).round(2),
        "num_dbs": 5,
        "frames_analyzed": rng.integers(10, 60, n_plays),
        "gameId": 100 + play_id // 40,
        "playId": play_id,
        "defensiveTeam": rng.choice(teams, n_plays),
        "passResult": result,
        "coverage": [COVERAGES[i][0] for i in cov],
        "coverageType": [COVERAGES[i][1] for i in cov],
        "completed": (result == "C").astype(int),
    }
    results = pd.DataFrame(columns)
    plays = results[["gameId", "playId", "passResult", "defensiveTeam"]]
    game_ids = sorted(results["gameId"].unique())
    games = pd.DataFrame(
        {"gameId": game_ids, "season": 2021, "week": [1 + i % 8 for i in range(len(game_ids))]}
    )
    paths = ExportInputs(tmp_path / "r.csv", tmp_path / "plays.csv", tmp_path / "games.csv")
    results.to_csv(paths.results, index=False)
    plays.to_csv(paths.plays, index=False)
    games.to_csv(paths.games, index=False)
    return paths


def build(inputs: ExportInputs) -> dict[str, Any]:
    return build_site_data(inputs, commit="abc1234", generated_at=FIXED_TIME)


def validate(data: dict[str, Any]) -> None:
    Draft202012Validator(SCHEMA).validate(data)  # pyright: ignore[reportUnknownMemberType]


def test_export_validates_against_schema(tmp_path: Path) -> None:
    validate(build(make_inputs(tmp_path)))


def test_schema_rejects_unknown_fields_and_bad_values(tmp_path: Path) -> None:
    data = build(make_inputs(tmp_path))
    extra = deepcopy(data)
    extra["surprise"] = 1
    bad = deepcopy(data)
    bad["validation"]["verdict"] = "great"
    for broken in (extra, bad):
        with pytest.raises(Exception, match=r"surprise|great"):
            validate(broken)


def test_rerun_is_deterministic_except_timestamp(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    first = dump_site_data(build(inputs))
    assert dump_site_data(build(inputs)) == first
    later = dump_site_data(
        build_site_data(inputs, commit="abc1234", generated_at=datetime(2027, 1, 1, tzinfo=UTC))
    )
    assert later != first
    a, b = json.loads(first), json.loads(later)
    a["provenance"]["generated_at"] = b["provenance"]["generated_at"]
    assert a == b


def test_full_size_export_stays_under_budget(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path, n_teams=32, n_plays=7510)
    text = dump_site_data(build(inputs))
    assert len(text.encode("utf-8")) < 300 * 1024


def test_statistics_match_independent_computation(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    data = build(inputs)
    df = pd.read_csv(inputs.results)
    res = stats.pearsonr(df["dss"], df["completed"])
    assert data["validation"]["pearson_dss_completed"] == {
        "r": round(float(res.statistic), 4),
        "p": round(float(res.pvalue), 4),
        "n": len(df),
    }
    va = next(s for s in data["metric"]["subscores"] if s["id"] == "va")
    assert va["mean"] == round(df["va"].mean(), 4)
    assert va["sd"] == round(df["va"].std(ddof=1), 4)
    quintiles = data["validation"]["quintiles"]
    assert sum(q["n"] for q in quintiles) == len(df)
    assert [q["q"] for q in quintiles] == [1, 2, 3, 4, 5]
    assert all(a["dss_max"] <= b["dss_min"] for a, b in itertools.pairwise(quintiles))
    prov = data["provenance"]
    assert (prov["plays_analyzed"], prov["teams"]) == (1200, 8)
    assert prov["dataset"] == "NFL Big Data Bowl 2023 (2021 season, weeks 1-8)"
    assert data["validation"]["model_comparison"] is None
    assert data["replays"] == []


def test_team_table_intervals_and_shrinkage(tmp_path: Path) -> None:
    data = build(make_inputs(tmp_path))
    teams = data["teams"]
    assert [t["team"] for t in teams] == sorted(t["team"] for t in teams)
    grand = float(np.average([t["dss_mean"] for t in teams], weights=[t["n"] for t in teams]))
    for team in teams:
        lo, hi = team["dss_ci95"]
        assert lo < team["dss_mean"] < hi
        assert abs(team["dss_shrunk"] - grand) <= abs(team["dss_mean"] - grand) + 1e-3


def test_shrinkage_collapses_to_grand_mean_without_between_team_variance() -> None:
    means = np.array([50.0, 50.1, 49.9])
    counts = np.array([100.0, 100.0, 100.0])
    variances = np.array([400.0, 400.0, 400.0])
    shrunk = export.shrink_means(means, counts, variances)
    assert shrunk == pytest.approx(np.full(3, 50.0))


def test_shrinkage_barely_moves_well_separated_teams() -> None:
    means = np.array([40.0, 60.0, 80.0])
    counts = np.array([1000.0, 1000.0, 1000.0])
    variances = np.array([1.0, 1.0, 1.0])
    assert export.shrink_means(means, counts, variances) == pytest.approx(means, abs=0.01)


def test_coverages_sorted_by_frequency(tmp_path: Path) -> None:
    coverages = build(make_inputs(tmp_path))["coverages"]
    assert [c["n"] for c in coverages] == sorted((c["n"] for c in coverages), reverse=True)
    assert {c["coverage"] for c in coverages} == {c for c, _ in COVERAGES}


@pytest.mark.parametrize(
    ("r", "p", "expected"),
    [
        (-0.15, 0.001, "signal"),
        (-0.10, 0.0099, "signal"),
        (-0.05, 0.001, "weak_signal"),
        (-0.15, 0.03, "weak_signal"),
        (-0.0185, 0.1098, "no_signal"),
        (0.2, 0.0001, "no_signal"),
        (0.0, 1.0, "no_signal"),
    ],
)
def test_verdict_rule(r: float, p: float, expected: str) -> None:
    assert export.verdict(r, p) == expected
    assert str(export.SIGNAL_ALPHA) in export.VERDICT_RULE
    assert str(export.SIGNAL_MIN_ABS_R) in export.VERDICT_RULE


def test_inconsistent_completed_flag_is_refused(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    df = pd.read_csv(inputs.results)
    completed = df["completed"].to_numpy().copy()
    completed[0] = 1 - completed[0]
    df["completed"] = completed
    df.to_csv(inputs.results, index=False)
    with pytest.raises(ExportError, match="disagree"):
        build(inputs)


def test_unknown_play_missing_file_and_bad_columns_are_refused(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    plays = pd.read_csv(inputs.plays).iloc[1:]
    plays.to_csv(inputs.plays, index=False)
    with pytest.raises(ExportError, match=r"absent from plays\.csv"):
        build(inputs)
    with pytest.raises(ExportError, match="missing input file"):
        build(ExportInputs(tmp_path / "x.csv", inputs.plays, inputs.games))
    pd.read_csv(inputs.results).drop(columns=["va"]).to_csv(inputs.results, index=False)
    with pytest.raises(ExportError, match="missing columns"):
        build(inputs)


def test_duplicate_plays_and_missing_games_are_refused(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    df = pd.read_csv(inputs.results)
    pd.concat([df, df.iloc[:1]]).to_csv(inputs.results, index=False)
    with pytest.raises(ExportError, match="duplicate"):
        build(inputs)
    df.to_csv(inputs.results, index=False)
    pd.read_csv(inputs.games).iloc[1:].to_csv(inputs.games, index=False)
    with pytest.raises(ExportError, match=r"absent from games\.csv"):
        build(inputs)


def test_constant_and_non_finite_values_are_refused() -> None:
    with pytest.raises(ExportError, match="constant"):
        export.pearson(np.ones(5), np.arange(5.0))
    with pytest.raises(ExportError, match="non-finite"):
        export.r4(float("nan"))


def test_git_commit_outside_a_repository_is_unknown(tmp_path: Path) -> None:
    assert export.git_commit(tmp_path) == "unknown"
    assert export.git_commit(ROOT) != ""


def test_committed_export_is_valid_and_small() -> None:
    text = COMMITTED.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 300 * 1024
    validate(json.loads(text))


def test_committed_export_is_reproduced_by_the_pipeline() -> None:
    """Drift guard. Needs the local Kaggle CSVs, so it is skipped in CI."""
    inputs = ExportInputs(
        ROOT / "output" / "dss_results.csv",
        ROOT / "data" / "plays.csv",
        ROOT / "data" / "games.csv",
    )
    if not inputs.plays.is_file() or not inputs.games.is_file():
        pytest.skip(
            "data/plays.csv and data/games.csv are not available (see scripts/fetch_data.sh)"
        )
    fresh = build(inputs)
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    for volatile in ("generated_at", "pipeline_commit"):
        fresh["provenance"].pop(volatile)
        committed["provenance"].pop(volatile)
    assert fresh == committed
