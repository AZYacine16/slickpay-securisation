#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Évaluation des approches de vérification biométrique sur un corpus élargi.
VERSION 2 : détection de visage robuste et diagnostic des échecs.

Corrections apportées par rapport à la version initiale :
  - paramètres de détection Haar assouplis, puis seconde tentative sur image
    égalisée si la première échoue ;
  - repli documenté sur un recadrage central lorsque la détection échoue, les
    images LFW étant déjà centrées sur le visage ;
  - les paires dont le score n'a pas pu être calculé sont EXCLUES du calcul des
    métriques au lieu d'être comptées comme des non-correspondances ;
  - décompte séparé des modes de détection, pour juger de la validité du test.

Prérequis :
    conda activate kyc
    pip install scikit-learn matplotlib

Usage :
    python evaluation_corpus_kyc.py 20      # test rapide
    python evaluation_corpus_kyc.py 50      # évaluation exploitable
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

N_PAIRES_PAR_CLASSE = int(sys.argv[1]) if len(sys.argv) > 1 else 50
DOSSIER_TRAVAIL = Path("corpus_lfw")
GRAINE = 42

SIMILARITY_THRESHOLD = 75.0
MIN_MATCHES_THRESHOLD = 20

STATS = {"haar": 0, "haar_egalise": 0, "repli_centre": 0}


# ===========================================================================
# 1. CONSTITUTION DU CORPUS
# ===========================================================================

