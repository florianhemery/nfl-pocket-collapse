"""Identify the defensive backs in coverage on each play."""

from __future__ import annotations

import pandas as pd

#: Official positions that belong to the secondary.
SECONDARY_POSITIONS = frozenset({"CB", "FS", "SS", "DB"})
COVERAGE_ROLE = "Coverage"
PLAY_KEY = ["gameId", "playId"]
PLAYER_KEY = ["gameId", "playId", "nflId"]


def resolve_team_abbr(tracking: pd.DataFrame, games: pd.DataFrame) -> pd.Series:
    """Team abbreviation of every tracking row.

    The tracking ``team`` column is either already an abbreviation or the literal ``home`` /
    ``away``. The latter is mapped through ``games`` so both layouts give the same result.
    """
    sides = games[["gameId", "homeTeamAbbr", "visitorTeamAbbr"]]
    joined = tracking[["gameId", "team"]].merge(sides, on="gameId", how="left")
    team = joined["team"]
    abbr = team.mask(team == "home", joined["homeTeamAbbr"]).mask(
        team == "away", joined["visitorTeamAbbr"]
    )
    abbr.index = tracking.index
    return abbr


def identify_secondary(
    tracking: pd.DataFrame,
    scouting: pd.DataFrame,
    players: pd.DataFrame,
    plays: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """Tracking rows of defensive backs whose PFF role is Coverage, on the defensive team.

    The result has one row per player and frame, plus a ``defensiveTeam`` column.
    """
    tracking = tracking.dropna(subset=["nflId"]).astype({"nflId": "int64"})
    db_ids = players.loc[players["officialPosition"].isin(SECONDARY_POSITIONS), "nflId"]
    coverage = scouting.loc[
        (scouting["pff_role"] == COVERAGE_ROLE) & scouting["nflId"].isin(db_ids), PLAYER_KEY
    ].drop_duplicates()
    merged = tracking.merge(coverage, on=PLAYER_KEY, how="inner")
    merged = merged.merge(plays[[*PLAY_KEY, "defensiveTeam"]], on=PLAY_KEY, how="inner")
    keep = resolve_team_abbr(merged, games) == merged["defensiveTeam"]
    return merged.loc[keep].reset_index(drop=True)
