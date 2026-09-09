# 05 — Supervision : mini-SIEM applicatif et intégration Wazuh (BC03)

Configuration et preuves de l'intégration de Wazuh (SIEM open source) déployé en
local via Docker Compose, en complément du mini-SIEM applicatif développé en Python.

> **Note** : ce dossier ne contient pas le code de Wazuh (dépôt officiel `wazuh-docker`),
> mais la **configuration** écrite pour ce projet et les **preuves** du déploiement.

## Configuration

| Fichier | Rôle |
|---|---|
| `config/local_rules.xml` | Quatre règles de corrélation personnalisées |
| `config/ossec-localfile.xml` | Déclaration de la source de journaux JSON |
| `config/docker-compose-volume.yml` | Montage du répertoire de journaux du prototype |

### Règles de détection

| ID | Niveau | Déclencheur |
|---|---|---|
| 100100 | 0 | Règle parente : événements émis par le prototype |
| 100101 | 10 | Alertes `ML_ANOMALY` du modèle Isolation Forest |
| 100102 | 12 | Transactions de sévérité `CRITICAL` |
| 100103 | 7 | Contextes inhabituels |

Les descriptions injectent dynamiquement `device_id` et `location`, afin de rendre
la remontée directement exploitable par un analyste.

## Preuves du déploiement

| Fichier | Rôle |
|---|---|
| `wazuh_compose_ps.txt` | État des conteneurs (Manager, Indexer, Dashboard) |
| `wazuh_manager_logs.txt` | Journaux du Wazuh Manager |
| `wazuh_indexer_logs.txt` | Journaux de l'Indexer (cluster OpenSearch GREEN) |
| `wazuh_dashboard_logs.txt` | Journaux du Dashboard |
| `wazuh_disk_state.txt`, `wazuh_docker_disk_usage.txt` | Consommation disque après expérimentation |

## Mise en œuvre

Déploiement depuis le dépôt officiel :

```bash
git clone https://github.com/wazuh/wazuh-docker.git
cd wazuh-docker/single-node
docker compose -f generate-indexer-certs.yml run --rm generator
docker compose up -d
```

Puis, pour l'intégration :

1. Ajouter le volume au `docker-compose.yml` du service `wazuh.manager`
2. Insérer le bloc `localfile` dans `ossec.conf`
3. Copier `local_rules.xml` dans `/var/ossec/etc/rules/`
4. Redémarrer le Manager
5. Valider avec `/var/ossec/bin/wazuh-logtest`

Dashboard accessible sur `https://localhost`.

## Validation obtenue

Le décodeur JSON extrait les 17 champs de l'alerte, la règle 100101 se déclenche
au niveau 10 avec une description enrichie du `device_id`, et le moteur conclut par
`Alert to be generated`. Captures dans le mémoire, annexe « Preuves de
l'intégration Wazuh ».

## Limite assumée

L'exploitation en continu de la pile s'est heurtée à une contrainte matérielle :
l'indexation OpenSearch sature l'espace disque du poste utilisé en quelques
minutes. La remontée dans le tableau de bord sur une période prolongée n'a donc
pas été conduite. Une exploitation réelle supposerait une infrastructure dédiée,
un agent déployé sur le parc et une politique de rétention des index.
