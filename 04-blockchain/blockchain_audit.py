#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
blockchain_audit.py

Preuve de concept blockchain légère pour SlickPay.

Objectif :
- Ne jamais stocker de données sensibles dans la blockchain locale.
- Stocker uniquement des empreintes SHA-256 de preuves techniques.
- Chaîner les blocs avec previous_hash.
- Vérifier ensuite :
  1. l'intégrité des blocs ;
  2. le chaînage entre blocs ;
  3. l'intégrité des fichiers de preuve Mini-SIEM et Wazuh.

Fichiers générés :
- logs/blockchain_ledger.json
- logs/blockchain_summary.txt
- logs/blockchain_verification.txt
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"

LEDGER_PATH = LOG_DIR / "blockchain_ledger.json"
SUMMARY_PATH = LOG_DIR / "blockchain_summary.txt"
VERIFICATION_PATH = LOG_DIR / "blockchain_verification.txt"


EVIDENCE_SOURCES = [
    {
        "path": "logs/siem_alerts.jsonl",
        "evidence_type": "MINI_SIEM_ALERT",
        "mode": "jsonl_lines",
        "description": "Alertes générées par le mini-SIEM applicatif",
    },
    {
        "path": "logs/siem_summary.txt",
        "evidence_type": "MINI_SIEM_SUMMARY",
        "mode": "file",
        "description": "Rapport de synthèse du mini-SIEM",
    },
    {
        "path": "logs/wazuh_compose_ps.txt",
        "evidence_type": "WAZUH_PROOF",
        "mode": "file",
        "description": "État des conteneurs Wazuh",
    },
    {
        "path": "logs/wazuh_dashboard_logs.txt",
        "evidence_type": "WAZUH_PROOF",
        "mode": "file",
        "description": "Journaux du Wazuh Dashboard",
    },
    {
        "path": "logs/wazuh_indexer_logs.txt",
        "evidence_type": "WAZUH_PROOF",
        "mode": "file",
        "description": "Journaux du Wazuh Indexer",
    },
    {
        "path": "logs/wazuh_manager_logs.txt",
        "evidence_type": "WAZUH_PROOF",
        "mode": "file",
        "description": "Journaux du Wazuh Manager",
    },
    {
        "path": "logs/wazuh_disk_state.txt",
        "evidence_type": "WAZUH_PROOF",
        "mode": "file",
        "description": "État disque après expérimentation Wazuh",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_json(data: Dict[str, Any]) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def compute_block_hash(block: Dict[str, Any]) -> str:
    block_without_hash = {
        key: value for key, value in block.items() if key != "block_hash"
    }
    return sha256_bytes(canonical_json(block_without_hash))


def extract_alert_metadata(line_bytes: bytes) -> Dict[str, Any]:
    """
    On extrait uniquement quelques métadonnées non sensibles si elles existent.
    Le contenu complet de l'alerte n'est jamais stocké dans la blockchain.
    """
    try:
        event = json.loads(line_bytes.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}

    allowed_keys = [
        "alert_id",
        "alert_type",
        "severity",
        "decision",
        "risk_score",
        "timestamp",
        "generated_at",
    ]

    return {
        key: event.get(key)
        for key in allowed_keys
        if key in event and event.get(key) is not None
    }


def collect_evidence_records() -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    records: List[Dict[str, Any]] = []
    missing_sources: List[Dict[str, str]] = []

    for source in EVIDENCE_SOURCES:
        relative_path = source["path"]
        path = BASE_DIR / relative_path

        if not path.exists():
            missing_sources.append(
                {
                    "path": relative_path,
                    "reason": "Fichier introuvable au moment de la génération",
                }
            )
            continue

        if source["mode"] == "file":
            records.append(
                {
                    "evidence_name": path.name,
                    "evidence_type": source["evidence_type"],
                    "source_path": relative_path,
                    "source_kind": "file",
                    "record_number": None,
                    "sha256": sha256_file(path),
                    "description": source["description"],
                    "metadata": {},
                }
            )

        elif source["mode"] == "jsonl_lines":
            lines = path.read_bytes().splitlines()

            if not lines:
                records.append(
                    {
                        "evidence_name": path.name,
                        "evidence_type": source["evidence_type"],
                        "source_path": relative_path,
                        "source_kind": "empty_jsonl_file",
                        "record_number": None,
                        "sha256": sha256_file(path),
                        "description": source["description"],
                        "metadata": {"note": "Fichier JSONL vide"},
                    }
                )
                continue

            for index, line_bytes in enumerate(lines, start=1):
                records.append(
                    {
                        "evidence_name": f"{path.name}:line_{index}",
                        "evidence_type": source["evidence_type"],
                        "source_path": relative_path,
                        "source_kind": "jsonl_line",
                        "record_number": index,
                        "sha256": sha256_bytes(line_bytes),
                        "description": source["description"],
                        "metadata": extract_alert_metadata(line_bytes),
                    }
                )

    return records, missing_sources


def generate_ledger() -> Dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    records, missing_sources = collect_evidence_records()

    blocks: List[Dict[str, Any]] = []
    previous_hash = "0" * 64

    for index, record in enumerate(records, start=1):
        block = {
            "index": index,
            "timestamp_utc": now_utc(),
            "evidence_name": record["evidence_name"],
            "evidence_type": record["evidence_type"],
            "source_path": record["source_path"],
            "source_kind": record["source_kind"],
            "record_number": record["record_number"],
            "description": record["description"],
            "metadata": record["metadata"],
            "sha256": record["sha256"],
            "previous_hash": previous_hash,
        }

        block["block_hash"] = compute_block_hash(block)
        blocks.append(block)
        previous_hash = block["block_hash"]

    ledger = {
        "ledger_version": "1.0",
        "project": "SlickPay IoT / Mini-SIEM / Wazuh blockchain audit PoC",
        "generated_at_utc": now_utc(),
        "hash_algorithm": "SHA-256",
        "privacy_note": (
            "Cette blockchain locale ne contient pas les données sensibles. "
            "Elle stocke uniquement des empreintes cryptographiques et des métadonnées minimales."
        ),
        "implementation_note": (
            "Il s'agit d'une preuve de concept locale basée sur une chaîne de hash, "
            "et non d'une blockchain distribuée de production."
        ),
        "blocks": blocks,
        "missing_sources": missing_sources,
    }

    LEDGER_PATH.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_summary(ledger)

    return ledger


def write_summary(ledger: Dict[str, Any]) -> None:
    blocks = ledger.get("blocks", [])
    missing_sources = ledger.get("missing_sources", [])

    counts_by_type: Dict[str, int] = {}
    for block in blocks:
        evidence_type = block["evidence_type"]
        counts_by_type[evidence_type] = counts_by_type.get(evidence_type, 0) + 1

    lines = []
    lines.append("=== Résumé de l'expérimentation blockchain locale ===")
    lines.append("")
    lines.append(f"Projet : {ledger.get('project')}")
    lines.append(f"Date de génération UTC : {ledger.get('generated_at_utc')}")
    lines.append(f"Algorithme de hash : {ledger.get('hash_algorithm')}")
    lines.append("")
    lines.append("Nature de l'expérimentation :")
    lines.append("- preuve de concept locale ;")
    lines.append("- chaîne de hash légère ;")
    lines.append("- aucune donnée sensible stockée dans la blockchain ;")
    lines.append("- stockage uniquement des empreintes SHA-256 des preuves.")
    lines.append("")
    lines.append(f"Nombre total de blocs générés : {len(blocks)}")
    lines.append("")

    lines.append("Répartition des blocs par type de preuve :")
    if counts_by_type:
        for evidence_type, count in sorted(counts_by_type.items()):
            lines.append(f"- {evidence_type} : {count}")
    else:
        lines.append("- Aucun bloc généré")

    lines.append("")
    lines.append("Fichiers absents au moment de la génération :")
    if missing_sources:
        for source in missing_sources:
            lines.append(f"- {source['path']} : {source['reason']}")
    else:
        lines.append("- Aucun fichier attendu n'est absent")

    lines.append("")
    if blocks:
        lines.append(f"Premier hash de bloc : {blocks[0]['block_hash']}")
        lines.append(f"Dernier hash de bloc : {blocks[-1]['block_hash']}")

    lines.append("")
    lines.append("Conclusion :")
    lines.append(
        "La chaîne générée permet de démontrer le principe d'intégrité et de traçabilité "
        "des preuves Mini-SIEM et Wazuh dans le cadre d'une simulation blockchain locale."
    )

    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def verify_evidence_hash(block: Dict[str, Any]) -> Tuple[bool, str]:
    path = BASE_DIR / block["source_path"]

    if not path.exists():
        return False, "Fichier source introuvable"

    expected_hash = block["sha256"]
    source_kind = block["source_kind"]

    if source_kind == "file":
        actual_hash = sha256_file(path)

    elif source_kind == "empty_jsonl_file":
        actual_hash = sha256_file(path)

    elif source_kind == "jsonl_line":
        record_number = block.get("record_number")
        if not isinstance(record_number, int) or record_number <= 0:
            return False, "Numéro de ligne invalide dans le bloc"

        lines = path.read_bytes().splitlines()

        if record_number > len(lines):
            return False, "Ligne JSONL introuvable dans le fichier actuel"

        actual_hash = sha256_bytes(lines[record_number - 1])

    else:
        return False, f"Type de source inconnu : {source_kind}"

    if actual_hash != expected_hash:
        return False, "Hash de preuve différent : le fichier ou la ligne semble modifié"

    return True, "Hash de preuve valide"


def verify_ledger() -> Tuple[bool, List[str]]:
    if not LEDGER_PATH.exists():
        return False, [f"Ledger introuvable : {LEDGER_PATH}"]

    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    blocks = ledger.get("blocks", [])

    messages: List[str] = []
    global_status = True

    if not blocks:
        global_status = False
        messages.append("Aucun bloc présent dans le ledger.")

    for index, block in enumerate(blocks):
        block_number = block.get("index", index + 1)

        expected_block_hash = compute_block_hash(block)
        stored_block_hash = block.get("block_hash")

        if expected_block_hash != stored_block_hash:
            global_status = False
            messages.append(
                f"[ERREUR] Bloc {block_number} : hash du bloc invalide."
            )
        else:
            messages.append(
                f"[OK] Bloc {block_number} : hash du bloc correct."
            )

        if index == 0:
            expected_previous_hash = "0" * 64
        else:
            expected_previous_hash = blocks[index - 1].get("block_hash")

        if block.get("previous_hash") != expected_previous_hash:
            global_status = False
            messages.append(
                f"[ERREUR] Bloc {block_number} : previous_hash invalide."
            )
        else:
            messages.append(
                f"[OK] Bloc {block_number} : chaînage previous_hash correct."
            )

        evidence_ok, evidence_message = verify_evidence_hash(block)

        if not evidence_ok:
            global_status = False
            messages.append(
                f"[ERREUR] Bloc {block_number} : {evidence_message}"
            )
        else:
            messages.append(
                f"[OK] Bloc {block_number} : {evidence_message}"
            )

    return global_status, messages


def write_verification_report() -> bool:
    status, messages = verify_ledger()

    lines = []
    lines.append("=== Vérification de la blockchain locale ===")
    lines.append("")
    lines.append(f"Date de vérification UTC : {now_utc()}")
    lines.append(f"Ledger vérifié : {LEDGER_PATH}")
    lines.append("")
    lines.append("Résultat global :")
    lines.append("VALIDÉ" if status else "INVALIDE")
    lines.append("")
    lines.append("Détails :")
    lines.extend(messages)
    lines.append("")

    if status:
        lines.append(
            "Conclusion : la chaîne de blocs locale est cohérente et les preuves "
            "n'ont pas été modifiées depuis la génération du ledger."
        )
    else:
        lines.append(
            "Conclusion : une incohérence a été détectée. Elle peut provenir d'une "
            "modification du ledger, d'une rupture du chaînage ou d'une altération "
            "d'un fichier de preuve."
        )

    VERIFICATION_PATH.write_text("\n".join(lines), encoding="utf-8")

    return status


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blockchain locale de preuves pour SlickPay"
    )

    parser.add_argument(
        "command",
        choices=["generate", "verify"],
        help="generate : génère le ledger ; verify : vérifie l'intégrité",
    )

    args = parser.parse_args()

    if args.command == "generate":
        ledger = generate_ledger()
        print("[OK] Blockchain locale générée.")
        print(f"[OK] Ledger : {LEDGER_PATH}")
        print(f"[OK] Résumé : {SUMMARY_PATH}")
        print(f"[INFO] Nombre de blocs : {len(ledger.get('blocks', []))}")

        if ledger.get("missing_sources"):
            print("[INFO] Certains fichiers attendus sont absents.")
            print("[INFO] Ils sont listés dans blockchain_summary.txt.")

    elif args.command == "verify":
        status = write_verification_report()

        if status:
            print("[OK] Blockchain locale valide.")
        else:
            print("[ERREUR] Blockchain locale invalide.")

        print(f"[OK] Rapport de vérification : {VERIFICATION_PATH}")


if __name__ == "__main__":
    main()
