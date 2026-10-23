"""Input handling and secondary identification."""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

from nfl_dss.ingest import InputError, iter_tracking, load_metadata, read_csv, tracking_files
from nfl_dss.secondary import identify_secondary


def test_missing_tracking_directory_has_actionable_message(tmp_path: Path) -> None:
    with pytest.raises(InputError, match=r"fetch_data\.sh"):
        tracking_files(tmp_path / "nope")


def test_empty_tracking_directory_fails(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="tracking_week_"):
        list(iter_tracking(tmp_path))


def test_missing_file_and_missing_column(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="missing input file"):
        read_csv(tmp_path / "a.csv", ["x"])
    (tmp_path / "a.csv").write_text("x,y\n1,2\n")
    with pytest.raises(InputError, match="missing columns: z"):
        read_csv(tmp_path / "a.csv", ["x", "z"])


def test_metadata_loads_all_four_tables(tiny_data: Path) -> None:
    meta = load_metadata(tiny_data)
    assert len(meta.games) == 1
    assert len(meta.plays) == 3
    assert len(meta.players) == 7
    assert {"pff_role", "nflId"} <= set(meta.scouting.columns)


def test_secondary_keeps_only_coverage_dbs_on_the_defense(tiny_data: Path) -> None:
    meta = load_metadata(tiny_data)
    tracking = next(iter_tracking(tiny_data / "tracking"))
    secondary = identify_secondary(tracking, meta.scouting, meta.players, meta.plays, meta.games)
    assert set(secondary["nflId"]) == {11, 12, 13}
    assert set(secondary["defensiveTeam"]) == {"HOM"}
    assert not secondary["nflId"].isna().any()
    assert len(secondary) == 6 * 3 + 6 * 2 + 6 * 3


def test_offensive_db_is_excluded(tiny_data: Path) -> None:
    meta = load_metadata(tiny_data)
    tracking = next(iter_tracking(tiny_data / "tracking"))
    tracking.loc[tracking["nflId"] == 12, "team"] = "away"
    secondary = identify_secondary(tracking, meta.scouting, meta.players, meta.plays, meta.games)
    assert 12 not in set(secondary["nflId"])


def test_no_loading_at_import() -> None:
    module = importlib.import_module("nfl_dss.pipeline")
    assert not any(isinstance(v, pd.DataFrame) for v in vars(module).values())
