"""Command line interface."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from nfl_dss.cli import EXIT_INPUT, EXIT_OK, main
from tests.test_export import make_inputs


def test_help_lists_both_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert "build" in out
    assert "export" in out


def test_command_is_required() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2


def test_build_writes_results_from_tiny_dataset(tiny_data: Path, tmp_path: Path) -> None:
    out = tmp_path / "out" / "dss_results.csv"
    assert main(["build", "--data-dir", str(tiny_data), "--output", str(out)]) == EXIT_OK
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == (
        "dss,va,sd,od,num_dbs,frames_analyzed,season,week,gameId,playId,"
        "defensiveTeam,coverage,coverageType,completed"
    )
    assert len(lines) == 2


def test_build_without_tracking_fails_clearly(
    tiny_data: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    shutil.rmtree(tiny_data / "tracking")
    code = main(["build", "--data-dir", str(tiny_data), "--output", str(tmp_path / "o.csv")])
    assert code == EXIT_INPUT
    assert "fetch_data.sh" in caplog.text
    assert not (tmp_path / "o.csv").exists()


def test_build_accepts_explicit_tracking_dir(tiny_data: Path, tmp_path: Path) -> None:
    moved = tmp_path / "elsewhere"
    shutil.move(tiny_data / "tracking", moved)
    out = tmp_path / "o.csv"
    args = [
        "build",
        "--data-dir",
        str(tiny_data),
        "--tracking-dir",
        str(moved),
        "--output",
        str(out),
    ]
    assert main(args) == EXIT_OK
    assert out.is_file()


def test_export_writes_valid_json(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    out = tmp_path / "exports" / "site-data.json"
    args = [
        "export",
        "--results",
        str(inputs.results),
        "--data-dir",
        str(tmp_path),
        "--output",
        str(out),
    ]
    assert main(args) == EXIT_OK
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.1"
    assert data["provenance"]["plays_analyzed"] == 1200


def test_export_with_missing_inputs_fails_clearly(tmp_path: Path) -> None:
    args = ["export", "--results", str(tmp_path / "none.csv"), "--data-dir", str(tmp_path)]
    assert main([*args, "--output", str(tmp_path / "x.json")]) == EXIT_INPUT
    assert not (tmp_path / "x.json").exists()


def test_export_results_only_needs_no_competition_files(tmp_path: Path) -> None:
    inputs = make_inputs(tmp_path)
    out = tmp_path / "site-data.json"
    args = ["export", "--results", str(inputs.results), "--results-only", "--output", str(out)]
    assert main([*args, "--data-dir", str(tmp_path / "absent")]) == EXIT_OK
    data = json.loads(out.read_text(encoding="utf-8"))
    assert list(data["provenance"]["input_sha256"]) == ["dss_results.csv"]
