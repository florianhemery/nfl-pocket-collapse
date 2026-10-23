# Defensive Sync Score (DSS)

Une métrique de données de suivi pour les défenses arrière de la NFL, construite à partir des
fichiers du NFL Big Data Bowl 2023 (saison 2021, semaines 1 à 8). La question : une défense
arrière qui se déplace de façon coordonnée concède-t-elle moins de passes complétées ?

La réponse courte, d'après les données de ce dépôt : toutes passes confondues, la métrique ne
montre aucune association linéaire avec la complétion. Ce résultat nul est trompeur pris seul.
Dans chaque famille de couverture l'association est réelle et du signe attendu, et elle disparaît
dès que le temps avant le lancer et la famille de couverture sont contrôlés. On n'a pas montré
que la métrique apporte une information sur les complétions au-delà de ces deux variables, et un
test sur données mises de côté, fixé à l'avance, ne trouve aucun gain à l'ajouter à un modèle qui
les connaît déjà (décision `no_signal`, voir « Test sur données mises de côté »).
Chaque nombre de cette page est lu dans [`exports/site-data.json`](exports/site-data.json), que
`uv run dss export` régénère à partir des résultats précalculés.

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

Variable d'intérêt : 1 si la passe est complétée, sinon 0. Cette section est le résultat
principal du projet : un résultat global nul, une association réelle au sein des groupes, et sa
disparition sous contrôle. C'est un exemple concret de facteur de confusion, et la raison pour
laquelle le DSS n'est pas présenté comme une métrique validée.

### 1. Toutes passes confondues : rien

Pour le DSS lui-même : r = -0,0185, p = 0,109833, n = 7510. Par quintile de DSS (du plus bas au
plus haut), le taux de complétion est de 0,6232, 0,6225, 0,5939, 0,5939 et 0,6198, avec 1502
passes chacun, ce qui n'est pas monotone. La règle de verdict écrite dans
`src/nfl_dss/export.py` ne regarde que cette corrélation globale et renvoie `no_signal`.

### 2. Dans chaque famille de couverture : une association réelle

| Famille de couverture | passes | r | p | complétion, DSS au moins égal à la médiane | complétion, DSS sous la médiane |
|---|---|---|---|---|---|
| Man | 2160 | -0,0708 | 0,000997 | 0,5014 | 0,5616 |
| Zone | 4943 | -0,0477 | 0,000793 | 0,635 | 0,6719 |
| Other | 407 | -0,0741 | 0,135459 | 0,4755 | 0,5468 |

En couverture individuelle (man) comme en zone, un DSS plus élevé va avec moins de passes
complétées, et les p-values sont petites. Les coupures à la médiane redonnent les chiffres cités
par la première version de ce README (environ 50 contre 56 % en man, 63,5 contre 67 % en zone) :
l'export les reproduit. Ils ne sont pas faux. Ils sont confondus. La corrélation globale est
nulle parce que la famille de couverture déplace les deux variables : les passes en zone ont un
DSS plus élevé et un taux de complétion plus élevé que les passes en man (Cover-3 : DSS
57,1389, complétion 0,6582 ; Cover-1 : DSS 53,5144, complétion 0,5299), ce qui annule la pente
interne à chaque famille. L'export nomme ce motif `simpson`, selon une règle écrite dans le code
(voir `docs/CONTRACT.md`).

### 3. Après contrôle : de nouveau rien

Le temps avant le lancer, mesuré en nombre d'images entre le snap et le lancer, est corrélé à la
complétion à r = -0,1891, bien plus que le DSS, et il diffère selon la famille de couverture. La
corrélation partielle entre DSS et complétion, en contrôlant le temps avant le lancer et la
famille de couverture, est r = -0,004, p = 0,731144, n = 7510. L'association interne aux familles
n'est donc plus distinguable de zéro une fois ces deux variables prises en compte. Les données ne
disent pas laquelle des deux fait le travail ; les départager demande la comparaison de modèles
sur données mises de côté ci-dessous.

### Sous-scores

Corrélation globale avec la complétion, non ajustée pour les facteurs ci-dessus :

| | moyenne | écart-type | r | p |
|---|---|---|---|---|
| VA | 65,0163 | 15,2238 | 0,005 | 0,667767 |
| SD | 71,0002 | 2,9968 | 0,0271 | 0,019032 |
| OD | 29,84 | 14,3135 | -0,0478 | 0,000034 |

OD a l'association globale la plus forte et du signe attendu. SD va dans l'autre sens (un
espacement plus discipliné va avec un peu plus de complétions). VA ne montre rien.

### Équipes

Les moyennes par équipe sont accompagnées d'un intervalle de confiance bootstrap à 95 %
(2000 rééchantillonnages, graine fixe) large de 1,74 à 2,50 points, et d'une moyenne rétrécie
par Bayes empirique. Le DSS diffère selon le schéma de couverture (par exemple 47,77 en Cover-0
et 59,66 en Quarters), et aucun ajustement pour le mélange de schémas d'une équipe n'est fait :
la moyenne d'une équipe n'est donc pas une mesure propre de sa coordination.

