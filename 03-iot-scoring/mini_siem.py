import json
import os
from datetime import datetime, timezone
from collections import Counter

INPUT_LOG = "logs/iot_events.jsonl"
ALERT_LOG = "logs/siem_alerts.jsonl"
SUMMARY_FILE = "logs/siem_summary.txt"
ML_SCORES_LOG = "logs/iot_ml_scores.jsonl"

ML_SEVERITY_THRESHOLD = -0.05


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def load_events():
    events = []

    if not os.path.exists(INPUT_LOG):
        print(f"Fichier introuvable : {INPUT_LOG}")
        return events

    with open(INPUT_LOG, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Ligne ignorée : JSON invalide à la ligne {line_number}")

    return events


def classify_alert(log_entry, index):
    event = log_entry.get("event", {})
    risk_score = log_entry.get("risk_score", 0)
    decision = log_entry.get("decision", "UNKNOWN")
    reasons = log_entry.get("reasons", [])

    device_id = event.get("device_id", "UNKNOWN_DEVICE")
    user_id = event.get("user_id", "UNKNOWN_USER")
    amount = event.get("amount", 0)
    location = event.get("location", "UNKNOWN_LOCATION")

    reasons_text = " ".join(reasons).lower()

    alert_type = None
    severity = None
    description = None

    if decision == "BLOCKED" or risk_score >= 70:
        alert_type = "HIGH_RISK_TRANSACTION"
        severity = "CRITICAL"
        description = "Transaction critique détectée par le moteur de scoring."

    elif decision == "REVIEW" or risk_score >= 40:
        alert_type = "SUSPICIOUS_TRANSACTION"
        severity = "HIGH"
        description = "Transaction suspecte nécessitant une vérification complémentaire."

    elif "localisation inhabituelle" in reasons_text or risk_score >= 30:
        alert_type = "UNUSUAL_CONTEXT"
        severity = "MEDIUM"
        description = "Contexte inhabituel détecté pour une transaction."

    if alert_type is None:
        return None

    alert = {
        "alert_id": f"SIEM-{index:04d}",
        "generated_at": now_utc(),
        "source": "SlickPay IoT Security POC",
        "alert_type": alert_type,
        "severity": severity,
        "description": description,
        "device_id": device_id,
        "user_id": user_id,
        "amount": amount,
        "location": location,
        "risk_score": risk_score,
        "decision": decision,
        "reasons": reasons,
        "source_event_time": event.get("timestamp"),
        "source_received_at": log_entry.get("received_at")
    }

    return alert


def build_ml_alerts(start_index):
    """Génère des alertes à partir des anomalies détectées par Isolation Forest."""
    ml_alerts = []

    if not os.path.exists(ML_SCORES_LOG):
        print(f"Scores ML introuvables ({ML_SCORES_LOG}) : alertes ML ignorées.")
        return ml_alerts

    index = start_index

    with open(ML_SCORES_LOG, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if int(entry.get("ml_anomalie", 0)) != 1:
                continue

            ml_score = float(entry.get("ml_score", 0))
            reasons = entry.get("reasons", "")
            if isinstance(reasons, str):
                reasons = [r.strip() for r in reasons.split("|") if r.strip()]

            ml_alerts.append({
                "alert_id": f"SIEM-ML-{index:04d}",
                "generated_at": now_utc(),
                "source": "SlickPay IoT Security POC - Isolation Forest",
                "alert_type": "ML_ANOMALY",
                "severity": "HIGH" if ml_score < ML_SEVERITY_THRESHOLD else "MEDIUM",
                "description": ("Anomalie comportementale détectée par le modèle "
                                "Isolation Forest, indépendamment du moteur de règles."),
                "device_id": entry.get("device_id", "UNKNOWN_DEVICE"),
                "user_id": entry.get("user_id", "UNKNOWN_USER"),
                "amount": entry.get("amount", 0),
                "location": entry.get("location", "UNKNOWN_LOCATION"),
                "risk_score": entry.get("risk_score", 0),
                "decision": entry.get("decision", "UNKNOWN"),
                "reasons": reasons,
                "ml_score": ml_score,
                "source_event_time": entry.get("timestamp"),
                "source_received_at": entry.get("received_at")
            })
            index += 1

    return ml_alerts


def write_alerts(alerts):
    os.makedirs("logs", exist_ok=True)

    with open(ALERT_LOG, "w", encoding="utf-8") as file:
        for alert in alerts:
            file.write(json.dumps(alert, ensure_ascii=False) + "\n")


def write_summary(events, alerts):
    severity_count = Counter(alert["severity"] for alert in alerts)
    type_count = Counter(alert["alert_type"] for alert in alerts)
    decision_count = Counter(event.get("decision", "UNKNOWN") for event in events)

    rules_alerts = [a for a in alerts if a["alert_type"] != "ML_ANOMALY"]
    ml_alerts = [a for a in alerts if a["alert_type"] == "ML_ANOMALY"]
    ml_only = [a for a in ml_alerts if a.get("decision") == "ACCEPTED"]

    with open(SUMMARY_FILE, "w", encoding="utf-8") as file:
        file.write("=== Mini-SIEM SlickPay - Rapport de synthèse ===\n\n")
        file.write(f"Nombre total d'événements analysés : {len(events)}\n")
        file.write(f"Nombre total d'alertes générées : {len(alerts)}\n")
        file.write(f"  - Alertes issues du moteur de règles : {len(rules_alerts)}\n")
        file.write(f"  - Alertes issues du modèle Isolation Forest : {len(ml_alerts)}\n\n")

        file.write("Répartition par décision :\n")
        for decision, count in decision_count.items():
            file.write(f"- {decision} : {count}\n")

        file.write("\nRépartition par sévérité :\n")
        for severity, count in severity_count.items():
            file.write(f"- {severity} : {count}\n")

        file.write("\nRépartition par type d'alerte :\n")
        for alert_type, count in type_count.items():
            file.write(f"- {alert_type} : {count}\n")

        file.write("\nApport du modèle d'apprentissage automatique :\n")
        file.write(f"- Anomalies ML sur des transactions acceptées par les règles : "
                   f"{len(ml_only)}\n")

        file.write("\nConclusion :\n")
        if severity_count.get("CRITICAL", 0) > 0:
            file.write("Des transactions critiques ont été détectées et doivent être traitées en priorité.\n")
        elif severity_count.get("HIGH", 0) > 0:
            file.write("Des transactions suspectes nécessitent une vérification complémentaire.\n")
        else:
            file.write("Aucune alerte critique ou élevée n'a été détectée.\n")


def main():
    events = load_events()
    alerts = []

    for index, log_entry in enumerate(events, start=1):
        alert = classify_alert(log_entry, index)
        if alert:
            alerts.append(alert)

    rules_count = len(alerts)

    ml_alerts = build_ml_alerts(start_index=1)
    alerts.extend(ml_alerts)

    write_alerts(alerts)
    write_summary(events, alerts)

    print("=== Mini-SIEM SlickPay ===")
    print(f"Événements analysés : {len(events)}")
    print(f"Alertes générées : {len(alerts)}")
    print(f"  - moteur de règles : {rules_count}")
    print(f"  - Isolation Forest (ML_ANOMALY) : {len(ml_alerts)}")
    print(f"Fichier d'alertes : {ALERT_LOG}")
    print(f"Rapport de synthèse : {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
