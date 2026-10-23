# AGENTS.md

## Profil du projet
- Profil qualite : `strict` (voir `docs/QUALITY.md`).
- Langue : README.md en anglais ; README.fr.md, ADR, AGENTS.md et QUALITY.md en francais. Code, noms et commentaires en anglais.

## Commandes
- Install : `uv sync --frozen` (Python 3.12, `uv` seul, jamais `pip install`).
- Tout verifier : `uv run ruff check && uv run ruff format --check && uv run pyright && uv run pytest`
- Export du site : `uv run dss export` (ecrit `exports/site-data.json`). Sans les fichiers Kaggle : `uv run dss export --results-only`.
- Ajouter les colonnes de contexte a un ancien `output/dss_results.csv` : `uv run dss enrich` (donnees Kaggle requises).
- Reconstruction complete : `bash scripts/fetch_data.sh` puis `uv run dss build` (donnees de suivi Kaggle requises, hors depot).

## Definition de "termine"
Ruff, pyright strict et pytest verts (couverture >= 80 %), `exports/site-data.json` regenere si `output/dss_results.csv` ou `src/nfl_dss/export.py` change, doc et ADR a jour dans le meme changement.

## Conventions
- Conventional Commits. Le commit et la publication de la branche se font dans deux commandes separees. Pas de mention d'IA, pas de co-auteur, pas de tiret long, pas d'emoji.
- Aucun chargement de donnees a l'import, pas de `print` (utiliser `logging`), pas de manipulation de `sys.path`.
- Aucun chiffre ecrit a la main dans l'export ou le README : il vient de `exports/site-data.json`.
- Ne pas modifier `docs/CONTRACT.md` ni le schema sans changer `schema_version` (ajout = mineur, retrait = majeur).
- Ajouter une dependance : verifier la version sur PyPI le jour meme, la fixer exactement dans `pyproject.toml`, mettre a jour `uv.lock`.
- `tests/legacy_dss.py` est une copie figee de l'ancien code, utilisee comme oracle : ne pas la modifier.

## Zones fragiles
- `src/nfl_dss/metrics.py` : les formules ne changent que par un ADR et un nouveau test d'equivalence.
- `data/` : jamais de CSV Kaggle dans le depot (voir ADR 0005).
- `src/nfl_dss/validation.py` : le protocole (decoupage, variables, modeles, regle de decision) est pre-enregistre dans l'ADR 0006 ; ne le changer qu'avec un nouvel ADR, jamais apres avoir vu un resultat.
