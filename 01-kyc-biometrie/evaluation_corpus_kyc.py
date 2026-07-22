#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Évaluation des approches de vérification biométrique sur un corpus élargi.

Compare le pipeline ORB du prototype et le modèle FaceNet sur N paires
positives et N paires négatives constituées à partir du jeu de données LFW
(Labeled Faces in the Wild), afin de produire des métriques statistiquement
exploitables : précision, rappel, F1, taux d'erreur égal (EER) et courbe ROC.

LIMITE ASSUMÉE : LFW est composé de photographies de visages en conditions
non contrôlées, et non de paires document d'identité / selfie. L'évaluation
porte donc sur la capacité de comparaison faciale, qui constitue le coeur
technique du processus KYC, et non sur la chaîne KYC complète.

Prérequis :
    conda activate kyc
    pip install scikit-learn matplotlib

Sorties :
    roc_kyc_comparaison.png          courbes ROC des deux approches
    distributions_scores_kyc.png     distributions des scores par classe
    resultats_corpus_kyc.txt         récapitulatif chiffré

Usage :
    python evaluation_corpus_kyc.py              # 50 paires par classe
    python evaluation_corpus_kyc.py 100          # 100 paires par classe
"""

import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ------------------------------- CONFIG ------------------------------------
N_PAIRES_PAR_CLASSE = int(sys.argv[1]) if len(sys.argv) > 1 else 50
DOSSIER_TRAVAIL = Path("corpus_lfw")
GRAINE = 42

# Seuils du prototype (inchangés)
SIMILARITY_THRESHOLD = 75.0
MIN_MATCHES_THRESHOLD = 20
# ---------------------------------------------------------------------------


# ===========================================================================
# 1. CONSTITUTION DU CORPUS
# ===========================================================================

def constituer_corpus():
    """Télécharge LFW et constitue des paires positives et négatives.

    Une paire positive associe deux photographies d'une même personne ;
    une paire négative associe deux personnes distinctes. Les images sont
    écrites sur disque car DeepFace attend des chemins de fichiers.
    """
    from sklearn.datasets import fetch_lfw_people

    print("Téléchargement du corpus LFW (~200 Mo au premier lancement)...")
    lfw = fetch_lfw_people(min_faces_per_person=2, color=True,
                           resize=1.0, funneled=True)

    images = (lfw.images * 255).astype(np.uint8)
    cibles = lfw.target
    print(f"  {len(images)} images, {len(lfw.target_names)} personnes")

    DOSSIER_TRAVAIL.mkdir(exist_ok=True)

    # Indexation des images par personne
    par_personne = {}
    for idx, personne in enumerate(cibles):
        par_personne.setdefault(int(personne), []).append(idx)

    multiples = [p for p, idxs in par_personne.items() if len(idxs) >= 2]
    rng = np.random.default_rng(GRAINE)

    paires = []

    # --- Paires positives : deux images de la même personne ---
    personnes_pos = rng.choice(multiples,
                               size=min(N_PAIRES_PAR_CLASSE, len(multiples)),
                               replace=False)
    for k, personne in enumerate(personnes_pos):
        i1, i2 = rng.choice(par_personne[int(personne)], size=2, replace=False)
        c1 = DOSSIER_TRAVAIL / f"pos_{k:03d}_a.png"
        c2 = DOSSIER_TRAVAIL / f"pos_{k:03d}_b.png"
        cv2.imwrite(str(c1), cv2.cvtColor(images[i1], cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(c2), cv2.cvtColor(images[i2], cv2.COLOR_RGB2BGR))
        paires.append((str(c1), str(c2), 1, f"pos_{k:03d}"))

    # --- Paires négatives : deux personnes différentes ---
    toutes = list(par_personne.keys())
    for k in range(N_PAIRES_PAR_CLASSE):
        p1, p2 = rng.choice(toutes, size=2, replace=False)
        i1 = rng.choice(par_personne[int(p1)])
        i2 = rng.choice(par_personne[int(p2)])
        c1 = DOSSIER_TRAVAIL / f"neg_{k:03d}_a.png"
        c2 = DOSSIER_TRAVAIL / f"neg_{k:03d}_b.png"
        cv2.imwrite(str(c1), cv2.cvtColor(images[i1], cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(c2), cv2.cvtColor(images[i2], cv2.COLOR_RGB2BGR))
        paires.append((str(c1), str(c2), 0, f"neg_{k:03d}"))

    print(f"  {len(paires)} paires constituées "
          f"({N_PAIRES_PAR_CLASSE} positives, {N_PAIRES_PAR_CLASSE} négatives)\n")
    return paires


# ===========================================================================
# 2. PIPELINE ORB (identique au prototype)
# ===========================================================================

def detect_faces(image):
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cascade.detectMultiScale(gris, 1.1, 5, minSize=(40, 40))


def plus_grand_visage(visages):
    if len(visages) == 0:
        return None
    return sorted(visages, key=lambda f: f[2] * f[3], reverse=True)[0]


def pretraiter(visage):
    gris = cv2.cvtColor(visage, cv2.COLOR_BGR2GRAY)
    gris = cv2.GaussianBlur(gris, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return cv2.resize(clahe.apply(gris), (250, 250))


def score_orb(chemin1, chemin2):
    """Retourne (similarité, nb correspondances) ou (None, None) si échec."""
    img1, img2 = cv2.imread(chemin1), cv2.imread(chemin2)
    if img1 is None or img2 is None:
        return None, None

    v1 = plus_grand_visage(detect_faces(img1))
    v2 = plus_grand_visage(detect_faces(img2))
    if v1 is None or v2 is None:
        return None, None

    x1, y1, w1, h1 = v1
    x2, y2, w2, h2 = v2
    f1 = pretraiter(img1[y1:y1 + h1, x1:x1 + w1])
    f2 = pretraiter(img2[y2:y2 + h2, x2:x2 + w2])

    orb = cv2.ORB_create(nfeatures=500, scaleFactor=1.2, nlevels=8)
    kp1, d1 = orb.detectAndCompute(f1, None)
    kp2, d2 = orb.detectAndCompute(f2, None)
    if d1 is None or d2 is None:
        return 0.0, 0

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    bons = []
    for paire in bf.knnMatch(d1, d2, k=2):
        if len(paire) == 2 and paire[0].distance < 0.75 * paire[1].distance:
            bons.append(paire[0])

    if len(bons) < 4:
        return 0.0, len(bons)

    src = np.float32([kp1[m.queryIdx].pt for m in bons]).reshape(-1, 1, 2)
    dst = np.float32([kp2[m.trainIdx].pt for m in bons]).reshape(-1, 1, 2)
    _, masque = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if masque is None:
        return 0.0, len(bons)

    return (int(masque.sum()) / len(bons)) * 100, len(bons)


# ===========================================================================
# 3. FACENET
# ===========================================================================

def score_facenet(chemin1, chemin2, modele):
    """Retourne la distance cosinus, ou None si un visage n'est pas détecté."""
    from deepface import DeepFace
    try:
        res = DeepFace.verify(
            img1_path=chemin1, img2_path=chemin2,
            model_name="Facenet", distance_metric="cosine",
            detector_backend="opencv", enforce_detection=True,
        )
        return res["distance"], res["threshold"]
    except Exception:
        return None, None


