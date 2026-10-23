# 0004. Integration statique au portfolio via site-data.json

- Statut : accepte
- Date : 2026-10-23
- Verifie le : 2026-10-23
- A revalider le : 2027-04-23

## Contexte et probleme
Le site du portfolio (depot portfolio-rag, `apps/site`) doit presenter ce travail. Il faut un moyen de lui fournir des chiffres sans heberger de serveur Python de plus et sans qu'un chiffre soit saisi a la main.

## Options etudiees
### Option A : un fichier JSON statique, produit par `dss export`, copie tel quel dans le site
- Pour : aucun service a heberger, diffable en revue, taille bornee, contrat verifiable par un schema JSON.
- Contre : les donnees ne sont pas interactives en direct ; il faut recopier le fichier a chaque mise a jour.
### Option B : une API hebergee que le site appelle
- Pour : donnees toujours a jour.
- Contre : un service de plus a exploiter et a securiser pour un jeu de donnees fige (saison 2021).
### Option C : integrer une application Dash dans le site
- Pour : interactivite.
- Contre : reprend les problemes de l'ADR 0003.

## Decision
Option A. Le contrat est `docs/CONTRACT.md` (version 1.0) et son schema `docs/site-data.schema.json`, qui refuse les champs inconnus. Regles : tout nombre est calcule par le pipeline, les flottants sont arrondis a 4 decimales, une section vide (`null` ou tableau vide) est masquee par le site, le fichier reste sous 300 Ko, un ajout de champ change la version mineure et un retrait la version majeure. Le verdict (`no_signal`, `weak_signal`, `signal`) vient d'une regle ecrite dans `src/nfl_dss/export.py` et recopiee dans le champ `verdict_rule`.

## Consequences
- `exports/site-data.json` est versionne ; un test verifie qu'il valide le schema et qu'il est reproduit par le pipeline quand les CSV locaux sont presents (il est ignore en CI, ou `data/` est absent).
- `model_comparison` et `replays` restent `null` et `[]` jusqu'aux phases suivantes (issues #5 et #6).
- Le champ `pipeline_commit` designe le commit a partir duquel l'export a ete genere, pas celui qui le contient.

## Sources
1. `docs/CONTRACT.md` de ce depot - document de conception interne, fichier lu - consulte le 2026-10-23
(Source unique et interne.)
