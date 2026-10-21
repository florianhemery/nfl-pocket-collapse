# Defensive Sync Score (DSS)

**What we built:** A new NFL metric — the Defensive Sync Score (DSS) — that quantifies how synchronized a defensive secondary moves as a unit on passing plays, using frame-by-frame player tracking data (122 games, 7,510 plays, NFL 2021 season).

**What it reveals:** DSS combines three sub-scores computed post-snap: Velocity Alignment (do DBs move together?), Spacing Discipline (do they hold their formation?), and Orientation Divergence (is each DB tracking his own assignment?). Key finding: defenses with high DSS allow **6.1 fewer completion percentage points in man coverage** — the strongest signal is in Cover-0/Cover-1, where secondary sync is hardest to maintain (DSS ~44) and communication breakdowns are most costly.

**Who uses it:** Defensive coordinators identifying coverage breakdowns before film review; scouts evaluating safeties who "quarterback" the secondary; commentators quantifying coordination in real time (*"Seattle's secondary is at 59 DSS today — their zone rotations are perfectly timed"*).

---

## Results at a glance

| | |
|---|---|
| Best synchronized secondary (2021) | **SEA** (DSS = 59.0) |
| Least synchronized | **LAC** (DSS = 51.5) |
| Man coverage effect | High DSS → **50.1%** vs 56.2% completion rate |
| Zone coverage effect | High DSS → **63.5%** vs 67.2% completion rate |
| Hardest coverage to sync | Cover-0 / Cover-1 (DSS ~44–47) |
| Easiest to sync | Prevent / Quarters (DSS ~60–63) |

## How to run

```bash
git clone https://github.com/florianhemery/nfl-pocket-collapse
cd nfl-pocket-collapse
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy scipy matplotlib plotly

# Download data into data/ from:
# https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data

# Full pipeline (loads data, computes DSS, generates all charts + GIF + HTML dashboard)
python src/main.py

# Interactive dashboard only (requires output/dss_results.csv)
python src/dashboard.py
# → open output/dss_dashboard.html in browser

# Jupyter notebook
jupyter notebook notebooks/analysis.ipynb
```

## Metric definition

**DSS = 100 × (0.40 × VA + 0.30 × SD + 0.30 × OD)**

Computed frame-by-frame from snap to pass release, then averaged:

- **VA (Velocity Alignment):** cosine similarity between each DB's velocity vector and the group mean. High = everyone moving the same direction.
- **SD (Spacing Discipline):** 1/(1+CV) where CV = std/mean of all pairwise DB distances. High = formation maintained.
- **OD (Orientation Divergence):** 1 − circular R of body orientations. Counter-intuitive: DBs looking *different* directions scores higher, because it means each one is tracking *his own* receiver, not all staring at the QB.

## Files

```
src/
  dss.py                # Metric computation
  dss_visualization.py  # Static charts + GIF animation
  dashboard.py          # Interactive Plotly HTML dashboard
  main.py               # Full pipeline
notebooks/
  analysis.ipynb        # End-to-end walkthrough
output/
  dss_results.csv       # Per-play DSS scores (7,510 rows)
  dss_team_ranking.png
  dss_vs_completion.png
  dss_heatmap.png
  dss_best_sync.gif
  dss_dashboard.html    # Open this in a browser
```

## Data

NFL Big Data Bowl tracking data — [ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data](https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data)

## Acknowledgments

Thanks to AWS for supporting this project.
