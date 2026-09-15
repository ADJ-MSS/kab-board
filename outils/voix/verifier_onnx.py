#!/usr/bin/env python3
"""Compare le modele ONNX au modele PyTorch sur les exemples du depot Mmeslay."""
import os
import sys
import time

import librosa
import numpy as np
import onnxruntime as ort
import torch

from charger import Mmeslay

base, fichier_onnx = sys.argv[1], sys.argv[2]

m = Mmeslay()
m.load_state_dict(torch.load(os.path.join(base, "ressources/e2e_model/squeezeformer"),
                             map_location="cpu"))
m.eval()
with open(os.path.join(base, "ressources/tokenizer/128_v7.txt"), encoding="utf-8") as f:
    jetons = [ligne.rstrip("\n") for ligne in f]

options = ort.SessionOptions()
options.log_severity_level = 3
session = ort.InferenceSession(fichier_onnx, options, providers=["CPUExecutionProvider"])


def glouton(logits):
    """Meilleur jeton par trame, repetitions fusionnees, blanc retire."""
    ids = logits.argmax(-1)[0].tolist()
    sortie, precedent = [], -1
    for i in ids:
        if i != precedent and jetons[i] != "_":
            sortie.append(jetons[i])
        precedent = i
    return "".join(sortie).replace("▁", " ").strip()


ecart_max = 0.0
echecs = 0
for nom in ("e1", "e2", "e3"):
    audio, _ = librosa.load(os.path.join(base, "ressources/examples/%s.mp3" % nom), sr=16000, mono=True)
    x = torch.from_numpy(audio).unsqueeze(0)
    with torch.no_grad():
        a = m(x, torch.tensor([x.shape[1]])).numpy()
    t0 = time.time()
    b = session.run(["logits"], {"audio": audio[None, :].astype(np.float32)})[0]
    duree = (time.time() - t0) * 1000
    ecart = float(np.abs(a - b).max())
    ecart_max = max(ecart_max, ecart)
    ta, tb = glouton(a), glouton(b)
    identique = ta == tb
    echecs += not identique
    print("%s  onnx %4.0f ms   ecart max %.2e   %s" % (nom, duree, ecart, "IDENTIQUE" if identique else "DIVERGENT"))
    print("    torch : %s" % ta)
    if not identique:
        print("    onnx  : %s" % tb)

print("\necart maximal sur les trois : %.3e" % ecart_max)
sys.exit(1 if echecs else 0)
