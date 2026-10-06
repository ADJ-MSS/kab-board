#!/usr/bin/env python3
"""La dictee, avec le modele Mmeslay de l'application Android.

Meme fichier ONNX, meme decodage glouton sans modele de langue : la
configuration dont l'auteur publie 19,54 % de WER et 6,00 % de CER. Le micro
passe par arecord, 16 kHz mono 16 bits. Tout se calcule ici.
"""
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import chemins
VOIX = chemins.voix() or Path("/inexistant")
MODELE = VOIX / "mmeslay.onnx"
JETONS = VOIX / "jetons.txt"

TAUX = 16000
MIN_ECHANTILLONS = 2400      # 0,15 s : en deca, le modele refuse l'entree
DUREE_MAX_S = 30
NOM_ENTREE = "audio"
BLANC = "_"
SILENCE = "|"
DEBUT_DE_MOT = "▁"           # marque de debut de mot de SentencePiece


def enregistrer(secondes: float, sortie: Path) -> Path:
    """Capte le micro. `arecord` plutot qu'une bibliotheque : il est deja la."""
    subprocess.run(
        ["arecord", "-q", "-f", "S16_LE", "-c", "1", "-r", str(TAUX),
         # arecord refuse « -d 2.0 ».
         "-d", str(max(1, round(min(secondes, DUREE_MAX_S)))), str(sortie)],
        check=True)
    return sortie


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
        self.jetons = charger_jetons()
        try:
            import onnxruntime
        except ImportError:
            import pont_onnx
            self.pont = pont_onnx.Session(MODELE)
            self.session = None
            return
        options = onnxruntime.SessionOptions()
        options.graph_optimization_level = \
            onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = onnxruntime.InferenceSession(str(MODELE), options,
                                                    providers=["CPUExecutionProvider"])

    def transcrire(self, echantillons: np.ndarray) -> str:
        if echantillons.size < MIN_ECHANTILLONS:
            return ""
        entree = echantillons.astype(np.float32).reshape(1, -1)
        if self.session is None:
            logits = self.pont.executer(entree)
        else:
            logits = self.session.run(None, {NOM_ENTREE: entree})[0][0]
        return decoder(logits, self.jetons)


def principal(argv):
    """Deux usages : enregistrer puis transcrire, ou transcrire un fichier.

        dictee.py 5                 enregistre 5 secondes, puis transcrit
        dictee.py --fichier x.wav   transcrit un enregistrement deja fait
    """
    if len(argv) > 2 and argv[1] == "--fichier":
        texte = Transcripteur().transcrire(lire_wav(Path(argv[2])))
    else:
        secondes = float(argv[1]) if len(argv) > 1 else 5.0
        with tempfile.TemporaryDirectory(prefix="kab-dictee-") as dossier:
            fichier = enregistrer(secondes, Path(dossier) / "dictee.wav")
            texte = Transcripteur().transcrire(lire_wav(fichier))
    print(texte)
    return 0 if texte else 1


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
