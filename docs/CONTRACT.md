# NFL DSS -> florianhemery.fr data contract (v1.2)

Producer: repo florianhemery/nfl-pocket-collapse, command `uv run dss export`.
Consumer: portfolio-rag `apps/site`, committed snapshot at
`apps/site/src/content/nfl-dss/site-data.json` (copied verbatim, never hand edited).

Rules
- Every number is computed by the pipeline from files. Never typed by hand, never rounded "to look nice".
- A section whose data is absent (null or empty array) is HIDDEN on the site, never filled with placeholder numbers.
- Floats: rates in [0,1], scores in [0,100]. Rounded to 4 decimals by the producer, except p-values (6 decimals, see v1.1).
- Field names are stable; additions bump `schema_version` minor, removals bump major.
- Size budget: the whole file < 300 KB.

```jsonc
{
  "schema_version": "1.2",
  "provenance": {
    "pipeline_commit": "abc1234",          // git sha of the producer
    "generated_at": "2026-10-24T10:00:00Z",
    "dataset": "NFL Big Data Bowl 2023 (2021 season, weeks 1-8)",
    "dataset_license_note": "string",      // what we know about the license, verified wording
    "input_sha256": { "dss_results.csv": "hex", "plays.csv": "hex" },
    "plays_analyzed": 7510,
    "games": 122,
    "teams": 32
  },
  "metric": {
    "formula": "DSS = 100 * (0.40*VA + 0.30*SD + 0.30*OD)",
    "subscores": [
      { "id": "va", "label": "Velocity Alignment", "mean": 65.02, "sd": 15.22,
        "r_completed": 0.005, "p_completed": 0.667767 }
    ]
  },
  "validation": {
    "outcome": "completed",
    "pearson_dss_completed": { "r": -0.0185, "p": 0.109833, "n": 7510 },
    "quintiles": [ { "q": 1, "dss_min": 27.0, "dss_max": 50.1, "completion_rate": 0.623, "n": 1503 } ],
    "confounders": [ { "id": "frames_analyzed", "label": "Time to throw (frames)", "r_completed": -0.1891 } ],
    "stratified": { ... },                 // optional since v1.1, see below
    "model_comparison": null,              // filled since v1.2, see "v1.2 additions" below
    "verdict": "no_signal" | "weak_signal" | "signal",   // derived by a written rule in code
    "verdict_rule": "string"               // the rule, human readable
  },
  "teams": [
    { "team": "SEA", "n": 250, "dss_mean": 57.1, "dss_ci95": [56.0, 58.2],
      "dss_shrunk": 56.8, "completion_rate": 0.61 }
  ],
  "coverages": [
    { "coverage": "Cover-3", "coverage_type": "Zone", "n": 1800, "dss_mean": 58.0, "completion_rate": 0.64 }
  ],
  "replays": []                            // empty until tracking data is available:
  // { "game_id": 2021090900, "play_id": 97, "defensive_team": "DAL", "coverage": "Cover-1",
  //   "pass_result": "I", "dss": 71.2, "fps": 10,
  //   "frames": [ { "frame": 1, "event": "ball_snap" | null, "dss_frame": 70.1 | null,
  //                 "players": [ { "id": 25511, "x": 0.0, "y": 0.0, "side": "off"|"def"|"ball", "db": false } ] } ] }
}
```

## v1.1 additions (2026-10-23)

`schema_version` becomes "1.1". New OPTIONAL key `validation.stratified` (consumers must accept its absence):

```jsonc
"stratified": {
  "by": "coverage_type",
  "strata": [
    { "stratum": "Man", "n": 2160, "r": -0.0708, "p": 0.000997,
      "completion_high_dss": 0.5014, "completion_low_dss": 0.5616 }   // median split within stratum
  ],
  "adjusted": {
    "method": "partial correlation of DSS and completed controlling for frames_analyzed and coverage_type",
    "controls": ["frames_analyzed", "coverage_type"],
    "r": -0.004, "p": 0.731144, "n": 7510
  },
  "reading": "simpson"   // "simpson" | "consistent" : derived by a written rule in code
}
```

p-values: keep full precision to 6 decimals (never 0.0); consumers render p < 0.0001 when below.
Producer text fields (`verdict_rule`, `dataset_license_note`, labels) are English. The French site maps known ids
(`verdict`, `reading`, subscore ids, confounder ids) to its own French copy and renders any other producer text inside `lang="en"`.

`measures.json` (optional companion, same folder): `[{ "id", "label", "value", "unit", "source": "site-data.json#/path" }]`
used only for the "VERIFIE" badge numbers.

## v1.2 additions (2026-10-24)

`schema_version` becomes "1.2". `validation.model_comparison` is filled by `dss export` (protocol:
`docs/decisions/0006-validation-hors-echantillon-protocole.md`). It stays nullable for consumers
that meet an older file. All fields below are required when the object is present:

