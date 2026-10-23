"""From tracking rows of the secondary to one DSS row per play."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from nfl_dss.ingest import iter_tracking, load_metadata
from nfl_dss.metrics import DEFAULT_WEIGHTS, FloatArray, FrameBatch, combine, frame_scores
from nfl_dss.secondary import PLAY_KEY, identify_secondary

logger = logging.getLogger(__name__)

SNAP_EVENT = "ball_snap"
END_EVENT = "pass_forward"
#: A frame needs at least this many defensive backs to be scored.
MIN_DBS_PER_FRAME = 3
#: A play needs at least this many scored frames.
MIN_FRAMES_PER_PLAY = 3
#: Sub-score used for a play when none of its frames could be scored.
FALLBACK_SUBSCORE = 0.5

FRAME_KEY = [*PLAY_KEY, "frameId"]
RESULT_COLUMNS = [
    "dss",
    "va",
    "sd",
    "od",
    "num_dbs",
    "frames_analyzed",
    "gameId",
    "playId",
    "defensiveTeam",
    "offensiveTeam",
    "passResult",
    "playResult",
    "coverage",
    "coverageType",
    "down",
    "yardsToGo",
    "completed",
    "sacked",
]


def _event_frames(secondary: pd.DataFrame, event: str, name: str) -> pd.Series:
    """First frame at which ``event`` occurs, per play."""
    rows = secondary.loc[secondary["event"] == event]
    return rows.groupby(PLAY_KEY)["frameId"].min().rename(name)


def select_frames(secondary: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Keep the rows between snap and pass release on frames with enough defensive backs.

    Returns the rows and the number of backs on the field at the snap, per play. Plays with
    no snap, no pass release, or fewer than ``MIN_FRAMES_PER_PLAY`` usable frames are dropped.
    """
    rows = secondary.drop_duplicates([*FRAME_KEY, "nflId"])
    bounds = pd.concat(
        [_event_frames(rows, SNAP_EVENT, "snap"), _event_frames(rows, END_EVENT, "end")],
        axis=1,
        join="inner",
    )
    bounds = bounds.loc[bounds["end"] > bounds["snap"]]
    rows = rows.merge(bounds.reset_index(), on=PLAY_KEY, how="inner")
    rows = rows.loc[(rows["frameId"] >= rows["snap"]) & (rows["frameId"] <= rows["end"])]
    rows = rows.assign(n_dbs=rows.groupby(FRAME_KEY)["nflId"].transform("size"))
    at_snap = rows.loc[rows["frameId"] == rows["snap"]].groupby(PLAY_KEY)["n_dbs"].first()
    rows = rows.loc[rows["n_dbs"] >= MIN_DBS_PER_FRAME]
    usable = rows.groupby(PLAY_KEY)["frameId"].nunique()
    keep = usable.index[usable >= MIN_FRAMES_PER_PLAY]
    rows = rows.set_index(PLAY_KEY).loc[keep].reset_index()
    return rows, at_snap.rename("num_dbs")


def _pad(
    values: pd.Series, frame_id: np.ndarray, slot: np.ndarray, shape: tuple[int, int]
) -> FloatArray:
    out: FloatArray = np.full(shape, np.nan, dtype=np.float64)
    out[frame_id, slot] = values.to_numpy(dtype=np.float64)
    return out


def frame_table(rows: pd.DataFrame) -> pd.DataFrame:
    """Score every frame of ``rows`` (output of ``select_frames``).

    Returns one row per frame with its play key and ``va``, ``sd``, ``od`` in [0, 1].
    """
    ordered = rows.sort_values([*FRAME_KEY, "nflId"], kind="stable").reset_index(drop=True)
    frame_id = ordered.groupby(FRAME_KEY, sort=False).ngroup().to_numpy()
    slot = ordered.groupby(FRAME_KEY, sort=False).cumcount().to_numpy()
    shape = (int(frame_id.max()) + 1, int(slot.max()) + 1)
    mask = np.zeros(shape, dtype=np.bool_)
    mask[frame_id, slot] = True
    scores = frame_scores(
        FrameBatch(
            x=_pad(ordered["x"], frame_id, slot, shape),
            y=_pad(ordered["y"], frame_id, slot, shape),
            s=_pad(ordered["s"], frame_id, slot, shape),
            direction_deg=_pad(ordered["dir"], frame_id, slot, shape),
            o_deg=_pad(ordered["o"], frame_id, slot, shape),
            mask=mask,
        )
    )
    keys = ordered.drop_duplicates(FRAME_KEY)[FRAME_KEY].reset_index(drop=True)
    return keys.assign(va=scores.va, sd=scores.sd, od=scores.od)


