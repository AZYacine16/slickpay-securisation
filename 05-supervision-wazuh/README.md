# 05 — Supervision Wazuh (BC03)

Preuves du déploiement expérimental de Wazuh (SIEM open source) en local via Docker
Compose, en complément du mini-SIEM applicatif.

> **Note** : ce dossier ne contient pas le code de Wazuh (dépôt officiel `wazuh-docker`),
> mais uniquement les **preuves** du déploiement réalisé dans le cadre du mémoire.

## Contenu

| Fichier | Rôle |
|---|---|
| `wazuh_compose_ps.txt` | État des conteneurs (Manager, Indexer, Dashboard) |
| `wazuh_manager_logs.txt` | Journaux du Wazuh Manager |
| `wazuh_indexer_logs.txt` | Journaux de l'Indexer (cluster OpenSearch GREEN) |
| `wazuh_dashboard_logs.txt` | Journaux du Dashboard |
| `wazuh_disk_state.txt`, `wazuh_docker_disk_usage.txt` | Consommation disque après expérimentation |

## Déploiement (rappel)

Wazuh a été déployé à partir du dépôt officiel :

```bash
git clone https://github.com/wazuh/wazuh-docker.git
cd wazuh-docker/single-node
docker compose -f generate-indexer-certs.yml run --rm generator
docker compose up -d
```

Dashboard accessible sur `https://localhost`. Le cluster OpenSearch était en état
`GREEN`, confirmant l'initialisation correcte des composants.

## Trajectoire d'intégration

Les journaux applicatifs de SlickPay étant au format JSON (`iot_events.jsonl`,
`siem_alerts.jsonl`), leur ingestion reposerait sur un agent Wazuh et un décodeur JSON
côté Manager, avec des règles de corrélation attribuant un niveau de criticité aux
alertes `ML_ANOMALY`.
