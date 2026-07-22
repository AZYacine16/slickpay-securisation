# 02 — Détection de fraude transactionnelle (BC02)

Comparaison de quatre modèles d'apprentissage automatique sur le dataset PaySim, avec
analyse d'explicabilité SHAP.

## Contenu

| Fichier | Rôle |
|---|---|
| `analyse_fraude_rf.py` | Préparation des données, entraînement et comparaison des modèles, courbe ROC, matrice de confusion, analyse SHAP |
| `resultats_analyse_rf.txt` | Métriques comparées (rappel, précision, exactitude, F1) |
| `roc_random_forest.png` | Courbe ROC du Random Forest (AUC 0,9993) |
| `matrice_confusion_rf.png` | Matrice de confusion sur 6 571 transactions de test |
| `shap_summary_rf.png` | Contributions SHAP des variables |

## Résultat clé

| Modèle | F1-score |
|---|---|
| Random Forest | 98,04 % |
| MLP | 96,55 % |
| Régression logistique | 80,71 % |
| Isolation Forest | 32,43 % |

Les colonnes d'identification directe (`nameOrig`, `nameDest`, `isFlaggedFraud`) sont
retirées pour éviter toute fuite d'information. L'analyse SHAP montre que la décision
repose sur la dynamique des soldes du compte émetteur, pas sur le montant seul —
réponse concrète à l'exigence d'explicabilité de l'article 22 du RGPD.

## Données requises

Le fichier `PS_*.csv` (~470 Mo) n'est pas inclus. Le télécharger sur Kaggle
(*PaySim1*) et le placer dans ce dossier.

## Exécution

```bash
pip install pandas numpy scikit-learn matplotlib shap imbalanced-learn
python analyse_fraude_rf.py
```
