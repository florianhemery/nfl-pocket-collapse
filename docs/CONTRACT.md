# NFL DSS -> florianhemery.fr data contract (v1)

Producer: repo florianhemery/nfl-pocket-collapse, command `uv run dss export`.
Consumer: portfolio-rag `apps/site`, committed snapshot at
`apps/site/src/content/nfl-dss/site-data.json` (copied verbatim, never hand edited).

Rules
- Every number is computed by the pipeline from files. Never typed by hand, never rounded "to look nice".
- A section whose data is absent (null or empty array) is HIDDEN on the site, never filled with placeholder numbers.
- Floats: rates in [0,1], scores in [0,100]. Rounded to 4 decimals by the producer.
- Field names are stable; additions bump `schema_version` minor, removals bump major.
- Size budget: the whole file < 300 KB.

```jsonc
{
  "schema_version": "1.0",
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
        "r_completed": 0.005, "p_completed": 0.6678 }
    ]
  },
  "validation": {
    "outcome": "completed",
    "pearson_dss_completed": { "r": -0.0185, "p": 0.1098, "n": 7510 },
    "quintiles": [ { "q": 1, "dss_min": 27.0, "dss_max": 50.1, "completion_rate": 0.623, "n": 1503 } ],
    "confounders": [ { "id": "frames_analyzed", "label": "Time to throw (frames)", "r_completed": -0.1891 } ],
    "model_comparison": null,              // filled by phase 2:
    // { "split": "train weeks 1-6 / test weeks 7-8", "baseline_features": [...],
    //   "baseline_auc": 0.0, "with_dss_auc": 0.0, "delta_auc": 0.0, "delta_auc_ci95": [lo, hi],
    //   "baseline_brier": 0.0, "with_dss_brier": 0.0 }
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

`measures.json` (optional companion, same folder): `[{ "id", "label", "value", "unit", "source": "site-data.json#/path" }]`
used only for the "VERIFIE" badge numbers.
