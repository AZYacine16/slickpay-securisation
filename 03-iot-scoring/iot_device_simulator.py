#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulation d'un dispositif IoT de paiement — SlickPay.

VERSION ÉTENDUE : génère un volume d'événements suffisant pour permettre
l'application d'un modèle d'apprentissage automatique (Isolation Forest)
sur les journaux produits.

Deux phases :
  1. Les 5 scénarios de démonstration d'origine, envoyés et affichés en détail
     (ce sont les cas présentés dans le tableau 4.3 du mémoire).
  2. Un volume complémentaire d'événements générés aléatoirement autour de
     profils d'usage réalistes : majorité de comportements normaux, minorité
     de comportements atypiques.

Prérequis : l'API FastAPI doit être en cours d'exécution sur le port 8000.

Usage :  python iot_device_simulator.py
"""

import json
import random
import time
from datetime import datetime, timedelta, timezone

import requests

API_URL = "http://127.0.0.1:8000/iot/payment-event"
API_KEY = "slickpay-demo-key"

headers = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY,
}

# Nombre total d'événements générés en phase 2
NB_EVENEMENTS_ALEATOIRES = 195

# Pause entre deux envois (0.05 s => ~10 s pour 195 événements)
PAUSE_PHASE_2 = 0.05


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def horodatage_aleatoire():
    """Retourne un horodatage réparti sur les 30 derniers jours.

    Les heures suivent une distribution réaliste : la majorité des paiements
    a lieu en journée, une minorité la nuit (comportement plus atypique).
    """
    base = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))
    if random.random() < 0.85:
        heure = random.randint(8, 21)      # heures ouvrées : cas courant
    else:
        heure = random.choice([0, 1, 2, 3, 4, 5, 23])  # nuit : plus rare
    return base.replace(hour=heure,
                        minute=random.randint(0, 59),
                        second=random.randint(0, 59)).isoformat()


# ---------------------------------------------------------------------------
# PHASE 1 — Scénarios de démonstration (inchangés)
# ---------------------------------------------------------------------------
evenements_demo = [
    {
        "device_id": "WATCH-001",
        "user_id": "USR-1001",
        "amount": 25.50,
        "location": "Paris",
        "transaction_type": "payment",
        "timestamp": utc_now(),
    },
    {
        "device_id": "PHONE-001",
        "user_id": "USR-1001",
        "amount": 320.00,
        "location": "Paris",
        "transaction_type": "payment",
        "timestamp": utc_now(),
    },
    {
        "device_id": "WATCH-001",
        "user_id": "USR-1001",
        "amount": 180.00,
        "location": "Marseille",
        "transaction_type": "payment",
        "timestamp": utc_now(),
    },
    {
        "device_id": "UNKNOWN-999",
        "user_id": "USR-1001",
        "amount": 850.00,
        "location": "Marseille",
        "transaction_type": "payment",
        "timestamp": utc_now(),
    },
    {
        "device_id": "WATCH-001",
        "user_id": "USR-9999",
        "amount": 1200.00,
        "location": "Berlin",
        "transaction_type": "payment",
        "timestamp": utc_now(),
    },
]


# ---------------------------------------------------------------------------
# PHASE 2 — Génération d'un volume d'événements réalistes
# ---------------------------------------------------------------------------
# Profils d'utilisateurs : chaque utilisateur possède ses dispositifs habituels
# et ses localisations habituelles. Un événement s'écartant de ce profil
# constitue une anomalie potentielle.
PROFILS = {
    "USR-1001": {"dispositifs": ["WATCH-001", "PHONE-001"],
                 "villes": ["Paris", "Marseille"]},
    "USR-1002": {"dispositifs": ["PHONE-002"],
                 "villes": ["Lyon"]},
    "USR-1003": {"dispositifs": ["WATCH-003", "PHONE-003"],
                 "villes": ["Toulouse", "Bordeaux"]},
    "USR-1004": {"dispositifs": ["PHONE-004"],
                 "villes": ["Lille"]},
    "USR-1005": {"dispositifs": ["WATCH-005"],
                 "villes": ["Nice"]},
}

VILLES_INHABITUELLES = ["Berlin", "Dubai", "Moscou", "Lagos", "Bangkok"]
DISPOSITIFS_INCONNUS = ["UNKNOWN-999", "UNKNOWN-777", "TERM-XX01"]
TYPES_TRANSACTION = ["payment", "transfer", "withdrawal"]


def generer_evenement_aleatoire():
    """Génère un événement selon une distribution réaliste.

    ~78 % de comportements normaux, ~22 % de comportements atypiques répartis
    entre montant élevé, localisation inhabituelle, dispositif inconnu et
    incohérence utilisateur/dispositif.
    """
    user_id = random.choice(list(PROFILS.keys()))
    profil = PROFILS[user_id]
    tirage = random.random()

    if tirage < 0.78:
        # Comportement normal : dispositif et ville habituels, petit montant
        device_id = random.choice(profil["dispositifs"])
        location = random.choice(profil["villes"])
        amount = round(random.uniform(5, 250), 2)

    elif tirage < 0.86:
        # Montant élevé depuis un dispositif habituel
        device_id = random.choice(profil["dispositifs"])
        location = random.choice(profil["villes"])
        amount = round(random.uniform(800, 3000), 2)

    elif tirage < 0.92:
        # Localisation inhabituelle
        device_id = random.choice(profil["dispositifs"])
        location = random.choice(VILLES_INHABITUELLES)
        amount = round(random.uniform(50, 900), 2)

    elif tirage < 0.97:
        # Dispositif inconnu
        device_id = random.choice(DISPOSITIFS_INCONNUS)
        location = random.choice(profil["villes"] + VILLES_INHABITUELLES)
        amount = round(random.uniform(200, 2000), 2)

    else:
        # Cas critique : dispositif appartenant à un autre utilisateur,
        # localisation inhabituelle et montant très élevé
        autre = random.choice([u for u in PROFILS if u != user_id])
        device_id = random.choice(PROFILS[autre]["dispositifs"])
        location = random.choice(VILLES_INHABITUELLES)
        amount = round(random.uniform(3000, 8000), 2)

    return {
        "device_id": device_id,
        "user_id": user_id,
        "amount": amount,
        "location": location,
        "transaction_type": random.choice(TYPES_TRANSACTION),
        "timestamp": horodatage_aleatoire(),
    }


def envoyer(event):
    """Envoie un événement à l'API et retourne la réponse JSON (ou None)."""
    try:
        reponse = requests.post(API_URL, headers=headers, json=event, timeout=5)
        return reponse.json()
    except requests.exceptions.RequestException as erreur:
        print(f"Erreur lors de l'envoi de l'événement : {erreur}")
        return None


