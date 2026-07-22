# 01 — Vérification d'identité KYC (BC02)

Comparaison biométrique entre un document d'identité et un selfie, et évaluation
critique de deux approches : descripteurs ORB (pipeline du prototype) et embeddings
faciaux FaceNet.

## Contenu

| Fichier | Rôle |
|---|---|
| `comparaison_kyc.py` | Pipeline ORB : détection faciale, extraction de descripteurs, appariement, règle de décision à double condition (score ≥ 75 % ET ≥ 20 correspondances) |
| `evaluation_corpus_kyc.py` / `evaluation_corpus_kyc_v2.py` | Évaluation ORB vs FaceNet sur le corpus LFW (182 paires) |
| `resultats_comparaison_kyc.txt` | Résultats sur les 3 paires de démonstration |
| `resultats_corpus_kyc.txt` | Métriques sur LFW (AUC, EER, précision, rappel) |
| `roc_kyc_comparaison.png`, `distributions_scores_kyc.png` | Courbes ROC et distributions de scores |
| `ID.png`, `sel.png`, `photo.jpg`, `Carte-Identite.jpg` | Images de test |

## Résultat clé

Sur 182 paires du corpus LFW : ORB obtient une **AUC de 0,566** (proche du hasard),
FaceNet une **AUC de 0,956**. La mesure démontre qu'ORB, conçu pour des objets rigides,
n'est pas adapté à la vérification biométrique — d'où la trajectoire vers un modèle
d'embeddings en production.

## Exécution

```bash
pip install opencv-python numpy scikit-learn matplotlib
python comparaison_kyc.py
python evaluation_corpus_kyc_v2.py   # nécessite corpus_lfw/ (voir README racine)
```
