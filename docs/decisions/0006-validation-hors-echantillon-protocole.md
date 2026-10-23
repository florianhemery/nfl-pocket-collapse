# 0006. Validation hors echantillon du DSS : protocole pre-enregistre

- Statut : accepte
- Date : 2026-10-24
- Verifie le : 2026-10-24
- A revalider le : 2027-04-24

## Contexte et probleme
Les analyses descriptives du depot (correlation poolee nulle, association reelle dans chaque famille de couverture, disparition de cette association apres controle du temps de lancer et de la famille de couverture) ont toutes ete faites sur les 7510 actions, semaines 1 a 8 melangees. Elles n'ont pas separe ce qui est appris de ce qui est evalue. La question restante est predictive : le DSS aide-t-il a predire la completion d'une passe sur des actions qu'un modele n'a jamais vues, au-dela de ce que le contexte de l'action dit deja ?

Ce document est ecrit et commite avant le code qui calcule le moindre modele. Aucun modele de ce protocole n'a ete ajuste, ni sur l'entrainement ni sur le test, au moment de l'ecriture. Ce qui est deja connu : les correlations descriptives ci-dessus, calculees sur l'ensemble des semaines, donc y compris les semaines de test. Elles ne servent pas a choisir quoi que ce soit ci-dessous, mais le lecteur doit savoir que les semaines 7 et 8 n'ont pas ete vierges de tout regard.

## Options etudiees
### Option A : un seul test confirmatoire, fixe a l'avance, sur un decoupage temporel
- Pour : le seul chiffre qui decide est connu avant le calcul ; pas de liberte pour choisir le meilleur parmi plusieurs ; le decoupage temporel evite de melanger des actions voisines d'un meme match entre entrainement et test.
- Contre : un seul decoupage donne un seul tirage ; la puissance depend de la taille du test (environ 1700 actions).
### Option B : validation croisee avec choix des hyperparametres et des variables sur les donnees
- Pour : meilleure utilisation des donnees, estimation moins dependante d'un decoupage.
- Contre : degres de liberte du chercheur, risque de surapprentissage du choix du modele sur le test, et un verdict que personne ne peut verifier sans refaire tout le parcours.
### Option C : se contenter de la correlation partielle deja publiee
- Pour : aucun travail supplementaire.
- Contre : c'est une mesure dans l'echantillon ; elle ne dit rien de la capacite predictive ni de l'incertitude du gain.

## Decision
Option A. Le protocole ci-dessous est la regle ; toute autre analyse est exploratoire et etiquetee comme telle.

### Resultats mesures
- Principal (confirmatoire) : `completed`, 1 si la passe est completee, 0 sinon. Modele : regression logistique.
- Secondaire (exploratoire) : `playResult`, yards de l'action tels que donnes par la competition (inclut sacks, interceptions, penalites). Modele : regression lineaire.

