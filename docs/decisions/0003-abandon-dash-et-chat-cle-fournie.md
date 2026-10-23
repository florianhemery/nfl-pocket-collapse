# 0003. Abandon de l'application Dash et du chat a cle fournie

- Statut : accepte
- Date : 2026-10-23
- Verifie le : 2026-10-23
- A revalider le : 2027-04-23

## Contexte et probleme
Le depot contenait cinq applications Dash qui se recouvraient (`app.py`, `app_v2.py`, `app_nextgen.py`, `dashboard.py`, `premium_dashboard.py`), sans test, et un chat d'analyse qui demandait au visiteur sa propre cle d'API (OpenAI, Anthropic, Google, Mistral). Dans `app_nextgen.py` (commit `1c9e489`), la cle saisie est rangee dans une instance de classe creee au niveau du module (`ai_provider = AI_Provider()`), donc partagee par toutes les sessions du processus : la cle d'un visiteur peut servir une autre session. Sept documents a la racine ne faisaient que decrire des corrections de ce code.

## Options etudiees
### Option A : supprimer les applications et tout le code des fournisseurs d'IA
- Pour : supprime la faille, reduit le depot a ce qui est teste, laisse la presentation au site du portfolio (ADR 0004).
- Contre : plus de tableau de bord interactif dans ce depot.
### Option B : garder une seule application et stocker la cle par session
- Pour : conserve l'interface.
- Contre : il faut concevoir, tester et maintenir un stockage de secrets par session et une surface d'attaque (saisie de cle, appels sortants) pour un gain faible, alors que le resultat principal (pas de signal detecte) ne demande pas de chat.
### Option C : ne rien changer
- Pour : aucun travail.
- Contre : la faille reste, le depot reste illisible.

## Decision
Option A. Pas de chat a cle fournie dans la version 1. Les cinq applications, les modules de visualisation et d'analyse de joueurs non utilises, le notebook qui les importait, les captures d'ecran de l'interface supprimee et les sept documents obsoletes sont retires.

## Consequences
- L'historique git conserve l'ancien code (commit `1c9e489`). Aucune cle reelle n'a ete cherchee dans l'historique pour cette decision : le scan gitleaks de la CI porte sur les commits de la PR, pas sur tout l'historique.
- Toute interface future passe par l'export statique (ADR 0004). Un chat reviendrait par un nouvel ADR, avec la cle cote serveur et jamais dans un objet partage entre sessions.

## Sources
1. Code du depot, `src/app_nextgen.py` au commit `1c9e489` (classe `AI_Provider`, instance `ai_provider`) - code de ce depot, fichier lu - consulte le 2026-10-23
(Source unique et interne : c'est le code decrit.)
