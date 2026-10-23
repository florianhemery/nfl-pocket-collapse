"""Command line entry point: ``dss build`` and ``dss export``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from nfl_dss.export import ExportError, ExportInputs, build_site_data, git_commit, write_site_data
from nfl_dss.ingest import InputError
from nfl_dss.pipeline import build_results, write_results

logger = logging.getLogger("nfl_dss")

EXIT_OK = 0
EXIT_INPUT = 2
REPO_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dss", description="Defensive Sync Score pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="full rebuild of output/dss_results.csv from tracking")
    build.add_argument("--data-dir", type=Path, default=Path("data"))
    build.add_argument("--tracking-dir", type=Path, default=None)
    build.add_argument("--output", type=Path, default=Path("output/dss_results.csv"))

    export = sub.add_parser("export", help="write exports/site-data.json from the results CSV")
    export.add_argument("--results", type=Path, default=Path("output/dss_results.csv"))
    export.add_argument("--data-dir", type=Path, default=Path("data"))
    export.add_argument("--output", type=Path, default=Path("exports/site-data.json"))
    export.add_argument(
        "--results-only",
        action="store_true",
        help="compute from the results CSV alone, without data/plays.csv and data/games.csv",
    )
    return parser


def run_build(args: argparse.Namespace) -> None:
    data_dir: Path = args.data_dir
    tracking_dir: Path = args.tracking_dir or data_dir / "tracking"
    results = build_results(data_dir, tracking_dir)
    write_results(results, args.output)
    logger.info("wrote %s (%d plays)", args.output, len(results))


def run_export(args: argparse.Namespace) -> None:
    data_dir: Path = args.data_dir
    if args.results_only:
        inputs = ExportInputs(results=args.results)
    else:
        inputs = ExportInputs(
            results=args.results, plays=data_dir / "plays.csv", games=data_dir / "games.csv"
        )
    data = build_site_data(inputs, commit=git_commit(REPO_ROOT))
    write_site_data(data, args.output)
    logger.info("wrote %s (%d plays)", args.output, data["provenance"]["plays_analyzed"])


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build":
            run_build(args)
        else:
            run_export(args)
    except (InputError, ExportError) as error:
        logger.error("error: %s", error)
        return EXIT_INPUT
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