### Test sur données mises de côté

La question laissée ouverte plus haut est prédictive : sur des passes qu'un modèle n'a jamais
vues, le DSS ajoute-t-il quelque chose à ce que le contexte de la passe dit déjà ? Le protocole a
été écrit et commité avant l'ajustement du moindre modèle
([ADR 0006](docs/decisions/0006-validation-hors-echantillon-protocole.md)). C'est le seul test
confirmatoire du projet ; tout le reste ci-dessous est exploratoire.

- Découpage : les passes des semaines 1 à 6 entraînent (5799 passes), celles des semaines 7 et 8
  testent (1711 passes, 28 matchs). Les modèles sont ajustés une seule fois.
- Base : temps avant le lancer (`frames_analyzed`), famille de couverture, couverture, down,
  distance à parcourir et distance à la ligne d'en-but adverse. Modèle : régression logistique
  (scikit-learn, L2, `C = 1.0`, rien n'est réglé). L'ADR remplace `absoluteYardlineNumber` par la
  distance à la ligne d'en-but, car le premier ne dit pas dans quel sens attaque l'offensive.
- Comparaison : la base contre la base plus le DSS. Incertitude : bootstrap apparié sur les
  matchs de test (2000 rééchantillonnages, graine 20261024, intervalle percentile à 95 %).
- Règle de décision, écrite à l'avance : `signal` si la borne basse du gain d'AUC est au-dessus de
  0 ; `weak_signal` sinon et si le gain dépasse 0,005 ; `no_signal` dans les autres cas.

| Jeu de test (1711 passes) | base | base plus DSS | différence (intervalle à 95 %) |
|---|---|---|---|
| AUC | 0,6489 | 0,649 | 0,0001 (-0,0021 à 0,0022) |
| Score de Brier | 0,2242 | 0,2242 | -0,0001 (-0,0004 à 0,0003) |
| log loss | 0,6395 | 0,6394 | |

Décision : `no_signal`. Le gain d'AUC est de 0,0001 et son intervalle, -0,0021 à 0,0022, contient
0. Sur ce jeu de test et avec ces modèles linéaires, le DSS n'améliore pas la prédiction des
complétions au-delà du temps avant le lancer, de la couverture, du down, de la distance et de la
position sur le terrain. C'est une absence de gain détecté, pas la preuve que le DSS est inutile :
le jeu de test couvre une saison et 1711 passes, et l'intervalle ne couvre pas l'incertitude de
l'échantillon d'entraînement.

Exploratoire, et sans effet sur la décision :

- Remplacer le DSS par ses trois sous-scores (VA, SD, OD) donne une AUC de test de 0,6491, soit
  0,0002 de plus que la base.
- Yards gagnés (`playResult`, régression linéaire) : RMSE de test de 10,0654 pour la base, 10,0482
  avec le DSS, et un gain de R2 de 0,0033.

Limites : un seul découpage, des modèles linéaires sans interactions, une saison, un bootstrap
sur les matchs seulement, et les semaines 7 et 8 avaient déjà été vues par les corrélations
descriptives ci-dessus (elles n'ont servi à rien choisir dans le protocole).

## Installation et usage

Nécessite [uv](https://docs.astral.sh/uv/) et Python 3.12.

```bash
uv sync --frozen
uv run dss export      # écrit exports/site-data.json depuis output/dss_results.csv
uv run dss enrich      # seulement pour ajouter les colonnes de contexte à un ancien fichier de résultats
```

`output/dss_results.csv` est l'artefact précalculé, une ligne par passe notée, conservé dans le
dépôt. Par défaut `export` lit aussi `data/plays.csv` et `data/games.csv` (voir Données) pour le
recouper. `uv run dss export --results-only` calcule les mêmes statistiques à partir du seul
fichier de résultats versionné ; c'est ce que fait la CI pour vérifier que
`exports/site-data.json` est toujours ce que produit le code.

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

Les fichiers Kaggle bruts ne sont pas stockés dans ce dépôt (voir
[ADR 0005](docs/decisions/0005-donnees-kaggle-hors-depot.md)). Un extrait au niveau des lignes
l'est : `output/dss_results.csv` contient une ligne par passe analysée avec les scores, les
identifiants de match et de passe, la saison et la semaine, l'équipe défensive, les étiquettes
de couverture PFF (`coverage`, `coverageType`) et l'indicateur de complétion. Il conserve aussi le
contexte de la passe utilisé par le test sur données mises de côté : `down`, `yardsToGo`,
`yardsToEndzone` (dérivée du côté du terrain, du numéro de ligne et de l'équipe en possession) et
`playResult`. Les autres colonnes de la compétition (résultat de passe, équipe offensive,
`absoluteYardlineNumber` et le reste de `plays.csv`) ne sont pas conservées. Les conditions de l'édition 2023 n'ont pas été vérifiées et les éditions récentes
seraient sous CC BY-NC 4.0 : savoir si la redistribution de cet extrait est permise n'est donc
pas vérifié. Lisez les
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
