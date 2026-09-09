# Supervision : mini-SIEM applicatif et intégration Wazuh

## Contenu

- `config/local_rules.xml` — quatre règles de corrélation personnalisées
- `config/ossec-localfile.xml` — déclaration de la source de journaux JSON
- `config/docker-compose-volume.yml` — montage du répertoire de journaux

## Règles de détection

| ID | Niveau | Déclencheur |
|---|---|---|
| 100100 | 0 | Règle parente : événements émis par le prototype |
| 100101 | 10 | Alertes `ML_ANOMALY` du modèle Isolation Forest |
| 100102 | 12 | Transactions de sévérité `CRITICAL` |
| 100103 | 7 | Contextes inhabituels |

Les descriptions injectent dynamiquement `device_id` et `location`.

## Mise en œuvre

1. Ajouter le volume au `docker-compose.yml` du service `wazuh.manager`
2. Insérer le bloc `localfile` dans `ossec.conf`
3. Copier `local_rules.xml` dans `/var/ossec/etc/rules/`
4. Redémarrer le Manager
5. Valider avec `/var/ossec/bin/wazuh-logtest`

## Validation obtenue

Le décodeur JSON extrait les 17 champs de l'alerte, la règle 100101 se déclenche
au niveau 10, et le moteur conclut par `Alert to be generated`. Captures dans le
mémoire, annexe « Preuves de l'intégration Wazuh ».

## Limite assumée

L'exploitation en continu de la pile s'est heurtée à une contrainte matérielle :
l'indexation OpenSearch sature l'espace disque du poste utilisé en quelques
minutes. La remontée dans le tableau de bord sur une période prolongée n'a donc
pas été conduite.
