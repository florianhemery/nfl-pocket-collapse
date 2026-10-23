# 0002. Paquet uv et outillage qualite

- Statut : accepte
- Date : 2026-10-23
- Verifie le : 2026-10-23
- A revalider le : 2027-04-23

## Contexte et probleme
Le code d'origine etait un dossier `src/` sans packaging, avec des `sys.path.insert`, des chargements de donnees a l'import, des `print` et aucun test. Il fallait un paquet installable, reproductible, type et teste, au meme niveau d'exigence que le projet portfolio-rag.

## Options etudiees
### Option A : paquet `nfl_dss` en disposition `src/`, gere par uv, qualite par ruff, pyright strict, pytest, hypothesis
- Pour : un seul outil pour Python, dependances et lockfile (`uv.lock`) ; versions exactes ; commande `dss` installee ; meme chaine que portfolio-rag (ruff, pytest) ; pyright strict attrape les erreurs de forme sur les tableaux.
- Contre : pandas-stubs et scipy-stubs sont necessaires pour que le mode strict reste utilisable ; pandas est le point le moins bien type.
### Option B : `requirements.txt`, pip, flake8 et mypy
- Pour : outillage tres repandu.
- Contre : pas de lockfile natif, deux outils de plus, installation moins reproductible.

## Decision
Option A. Python 3.12 (`requires-python >=3.12`, `.python-version`), backend de build `uv_build`, dependances d'execution numpy, pandas, scipy fixees exactement, groupe de developpement pytest, hypothesis, ruff, pyright, pytest-cov, jsonschema, pandas-stubs, scipy-stubs. Seuils (voir `docs/QUALITY.md`) : couverture >= 80 % imposee par `--cov-fail-under` dans `pyproject.toml`, complexite maximale 10 (regle C901), pyright en mode `strict`, ruff lint et format sans erreur.

## Consequences
- Les versions ont ete lues sur PyPI le 2026-10-23. pandas 3.1.0 date du 2026-10-22, la veille : version tres recente, a surveiller via Renovate (`renovate.json`).
- Python 3.12 est impose explicitement : le Python par defaut de la machine de developpement est plus recent et scipy n'y compile pas.
- La CI (`.github/workflows/quality.yml`) rejoue les memes commandes avec `uv sync --frozen`, un scan de secrets (gitleaks) et `pip-audit`.
- pyright, pandas-stubs et scipy-stubs sont des outils de developpement uniquement.

## Sources
1. [uv, The uv build backend](https://docs.astral.sh/uv/concepts/build-backend/) - officiel, page lue - consulte le 2026-10-23
2. [Ruff, Settings (lint.mccabe.max-complexity)](https://docs.astral.sh/ruff/settings/#lint_mccabe_max-complexity) - officiel, page lue - consulte le 2026-10-23
3. [PyPI, pages JSON de numpy, pandas, scipy, pytest, hypothesis, ruff, pyright, pytest-cov, jsonschema, pandas-stubs, scipy-stubs](https://pypi.org/) - registre officiel, versions et dates de publication lues par l'API - consulte le 2026-10-23
(Sources 1 et 2 : meme vendeur, Astral.)
