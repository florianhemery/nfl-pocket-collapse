# 0005. Donnees Kaggle hors depot

- Statut : accepte
- Date : 2026-10-23
- Verifie le : 2026-10-23
- A revalider le : 2027-04-23

## Contexte et probleme
Quatre fichiers du NFL Big Data Bowl 2023 (`games`, `plays`, `players`, `pffScoutingData`, environ 15 Mo) etaient commites. Les fichiers de suivi, bien plus gros, etaient deja ignores. Il faut savoir si redistribuer ces fichiers est permis.

## Options etudiees
### Option A : retirer les CSV de l'arbre, les ignorer, fournir un script de telechargement et des sommes de controle
- Pour : ne redistribue rien dont les conditions sont incertaines ; reproductible via la CLI Kaggle ; les sommes de controle detectent un fichier different.
- Contre : le telechargement demande un compte Kaggle et l'acceptation des regles ; l'export recoupe par plays.csv et games.csv ne tourne pas en CI sans les fichiers ; `dss export --results-only` tourne depuis le fichier de resultats versionne et sert de garde de derive.
### Option B : garder les CSV dans le depot
- Pour : tout fonctionne apres un clone.
- Contre : risque de redistribution contraire aux conditions.

## Decision
Option A. `data/*.csv` et `data/tracking/` sont ignores (les fichiers restent sur le disque), `scripts/fetch_data.sh` telecharge la competition `nfl-big-data-bowl-2023` avec la CLI kaggle et renomme les fichiers de suivi en `data/tracking/tracking_week_N.csv`, `data/checksums.sha256` donne le sha256 des quatre fichiers de metadonnees. `output/dss_results.csv` reste versionne comme artefact precalcule, mais reduit aux colonnes dont l'export a besoin : scores calcules, identifiants de match et de passe, saison et semaine, equipe defensive, etiquettes de couverture PFF et indicateur de completion. Les colonnes brutes de la competition qui ne servent pas (resultat de passe, equipe offensive, indicateur de sack) en sont retirees. Le contexte de l'action ajoute ensuite par l'ADR 0006 (voir la mise a jour ci-dessous) en fait partie depuis le 2026-10-24.

## Consequences
- Ce qui reste suivi est quand meme un extrait au niveau des lignes de donnees de la competition (identifiants, equipe defensive, etiquettes PFF) : on ne peut donc pas ecrire que les donnees ne sont pas redistribuees. Les conditions de redistribution de cet extrait ne sont pas verifiees ; la note de licence de l'export le dit.
- Etat des connaissances sur la licence : les editions recentes du Big Data Bowl sont indiquees sous CC BY-NC 4.0 par des depots tiers vus dans des resultats de recherche ; les conditions de l'edition 2023 n'ont pas pu etre lues (la page des regles de Kaggle n'a rien renvoye au telechargement du 2026-10-23, elle est rendue par JavaScript). On n'affirme rien de plus : voir `dataset_license_note` dans l'export.
- Retirer les fichiers de l'arbre ne les retire pas de l'historique git. Reecrire l'historique est destructif et n'est pas decide ici.
- Les sommes de controle des fichiers de suivi manquent : ils n'etaient pas disponibles en local, et le script le signale a la fin. Le script verifie les quatre fichiers de metadonnees dans le repertoire temporaire avant de rien deplacer dans `data/`, et utilise `shasum` si `sha256sum` manque. Il n'a pas pu etre execute avec un vrai telechargement (pas de compte Kaggle dans cet environnement) ; la verification a ete testee avec une fausse commande `kaggle` et un fichier altere.
- Verifier les regles de la page Kaggle avant toute reutilisation ou republication des donnees.

## Mise a jour du 2026-10-24 (ADR 0006)
La validation hors echantillon (ADR 0006) lit le contexte de l'action, et la garde de derive tourne en CI sans les fichiers Kaggle. Quatre colonnes de niveau action ont donc ete ajoutees a `output/dss_results.csv`. La liste complete des champs de niveau ligne suivis dans le depot est maintenant :
- identifiants : `gameId`, `playId` ;
- saison et semaine : `season`, `week` ;
- equipe defensive : `defensiveTeam` ;
- etiquettes PFF : `coverage`, `coverageType` ;
- issue : `completed` (derive de `passResult`, qui n'est pas suivi) ;
- contexte ajoute : `down`, `yardsToGo`, `yardsToEndzone` (derive de `yardlineSide`, `yardlineNumber` et `possessionTeam`, qui ne sont pas suivis) et `playResult` ;
- valeurs calculees : `dss`, `va`, `sd`, `od`, `num_dbs`, `frames_analyzed`.
`absoluteYardlineNumber`, `yardlineSide`, `yardlineNumber`, `possessionTeam`, `passResult`, `offenseFormation` et les autres colonnes de `plays.csv` ne sont pas suivies. Les quatre colonnes ajoutees sont des champs de la competition (ou calcules a partir de champs de la competition) : l'extrait suivi est donc un peu plus large, et les conditions de redistribution restent non verifiees. La note de licence de l'export (`dataset_license_note`) liste ces champs.

## Sources
1. [NFL Big Data Bowl 2023, regles](https://www.kaggle.com/competitions/nfl-big-data-bowl-2023/rules) - officiel - tentative de lecture le 2026-10-23, contenu non obtenu : a verifier
2. [tzeng7/bdb27](https://github.com/tzeng7/bdb27) et [harsha-suribhatla/combine-translation](https://github.com/harsha-suribhatla/combine-translation) - depots tiers, extraits vus dans des resultats de recherche, pages non rouvertes : a verifier - edition 2027, CC BY-NC 4.0
