# 04 — Intégrité des preuves par blockchain (BC03)

Traçabilité et intégrité des preuves de sécurité à deux niveaux : une chaîne de hash
locale en Python, et un smart contract déployé sur une blockchain Ethereum locale.

## Contenu

| Fichier | Rôle |
|---|---|
| `blockchain_audit.py` | Niveau 1 — génère un ledger local en chaînant les empreintes SHA-256 des preuves (mini-SIEM, Wazuh) |
| `blockchain_ledger.json`, `blockchain_summary.txt`, `blockchain_verification.txt` | Ledger produit et rapports de vérification |
| `hardhat/contracts/EvidenceRegistry.sol` | Niveau 2 — smart contract Solidity d'enregistrement d'empreintes |
| `hardhat/scripts/deploy.js` | Déploiement du contrat |
| `hardhat/scripts/registerEvidence.js` | Enregistrement des empreintes SHA-256 |
| `hardhat/scripts/verifyEvidence.js` | Vérification d'intégrité |
| `hardhat_*.json`, `hardhat_*.txt` | Preuves : adresse du contrat, transactions, vérification |

## Résultat clé

**216 blocs** dans le ledger régénéré (210 alertes hachées individuellement + synthèse
+ 5 preuves Wazuh). Vérification d'intégrité : **VALIDÉ**. Seules les empreintes
SHA-256 sont enregistrées — aucune donnée sensible n'est stockée on-chain.

## Contrôle d'accès

L'écriture dans `EvidenceRegistry` est restreinte au propriétaire via le modificateur
`onlyOwner` : seule l'adresse ayant déployé le contrat peut enregistrer une empreinte,
et la propriété est transférable via `transferOwnership`. La lecture reste ouverte, ce
qui permet à un tiers de vérifier une preuve sans pouvoir en ajouter. Les empreintes
enregistrées ne peuvent être ni modifiées ni supprimées.

## Limites assumées

Le réseau Hardhat utilisé est local et temporaire : il ne s'agit pas d'une blockchain
de production. La gouvernance des clés et la persistance du registre restent hors
périmètre ; une version industrialisée supposerait un réseau privé persistant, une
gestion sécurisée des clés et une gouvernance des nœuds.


## Exécution

```bash
# Niveau 1 — ledger Python
python blockchain_audit.py

# Niveau 2 — Hardhat
cd hardhat
npm install
npx hardhat node          # terminal 1 : réseau local
npx hardhat run scripts/deploy.js --network localhost
npx hardhat run scripts/registerEvidence.js --network localhost
npx hardhat run scripts/verifyEvidence.js --network localhost
```
