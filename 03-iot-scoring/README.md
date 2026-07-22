# 03 — Dispositif IoT sécurisé & supervision (BC03 · BC04)

Chaîne complète : un simulateur envoie des événements de paiement à une API qui
calcule un score de risque, un modèle non supervisé détecte les anomalies, et un
mini-SIEM transforme le tout en alertes qualifiées.

## Contenu

| Fichier | Rôle |
|---|---|
| `app/main.py` | API FastAPI sécurisée par clé, scoring de risque par règles pondérées, décisions ACCEPTED / REVIEW / BLOCKED |
| `iot_device_simulator.py` | Simulateur de dispositif IoT (200 événements sur 5 profils utilisateurs) |
| `iot_ml_detection.py` | Détection d'anomalies non supervisée (Isolation Forest) |
| `mini_siem.py` | Analyse des journaux, génération d'alertes (UNUSUAL, SUSPICIOUS, HIGH_RISK, ML_ANOMALY) et rapport de synthèse |
| `logs/` | Journaux de preuve : événements, scores ML, alertes, synthèses |
| `requirements.txt` | Dépendances Python |

## Résultat clé

Sur 200 événements : **210 alertes** (180 issues des règles, 30 du modèle ML).
Le modèle converge avec le moteur de règles sur **27 des 30 anomalies** (validation
croisée), et détecte **3 cas** que les règles avaient acceptés. La chaîne
événement → score ML → alerte `ML_ANOMALY` matérialise la cybersécurité par l'IA (BC04).

## Sécurité

L'API est protégée par une clé de démonstration (`slickpay-demo-key`). En production,
cette clé serait gérée via une variable d'environnement ou un gestionnaire de secrets.

## Exécution

```bash
pip install -r requirements.txt

# Terminal 1 — lancer l'API
uvicorn app.main:app --reload

# Terminal 2 — envoyer les événements, puis analyser
python iot_device_simulator.py
python iot_ml_detection.py
python mini_siem.py
```
