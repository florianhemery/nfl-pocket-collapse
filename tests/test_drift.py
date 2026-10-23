"""Drift guards: the committed export must be what the pipeline produces from tracked inputs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from nfl_dss.export import ExportInputs, build_site_data, sha256_file

ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "exports" / "site-data.json"
RESULTS = ROOT / "output" / "dss_results.csv"
DATA = ROOT / "data"
VOLATILE = ("generated_at", "pipeline_commit")


def stable(data: dict[str, Any]) -> dict[str, Any]:
    """Drop what legitimately changes between two runs: time, commit, extra input hashes."""
    provenance = {k: v for k, v in data["provenance"].items() if k not in VOLATILE}
    return {**data, "provenance": provenance}


def committed_export() -> dict[str, Any]:
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


def fresh_export(inputs: ExportInputs) -> dict[str, Any]:
    return build_site_data(inputs, commit="x", generated_at=datetime(2026, 1, 1, tzinfo=UTC))


def test_committed_export_is_reproduced_from_the_tracked_results() -> None:
    """Runs in CI: it needs only ``output/dss_results.csv``, which is tracked.

    The committed export was made with the cross-checked path, so its ``input_sha256`` also
    lists ``plays.csv`` and ``games.csv``; only the hash of the results file can be compared.
    """
    fresh, committed = stable(fresh_export(ExportInputs(RESULTS))), stable(committed_export())
    committed_hashes = committed["provenance"].pop("input_sha256")
    fresh_hashes = fresh["provenance"].pop("input_sha256")
    assert fresh_hashes["dss_results.csv"] == committed_hashes["dss_results.csv"]
    assert fresh == committed


def test_committed_results_hash_matches_the_file() -> None:
    hashes = committed_export()["provenance"]["input_sha256"]
    assert hashes["dss_results.csv"] == sha256_file(RESULTS)


def test_committed_export_is_reproduced_with_the_competition_files() -> None:
    """Local only: also covers the cross-checks against plays.csv and games.csv."""
    inputs = ExportInputs(RESULTS, DATA / "plays.csv", DATA / "games.csv")
    if inputs.plays is None or not inputs.plays.is_file() or not (DATA / "games.csv").is_file():
        pytest.skip("data/plays.csv and data/games.csv are not available (scripts/fetch_data.sh)")
    assert stable(fresh_export(inputs)) == stable(committed_export())
