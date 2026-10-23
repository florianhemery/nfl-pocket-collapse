"""Export contract: schema, determinism, size, and the statistics themselves."""

from __future__ import annotations

import itertools
import json
import re
import shutil
import subprocess
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
        "season": 2021,
        "week": 1 + (play_id // 40) % 8,
        "gameId": 100 + play_id // 40,
        "playId": play_id,
        "defensiveTeam": rng.choice(teams, n_plays),
        "coverage": [COVERAGES[i][0] for i in cov],
        "coverageType": [COVERAGES[i][1] for i in cov],
        "completed": (result == "C").astype(int),
    }
    results = pd.DataFrame(columns)
    plays = results[["gameId", "playId", "defensiveTeam"]].assign(passResult=result)
    games = results[["gameId", "season", "week"]].drop_duplicates()
    paths = ExportInputs(tmp_path / "r.csv", tmp_path / "plays.csv", tmp_path / "games.csv")
    results.to_csv(paths.results, index=False)
    plays.to_csv(paths.plays, index=False)
    games.to_csv(paths.games, index=False)
    return paths


def path_of(path: Path | None) -> Path:
    assert path is not None
    return path


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
        "p": round(float(res.pvalue), 6),
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
    plays = pd.read_csv(path_of(inputs.plays)).iloc[1:]
    plays.to_csv(path_of(inputs.plays), index=False)
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
    pd.read_csv(path_of(inputs.games)).iloc[1:].to_csv(path_of(inputs.games), index=False)
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


def test_schema_is_a_valid_json_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)  # pyright: ignore[reportUnknownMemberType]


