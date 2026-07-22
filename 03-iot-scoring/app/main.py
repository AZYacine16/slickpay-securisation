from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import json
import os

app = FastAPI(
    title="SlickPay IoT Security POC",
    description="POC IoT pour la détection de risque sur des transactions issues d'objets connectés.",
    version="1.0.0"
)

API_KEY = "slickpay-demo-key"
LOG_FILE = "logs/iot_events.jsonl"


class IoTPaymentEvent(BaseModel):
    device_id: str = Field(..., example="WATCH-001")
    user_id: str = Field(..., example="USR-1001")
    amount: float = Field(..., example=250.0)
    location: str = Field(..., example="Paris")
    transaction_type: str = Field(..., example="payment")
    timestamp: Optional[str] = Field(None, example="2026-04-27T14:30:00")


KNOWN_DEVICES = {
    "WATCH-001": {
        "user_id": "USR-1001",
        "usual_location": "Paris",
        "device_type": "smartwatch"
    },
    "PHONE-001": {
        "user_id": "USR-1001",
        "usual_location": "Paris",
        "device_type": "smartphone"
    },
    "POS-001": {
        "user_id": "MERCHANT-001",
        "usual_location": "Lyon",
        "device_type": "payment_terminal"
    }
}


def calculate_risk_score(event: IoTPaymentEvent):
    score = 0
    reasons = []

    device_info = KNOWN_DEVICES.get(event.device_id)

    if device_info is None:
        score += 35
        reasons.append("Dispositif inconnu")

    else:
        if device_info["user_id"] != event.user_id:
            score += 40
            reasons.append("Dispositif associé à un autre utilisateur")

        if device_info["usual_location"].lower() != event.location.lower():
            score += 20
            reasons.append("Localisation inhabituelle")

    if event.amount >= 1000:
        score += 35
        reasons.append("Montant très élevé")
    elif event.amount >= 300:
        score += 20
        reasons.append("Montant élevé")
    elif event.amount >= 100:
        score += 10
        reasons.append("Montant modéré")

    if event.transaction_type.lower() not in ["payment", "refund", "transfer"]:
        score += 15
        reasons.append("Type de transaction inhabituel")

    if not reasons:
        reasons.append("Comportement normal")

    score = min(score, 100)

    if score >= 70:
        decision = "BLOCKED"
    elif score >= 40:
        decision = "REVIEW"
    else:
        decision = "ACCEPTED"

    return score, decision, reasons


def write_log(event: IoTPaymentEvent, risk_score: int, decision: str, reasons: list):
    os.makedirs("logs", exist_ok=True)

    log_entry = {
        "received_at": datetime.utcnow().isoformat(),
        "event": event.model_dump(),
        "risk_score": risk_score,
        "decision": decision,
        "reasons": reasons
    }

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


@app.get("/")
def home():
    return {
        "message": "SlickPay IoT Security POC is running",
        "endpoint": "POST /iot/payment-event"
    }


@app.post("/iot/payment-event")
def receive_iot_payment_event(
    event: IoTPaymentEvent,
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    risk_score, decision, reasons = calculate_risk_score(event)
    write_log(event, risk_score, decision, reasons)

    return {
        "device_id": event.device_id,
        "user_id": event.user_id,
        "risk_score": risk_score,
        "decision": decision,
        "reasons": reasons
    }
