# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `nfl_dss` package (uv, Python 3.12, src layout) with `ingest`, `secondary`, `metrics`,
  `pipeline`, `export` and `cli` modules, and the `dss` command (`dss build`, `dss export`).
- Vectorized DSS sub-scores, equal to the original loop-based code within 1e-9 on random
  frames (OD is now clipped to [0, 1]). The equivalence test covers the metric only
  (`tests/legacy_dss.py`). The old `identify_secondary` and `compute_dss_all_plays` are not in
  the oracle: the team filter, the home/away mapping and the attachment of play metadata are
  covered by the golden test on one synthetic play, not by an old-versus-new comparison.
- `exports/site-data.json`, `docs/CONTRACT.md` and `docs/site-data.schema.json` (schema 1.1):
  export with provenance, subscore statistics, quintiles, a confounder, a written verdict rule,
  per-team bootstrap intervals and shrunk means, and per-coverage figures.
- `validation.stratified` in the export: DSS/completion correlation and median-split completion
  rates inside each coverage family, a partial correlation controlling time to throw and
  coverage family, and a `simpson` or `consistent` reading from a written rule. p-values keep
  six decimals.
- `dss export --results-only`: the export computed from `output/dss_results.csv` alone. CI uses
  it to check that `exports/site-data.json` is what the code produces.
- Tests: Hypothesis property tests, golden test on a tiny synthetic play, old-versus-new
  equivalence, export and CLI tests, pinned values for the bootstrap interval and the
  shrinkage. Coverage threshold 80 percent.
- CI workflow (ruff, pyright strict, pytest, gitleaks, pip-audit), Renovate configuration,
  AGENTS.md, `docs/QUALITY.md`, ADRs 0001 to 0005.
- MIT `LICENSE`, `scripts/fetch_data.sh` and `data/checksums.sha256`.

- Held-out validation (issue #5, [ADR 0006](docs/decisions/0006-validation-hors-echantillon-protocole.md)),
  protocol written before the code: logistic regression on completion, train weeks 1-6 and test
  weeks 7-8, baseline (time to throw, coverage family and coverage, down, yards to go, yards to
  the end zone) against baseline plus DSS, AUC, Brier and log loss, paired bootstrap over test
  games (2000 resamples, fixed seed) and a written decision rule. `nfl_dss.validation` fills
  `validation.model_comparison`; the README reports the result as is (`no_signal`).
- Data contract and schema 1.2: `validation.model_comparison` gets `n_train`, `n_test`,
  `n_test_games`, `delta_brier` and its interval, log loss, `subscores_auc`, a `yards` block,
  `bootstrap`, `decision_rule` and `decision`.
- `dss enrich`: adds the play context columns to an existing `output/dss_results.csv` from
  `data/plays.csv`, without tracking data.
- `scikit-learn` 1.9.1 as a pinned dependency.

### Changed
- `output/dss_results.csv` gains four play-level columns, `down`, `yardsToGo`, `yardsToEndzone`
  (derived from the yard line) and `playResult`, so that the held-out comparison and the drift
  guard run in CI without the Kaggle files. ADR 0005, the license note of the export and both
  READMEs list exactly which row-level fields are tracked; the redistribution terms stay
  unverified. The export now also checks these columns against `plays.csv` when it is present.
- README.md rewritten, README.fr.md added in French. Figures are read from the export. The
  earlier README quoted larger effects within man and zone coverage. The export reproduces
  them (median split: 0.5014 versus 0.5616 in man, 0.635 versus 0.6719 in zone). The pooled
  correlation is null (r = -0.0185), the within-family association is real, and it is not
  distinguishable from zero once time to throw and coverage family are controlled
  (partial r = -0.004, p = 0.731144). The README now says so.
- Kaggle CSV files are no longer tracked (they stay on disk, ignored).
- `output/dss_results.csv` keeps only what the export needs (scores, ids, season, week,
  defensive team, PFF coverage labels, completion flag). The pass and play results, down,
  yardage, offensive team and sack flag columns were dropped. The file is still a row-level
  extract of competition data, and the license note says so; the redistribution terms are
  unverified.
- `scripts/fetch_data.sh` verifies checksums before moving files into `data/`, and falls back to
  `shasum` when `sha256sum` is missing. The 8 tracking files have no checksum.
- The workflow checks out without persisted credentials, has a job timeout, and runs pip-audit
  from the locked dev group.
- `pipeline_commit` in the export gets a `-dirty` suffix for a modified working tree.

### Removed
- The five Dash apps, the visualization and player analysis modules, the notebook and the
  screenshots of the removed interface.
- All AI provider code, including the module-level API key holder (ADR 0003).
- Seven root documents that only described fixes to the removed code.
