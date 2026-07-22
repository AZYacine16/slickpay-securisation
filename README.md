# Sécurisation d'un système d'information de paiement électronique par l'IA

Code source des expérimentations du mémoire de fin d'études — Titre RNCP niveau 7,
**Expert en Systèmes d'Information et Sécurité (RNCP39394)**, ESIC Paris.

**Auteur :** Yacine Azougli — **Année :** 2025–2026

Ce dépôt regroupe les preuves de concept développées pour démontrer la faisabilité
d'une approche de sécurisation multicouche (défense en profondeur) appliquée à une
application de paiement électronique. Il ne s'agit pas d'une solution de production,
mais d'un ensemble d'expérimentations rattachées aux blocs de compétences du référentiel.

---

## Organisation du dépôt

| Dossier | Brique | Bloc RNCP |
|---|---|---|
| [`01-kyc-biometrie`](01-kyc-biometrie) | Vérification d'identité KYC (ORB vs FaceNet, évaluation LFW) | BC02 |
| [`02-detection-fraude`](02-detection-fraude) | Détection de fraude transactionnelle sur PaySim | BC02 |
| [`03-iot-scoring`](03-iot-scoring) | Simulateur IoT, API de scoring, mini-SIEM, détection ML | BC03 · BC04 |
| [`04-blockchain`](04-blockchain) | Intégrité des preuves : ledger Python + smart contract Hardhat | BC03 |
| [`05-supervision-wazuh`](05-supervision-wazuh) | Preuves du déploiement expérimental Wazuh | BC03 |

Chaque dossier contient son propre `README.md` décrivant son rôle, ses dépendances
et la manière de l'exécuter.

---

## Données non incluses

Deux jeux de données ne sont pas versionnés (volume / licence). Ils doivent être
téléchargés séparément :

- **PaySim** (`02-detection-fraude`) — dataset de ~470 Mo.
  Disponible sur Kaggle : *PaySim1 — Synthetic Financial Datasets For Fraud Detection*.
  Placer le fichier `PS_*.csv` dans `02-detection-fraude/`.
- **LFW** (`01-kyc-biometrie`) — corpus *Labeled Faces in the Wild*.
  Disponible sur le site de l'Université du Massachusetts (vis-lab / lfw).
  Placer les images dans `01-kyc-biometrie/corpus_lfw/`.

---

## Avertissement de sécurité

Ces expérimentations sont des **preuves de concept académiques**. Elles comportent des
simplifications assumées et documentées dans le mémoire (chapitre 4, section « Limites
assumées »), notamment :

- la clé d'API du prototype IoT est une clé de démonstration (`slickpay-demo-key`) ;
- le smart contract `EvidenceRegistry` ne restreint pas l'écriture à une identité
  autorisée (pas de mécanisme `onlyOwner`) — limite identifiée et destinée à une
  version industrialisée ;
- le déploiement AWS et le réseau blockchain Hardhat sont locaux et temporaires.

Ne pas réutiliser en l'état dans un environnement de production.