def constituer_corpus():
    from sklearn.datasets import fetch_lfw_people

    print("Chargement du corpus LFW...")
    lfw = fetch_lfw_people(min_faces_per_person=2, color=True,
                           resize=1.0, funneled=True)

    images = (lfw.images * 255).astype(np.uint8)
    cibles = lfw.target
    print(f"  {len(images)} images, {len(lfw.target_names)} personnes")

    DOSSIER_TRAVAIL.mkdir(exist_ok=True)

    par_personne = {}
    for idx, personne in enumerate(cibles):
        par_personne.setdefault(int(personne), []).append(idx)

    multiples = [p for p, idxs in par_personne.items() if len(idxs) >= 2]
    rng = np.random.default_rng(GRAINE)
    paires = []

    personnes_pos = rng.choice(multiples,
                               size=min(N_PAIRES_PAR_CLASSE, len(multiples)),
                               replace=False)
    for k, personne in enumerate(personnes_pos):
        i1, i2 = rng.choice(par_personne[int(personne)], size=2, replace=False)
        c1 = DOSSIER_TRAVAIL / f"pos_{k:03d}_a.png"
        c2 = DOSSIER_TRAVAIL / f"pos_{k:03d}_b.png"
        cv2.imwrite(str(c1), cv2.cvtColor(images[i1], cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(c2), cv2.cvtColor(images[i2], cv2.COLOR_RGB2BGR))
        paires.append((str(c1), str(c2), 1))

    toutes = list(par_personne.keys())
    for k in range(N_PAIRES_PAR_CLASSE):
        p1, p2 = rng.choice(toutes, size=2, replace=False)
        i1 = rng.choice(par_personne[int(p1)])
        i2 = rng.choice(par_personne[int(p2)])
        c1 = DOSSIER_TRAVAIL / f"neg_{k:03d}_a.png"
        c2 = DOSSIER_TRAVAIL / f"neg_{k:03d}_b.png"
        cv2.imwrite(str(c1), cv2.cvtColor(images[i1], cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(c2), cv2.cvtColor(images[i2], cv2.COLOR_RGB2BGR))
        paires.append((str(c1), str(c2), 0))

    print(f"  {len(paires)} paires constituées "
          f"({N_PAIRES_PAR_CLASSE} positives, {N_PAIRES_PAR_CLASSE} négatives)\n")
    return paires


# ===========================================================================
# 2. DÉTECTION DE VISAGE ROBUSTE
# ===========================================================================

def _detecter(gris, scale, voisins, taille_min):
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return cascade.detectMultiScale(gris, scale, voisins, minSize=taille_min)


def extraire_visage(image):
    """Retourne la zone de visage selon trois stratégies successives."""
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gris.shape

    visages = _detecter(gris, 1.05, 3, (20, 20))
    if len(visages) > 0:
        STATS["haar"] += 1
    else:
        visages = _detecter(cv2.equalizeHist(gris), 1.05, 3, (20, 20))
        if len(visages) > 0:
            STATS["haar_egalise"] += 1

    if len(visages) > 0:
        x, y, lw, lh = sorted(visages, key=lambda f: f[2] * f[3],
                              reverse=True)[0]
        return image[y:y + lh, x:x + lw]

    STATS["repli_centre"] += 1
    mx, my = int(w * 0.25), int(h * 0.25)
    return image[my:h - my, mx:w - mx]


def pretraiter(visage):
    gris = cv2.cvtColor(visage, cv2.COLOR_BGR2GRAY)
    gris = cv2.GaussianBlur(gris, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return cv2.resize(clahe.apply(gris), (250, 250))


# ===========================================================================
# 3. SCORE ORB
# ===========================================================================

def score_orb(chemin1, chemin2):
    img1, img2 = cv2.imread(chemin1), cv2.imread(chemin2)
    if img1 is None or img2 is None:
        return None, None

    f1 = pretraiter(extraire_visage(img1))
    f2 = pretraiter(extraire_visage(img2))

    orb = cv2.ORB_create(nfeatures=500, scaleFactor=1.2, nlevels=8)
    kp1, d1 = orb.detectAndCompute(f1, None)
    kp2, d2 = orb.detectAndCompute(f2, None)
    if d1 is None or d2 is None or len(kp1) < 2 or len(kp2) < 2:
        return None, None

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
# 4. SCORE FACENET
# ===========================================================================

def score_facenet(chemin1, chemin2):
    from deepface import DeepFace
    try:
        res = DeepFace.verify(
            img1_path=chemin1, img2_path=chemin2,
            model_name="Facenet", distance_metric="cosine",
            detector_backend="opencv", enforce_detection=False,
        )
        return res["distance"], res["threshold"]
    except Exception:
        return None, None


# ===========================================================================
# 5. MÉTRIQUES
# ===========================================================================

def calculer_eer(y_vrai, scores):
    from sklearn.metrics import roc_curve
    fpr, tpr, seuils = roc_curve(y_vrai, scores)
    fnr = 1 - tpr
    idx = int(np.nanargmin(np.abs(fnr - fpr)))
    return (fpr[idx] + fnr[idx]) / 2 * 100, seuils[idx], fpr, tpr


def metriques(y_vrai, y_pred):
    from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                                 precision_score, recall_score)
    vn, fp, fn, vp = confusion_matrix(y_vrai, y_pred, labels=[0, 1]).ravel()
    return {
        "precision": precision_score(y_vrai, y_pred, zero_division=0),
        "rappel": recall_score(y_vrai, y_pred, zero_division=0),
        "exactitude": accuracy_score(y_vrai, y_pred),
        "f1": f1_score(y_vrai, y_pred, zero_division=0),
        "vp": int(vp), "vn": int(vn), "fp": int(fp), "fn": int(fn),
    }


# ===========================================================================
# 6. EXÉCUTION
# ===========================================================================

def main():
    debut = time.time()
    paires = constituer_corpus()

    print("Évaluation en cours...\n")

    valides = []
    exclues_orb = exclues_fnet = 0
    seuil_fnet = 0.40

    for i, (c1, c2, etiquette) in enumerate(paires, start=1):
        sim, nb = score_orb(c1, c2)
        dist, seuil = score_facenet(c1, c2)
        if seuil is not None:
            seuil_fnet = seuil

        if sim is None:
            exclues_orb += 1
        elif dist is None:
            exclues_fnet += 1
        else:
            valides.append((etiquette, sim, nb, dist))

        if i % 20 == 0:
            print(f"  {i}/{len(paires)} paires traitées...")

    if len(valides) < 10:
        raise SystemExit(
            f"\nSeulement {len(valides)} paires exploitables sur {len(paires)} : "
            "résultats non significatifs.\nL'expérimentation sur corpus élargi "
            "n'est pas concluante dans cette configuration."
        )

    y_vrai = np.array([l[0] for l in valides])
    s_orb = np.array([l[1] for l in valides])
    n_orb = np.array([l[2] for l in valides])
    s_fnet = np.array([l[3] for l in valides])

    pred_orb = ((s_orb >= SIMILARITY_THRESHOLD) &
                (n_orb >= MIN_MATCHES_THRESHOLD)).astype(int)
    pred_fnet = (s_fnet <= seuil_fnet).astype(int)

    m_orb = metriques(y_vrai, pred_orb)
    m_fnet = metriques(y_vrai, pred_fnet)

    eer_orb, seuil_eer_orb, fpr_o, tpr_o = calculer_eer(y_vrai, s_orb)
    eer_fnet, seuil_eer_fnet, fpr_f, tpr_f = calculer_eer(y_vrai, -s_fnet)

    from sklearn.metrics import auc
    auc_orb, auc_fnet = auc(fpr_o, tpr_o), auc(fpr_f, tpr_f)

    plt.figure(figsize=(6.5, 5.5))
    plt.plot(fpr_o, tpr_o, color="#c1666b", lw=2,
             label=f"Pipeline ORB (AUC = {auc_orb:.4f})")
    plt.plot(fpr_f, tpr_f, color="#1f4e79", lw=2,
             label=f"FaceNet (AUC = {auc_fnet:.4f})")
    plt.plot([0, 1], [0, 1], "--", color="grey", label="Aléatoire")
    plt.xlabel("Taux de faux positifs")
    plt.ylabel("Taux de vrais positifs")
    plt.title(f"Courbes ROC — vérification biométrique "
              f"({len(valides)} paires, corpus LFW)")
    plt.legend(loc="lower right")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("roc_kyc_comparaison.png", dpi=200)
    plt.close()

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

    duree = time.time() - debut
    total_det = max(1, sum(STATS.values()))
    lignes = [
        "=" * 76,
        "EVALUATION SUR CORPUS ELARGI — VERIFICATION BIOMETRIQUE KYC",
        "=" * 76,
        "",
        "Corpus            : LFW (Labeled Faces in the Wild)",
        f"Paires generees   : {len(paires)}",
        f"Paires evaluees   : {len(valides)} "
        f"(exclues : {exclues_orb} ORB, {exclues_fnet} FaceNet)",
        f"Duree du test     : {duree/60:.1f} minutes",
        "",
        "Detection de visage (images traitees) :",
        f"  Haar parametres assouplis : {STATS['haar']} "
        f"({100*STATS['haar']/total_det:.1f} %)",
        f"  Haar sur image egalisee   : {STATS['haar_egalise']} "
        f"({100*STATS['haar_egalise']/total_det:.1f} %)",
        f"  Repli recadrage central   : {STATS['repli_centre']} "
        f"({100*STATS['repli_centre']/total_det:.1f} %)",
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
        f"Seuils du prototype : ORB {SIMILARITY_THRESHOLD:.0f} % et "
        f"{MIN_MATCHES_THRESHOLD} correspondances | FaceNet {seuil_fnet}",
        f"Seuils optimaux EER : ORB {seuil_eer_orb:.2f} % | "
        f"FaceNet {-seuil_eer_fnet:.4f}",
        "",
        "Rappel : un AUC proche de 0,50 indique une discrimination equivalente",
        "au hasard ; un EER faible traduit une bonne separation des classes.",
        "",
        "Figures : roc_kyc_comparaison.png, distributions_scores_kyc.png",
        "=" * 76,
    ]

    rapport = "\n".join(lignes)
    Path("resultats_corpus_kyc.txt").write_text(rapport + "\n", encoding="utf-8")
    print("\n" + rapport)
    print("\nRapport ecrit dans : resultats_corpus_kyc.txt")


if __name__ == "__main__":
    main()
