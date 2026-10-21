# Defensive Sync Score (DSS)

**Ce que nous avons construit :** Une nouvelle métrique NFL — le Defensive Sync Score (DSS) — qui quantifie à quel point une défense arrière (secondary) se déplace de manière synchronisée, comme une unité, sur les jeux de passe, à partir des données de suivi des joueurs image par image (122 matchs, 7 510 jeux, saison NFL 2021).

**Ce qu'elle révèle :** Le DSS combine trois sous-scores calculés après le snap : l'Alignement des vitesses (les DBs se déplacent-ils ensemble ?), la Discipline d'espacement (tiennent-ils leur formation ?) et la Divergence d'orientation (chaque DB suit-il bien sa propre assignation ?). Résultat clé : les défenses avec un DSS élevé concèdent **6,1 points de pourcentage de passes complétées en moins en couverture individuelle (man coverage)** — le signal le plus fort se trouve en Cover-0/Cover-1, où la synchronisation de la défense arrière est la plus difficile à maintenir (DSS ~44) et où les erreurs de communication coûtent le plus cher.

**Qui l'utilise :** Les coordinateurs défensifs, pour repérer les failles de couverture avant l'analyse vidéo ; les recruteurs, pour évaluer les safeties qui « dirigent » la défense arrière ; les commentateurs, pour quantifier la coordination en temps réel (*« La défense arrière de Seattle est à 59 de DSS aujourd'hui — leurs rotations en zone sont parfaitement synchronisées »*).

---

## Résultats en un coup d'œil

| | |
|---|---|
| Défense arrière la mieux synchronisée (2021) | **SEA** (DSS = 59,0) |
| La moins synchronisée | **LAC** (DSS = 51,5) |
| Effet en couverture individuelle | DSS élevé → **50,1 %** vs 56,2 % de passes complétées |
| Effet en couverture de zone | DSS élevé → **63,5 %** vs 67,2 % de passes complétées |
| Couverture la plus difficile à synchroniser | Cover-0 / Cover-1 (DSS ~44–47) |
| La plus facile à synchroniser | Prevent / Quarters (DSS ~60–63) |

## Comment l'exécuter

```bash
git clone https://github.com/florianhemery/nfl-pocket-collapse
cd nfl-pocket-collapse
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy scipy matplotlib plotly

# Téléchargez les données dans data/ depuis :
# https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data

# Pipeline complet (charge les données, calcule le DSS, génère tous les graphiques + GIF + tableau de bord HTML)
python src/main.py

# Tableau de bord interactif uniquement (nécessite output/dss_results.csv)
python src/dashboard.py
# → ouvrez output/dss_dashboard.html dans un navigateur

# Notebook Jupyter
jupyter notebook notebooks/analysis.ipynb
```

## Définition de la métrique

**DSS = 100 × (0,40 × VA + 0,30 × SD + 0,30 × OD)**

Calculé image par image du snap jusqu'au lâcher de la passe, puis moyenné :

- **VA (Velocity Alignment — Alignement des vitesses) :** similarité cosinus entre le vecteur vitesse de chaque DB et la moyenne du groupe. Élevé = tout le monde se déplace dans la même direction.
- **SD (Spacing Discipline — Discipline d'espacement) :** 1/(1+CV) où CV = écart-type/moyenne de toutes les distances entre paires de DBs. Élevé = formation maintenue.
- **OD (Orientation Divergence — Divergence d'orientation) :** 1 − R circulaire des orientations du corps. Contre-intuitif : des DBs qui regardent dans des directions *différentes* obtiennent un score plus élevé, car cela signifie que chacun suit *son propre* receveur, au lieu de tous fixer le QB.

## Fichiers

```
src/
  dss.py                # Calcul de la métrique
  dss_visualization.py  # Graphiques statiques + animation GIF
  dashboard.py          # Tableau de bord HTML interactif Plotly
  main.py               # Pipeline complet
notebooks/
  analysis.ipynb        # Démonstration de bout en bout
output/
  dss_results.csv       # Scores DSS par jeu (7 510 lignes)
  dss_team_ranking.png
  dss_vs_completion.png
  dss_heatmap.png
  dss_best_sync.gif
  dss_dashboard.html    # Ouvrez ce fichier dans un navigateur
```

## Données

Données de suivi du NFL Big Data Bowl — [ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data](https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data)
