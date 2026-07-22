#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Détection d'anomalies par IA (Isolation Forest) sur les événements IoT — SlickPay.

VERSION ADAPTÉE à la structure réelle de logs/iot_events.jsonl :
les champs métier sont imbriqués dans un sous-objet "event".

Objectif (BC04) : appliquer un modèle d'apprentissage automatique non supervisé
aux événements du dispositif IoT simulé, en complément du scoring par règles.
Le modèle N'UTILISE PAS risk_score ni decision : il est volontairement
indépendant du moteur de règles, pour éviter toute circularité.

Entrée  : logs/iot_events.jsonl
Sorties : logs/iot_ml_scores.jsonl   (événements aplatis + ml_score + ml_anomalie)
          logs/iot_ml_summary.txt    (rapport de synthèse -> capture pour A.4)

Usage :  python iot_ml_detection.py
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# --------------------------------- CONFIG ---------------------------------
FICHIER_EVENEMENTS = Path("logs/iot_events.jsonl")
FICHIER_SCORES     = Path("logs/iot_ml_scores.jsonl")
FICHIER_SYNTHESE   = Path("logs/iot_ml_summary.txt")

CONTAMINATION = 0.15   # proportion attendue d'anomalies (15 %)
# ---------------------------------------------------------------------------


def charger_evenements(chemin: Path) -> pd.DataFrame:
    """Lit le JSONL et aplatit le sous-objet 'event' à la racine.

    {"received_at": ..., "event": {"device_id": ...}, "risk_score": ...}
    devient une ligne : device_id, user_id, amount, ..., risk_score, decision.
    """
    lignes = []
    for brut in chemin.read_text(encoding="utf-8").splitlines():
        brut = brut.strip()
        if not brut:
            continue
        obj = json.loads(brut)
        plat = dict(obj.get("event", {}))          # champs métier
        plat["received_at"] = obj.get("received_at")
        plat["risk_score"] = obj.get("risk_score")  # conservé pour comparaison
        plat["decision"] = obj.get("decision")      # NON utilisé par le modèle
        raisons = obj.get("reasons", [])
        plat["reasons"] = " | ".join(raisons) if isinstance(raisons, list) else raisons
        lignes.append(plat)
    return pd.DataFrame(lignes)


def construire_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Construit les variables numériques exploitées par l'Isolation Forest.

    Variables retenues :
      - montant de la transaction ;
      - fréquence d'apparition du dispositif (un dispositif rare est suspect) ;
      - fréquence de la localisation ;
      - cohérence du couple utilisateur/dispositif (fréquence conjointe) ;
      - heure de la transaction.
    Aucune de ces variables ne dépend du moteur de règles.
    """
    X = pd.DataFrame(index=df.index)
    X["montant"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    freq_disp = df["device_id"].value_counts(normalize=True)
    X["freq_dispositif"] = df["device_id"].map(freq_disp)

    freq_loc = df["location"].value_counts(normalize=True)
    X["freq_localisation"] = df["location"].map(freq_loc)

    couple = df["user_id"].astype(str) + "|" + df["device_id"].astype(str)
    X["freq_couple_user_device"] = couple.map(couple.value_counts(normalize=True))

    horodatage = pd.to_datetime(df["timestamp"], errors="coerce")
    X["heure"] = horodatage.dt.hour.fillna(12)

    return X.fillna(0)


def main():
    if not FICHIER_EVENEMENTS.exists():
        raise SystemExit(f"Fichier introuvable : {FICHIER_EVENEMENTS} "
                         "(lance ce script depuis ~/slickpay_iot_poc)")

    df = charger_evenements(FICHIER_EVENEMENTS)

    if len(df) < 50:
        print(f"[AVERTISSEMENT] Seulement {len(df)} événements. "
              "Relance le simulateur pour en générer ~200 : le modèle et la "
              "capture d'écran seront bien plus convaincants.\n")

    X = construire_variables(df)
    X_norm = StandardScaler().fit_transform(X)

    modele = IsolationForest(n_estimators=200,
                             contamination=CONTAMINATION,
                             random_state=42)
    predictions = modele.fit_predict(X_norm)      # -1 = anomalie, 1 = normal
    scores = modele.decision_function(X_norm)     # plus bas = plus anormal

    df["ml_score"] = [round(float(s), 4) for s in scores]
    df["ml_anomalie"] = [1 if p == -1 else 0 for p in predictions]

    with FICHIER_SCORES.open("w", encoding="utf-8") as f:
        for _, ligne in df.iterrows():
            f.write(json.dumps(ligne.to_dict(), ensure_ascii=False,
                               default=str) + "\n")

    nb_total = len(df)
    nb_anomalies = int(df["ml_anomalie"].sum())

    # Croisement ML / règles : combien d'anomalies ML étaient déjà signalées ?
    deja_signalees = int(((df["ml_anomalie"] == 1) &
                          (df["decision"].isin(["REVIEW", "BLOCKED"]))).sum())
    nouvelles = nb_anomalies - deja_signalees

    colonnes = ["device_id", "user_id", "amount", "location",
                "risk_score", "decision", "ml_score", "ml_anomalie"]
    colonnes = [c for c in colonnes if c in df.columns]
    top = df.nsmallest(5, "ml_score")[colonnes]

    synthese = [
        "=== Detection d'anomalies IoT par Isolation Forest ===",
        f"Genere le             : {datetime.now().isoformat(timespec='seconds')}",
        f"Evenements analyses   : {nb_total}",
        f"Anomalies detectees   : {nb_anomalies} "
        f"({100 * nb_anomalies / nb_total:.1f} %)",
        f"Contamination         : {CONTAMINATION}",
        "Variables utilisees   : montant, freq_dispositif, freq_localisation, "
        "freq_couple_user_device, heure",
        "",
        "--- Croisement avec le moteur de regles ---",
        f"Anomalies ML deja signalees par les regles (REVIEW/BLOCKED) : "
        f"{deja_signalees}",
        f"Anomalies ML NON signalees par les regles                   : "
        f"{nouvelles}",
        "",
        "Top 5 des evenements les plus anormaux (ml_score croissant) :",
        top.to_string(index=False),
    ]
    FICHIER_SYNTHESE.write_text("\n".join(synthese) + "\n", encoding="utf-8")

    print("\n".join(synthese))
    print(f"\nScores ecrits dans   : {FICHIER_SCORES}")
    print(f"Synthese ecrite dans : {FICHIER_SYNTHESE}")
    print("\nNote ces chiffres : ils remplissent les crochets [N], [k], [p], "
          "[x] du Bloc 3 LaTeX.")


if __name__ == "__main__":
    main()
