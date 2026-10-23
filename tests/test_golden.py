"""End-to-end golden test on a tiny synthetic play with hand-derived expected values.

Play 1 of tests/fixtures/tiny has three defensive backs in coverage (the linebacker is also
scouted as Coverage but is not a DB). The scored window is frames 2 to 5:

* frames 2 and 3 (config A): all move at 5 yd/s in direction 0, positions (0,0) (3,0) (0,4),
  orientations 0, 90, 180 degrees.
    VA = 1. Distances 3, 4, 5: mean 4, population sd sqrt(2/3), so SD = 1 / (1 + sqrt(2/3) / 4).
    Orientation resultant R = |(0, 1/3)| = 1/3, so OD = 2/3.
* frames 4 and 5 (config B): speed 5, directions 0, 90, 180, positions (0,0) (1,0) (2,0),
  all orientations 0.
    Mean velocity (0, 5/3); only the 90 degree player is aligned: VA = 1/3.
    Distances 1, 1, 2: mean 4/3, sd sqrt(2)/3, so SD = 1 / (1 + (sqrt(2)/3) / (4/3)).
    All orientations equal: R = 1, OD = 0.

Frames 1 and 6 hold garbage values and must not count. Play 2 has only two DBs and play 3 has
no pass release: both must be dropped.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from nfl_dss.pipeline import RESULT_COLUMNS, build_results

SD_A = 1 / (1 + math.sqrt(2 / 3) / 4)
SD_B = 1 / (1 + (math.sqrt(2) / 3) / (4 / 3))
VA = (1 + 1 / 3) / 2
SD = (SD_A + SD_B) / 2
OD = (2 / 3 + 0) / 2
DSS = 100 * (0.40 * VA + 0.30 * SD + 0.30 * OD)


def test_tiny_play_matches_hand_computation(tiny_data: Path) -> None:
    results = build_results(tiny_data, tiny_data / "tracking")
    assert list(results.columns) == RESULT_COLUMNS
    assert len(results) == 1
    row = results.iloc[0]
    assert row["dss"] == pytest.approx(DSS, abs=0.006)
    assert row["va"] == pytest.approx(100 * VA, abs=0.006)
    assert row["sd"] == pytest.approx(100 * SD, abs=0.006)
    assert row["od"] == pytest.approx(100 * OD, abs=0.006)
    assert row["num_dbs"] == 3
    assert row["frames_analyzed"] == 4
    assert (row["gameId"], row["playId"]) == (1, 1)
    assert row["defensiveTeam"] == "HOM"
    assert (row["season"], row["week"]) == (2021, 1)
    assert (row["coverage"], row["coverageType"]) == ("Cover-3", "Zone")
    assert row["completed"] == 1
    raw = {"offensiveTeam", "passResult", "playResult", "down", "yardsToGo", "sacked"}
    assert raw.isdisjoint(results.columns)


def test_team_abbreviations_give_the_same_result(tiny_data: Path) -> None:
    path = tiny_data / "tracking" / "tracking_week_1.csv"
    tracking = pd.read_csv(path)
    tracking["team"] = tracking["team"].replace({"home": "HOM", "away": "VIS"})
    tracking.to_csv(path, index=False)
    results = build_results(tiny_data, tiny_data / "tracking")
    assert results["dss"].iloc[0] == pytest.approx(DSS, abs=0.006)
