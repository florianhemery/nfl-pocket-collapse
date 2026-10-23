# 0001. Documenter les decisions d'architecture avec des ADR

- Statut : accepte
- Date : 2026-10-23
- Verifie le : 2026-10-23
- A revalider le : 2027-04-23

## Contexte et probleme
Le depot a change de forme (applications Dash, puis paquet et export statique) sans trace des raisons. Sans trace des choix, on ne sait plus pourquoi une decision a ete prise ni quand la remettre en cause.

## Options etudiees
### Option A : ADR au format court dans le depot (`docs/decisions/`)
- Pour : versionne avec le code, relu dans les PR, meme format que le projet portfolio-rag.
- Contre : demande de la discipline.
### Option B : notes dans le README ou une page externe
- Pour : aucune structure a maintenir.
- Contre : se desynchronise du code, melange decision et mode d'emploi.

## Decision
Option A, avec le gabarit `0000-template.md` (statut, date, date de revalidation, options, sources datees).

## Consequences
Chaque decision structurante ajoute un fichier numerote. Une decision remplacee garde son fichier et indique `remplace par NNNN`.

## Sources
1. ADR 0001 du depot portfolio-rag (`docs/decisions/0001-documenter-les-decisions.md`) et son gabarit `0000-template.md` - depot du meme auteur, fichiers lus - consulte le 2026-10-23
(Source unique, interne au meme auteur : le format est repris tel quel, sans validation externe.)
