# Defensive Sync Score (DSS)

Une métrique de données de suivi pour les défenses arrière de la NFL, construite à partir des
fichiers du NFL Big Data Bowl 2023 (saison 2021, semaines 1 à 8). La question : une défense
arrière qui se déplace de façon coordonnée concède-t-elle moins de passes complétées ?

La réponse courte, d'après les données de ce dépôt : la métrique telle qu'elle est définie ne
montre aucune association linéaire détectable avec la complétion de la passe. Le détail et les
limites sont ci-dessous. Chaque nombre de cette page est lu dans
[`exports/site-data.json`](exports/site-data.json), que `uv run dss export` régénère à partir
des résultats précalculés.

## La métrique

Pour chaque passe, les images comprises entre le snap et le lancer sont notées sur les arrières
défensifs en couverture (rôle PFF `Coverage`, poste officiel CB, FS, SS ou DB, dans l'équipe
défensive). Trois sous-scores dans [0, 1] sont moyennés sur les images :

| Sous-score | Définition |
|---|---|
| VA, alignement des vitesses | similarité cosinus moyenne entre la vitesse de chaque joueur en mouvement et la vitesse moyenne du groupe, bornée à [0, 1] |
| SD, discipline d'espacement | `1 / (1 + cv)`, où `cv` est le coefficient de variation des distances deux à deux |
| OD, divergence d'orientation | `1 - R`, où `R` est la longueur résultante des orientations du corps |

`DSS = 100 * (0,40*VA + 0,30*SD + 0,30*OD)`. Les poids sont fixés à la main, pas ajustés.
Une passe exige au moins 3 arrières sur au moins 3 images.

## Résultats (7510 passes, 122 matchs, 32 équipes)

Corrélation avec la complétion (1 si la passe est complétée, sinon 0). Pour le DSS lui-même :
r = -0,0185, p = 0,1098, n = 7510. Pour les sous-scores :

| | moyenne | écart-type | r | p |
|---|---|---|---|---|
| VA | 65,0163 | 15,2238 | 0,005 | 0,6678 |
| SD | 71,0002 | 2,9968 | 0,0271 | 0,019 |
| OD | 29,84 | 14,3135 | -0,0478 | 0,0 (arrondi à 4 décimales) |

Par quintile de DSS (du plus bas au plus haut), le taux de complétion est de 0,6232, 0,6225,
0,5939, 0,5939 et 0,6198, avec 1502 passes chacun. Le motif n'est pas monotone. La règle de
verdict écrite dans `src/nfl_dss/export.py` renvoie `no_signal`.

Le nombre d'images entre le snap et le lancer (temps avant le lancer) est corrélé à la
complétion à r = -0,1891, bien plus que le DSS. Le DSS diffère aussi selon le schéma de
couverture (par exemple 47,77 en Cover-0 et 59,66 en Quarters) : les écarts entre équipes
reflètent donc en partie le mélange de schémas. Les moyennes par équipe sont accompagnées d'un
intervalle de confiance bootstrap à 95 % (2000 rééchantillonnages, graine fixe) large de 1,74 à
2,50 points, et d'une moyenne rétrécie par Bayes empirique.

Ce qui n'est pas encore fait : une comparaison de modèles sur données mises de côté (le DSS
améliore-t-il une base qui connaît déjà le temps avant le lancer et la couverture ?). Elle est
suivie dans l'issue #5 et le champ d'export `model_comparison` vaut `null` d'ici là. Une version
antérieure de ce README citait des effets plus grands (par exemple en couverture individuelle) ;
l'export ne les reproduit pas, ils ne sont donc pas repris ici.

## Installation et usage

Nécessite [uv](https://docs.astral.sh/uv/) et Python 3.12.

```bash
uv sync --frozen
uv run dss export      # écrit exports/site-data.json depuis output/dss_results.csv
```

`export` a besoin de `data/plays.csv` et `data/games.csv` (voir Données).
`output/dss_results.csv` est l'artefact précalculé, une ligne par passe notée, conservé dans le
dépôt.

Reconstruction complète depuis les données de suivi :

```bash
bash scripts/fetch_data.sh   # nécessite la CLI kaggle et les règles de la compétition acceptées
uv run dss build             # écrit output/dss_results.csv
```

La reconstruction complète n'a pas été exécutée lors de l'écriture du paquet : les fichiers de
suivi n'étaient pas disponibles en local. Le pipeline est couvert par des jeux synthétiques et
par un test d'équivalence avec l'implémentation d'origine à boucles (l'issue #6, rejeu animé,
dépend aussi des données de suivi).

## Données

Les fichiers Kaggle ne sont pas stockés dans ce dépôt (voir
[ADR 0005](docs/decisions/0005-donnees-kaggle-hors-depot.md)). Les conditions de l'édition 2023
n'ont pas été vérifiées ; les éditions récentes seraient sous CC BY-NC 4.0. Lisez les
[règles de la compétition](https://www.kaggle.com/competitions/nfl-big-data-bowl-2023/rules)
avant toute réutilisation. `data/checksums.sha256` contient le sha256 des quatre fichiers de
métadonnées.

## Développement

```bash
uv run ruff check && uv run ruff format --check
uv run pyright          # mode strict
uv run pytest           # seuil de couverture 80 %
```

Voir [AGENTS.md](AGENTS.md), [docs/QUALITY.md](docs/QUALITY.md), les décisions dans
[docs/decisions](docs/decisions) et le contrat de données dans [docs/CONTRACT.md](docs/CONTRACT.md).

## Licence

MIT, voir [LICENSE](LICENSE). Le code est sous MIT ; les données gardent leurs propres
conditions.
