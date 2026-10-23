# Defensive Sync Score (DSS)

A tracking-data metric for NFL secondaries, built from the NFL Big Data Bowl 2023 files
(2021 season, weeks 1 to 8). The question: does a secondary that moves as a coordinated unit
allow fewer completions?

The short answer from the data in this repository is that the metric, as defined, shows no
detectable linear association with pass completion. Details and limits are below. Every number
on this page is read from [`exports/site-data.json`](exports/site-data.json), which
`uv run dss export` regenerates from the precomputed results.

## The metric

For every pass play, frames from the snap to the pass release are scored on the defensive backs
who are in coverage (PFF role `Coverage`, official position CB, FS, SS or DB, on the defensive
team). Three sub-scores in [0, 1] are averaged over the frames:

| Sub-score | Definition |
|---|---|
| VA, velocity alignment | mean cosine similarity between each moving player's velocity and the group mean velocity, clamped to [0, 1] |
| SD, spacing discipline | `1 / (1 + cv)`, with `cv` the coefficient of variation of the pairwise distances |
| OD, orientation divergence | `1 - R`, with `R` the resultant length of the body orientations |

`DSS = 100 * (0.40*VA + 0.30*SD + 0.30*OD)`. The weights are fixed by hand, not fitted.
A play needs at least 3 backs on at least 3 frames.

## Results (7510 plays, 122 games, 32 teams)

Correlation with completion (1 if the pass was completed, else 0). For the DSS itself:
r = -0.0185, p = 0.1098, n = 7510. For the sub-scores:

| | mean | sd | r | p |
|---|---|---|---|---|
| VA | 65.0163 | 15.2238 | 0.005 | 0.6678 |
| SD | 71.0002 | 2.9968 | 0.0271 | 0.019 |
| OD | 29.84 | 14.3135 | -0.0478 | 0.0 (rounded to 4 decimals) |

By DSS quintile (lowest to highest), the completion rate is 0.6232, 0.6225, 0.5939, 0.5939 and
0.6198, with 1502 plays each. The pattern is not monotonic. The written verdict rule in
`src/nfl_dss/export.py` returns `no_signal`.

The number of frames between snap and release (time to throw) correlates with completion at
r = -0.1891, far more than DSS does. DSS also differs between coverage schemes (for example
47.77 in Cover-0 and 59.66 in Quarters), so team differences partly reflect the mix of
schemes. Per-team means come with bootstrap 95% intervals (2000 resamples, fixed seed) 1.74 to
2.50 points wide, and with an empirical-Bayes shrunk mean.

What is not done yet: a held-out model comparison (does DSS improve a baseline that already
knows time to throw and coverage?). It is tracked in issue #5 and the export field
`model_comparison` is `null` until then. An earlier version of this README quoted larger
effects (for example in man coverage); the export does not reproduce them, so they are not
repeated here.

## Install and use

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync --frozen
uv run dss export      # writes exports/site-data.json from output/dss_results.csv
```

`export` needs `data/plays.csv` and `data/games.csv` (see Data). `output/dss_results.csv` is the
precomputed artifact, one row per scored play, kept in the repository.

A full rebuild from tracking data:

```bash
bash scripts/fetch_data.sh   # needs the kaggle CLI and accepted competition rules
uv run dss build             # writes output/dss_results.csv
```

The full rebuild was not run when the package was written: the tracking files were not
available locally. The pipeline is covered by synthetic fixtures and by an equivalence test
against the original loop-based implementation (issue #6 tracks the replay feature that also
needs tracking data).

## Data

The Kaggle files are not stored in this repository (see
[ADR 0005](docs/decisions/0005-donnees-kaggle-hors-depot.md)). The terms of the 2023 edition
were not verified; recent editions are reported to use CC BY-NC 4.0. Check the
[competition rules](https://www.kaggle.com/competitions/nfl-big-data-bowl-2023/rules) before
reusing the data. `data/checksums.sha256` holds the sha256 of the four metadata files.

## Development

```bash
uv run ruff check && uv run ruff format --check
uv run pyright          # strict
uv run pytest           # coverage threshold 80 percent
```

See [AGENTS.md](AGENTS.md), [docs/QUALITY.md](docs/QUALITY.md), the decisions in
[docs/decisions](docs/decisions) and the data contract in [docs/CONTRACT.md](docs/CONTRACT.md).

## License

MIT, see [LICENSE](LICENSE). The code is MIT; the data keeps its own terms.