# ===========================================================================
# 4. MÉTRIQUES
# ===========================================================================

def calculer_eer(y_vrai, scores):
    """Calcule le taux d'erreur égal et le seuil correspondant.

    Le score fourni doit être croissant avec la probabilité d'appartenance
    à la classe positive.
    """
    from sklearn.metrics import roc_curve
    fpr, tpr, seuils = roc_curve(y_vrai, scores)
    fnr = 1 - tpr
    idx = int(np.nanargmin(np.abs(fnr - fpr)))
    eer = (fpr[idx] + fnr[idx]) / 2
    return eer * 100, seuils[idx], fpr, tpr


def metriques(y_vrai, y_pred):
    from sklearn.metrics import (accuracy_score, f1_score, precision_score,
                                 recall_score, confusion_matrix)
    vn, fp, fn, vp = confusion_matrix(y_vrai, y_pred, labels=[0, 1]).ravel()
    return {
        "precision": precision_score(y_vrai, y_pred, zero_division=0),
        "rappel": recall_score(y_vrai, y_pred, zero_division=0),
        "exactitude": accuracy_score(y_vrai, y_pred),
        "f1": f1_score(y_vrai, y_pred, zero_division=0),
        "vp": int(vp), "vn": int(vn), "fp": int(fp), "fn": int(fn),
    }