def aggregate_plays(
    frames: pd.DataFrame,
    num_dbs: pd.Series,
    weights: tuple[float, float, float] = DEFAULT_WEIGHTS,
    decimals: int | None = 2,
) -> pd.DataFrame:
    """Average frame scores per play and combine them into the DSS.

    Sub-scores are averaged over the frames where they are defined. A play needs at least two
    frames with a defined VA. SD and OD fall back to 0.5 when undefined for the whole play.
    Scores are on the 0-100 scale, rounded to ``decimals`` (``None`` keeps full precision).
    """
    grouped = frames.groupby(PLAY_KEY)
    mean = grouped[["va", "sd", "od"]].mean()
    mean["frames_analyzed"] = grouped["va"].count()
    mean = mean.loc[mean["frames_analyzed"] >= 2].copy()
    for name in ("sd", "od"):
        mean[name] = mean[name].fillna(FALLBACK_SUBSCORE)
    va, sd, od = (mean[c].to_numpy(dtype=np.float64) for c in ("va", "sd", "od"))
    out = pd.DataFrame(
        {
            "dss": combine(va, sd, od, weights),
            "va": 100.0 * va,
            "sd": 100.0 * sd,
            "od": 100.0 * od,
        },
        index=mean.index,
    )
    if decimals is not None:
        out = out.round(decimals)
    out["num_dbs"] = num_dbs.reindex(out.index).fillna(0).astype("int64")
    out["frames_analyzed"] = mean["frames_analyzed"].astype("int64")
    return out.reset_index()


def score_plays(
    secondary: pd.DataFrame,
    weights: tuple[float, float, float] = DEFAULT_WEIGHTS,
    decimals: int | None = 2,
) -> pd.DataFrame:
    """DSS, sub-scores, ``num_dbs`` and ``frames_analyzed`` for every scorable play."""
    rows, num_dbs = select_frames(secondary)
    if rows.empty:
        return pd.DataFrame(columns=[*PLAY_KEY, "dss", "va", "sd", "od", "num_dbs"])
    return aggregate_plays(frame_table(rows), num_dbs, weights, decimals)


def attach_play_metadata(scores: pd.DataFrame, plays: pd.DataFrame) -> pd.DataFrame:
    """Add team, result, coverage and situation columns, in the layout of ``RESULT_COLUMNS``."""
    meta = plays.rename(
        columns={
            "possessionTeam": "offensiveTeam",
            "pff_passCoverage": "coverage",
            "pff_passCoverageType": "coverageType",
        }
    )
    cols = [
        *PLAY_KEY,
        "defensiveTeam",
        "offensiveTeam",
        "passResult",
        "playResult",
        "coverage",
        "coverageType",
        "down",
        "yardsToGo",
    ]
    merged = scores.merge(meta[cols], on=PLAY_KEY, how="inner")
    merged["completed"] = (merged["passResult"] == "C").astype("int64")
    merged["sacked"] = (merged["passResult"] == "S").astype("int64")
    return merged[RESULT_COLUMNS].sort_values(PLAY_KEY).reset_index(drop=True)


def build_results(data_dir: Path, tracking_dir: Path) -> pd.DataFrame:
    """Full rebuild: weekly tracking files plus metadata to the per-play DSS table."""
    meta = load_metadata(data_dir)
    parts: list[pd.DataFrame] = []
    for tracking in iter_tracking(tracking_dir):
        secondary = identify_secondary(
            tracking, meta.scouting, meta.players, meta.plays, meta.games
        )
        parts.append(score_plays(secondary))
    scores = pd.concat(parts, ignore_index=True)
    results = attach_play_metadata(scores, meta.plays)
    logger.info("scored %d plays", len(results))
    return results


def write_results(results: pd.DataFrame, path: Path) -> None:
    """Write the per-play table as CSV, creating the parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(path, index=False)
