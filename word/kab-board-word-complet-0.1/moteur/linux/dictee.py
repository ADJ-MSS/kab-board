#!/usr/bin/env python3
"""Transcription par Mmeslay : le modele ONNX de l'application Android, decode en
CTC glouton sans modele de langue (19,54 % de WER publies par l'auteur dans cette
configuration). Le micro est capte par le complement Word (Micro.cs).
"""
import re
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chemins
VOIX = chemins.voix() or Path("/inexistant")
MODELE = VOIX / "mmeslay.onnx"
JETONS = VOIX / "jetons.txt"

TAUX = 16000
MIN_ECHANTILLONS = 1600      # un dixieme de seconde : en deca, rien a decoder
DUREE_MAX_S = 30
NOM_ENTREE = "audio"
BLANC = "_"
SILENCE = "|"
DEBUT_DE_MOT = "▁"           # marque de debut de mot de SentencePiece


def lire_wav(chemin: Path) -> np.ndarray:
    with wave.open(str(chemin), "rb") as f:
        brut = f.readframes(f.getnframes())
        canaux = f.getnchannels()
    echantillons = np.frombuffer(brut, dtype=np.int16).astype(np.float32) / 32768.0
    if canaux > 1:
        echantillons = echantillons.reshape(-1, canaux).mean(axis=1)
    return echantillons


def charger_jetons() -> list:
    jetons = JETONS.read_text(encoding="utf-8").split("\n")
    return [j for j in jetons if j != ""] if jetons[-1] == "" else jetons


def decoder(logits: np.ndarray, jetons: list) -> str:
    """CTC glouton : meilleur jeton par trame, sans les repetitions ni le blanc."""
    morceaux = []
    precedent = -1
    for meilleur in logits.argmax(axis=-1):
        if meilleur != precedent:
            jeton = jetons[meilleur] if meilleur < len(jetons) else None
            if jeton is not None and jeton not in (BLANC, SILENCE):
                morceaux.append(jeton)
        precedent = meilleur
    texte = "".join(morceaux).replace(DEBUT_DE_MOT, " ")
    texte = re.sub(r"-{2,}", "-", texte).strip()
    return re.sub(r"\s+", " ", texte)


class Transcripteur:

    def __init__(self):
        import onnxruntime
        options = onnxruntime.SessionOptions()
        options.graph_optimization_level = \
            onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = onnxruntime.InferenceSession(str(MODELE), options,
                                                    providers=["CPUExecutionProvider"])
        self.jetons = charger_jetons()

    def transcrire(self, echantillons: np.ndarray) -> str:
        if echantillons.size < MIN_ECHANTILLONS:
            return ""
        entree = echantillons.astype(np.float32).reshape(1, -1)
        logits = self.session.run(None, {NOM_ENTREE: entree})[0][0]
        return decoder(logits, self.jetons)


def principal(argv):
    """Transcrit un enregistrement deja fait : dictee.py fichier.wav"""
    texte = Transcripteur().transcrire(lire_wav(Path(argv[1])))
    print(texte)
    return 0 if texte else 1


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
