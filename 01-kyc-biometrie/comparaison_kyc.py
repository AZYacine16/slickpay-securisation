#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparaison de deux approches de vérification biométrique KYC — SlickPay.

Compare, sur les mêmes paires d'images :
  1. le pipeline ORB existant (détection Haar, CLAHE, descripteurs ORB,
     filtrage de Lowe, validation géométrique RANSAC) ;
  2. une approche par embeddings faciaux (FaceNet, distance cosinus).

Objectif : quantifier l'écart entre l'approche par points d'intérêt retenue
dans le prototype et l'approche de référence utilisée en production, afin
d'objectiver la limite méthodologique identifiée dans le mémoire.

Prérequis (environnement conda dédié) :
    conda activate kyc
    pip install deepface opencv-python pillow

Les 4 images doivent être dans le même dossier que ce script.

Sortie :
    resultats_comparaison_kyc.txt  (récapitulatif à capturer pour l'annexe)

Usage :
    python comparaison_kyc.py
"""

import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"   # masque les logs TensorFlow

import cv2
import numpy as np
from PIL import Image

# ---------------------------- PARAMÈTRES ORB -------------------------------
SIMILARITY_THRESHOLD = 75.0
MIN_MATCHES_THRESHOLD = 20

# Paires évaluées : (document d'identité, selfie, libellé)
PAIRES = [
    ("ID.png", "sel.png", "Positif 1"),
    ("Carte-Identite.jpg", "photo.jpg", "Positif 2"),
    ("ID.png", "photo.jpg", "Négatif"),
]
# ---------------------------------------------------------------------------


# ===========================================================================
# PARTIE 1 — PIPELINE ORB (identique au prototype du mémoire)
# ===========================================================================

def load_image_safe(path):
    img = Image.open(path).convert("RGB")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def detect_faces(image):
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                    minSize=(40, 40))


def get_largest_face(faces):
    if len(faces) == 0:
        return None
    return sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]


def preprocess_face(face):
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    return cv2.resize(gray, (250, 250))


def extract_features(image):
    orb = cv2.ORB_create(nfeatures=500, scaleFactor=1.2, nlevels=8)
    return orb.detectAndCompute(image, None)


def match_descriptors(desc1, desc2):
    if desc1 is None or desc2 is None:
        return []
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    bons = []
    for pair in bf.knnMatch(desc1, desc2, k=2):
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < 0.75 * n.distance:     # ratio test de Lowe
            bons.append(m)
    return bons


def compute_similarity(kp1, desc1, kp2, desc2):
    bons = match_descriptors(desc1, desc2)
    if len(bons) < 4:
        return 0.0, bons
    src = np.float32([kp1[m.queryIdx].pt for m in bons]).reshape(-1, 1, 2)
    dst = np.float32([kp2[m.trainIdx].pt for m in bons]).reshape(-1, 1, 2)
    _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if mask is None:
        return 0.0, bons
    return (int(mask.sum()) / len(bons)) * 100, bons


def comparer_orb(chemin_id, chemin_selfie):
    """Retourne (similarité, nb correspondances, décision)."""
    image_id = load_image_safe(chemin_id)
    image_selfie = load_image_safe(chemin_selfie)

    visage_id = get_largest_face(detect_faces(image_id))
    visage_selfie = get_largest_face(detect_faces(image_selfie))
    if visage_id is None or visage_selfie is None:
        return None, None, "ÉCHEC (visage non détecté)"

    x1, y1, w1, h1 = visage_id
    x2, y2, w2, h2 = visage_selfie
    face1 = preprocess_face(image_id[y1:y1 + h1, x1:x1 + w1])
    face2 = preprocess_face(image_selfie[y2:y2 + h2, x2:x2 + w2])

    kp1, d1 = extract_features(face1)
    kp2, d2 = extract_features(face2)
    similarite, bons = compute_similarity(kp1, d1, kp2, d2)

    correspond = (similarite >= SIMILARITY_THRESHOLD
                  and len(bons) >= MIN_MATCHES_THRESHOLD)
    decision = "CORRESPONDANCE" if correspond else "NON-CORRESPONDANCE"
    return round(similarite, 2), len(bons), decision


# ===========================================================================
# PARTIE 2 — EMBEDDINGS FACIAUX (FaceNet)
# ===========================================================================

def comparer_facenet(chemin_id, chemin_selfie):
    """Retourne (distance cosinus, seuil du modèle, décision)."""
    from deepface import DeepFace
    try:
        res = DeepFace.verify(
            img1_path=chemin_id,
            img2_path=chemin_selfie,
            model_name="Facenet",
            distance_metric="cosine",
            detector_backend="opencv",
            enforce_detection=True,
        )
        decision = "CORRESPONDANCE" if res["verified"] else "NON-CORRESPONDANCE"
        return round(res["distance"], 4), round(res["threshold"], 4), decision
    except Exception as erreur:
        return None, None, f"ÉCHEC ({type(erreur).__name__})"


# ===========================================================================
# PARTIE 3 — EXÉCUTION ET SYNTHÈSE
# ===========================================================================

def main():
    manquants = [f for p in PAIRES for f in p[:2] if not Path(f).exists()]
    if manquants:
        raise SystemExit(
            "Images introuvables : " + ", ".join(sorted(set(manquants))) +
            "\nCopie-les dans ce dossier :\n"
            "  cp ~/Documents/MasterPFE/*.png ~/Documents/MasterPFE/*.jpg ."
        )

    print("Chargement du modèle FaceNet (premier lancement : téléchargement "
          "des poids, ~90 Mo)...\n")

    lignes_rapport = []
    resultats = []

    for chemin_id, chemin_selfie, libelle in PAIRES:
        print("=" * 74)
        print(f"{libelle} : {chemin_id} vs {chemin_selfie}")
        print("=" * 74)

        sim_orb, nb_corr, dec_orb = comparer_orb(chemin_id, chemin_selfie)
        print(f"  ORB     : similarité {sim_orb} % sur {nb_corr} "
              f"correspondances  ->  {dec_orb}")

        dist, seuil, dec_fn = comparer_facenet(chemin_id, chemin_selfie)
        if dist is not None:
            print(f"  FaceNet : distance cosinus {dist} "
                  f"(seuil {seuil})  ->  {dec_fn}")
        else:
            print(f"  FaceNet : {dec_fn}")

        accord = "OUI" if dec_orb == dec_fn else "NON"
        print(f"  Concordance des décisions : {accord}\n")

        resultats.append({
            "cas": libelle, "sim_orb": sim_orb, "nb_corr": nb_corr,
            "dec_orb": dec_orb, "dist": dist, "seuil": seuil,
            "dec_fn": dec_fn, "accord": accord,
        })

    # ---------------------- Tableau de synthèse ----------------------------
    nb_accords = sum(1 for r in resultats if r["accord"] == "OUI")

    lignes_rapport += [
        "=" * 74,
        "COMPARAISON DES APPROCHES DE VERIFICATION BIOMETRIQUE (KYC)",
        "=" * 74,
        "",
        f"{'Cas':<12} {'ORB (%)':>9} {'Corresp.':>9} {'Decision ORB':>20}",
        "-" * 74,
    ]
    for r in resultats:
        lignes_rapport.append(
            f"{r['cas']:<12} {r['sim_orb']:>9} {r['nb_corr']:>9} "
            f"{r['dec_orb']:>20}"
        )

    lignes_rapport += [
        "",
        f"{'Cas':<12} {'Distance':>9} {'Seuil':>9} {'Decision FaceNet':>20}",
        "-" * 74,
    ]
    for r in resultats:
        lignes_rapport.append(
            f"{r['cas']:<12} {str(r['dist']):>9} {str(r['seuil']):>9} "
            f"{r['dec_fn']:>20}"
        )

    lignes_rapport += [
        "",
        "-" * 74,
        f"Concordance des decisions : {nb_accords}/{len(resultats)} cas",
        "-" * 74,
        "",
        "Note : le pourcentage ORB (proportion d'inliers RANSAC) et la distance",
        "cosinus FaceNet ne sont pas directement comparables. Seules les",
        "DECISIONS finales le sont.",
    ]

    rapport = "\n".join(lignes_rapport)
    Path("resultats_comparaison_kyc.txt").write_text(rapport + "\n",
                                                     encoding="utf-8")
    print(rapport)
    print("\nRapport ecrit dans : resultats_comparaison_kyc.txt")


if __name__ == "__main__":
    main()