def main():
    random.seed(42)  # reproductibilité des résultats présentés dans le mémoire

    print("=== Simulation d'un objet connecté SlickPay ===\n")
    print("--- PHASE 1 : scénarios de démonstration ---\n")

    for index, event in enumerate(evenements_demo, start=1):
        print(f"--- Événement IoT #{index} ---")
        print("Événement envoyé :")
        print(json.dumps(event, indent=2, ensure_ascii=False))

        reponse = envoyer(event)
        if reponse is not None:
            print("\nRéponse de l'API :")
            print(json.dumps(reponse, indent=2, ensure_ascii=False))
        print("\n")
        time.sleep(1)

    print(f"--- PHASE 2 : génération de {NB_EVENEMENTS_ALEATOIRES} "
          "événements complémentaires ---\n")

    compteur = {"ACCEPTED": 0, "REVIEW": 0, "BLOCKED": 0}
    erreurs = 0

    for i in range(1, NB_EVENEMENTS_ALEATOIRES + 1):
        event = generer_evenement_aleatoire()
        reponse = envoyer(event)

        if reponse is None:
            erreurs += 1
        else:
            decision = reponse.get("decision", "INCONNU")
            compteur[decision] = compteur.get(decision, 0) + 1

        if i % 25 == 0:
            print(f"  {i}/{NB_EVENEMENTS_ALEATOIRES} événements envoyés...")

        time.sleep(PAUSE_PHASE_2)

    total = len(evenements_demo) + NB_EVENEMENTS_ALEATOIRES
    print("\n=== Synthèse de la simulation ===")
    print(f"Événements de démonstration : {len(evenements_demo)}")
    print(f"Événements complémentaires  : {NB_EVENEMENTS_ALEATOIRES}")
    print(f"Total envoyé                : {total}")
    if erreurs:
        print(f"Échecs d'envoi              : {erreurs}")
    print("\nRépartition des décisions (phase 2) :")
    for decision, nombre in compteur.items():
        print(f"  {decision:<10} : {nombre}")
    print("\nÉtape suivante : python iot_ml_detection.py")


if __name__ == "__main__":
    main()
