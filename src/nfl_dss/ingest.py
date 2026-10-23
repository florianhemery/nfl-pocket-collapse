"""Read the Big Data Bowl files. Nothing is loaded at import time."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

TRACKING_GLOB = "tracking_week_*.csv"
TRACKING_COLUMNS = [
    "gameId",
    "playId",
    "nflId",
    "frameId",
    "team",
    "x",
    "y",
    "s",
    "o",
    "dir",
    "event",
]
PLAYS_COLUMNS = [
    "gameId",
    "playId",
    "possessionTeam",
    "defensiveTeam",
    "passResult",
    "playResult",
    "pff_passCoverage",
    "pff_passCoverageType",
    "down",
    "yardsToGo",
]
GAMES_COLUMNS = ["gameId", "season", "week", "homeTeamAbbr", "visitorTeamAbbr"]
PLAYERS_COLUMNS = ["nflId", "officialPosition"]
SCOUTING_COLUMNS = ["gameId", "playId", "nflId", "pff_role"]

FETCH_HINT = "run scripts/fetch_data.sh (needs the kaggle CLI), see README.md"


class InputError(RuntimeError):
    """An input file is missing or does not have the expected columns."""


@dataclass(frozen=True)
class Metadata:
    """The four metadata tables of the competition."""

    games: pd.DataFrame
    plays: pd.DataFrame
    players: pd.DataFrame
    scouting: pd.DataFrame


def read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    """Read the given columns of a CSV, failing with a clear message if one is absent."""
    if not path.is_file():
        raise InputError(f"missing input file: {path} ({FETCH_HINT})")
    header = pd.read_csv(path, nrows=0).columns
    missing = [c for c in columns if c not in header]
    if missing:
        raise InputError(f"{path} is missing columns: {', '.join(missing)}")
    return pd.read_csv(path, usecols=columns)


def load_metadata(data_dir: Path) -> Metadata:
    """Load games, plays, players and the PFF scouting table from ``data_dir``."""
    return Metadata(
        games=read_csv(data_dir / "games.csv", GAMES_COLUMNS),
        plays=read_csv(data_dir / "plays.csv", PLAYS_COLUMNS),
        players=read_csv(data_dir / "players.csv", PLAYERS_COLUMNS),
        scouting=read_csv(data_dir / "pffScoutingData.csv", SCOUTING_COLUMNS),
    )


def tracking_files(tracking_dir: Path) -> list[Path]:
    """List the weekly tracking files, or fail with an actionable error."""
    if not tracking_dir.is_dir():
        raise InputError(f"tracking directory not found: {tracking_dir} ({FETCH_HINT})")
    files = sorted(tracking_dir.glob(TRACKING_GLOB))
    if not files:
        raise InputError(f"no {TRACKING_GLOB} file in {tracking_dir} ({FETCH_HINT})")
    return files


def iter_tracking(tracking_dir: Path) -> Iterator[pd.DataFrame]:
    """Yield one tracking table per weekly file, keeping only the columns the metric needs."""
    for path in tracking_files(tracking_dir):
        logger.info("reading %s", path.name)
        yield read_csv(path, TRACKING_COLUMNS)