### Variables
- Base : temps de lancer (`frames_analyzed`, nombre d'images entre snap et lancer), famille de couverture (`coverageType`), couverture (`coverage`), down (`down`, indicatrices), distance a parcourir (`yardsToGo`) et distance a la ligne d'en-but adverse (`yardsToEndzone`).
- Ecart a la consigne de depart, decide avant tout calcul : `absoluteYardlineNumber` est compte depuis le bord gauche du terrain, quel que soit le sens d'attaque. Sans le sens du jeu, il ne dit pas a combien de yards on est de la ligne d'en-but. On le remplace par `yardsToEndzone`, derive de `yardlineSide`, `yardlineNumber` et `possessionTeam` : si `yardlineSide` est l'equipe qui a le ballon, `100 - yardlineNumber` ; sinon `yardlineNumber` ; au milieu du terrain (`yardlineNumber` 50, `yardlineSide` absent), 50. Cela donne une base plus forte, donc un test plus dur pour le DSS.
- Base plus DSS : la base plus la colonne `dss`.
- Base plus sous-scores : la base plus `va`, `sd`, `od` (sans `dss`, qui en est une combinaison lineaire).
- Les variables numeriques sont centrees et reduites avec la moyenne et l'ecart type de l'entrainement. Les variables categorielles sont des indicatrices construites sur l'entrainement ; une categorie absente de l'entrainement vaut zero partout dans le test.

### Modeles
- Regression logistique de scikit-learn (version fixee dans `pyproject.toml`), penalite L2, `C = 1.0`, solveur `lbfgs`, `max_iter = 1000`. Aucun hyperparametre n'est regle, ni sur l'entrainement ni sur le test.
- Regression lineaire de scikit-learn par moindres carres, sans penalite, pour les yards.
- Forme lineaire dans les variables : pas d'interaction, pas de terme non lineaire.

### Decoupage
Entrainement : semaines 1 a 6. Test : semaines 7 et 8. La semaine vient de `games.csv` (colonne `week` de `output/dss_results.csv`). Les modeles sont ajustes une seule fois sur l'entrainement ; le test n'est utilise que pour predire.

### Metriques sur le test
- Completion : AUC, score de Brier, log loss.
- Yards : RMSE et R2 (R2 calcule sur le test, avec la moyenne du test comme reference).

### Incertitude
Bootstrap apparie par grappes sur les matchs du test : on tire avec remise les matchs du test, on garde toutes les actions de chaque match tire, et on evalue les deux modeles (deja ajustes) sur le meme echantillon. 2000 reechantillonnages, graine fixe `20261024`, intervalle percentile a 95 % pour la difference d'AUC et la difference de Brier. Le bootstrap mesure l'incertitude due au choix des matchs de test ; il ne reajuste pas les modeles et ne mesure donc pas l'incertitude due a l'entrainement. Un reechantillonnage dont les etiquettes n'ont qu'une classe est ecarte (le nombre de reechantillonnages retenus est publie).

### Regle de decision, ecrite avant le calcul
Soit `delta_auc` = AUC(base plus DSS) moins AUC(base) sur le test, et `[lo, hi]` son intervalle a 95 %. La regle s'applique aux valeurs arrondies a 4 decimales ecrites dans l'export, pour qu'on puisse la refaire depuis le fichier.
- `signal` : `lo > 0`.
- `weak_signal` : `lo <= 0` et `delta_auc > 0.005`.
- `no_signal` : tous les autres cas, y compris un gain negatif.

### Statut des analyses
La difference d'AUC entre la base et la base plus DSS est le seul test confirmatoire. Tout le reste est exploratoire et publie comme tel : Brier, log loss, modele avec VA, SD, OD, yards. Aucune de ces valeurs ne change la decision. Si un resultat exploratoire parait interessant, il est une hypothese pour un autre jeu de donnees, pas une conclusion.

## Consequences
- `dss export` calcule la comparaison depuis `output/dss_results.csv`, qui doit donc contenir les colonnes de base. Pour que la garde de derive tourne en CI sans les fichiers Kaggle, quatre colonnes de niveau action sont ajoutees au fichier suivi : `down`, `yardsToGo`, `yardsToEndzone` (derivee) et `playResult`. L'ADR 0005 et la note de licence de l'export sont mis a jour pour dire exactement quels champs sont suivis ; les conditions de redistribution restent non verifiees.
- Le contrat de donnees passe en 1.2 (ajout de champs a `validation.model_comparison`, version mineure).
- `scikit-learn` devient une dependance de production, version fixee exactement.
- Limites assumees : un seul decoupage, modeles lineaires, une seule saison, environ 1700 actions de test ; un intervalle large qui contient 0 ne prouve pas l'absence d'effet, il dit que ce test ne le distingue pas de zero. Le resultat est publie tel quel, quel qu'il soit.
- Le choix `yardsToEndzone` au lieu de `absoluteYardlineNumber` est un ecart a la consigne initiale, justifie ci-dessus et decide avant tout calcul.

## Sources
1. [scikit-learn, LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html) - officiel - valeurs par defaut `C=1.0`, penalite `l2`, solveur `lbfgs` - a verifier a la version fixee
