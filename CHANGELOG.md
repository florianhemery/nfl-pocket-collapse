# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `nfl_dss` package (uv, Python 3.12, src layout) with `ingest`, `secondary`, `metrics`,
  `pipeline`, `export` and `cli` modules, and the `dss` command (`dss build`, `dss export`).
- Vectorized DSS sub-scores, equal to the original loop-based code within 1e-9 on random
  frames (OD is now clipped to [0, 1]).
- `exports/site-data.json`, `docs/CONTRACT.md` and `docs/site-data.schema.json`: descriptive
  export with provenance, subscore statistics, quintiles, a confounder, a written verdict rule,
  per-team bootstrap intervals and shrunk means, and per-coverage figures.
- Tests: Hypothesis property tests, golden test on a tiny synthetic play, old-versus-new
  equivalence, export and CLI tests. Coverage threshold 80 percent.
- CI workflow (ruff, pyright strict, pytest, gitleaks, pip-audit), Renovate configuration,
  AGENTS.md, `docs/QUALITY.md`, ADRs 0001 to 0005.
- MIT `LICENSE`, `scripts/fetch_data.sh` and `data/checksums.sha256`.

### Changed
- README.md rewritten, README.fr.md added in French. Figures are read from the export.
- Kaggle CSV files are no longer tracked (they stay on disk, ignored).

### Removed
- The five Dash apps, the visualization and player analysis modules, the notebook and the
  screenshots of the removed interface.
- All AI provider code, including the module-level API key holder (ADR 0003).
- Seven root documents that only described fixes to the removed code.