def test_results_only_gives_the_same_statistics_as_the_cross_checked_path(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    full = build(inputs)
    light = build(ExportInputs(inputs.results))
    assert set(light["provenance"]["input_sha256"]) == {"dss_results.csv"}
    assert set(full["provenance"]["input_sha256"]) == {"dss_results.csv", "games.csv", "plays.csv"}
    for data in (full, light):
        data["provenance"].pop("input_sha256")
    assert full == light
    validate(build(ExportInputs(inputs.results)))


def test_plays_and_games_come_together(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    with pytest.raises(ValueError, match="together"):
        ExportInputs(inputs.results, plays=inputs.plays)


def test_week_that_disagrees_with_games_csv_is_refused(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    games = pd.read_csv(path_of(inputs.games))
    games.loc[0, "week"] = 99
    games.to_csv(path_of(inputs.games), index=False)
    with pytest.raises(ExportError, match=r"disagree with games\.csv"):
        build(inputs)


def test_two_seasons_are_refused(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    results = pd.read_csv(inputs.results)
    results.loc[0, "season"] = 2022
    results.to_csv(inputs.results, index=False)
    with pytest.raises(ExportError, match="one season"):
        build(ExportInputs(inputs.results))


def test_p_values_keep_six_decimals_and_are_never_zero() -> None:
    assert export.p6(0.1098332508) == 0.109833
    assert export.p6(3.2e-9) == 1e-6
    with pytest.raises(ExportError, match="p-value"):
        export.p6(float("nan"))


def stratified_frame(seed: int = 3) -> pd.DataFrame:
    """Two coverage families whose own DSS/outcome slopes are negative but whose pooled one is not.

    Zone plays have a high DSS and a high completion rate, Man plays the opposite, so pooling
    hides the within-family association.
    """
    rng = np.random.default_rng(seed)
    n = 800
    frames: list[pd.DataFrame] = []
    for k, (kind, centre, base) in enumerate([("Zone", 60.0, 0.70), ("Man", 50.0, 0.40)]):
        dss = rng.normal(centre, 4.0, n)
        prob = np.clip(base - 0.012 * (dss - centre), 0.02, 0.98)
        frames.append(
            pd.DataFrame(
                {
                    "dss": dss,
                    "completed": (rng.random(n) < prob).astype(int),
                    "coverageType": kind,
                    "frames_analyzed": rng.integers(10, 40, n),
                    "gameId": k,
                    "playId": np.arange(n),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_stratum_table_matches_independent_computation() -> None:
    frame = stratified_frame()
    table = export.stratum_table(frame)
    assert [row["stratum"] for row in table] == ["Man", "Zone"]
    kind = frame["coverageType"].to_numpy()
    dss = frame["dss"].to_numpy(dtype=np.float64)
    completed = frame["completed"].to_numpy(dtype=np.float64)
    for row in table:
        pick = kind == row["stratum"]
        r = float(np.corrcoef(dss[pick], completed[pick])[0, 1])
        dof = int(pick.sum()) - 2
        t = abs(r) * float(np.sqrt(dof / (1 - r * r)))
        p = 2.0 * float(stats.t.sf(t, dof))
        median = float(np.median(dss[pick]))
        high = pick & (dss >= median)
        low = pick & (dss < median)
        assert row["n"] == int(pick.sum())
        assert row["r"] == round(r, 4)
        assert row["p"] == pytest.approx(max(round(p, 6), 1e-6), abs=2e-6)
        assert row["completion_high_dss"] == round(float(completed[high].mean()), 4)
        assert row["completion_low_dss"] == round(float(completed[low].mean()), 4)
        assert row["completion_low_dss"] > row["completion_high_dss"]


def test_small_or_constant_strata_are_left_out() -> None:
    frame = stratified_frame()
    tiny = pd.DataFrame(
        {
            "dss": [40.0, 41.0],
            "completed": [1, 0],
            "coverageType": "Tiny",
            "frames_analyzed": [10, 11],
            "gameId": 9,
            "playId": [0, 1],
        }
    )
    flat = tiny.assign(coverageType="Flat", completed=1, dss=[1.0, 2.0], playId=[5, 6])
    flat = pd.concat([flat] * 3, ignore_index=True).assign(playId=range(6))
    table = export.stratum_table(pd.concat([frame, tiny, flat], ignore_index=True))
    assert {row["stratum"] for row in table} == {"Man", "Zone"}


def test_partial_correlation_matches_the_precision_matrix_formula() -> None:
    rng = np.random.default_rng(11)
    n = 400
    controls = rng.normal(size=(n, 2))
    x = controls @ np.array([1.0, -0.5]) + rng.normal(size=n)
    y = controls @ np.array([0.3, 0.8]) - 0.2 * x + rng.normal(size=n)
    r, p, count = export.partial_correlation(y, x, controls)
    precision = np.linalg.inv(np.corrcoef(np.column_stack([y, x, controls]), rowvar=False))
    expected = -precision[0, 1] / np.sqrt(precision[0, 0] * precision[1, 1])
    assert r == pytest.approx(expected, abs=1e-9)
    dof = n - 2 - 2
    t = expected * np.sqrt(dof / (1 - expected**2))
    assert p == pytest.approx(2 * stats.t.sf(abs(t), dof), abs=1e-9)
    assert count == n


def test_partial_correlation_refuses_degenerate_inputs() -> None:
    controls = np.arange(10.0)[:, None]
    with pytest.raises(ExportError, match="explained"):
        export.partial_correlation(2 * np.arange(10.0), np.arange(10.0) ** 2, controls)
    with pytest.raises(ExportError, match="enough plays"):
        export.partial_correlation(np.arange(3.0), np.arange(3.0), np.ones((3, 1)))


def test_adjusted_estimate_removes_a_pure_confounder() -> None:
    rng = np.random.default_rng(5)
    n = 6000
    frames = rng.integers(10, 60, n)
    kind = rng.choice(["Man", "Zone"], n)
    dss = 70.0 - 0.3 * frames + 6.0 * (kind == "Zone") + rng.normal(0, 3, n)
    prob = np.clip(0.9 - 0.008 * frames - 0.2 * (kind == "Man"), 0.01, 0.99)
    frame = pd.DataFrame(
        {
            "dss": dss,
            "completed": (rng.random(n) < prob).astype(int),
            "coverageType": kind,
            "frames_analyzed": frames,
        }
    )
    pooled, _ = export.pearson(frame["dss"].to_numpy(), frame["completed"].to_numpy(dtype=float))
    adjusted = export.adjusted_estimate(frame)
    assert abs(pooled) > 0.1
    assert abs(adjusted["r"]) < 0.04
    assert adjusted["controls"] == ["frames_analyzed", "coverage_type"]
    assert adjusted["n"] == n
    assert "frames_analyzed" in adjusted["method"]
    assert "coverage_type" in adjusted["method"]


def strata_rows(*rows: tuple[int, float, float]) -> list[export.Json]:
    return [{"stratum": f"s{i}", "n": n, "r": r, "p": p} for i, (n, r, p) in enumerate(rows)]


@pytest.mark.parametrize(
    ("pooled", "strata", "expected"),
    [
        # pooled null, every large stratum negative and significant
        ((-0.0185, 0.1098), [(2160, -0.07, 0.001), (4943, -0.05, 0.0008)], "simpson"),
        # pooled and strata agree: all significant
        ((-0.1, 0.0001), [(2160, -0.07, 0.001), (4943, -0.05, 0.0008)], "consistent"),
        # pooled and strata agree: all null
        ((-0.01, 0.4), [(2160, -0.01, 0.4), (4943, 0.01, 0.5)], "consistent"),
        # strata disagree among themselves: no uniform reading
        ((-0.0185, 0.1098), [(2160, -0.07, 0.001), (4943, -0.01, 0.5)], "consistent"),
        # pooled significant, strata all null
        ((-0.05, 0.001), [(2160, -0.01, 0.4), (4943, 0.01, 0.5)], "simpson"),
        # pooled positive and significant, strata negative and significant
        ((0.05, 0.001), [(2160, -0.07, 0.001), (4943, -0.05, 0.0008)], "simpson"),
        # a small stratum does not enter the reading
        (
            (-0.0185, 0.1098),
            [(2160, -0.07, 0.001), (4943, -0.05, 0.001), (407, -0.07, 0.14)],
            "simpson",
        ),
        # nothing large enough to read
        ((-0.0185, 0.1098), [(100, -0.2, 0.001)], "consistent"),
    ],
)
def test_reading_rule(
    pooled: tuple[float, float], strata: list[tuple[int, float, float]], expected: str
) -> None:
    assert export.reading(pooled[0], pooled[1], strata_rows(*strata)) == expected
    assert str(export.READING_MIN_PLAYS) in export.READING_RULE
    assert str(export.WEAK_SIGNAL_ALPHA) in export.READING_RULE


def test_export_carries_the_stratified_block(tmp_path: Path) -> None:
    data = build(make_inputs(tmp_path))
    block = data["validation"]["stratified"]
    assert block["by"] == "coverage_type"
    assert block["reading"] in {"simpson", "consistent"}
    assert {row["stratum"] for row in block["strata"]} == {"Zone", "Man", "Other"}
    assert block["adjusted"]["n"] == 1200
    validate(data)


def test_git_commit_marks_a_modified_tree(tmp_path: Path) -> None:
    git = shutil.which("git")
    assert git is not None
    quiet = [git, "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(tmp_path)]
    subprocess.run([git, "-C", str(tmp_path), "init", "-q"], check=True)  # noqa: S603
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run([*quiet, "add", "a.txt"], check=True)  # noqa: S603
    subprocess.run([*quiet, "-c", "commit.gpgsign=false", "commit", "-qm", "init"], check=True)  # noqa: S603
    clean = export.git_commit(tmp_path)
    assert re.fullmatch(r"[0-9a-f]{7}", clean)
    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")
    assert export.git_commit(tmp_path) == f"{clean}-dirty"
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    assert export.git_commit(tmp_path) == clean
    (tmp_path / "new.txt").write_text("untracked\n", encoding="utf-8")
    assert export.git_commit(tmp_path) == f"{clean}-dirty"
    (tmp_path / "new.txt").unlink()
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "site-data.json").write_text("{}\n", encoding="utf-8")
    assert export.git_commit(tmp_path) == clean
