# Pocket Collapse Index (PCI)

A new NFL analytics metric that measures how fast the quarterback pocket collapses on passing plays, using frame-by-frame player tracking data from the NFL Next Gen Stats Big Data Bowl dataset.

## What it reveals

The PCI quantifies the rate at which the protective "bubble" around the quarterback shrinks after the snap. A lower PCI means the offensive line held their blocks longer; a higher PCI means pressure arrived faster. This exposes:

- **Offensive line performance** — which units give their QB the most time
- **Pass rusher impact** — which defenders collapse the pocket fastest
- **Scheme effectiveness** — which defensive formations generate quickest pressure

## Who would use it

- **Coaches** evaluating OL performance and identifying protection scheme weaknesses
- **Recruiters** scouting edge rushers by their collapse speed
- **Commentators** adding real-time context ("pocket collapsed in 2.1s, well below the league average of 2.8s")

## Data

NFL Big Data Bowl 2023 tracking data (frame-by-frame x/y position, speed, acceleration, orientation for every player on every play).

Source: [nfl-big-data-bowl-regional-event-data](https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data)

## Structure

```
nfl-pocket-collapse/
├── data/           # Raw CSVs (gitignored)
│   └── tracking/   # Per-game tracking files
├── src/            # Metric computation & visualization
├── notebooks/      # Analysis notebooks
├── output/         # Generated charts & animations (gitignored)
└── README.md
```
