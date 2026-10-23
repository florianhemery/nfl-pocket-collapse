# Defensive Sync Score (DSS)

A tracking-data metric for NFL secondaries, built from the NFL Big Data Bowl 2023 files
(2021 season, weeks 1 to 8). The question: does a secondary that moves as a coordinated unit
allow fewer completions?

The short answer from the data in this repository: pooled over all plays, the metric shows no
linear association with pass completion. That null result is misleading on its own. Inside each
coverage family the association is real and has the expected sign, and it disappears once time
to throw and coverage family are controlled. The metric has not been shown to carry
information about completions beyond those two variables. Every number on this page is read
from [`exports/site-data.json`](exports/site-data.json), which `uv run dss export` regenerates
from the precomputed results.

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

Outcome: 1 if the pass was completed, else 0. This section is the project's main finding: a
null pooled result, a real within-group association, and its disappearance under control. It
is a worked example of confounding, and the reason the DSS is not presented as a validated
metric.

### 1. Pooled over all plays: nothing

For the DSS itself: r = -0.0185, p = 0.109833, n = 7510. By DSS quintile (lowest to highest)
the completion rate is 0.6232, 0.6225, 0.5939, 0.5939 and 0.6198, with 1502 plays each, which
is not monotonic. The written verdict rule in `src/nfl_dss/export.py` looks at this pooled
correlation only and returns `no_signal`.

### 2. Inside each coverage family: a real association

| Coverage family | plays | r | p | completion, DSS at or above median | completion, DSS below median |
|---|---|---|---|---|---|
| Man | 2160 | -0.0708 | 0.000997 | 0.5014 | 0.5616 |
| Zone | 4943 | -0.0477 | 0.000793 | 0.635 | 0.6719 |
| Other | 407 | -0.0741 | 0.135459 | 0.4755 | 0.5468 |

In man and in zone coverage a higher DSS goes with fewer completions, and the p-values are
small. The median splits give the figures quoted by the first version of this README (about
50 versus 56 percent in man coverage, 63.5 versus 67 in zone): the export reproduces them. They
are not wrong. They are confounded. The pooled correlation is null because coverage family
moves both variables: zone plays have a higher DSS and a higher completion rate than man
plays (Cover-3: DSS 57.1389, completion 0.6582; Cover-1: DSS 53.5144, completion 0.5299),
which cancels the within-family slope. The export labels this pattern `simpson`, by a rule
written in the code (see `docs/CONTRACT.md`).

### 3. After control: nothing again

Time to throw, measured as the number of frames between snap and release, correlates with
completion at r = -0.1891, far more than the DSS does, and it differs between coverage
families. The partial correlation of DSS and completion, controlling for time to throw and
coverage family, is r = -0.004, p = 0.731144, n = 7510. The within-family association is
therefore not distinguishable from zero once those two variables are accounted for. The data do
not say which of the two does the work; telling them apart needs the held-out model comparison
below.

### Sub-scores

Pooled correlation with completion, not adjusted for the confounders above:

| | mean | sd | r | p |
|---|---|---|---|---|
| VA | 65.0163 | 15.2238 | 0.005 | 0.667767 |
| SD | 71.0002 | 2.9968 | 0.0271 | 0.019032 |
| OD | 29.84 | 14.3135 | -0.0478 | 0.000034 |

OD has the strongest pooled association and the expected sign. SD points the other way
(a more disciplined spacing goes with slightly more completions). VA shows nothing.

### Teams

Per-team means come with bootstrap 95% intervals (2000 resamples, fixed seed) 1.74 to 2.50
points wide, and with an empirical-Bayes shrunk mean. DSS differs between coverage schemes
(for example 47.77 in Cover-0 and 59.66 in Quarters), and no adjustment for the mix of schemes
a team plays is made, so a team's mean is not a clean measure of its coordination.

### Not done yet

A held-out model comparison (does DSS improve a baseline that already knows time to throw and
coverage?). It is tracked in issue #5 and the export field `model_comparison` is `null` until
then. Until it exists, the claim supported by this repository is limited to what is above: no
pooled association, a within-family association that does not survive the two controls.

## Install and use

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync --frozen
uv run dss export      # writes exports/site-data.json from output/dss_results.csv
```

`output/dss_results.csv` is the precomputed artifact, one row per scored play, kept in the
repository. By default `export` also reads `data/plays.csv` and `data/games.csv` (see Data) to
cross-check it. `uv run dss export --results-only` computes the same statistics from the
tracked results file alone; this is what CI does to check that `exports/site-data.json` is
still what the code produces.

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

The raw Kaggle files are not stored in this repository (see
[ADR 0005](docs/decisions/0005-donnees-kaggle-hors-depot.md)). A row-level extract is:
`output/dss_results.csv` has one row per analyzed play with the scores, the game and play ids,
the season and week, the defensive team, the PFF coverage labels (`coverage`, `coverageType`)
and the completion flag. Other competition columns (pass and play results, down, yardage,
offensive team) are not kept. The terms of the 2023 edition were not verified, and recent
editions are reported to use CC BY-NC 4.0, so whether redistributing that extract is permitted
is unverified. Check the
[competition rules](https://www.kaggle.com/competitions/nfl-big-data-bowl-2023/rules) before
reusing it. `data/checksums.sha256` holds the sha256 of the four metadata files.

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