# ===========================================================================
# 5. EXÉCUTION
# ===========================================================================

def main():
    debut = time.time()
    paires = constituer_corpus()

    print("Évaluation en cours (peut prendre plusieurs minutes)...\n")

    y_vrai, s_orb, s_fnet = [], [], []
    echecs_orb = echecs_fnet = 0
    seuil_fnet = 0.40

    for i, (c1, c2, etiquette, nom) in enumerate(paires, start=1):
        sim, _ = score_orb(c1, c2)
        dist, seuil = score_facenet(c1, c2, None)
        if seuil is not None:
            seuil_fnet = seuil

        if sim is None:
            echecs_orb += 1
            sim = 0.0
        if dist is None:
            echecs_fnet += 1
            dist = 1.0

        y_vrai.append(etiquette)
        s_orb.append(sim)
        s_fnet.append(dist)

        if i % 20 == 0:
            print(f"  {i}/{len(paires)} paires traitées...")

    y_vrai = np.array(y_vrai)
    s_orb = np.array(s_orb)
    s_fnet = np.array(s_fnet)

    # Décisions selon les règles de chaque approche
    pred_orb = (s_orb >= SIMILARITY_THRESHOLD).astype(int)
    pred_fnet = (s_fnet <= seuil_fnet).astype(int)

    m_orb = metriques(y_vrai, pred_orb)
    m_fnet = metriques(y_vrai, pred_fnet)

    # EER : le score doit croître avec la probabilité de correspondance.
    # Pour FaceNet, la distance décroît quand la ressemblance augmente :
    # on utilise donc son opposé.
    eer_orb, seuil_eer_orb, fpr_o, tpr_o = calculer_eer(y_vrai, s_orb)
    eer_fnet, seuil_eer_fnet, fpr_f, tpr_f = calculer_eer(y_vrai, -s_fnet)

    from sklearn.metrics import auc
    auc_orb = auc(fpr_o, tpr_o)
    auc_fnet = auc(fpr_f, tpr_f)

    # ----------------------- Courbes ROC -----------------------------------
    plt.figure(figsize=(6.5, 5.5))
    plt.plot(fpr_o, tpr_o, color="#c1666b", lw=2,
             label=f"Pipeline ORB (AUC = {auc_orb:.4f})")
    plt.plot(fpr_f, tpr_f, color="#1f4e79", lw=2,
             label=f"FaceNet (AUC = {auc_fnet:.4f})")
    plt.plot([0, 1], [0, 1], "--", color="grey", label="Aléatoire")
    plt.xlabel("Taux de faux positifs")
    plt.ylabel("Taux de vrais positifs")
    plt.title(f"Courbes ROC — vérification biométrique "
              f"({len(paires)} paires, corpus LFW)")
    plt.legend(loc="lower right")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("roc_kyc_comparaison.png", dpi=200)
    plt.close()

    # ------------------ Distributions des scores ---------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].hist(s_orb[y_vrai == 1], bins=20, alpha=0.65,
                 label="Même personne", color="#1f4e79")
    axes[0].hist(s_orb[y_vrai == 0], bins=20, alpha=0.65,
                 label="Personnes différentes", color="#c1666b")
    axes[0].axvline(SIMILARITY_THRESHOLD, color="black", ls="--",
                    label=f"Seuil {SIMILARITY_THRESHOLD:.0f} %")
    axes[0].set_xlabel("Score de similarité ORB (%)")
    axes[0].set_ylabel("Nombre de paires")
    axes[0].set_title("Pipeline ORB")
    axes[0].legend(fontsize=8)

    axes[1].hist(s_fnet[y_vrai == 1], bins=20, alpha=0.65,
                 label="Même personne", color="#1f4e79")
    axes[1].hist(s_fnet[y_vrai == 0], bins=20, alpha=0.65,
                 label="Personnes différentes", color="#c1666b")
    axes[1].axvline(seuil_fnet, color="black", ls="--",
                    label=f"Seuil {seuil_fnet}")
    axes[1].set_xlabel("Distance cosinus FaceNet")
    axes[1].set_title("FaceNet (embeddings)")
    axes[1].legend(fontsize=8)

    plt.tight_layout()
    plt.savefig("distributions_scores_kyc.png", dpi=200)
    plt.close()

    # --------------------------- Rapport -----------------------------------
    duree = time.time() - debut
    lignes = [
        "=" * 76,
        "EVALUATION SUR CORPUS ELARGI — VERIFICATION BIOMETRIQUE KYC",
        "=" * 76,
        "",
        f"Corpus            : LFW (Labeled Faces in the Wild)",
        f"Paires evaluees   : {len(paires)} "
        f"({N_PAIRES_PAR_CLASSE} positives, {N_PAIRES_PAR_CLASSE} negatives)",
        f"Duree du test     : {duree/60:.1f} minutes",
        f"Echecs detection  : ORB {echecs_orb}, FaceNet {echecs_fnet}",
        "",
        "-" * 76,
        f"{'Metrique':<22} {'Pipeline ORB':>18} {'FaceNet':>18}",
        "-" * 76,
        f"{'Precision':<22} {m_orb['precision']:>18.4f} {m_fnet['precision']:>18.4f}",
        f"{'Rappel':<22} {m_orb['rappel']:>18.4f} {m_fnet['rappel']:>18.4f}",
        f"{'Exactitude':<22} {m_orb['exactitude']:>18.4f} {m_fnet['exactitude']:>18.4f}",
        f"{'F1-score':<22} {m_orb['f1']:>18.4f} {m_fnet['f1']:>18.4f}",
        f"{'AUC':<22} {auc_orb:>18.4f} {auc_fnet:>18.4f}",
        f"{'EER (%)':<22} {eer_orb:>18.2f} {eer_fnet:>18.2f}",
        "-" * 76,
        f"{'Vrais positifs':<22} {m_orb['vp']:>18} {m_fnet['vp']:>18}",
        f"{'Vrais negatifs':<22} {m_orb['vn']:>18} {m_fnet['vn']:>18}",
        f"{'Faux positifs':<22} {m_orb['fp']:>18} {m_fnet['fp']:>18}",
        f"{'Faux negatifs':<22} {m_orb['fn']:>18} {m_fnet['fn']:>18}",
        "-" * 76,
        "",
        f"Seuils appliques  : ORB {SIMILARITY_THRESHOLD:.0f} % | "
        f"FaceNet {seuil_fnet}",
        f"Seuils optimaux (EER) : ORB {seuil_eer_orb:.2f} % | "
        f"FaceNet {-seuil_eer_fnet:.4f}",
        "",
        "Figures generees :",
        "  roc_kyc_comparaison.png",
        "  distributions_scores_kyc.png",
        "=" * 76,
    ]

    rapport = "\n".join(lignes)
    Path("resultats_corpus_kyc.txt").write_text(rapport + "\n", encoding="utf-8")
    print("\n" + rapport)
    print("\nRapport ecrit dans : resultats_corpus_kyc.txt")


if __name__ == "__main__":
    main()
