# Defensive Sync Score (DSS)

A new NFL analytics metric that quantifies how synchronized a defensive secondary moves as a unit, using frame-by-frame player tracking data from the NFL Next Gen Stats Big Data Bowl dataset (122 games, 8,557 plays, NFL 2021 season).

## What it reveals

The DSS measures defensive backfield coordination through three sub-scores computed across post-snap frames (snap → pass release):

| Sub-score | What it measures | How |
|---|---|---|
| **Velocity Alignment (VA, 40%)** | DBs moving in the same direction at the same time | Cosine similarity of velocity vectors vs. group mean |
| **Spacing Discipline (SD, 30%)** | DBs maintaining their formation | Inverse of pairwise distance coefficient of variation |
| **Orientation Divergence (OD, 30%)** | Each DB tracking his own assignment | *Inverted* circular variance of body orientation |

**DSS = 100 × (0.40·VA + 0.30·SD + 0.30·OD)** — scale 0-100. Higher = better-coordinated secondary.

### Key finding: orientation divergence is the counterintuitive insight

When all DBs look the same direction (high coherence), completions go *up*. Why? Because a secondary all staring at the QB is *not* in coverage — they're reading the quarterback's eyes. Truly coordinated coverage has each DB tracking *his own* receiver, not everyone staring at the same focal point. The DSS inverts this sub-score accordingly.

## Results (122 games, 7,510 plays)

- **DSS range:** 27 – 82 / 100
- **Best secondary:** SEA (59.0) — worst: LAC (51.5)
- **Man coverage:** top-quartile DSS defenses allowed **50.1%** completion rate vs **56.2%** for bottom-quartile (+6.1 pp)
- **Zone coverage:** 63.5% vs 67.2% (+3.7 pp)
- **Cover-0/Cover-1 DSS ~44-47** — full man, hardest to synchronize; Prevent/Quarters ~63 — simple formations

## Who would use it

- **Defensive coordinators** identifying coverage breakdowns and communication failures, especially in Cover-1/Cover-0 where DB sync is hardest to maintain
- **Scouts** evaluating safeties who "quarterback" the secondary (high VA leaders = the players pulling the group into alignment)
- **Commentators** adding real-time context: *"The Seahawks secondary is running at 59 DSS today — their zone rotations are perfectly timed"*

## Data

NFL Big Data Bowl tracking data: frame-by-frame `x, y, s` (speed), `o` (body orientation), `dir` (direction of motion) for every player on every play.

Source: [nfl-big-data-bowl-regional-event-data](https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data)

## Structure

```
├── data/                       # Raw CSVs (gitignored — download from source above)
│   ├── games.csv, plays.csv, players.csv, pffScoutingData.csv
│   └── tracking/               # 122 per-game tracking files
├── src/
│   ├── dss.py                  # Metric computation (VA, SD, OD, DSS)
│   ├── dss_visualization.py    # Animations, team ranking, scatter, heatmap
│   └── main.py                 # Full pipeline (load → compute → visualize → export)
└── output/                     # Generated charts & animations (gitignored)
```

## How to run

```bash
git clone https://github.com/florianhemery/nfl-pocket-collapse
cd nfl-pocket-collapse
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy scipy matplotlib plotly

# Download data from source repo into data/ and data/tracking/
python src/main.py
```

Outputs to `output/`: team ranking chart, DSS vs completion scatter, coverage heatmap, GIF animation of best-sync play.