```jsonc
"model_comparison": {
  "split": "train weeks 1-6 / test weeks 7-8",
  "baseline_features": ["frames_analyzed", "coverageType", "coverage", "down", "yardsToGo", "yardsToEndzone"],
  "n_train": 0, "n_test": 0, "n_test_games": 0,
  "baseline_auc": 0.0, "with_dss_auc": 0.0,
  "delta_auc": 0.0, "delta_auc_ci95": [lo, hi],        // with_dss minus baseline; the confirmatory test
  "baseline_brier": 0.0, "with_dss_brier": 0.0,
  "delta_brier": 0.0, "delta_brier_ci95": [lo, hi],    // with_dss minus baseline; negative is better
  "baseline_logloss": 0.0, "with_dss_logloss": 0.0,
  "subscores_auc": 0.0,                                // baseline plus VA, SD, OD (exploratory)
  "delta_subscores_auc": 0.0,                          // subscores_auc minus baseline_auc
  "yards": { "baseline_rmse": 0.0, "with_dss_rmse": 0.0, "delta_r2": 0.0 },   // exploratory
  "bootstrap": { "unit": "game", "resamples": 2000, "seed": 20261024 },
  "decision_rule": "string",                           // the rule, human readable
  "decision": "no_signal" | "weak_signal" | "signal"   // derived by the written rule in code
}
```

`decision` is not `validation.verdict`. The verdict reads the pooled correlation over all
plays; the decision reads the held-out comparison and is the one the project reports as its
conclusion. The two are never merged. Producer text (`decision_rule`, `split`) is English; the
French site maps `decision` to its own copy.

## Producer notes (this repository)

How `dss export` fills the fields, so that the numbers can be reproduced. All of it is in
`src/nfl_dss/export.py`.

- Quintiles: plays are sorted by DSS, ties broken by `gameId` then `playId`, and cut into five
  groups of equal size (the sizes differ by at most one play). A DSS value shared by two
  neighbouring groups can therefore be both the `dss_max` of one and the `dss_min` of the next.
- `validation.stratified.strata`: one row per `coverageType` value, largest first. A family with
  fewer than 3 plays or with a constant outcome has no correlation and is left out.
  `completion_high_dss` is the completion rate of the plays with DSS at or above the median of
  the family, `completion_low_dss` that of the plays below it.
- `validation.stratified.adjusted`: DSS and the outcome are each regressed (least squares) on an
  intercept, `frames_analyzed` and one indicator per coverage family but the first; the
  residuals are correlated. The p-value uses `n - k - 2` degrees of freedom, `k` being the
  number of control columns (here 3).
- `validation.stratified.reading` follows this written rule (`READING_RULE` in the code). A
  stratum enters the reading when it has at least 500 plays; smaller ones are reported but
  ignored. A correlation counts as an association when `r < 0` and `p < 0.05`. The reading is
  `simpson` when all the strata that enter the reading agree on whether there is an
  association and the pooled correlation says the opposite; it is `consistent` in every other
  case, including when the strata disagree among themselves.
- p-values are rounded to 6 decimals and floored at 0.000001, so a very small p is never
  written as 0.
- `provenance.input_sha256` always lists `dss_results.csv`. It also lists `plays.csv` and
  `games.csv` when the export is cross-checked against them. With `--results-only` it lists
  only `dss_results.csv`; every other field is identical.
- `provenance.pipeline_commit` is the short sha of `HEAD`, with `-dirty` appended when the
  working tree has uncommitted changes (the export file itself is ignored for that test).
- `dataset_license_note` says which data are tracked: the raw competition files are not, a
  row-level extract (`output/dss_results.csv`) is, and the redistribution terms are unverified.

### Held-out comparison (`validation.model_comparison`)

All of it is in `src/nfl_dss/validation.py`, and every choice below was written before any
model was fitted (ADR 0006).

- Split: plays of weeks 1 to 6 train, plays of weeks 7 and 8 test, by the `week` column. Models
  are fitted once; the test set is only used to predict.
- Baseline inputs: `frames_analyzed`, `yardsToGo` and `yardsToEndzone` (standardized with the
  training mean and standard deviation), and one indicator per training level of
  `coverageType`, `coverage` and `down`. A level unseen in training is all zeros in the test.
  `yardsToEndzone` is `100 - yardlineNumber` when `yardlineSide` is the possession team,
  `yardlineNumber` when it is the other team, and 50 at midfield.
- Models: scikit-learn `LogisticRegression` (L2, `C = 1.0`, `lbfgs`, `max_iter = 1000`, nothing
  tuned) for `completed`; `LinearRegression` for `playResult`. The logistic fit is refused if
  it does not converge.
- `delta_auc` and `delta_brier` are computed from unrounded values, then rounded, so they can
  differ by 0.0001 from the difference of the two rounded values next to them.
- Bootstrap: test games are drawn with replacement, all the plays of a drawn game are kept, and
  both models are scored on the same resample. The models are not refitted, so the interval
  covers the choice of test games and not the training sample. Resamples with a single outcome
  class are skipped; `bootstrap.resamples` is the number kept. The interval is the 2.5 and 97.5
  percentiles.
- Decision, applied to the rounded values in the file: `signal` if the lower bound of
  `delta_auc_ci95` is above 0; `weak_signal` if not and `delta_auc` is above 0.005;
  `no_signal` otherwise. This is the only confirmatory test; Brier, log loss, the sub-score
  model and the yards model are exploratory.
- `subscores_auc` uses VA, SD and OD instead of DSS (not both: DSS is a linear combination of
  them). `yards.delta_r2` is the test R2 with DSS minus the test R2 without.
- `output/dss_results.csv` carries the play context the comparison needs: `down`, `yardsToGo`,
  `yardsToEndzone`, `playResult`. With the competition files present, `dss export` checks
  them against `plays.csv`.
