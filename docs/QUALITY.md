# Standard de qualite

Profil `strict` (voir AGENTS.md). Les seuils sont ceux appliques par la CI (`.github/workflows/quality.yml`).

| Controle | Seuil | Outil |
|---|---|---|
| Tests verts | oui | `uv run pytest` |
| Types | pyright en mode `strict`, 0 erreur | `uv run pyright` |
| Lint | 0 erreur | `uv run ruff check` |
| Format | aucun fichier a reformater | `uv run ruff format --check` |
| Complexite max par fonction | 10 (regle C901) | ruff |
| Couverture minimale | 80 % du paquet `nfl_dss` (bloquant) | `--cov-fail-under=80` dans `pyproject.toml` |
| Scan de secrets | 0 fuite | gitleaks (action epinglee par sha) |
| Audit des dependances | 0 vulnerabilite connue | `pip-audit` (verrouille dans `uv.lock`) sur l'export de `uv.lock` |
| Dependances a jour | PR hebdomadaires | Renovate (`renovate.json`) |
| Schema de l'export | `exports/site-data.json` valide `docs/site-data.schema.json` (lui-meme un schema valide), moins de 300 Ko | `tests/test_export.py` |
| Derive de l'export | `exports/site-data.json` est reproduit par `dss export --results-only` depuis `output/dss_results.csv` (suivi), hors date et commit | `tests/test_drift.py`, en CI |
| ADR pour chaque choix structurant | oui | `docs/decisions/` |

Non retenus dans ce depot : test d'abus par regle d'acces (pas d'acces), mutation testing (pas encore, a envisager sur `metrics.py`), verificateur independant.

Rappel : la couverture prouve qu'une ligne a tourne, pas qu'un bug serait detecte. Les garanties qui comptent pour la metrique sont les tests de proprietes (bornes, invariance par rotation, translation et permutation des joueurs), le test de reference sur une action synthetique aux valeurs calculees a la main, et l'equivalence avec l'ancien code a boucles (`tests/legacy_dss.py`, a 1e-9 pres). Pour l'export, des valeurs figees (intervalle bootstrap pour une graine fixe, retrecissement calcule a la main, nombre de reechantillonnages) et la garde de derive en CI. Les mutations de ces constantes (niveau de l'intervalle, graine, nombre de reechantillonnages, percentile, ddof, moyenne ponderee) ont ete essayees a la main : chacune fait echouer au moins un test sans les fichiers Kaggle.

Limite de l'oracle d'equivalence : il couvre la metrique seulement. Les fonctions `identify_secondary` et `compute_dss_all_plays` de l'ancien code n'y figurent pas ; le filtre d'equipe, la correspondance domicile/exterieur et le rattachement des metadonnees ne sont verifies que par le test de reference sur une action synthetique, pas par une comparaison ancien/nouveau.

## Mesure

Au 2026-10-23, sur la branche `feat/foundation` : 90 tests passes, couverture totale 98,7 % (524 lignes sur 531), obtenue avec `uv run pytest`.

Limite : la reconstruction complete depuis les fichiers de suivi n'est pas couverte par un test sur donnees reelles, seulement par des jeux synthetiques (voir README).
