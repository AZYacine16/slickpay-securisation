#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse complémentaire du modèle Random Forest — dataset PaySim.

Reproduit l'EXPÉRIENCE 2 (sans identifiants) du script de détection de fraude,
celle qui correspond au tableau 4.2 du mémoire, puis produit les éléments
d'évaluation attendus :

  - roc_random_forest.png      : courbe ROC et aire sous la courbe (AUC)
  - matrice_confusion_rf.png   : matrice de confusion
  - shap_summary_rf.png        : explicabilité SHAP (article 22 RGPD)
  - resultats_analyse_rf.txt   : récapitulatif chiffré (preuve pour l'annexe)
  - latence d'inférence mesurée en millisecondes par transaction

Prérequis :
    pip install shap
    le fichier CSV PaySim dans le même dossier (ou adapter CHEMIN_CSV)

Usage :
    python analyse_fraude_rf.py
"""

import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # sauvegarde directe, pas d'affichage interactif
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, auc, ConfusionMatrixDisplay,
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_curve)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# ------------------------------- CONFIG -------------------------------------
CHEMIN_CSV = Path("PS_20174392719_1491204439457_log.csv")
COLONNE_CIBLE = "isFraud"
RATIO_NON_FRAUDE = 3        # même ratio 1:3 que le script d'origine
TAILLE_ECHANTILLON_SHAP = 2000
# ----------------------------------------------------------------------------


def charger_et_echantillonner():
    """Charge PaySim et reproduit le sous-échantillonnage du script d'origine."""
    if not CHEMIN_CSV.exists():
        raise SystemExit(
            f"Fichier introuvable : {CHEMIN_CSV}\n"
            "Copie le CSV dans ce dossier :\n"
            "  cp ~/Downloads/PS_20174392719_1491204439457_log.csv ."
        )

    print("Chargement du dataset (cela peut prendre une minute)...")
    df = pd.read_csv(CHEMIN_CSV)
    print(f"  Dataset complet : {df.shape[0]} lignes, {df.shape[1]} colonnes")

    fraudes = df[df[COLONNE_CIBLE] == 1].copy()
    non_fraudes = df[df[COLONNE_CIBLE] == 0].copy()
    echantillon_non_fraudes = non_fraudes.sample(
        n=len(fraudes) * RATIO_NON_FRAUDE, random_state=42
    )

    df_sample = pd.concat([fraudes, echantillon_non_fraudes], axis=0)
    df_sample = df_sample.sample(frac=1, random_state=42).reset_index(drop=True)

    print(f"  Sous-échantillon : {df_sample.shape[0]} lignes "
          f"({len(fraudes)} fraudes, {len(echantillon_non_fraudes)} légitimes)")
    return df_sample


def preparer_experience_2(df_sample):
    """Reproduit l'expérience 2 : suppression des identifiants directs."""
    colonnes_retirees = [c for c in ["nameOrig", "nameDest", "isFlaggedFraud"]
                         if c in df_sample.columns]
    print(f"  Colonnes retirées (expérience 2) : {colonnes_retirees}")

    df_exp2 = df_sample.drop(columns=colonnes_retirees)
    X = df_exp2.drop(columns=[COLONNE_CIBLE])
    y = df_exp2[COLONNE_CIBLE].astype(int)

    for colonne in X.select_dtypes(include=["object"]).columns:
        X[colonne] = LabelEncoder().fit_transform(X[colonne].astype(str))

    return train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)


def tracer_roc(y_test, y_proba):
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    roc_auc = auc(fpr, tpr)

    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, color="#1f4e79", lw=2,
             label=f"Random Forest (AUC = {roc_auc:.4f})")
    plt.plot([0, 1], [0, 1], linestyle="--", color="grey", label="Aléatoire")
    plt.xlabel("Taux de faux positifs")
    plt.ylabel("Taux de vrais positifs (rappel)")
    plt.title("Courbe ROC — Détection de fraude (PaySim, sans identifiants)")
    plt.legend(loc="lower right")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("roc_random_forest.png", dpi=200)
    plt.close()
    return roc_auc


def tracer_matrice_confusion(y_test, y_pred):
    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ConfusionMatrixDisplay(cm, display_labels=["Légitime", "Fraude"]).plot(
        cmap="Blues", values_format="d", ax=ax, colorbar=False
    )
    ax.set_title("Matrice de confusion — Random Forest (PaySim)")
    ax.set_xlabel("Classe prédite")
    ax.set_ylabel("Classe réelle")
    plt.tight_layout()
    plt.savefig("matrice_confusion_rf.png", dpi=200)
    plt.close()
    return cm


def calculer_shap(modele, X_test):
    """Calcule les valeurs SHAP et produit le graphique de synthèse."""
    import shap

    X_echantillon = X_test.sample(
        n=min(TAILLE_ECHANTILLON_SHAP, len(X_test)), random_state=42
    )

    explainer = shap.TreeExplainer(modele)
    valeurs = explainer.shap_values(X_echantillon)

    # Selon la version de shap : liste [classe0, classe1] ou tableau 3D
    if isinstance(valeurs, list):
        valeurs = valeurs[1]
    elif getattr(valeurs, "ndim", 2) == 3:
        valeurs = valeurs[:, :, 1]

    plt.figure()
    shap.summary_plot(valeurs, X_echantillon, show=False)
    plt.tight_layout()
    plt.savefig("shap_summary_rf.png", dpi=200, bbox_inches="tight")
    plt.close()

    importance = pd.DataFrame({
        "variable": X_echantillon.columns,
        "importance_shap": np.abs(valeurs).mean(axis=0),
    }).sort_values("importance_shap", ascending=False)

    return importance


def main():
    df_sample = charger_et_echantillonner()
    X_train, X_test, y_train, y_test = preparer_experience_2(df_sample)

    print("\nEntraînement du Random Forest...")
    modele = RandomForestClassifier(n_estimators=100, max_depth=12,
                                    random_state=42, n_jobs=-1)
    modele.fit(X_train, y_train)

    y_pred = modele.predict(X_test)
    y_proba = modele.predict_proba(X_test)[:, 1]

    # Métriques de contrôle : doivent correspondre au tableau 4.2 du mémoire
    rappel = recall_score(y_test, y_pred, zero_division=0)
    precision = precision_score(y_test, y_pred, zero_division=0)
    exactitude = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    print("Génération de la courbe ROC...")
    roc_auc = tracer_roc(y_test, y_proba)

    print("Génération de la matrice de confusion...")
    cm = tracer_matrice_confusion(y_test, y_pred)
    vn, fp, fn, vp = cm.ravel()

    print("Mesure de la latence d'inférence...")
    debut = time.perf_counter()
    modele.predict(X_test)
    latence_ms = (time.perf_counter() - debut) / len(X_test) * 1000

    print("Calcul des valeurs SHAP (étape la plus longue)...")
    importance = calculer_shap(modele, X_test)

    lignes = [
        "=" * 68,
        "ANALYSE COMPLEMENTAIRE — RANDOM FOREST (PaySim, sans identifiants)",
        "=" * 68,
        "",
        "--- Controle de coherence avec le tableau 4.2 du memoire ---",
        f"Rappel      : {rappel:.4f}   (memoire : 0.9757)",
        f"Precision   : {precision:.4f}   (memoire : 0.9852)",
        f"Exactitude  : {exactitude:.4f}   (memoire : 0.9903)",
        f"F1-score    : {f1:.4f}   (memoire : 0.9804)",
        "",
        "--- Valeurs a reporter dans le LaTeX (Bloc 5) ---",
        f"AUC                          : {roc_auc:.4f}",
        f"Vrais positifs   (VP)        : {vp}",
        f"Vrais negatifs   (VN)        : {vn}",
        f"Faux positifs    (FP)        : {fp}",
        f"Faux negatifs    (FN)        : {fn}",
        f"Latence d'inference          : {latence_ms:.4f} ms / transaction",
        f"Taille de l'ensemble de test : {len(X_test)} transactions",
        "",
        "--- Variables les plus contributives, SHAP (Bloc 4) ---",
    ]
    for _, ligne in importance.head(6).iterrows():
        lignes.append(f"  {ligne['variable']:<20} {ligne['importance_shap']:.5f}")
    lignes += [
        "",
        "Figures generees :",
        "  roc_random_forest.png",
        "  matrice_confusion_rf.png",
        "  shap_summary_rf.png",
        "=" * 68,
    ]

    rapport = "\n".join(lignes)
    Path("resultats_analyse_rf.txt").write_text(rapport + "\n", encoding="utf-8")

    print("\n" + rapport)
    print("\nRecapitulatif ecrit dans : resultats_analyse_rf.txt")


if __name__ == "__main__":
    main()
