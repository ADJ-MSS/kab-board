#!/usr/bin/env python3
"""Exporte le modele de Mmeslay en un seul fichier ONNX, du son brut aux logits."""
import os
import sys
import tempfile

import onnx
import torch

from charger import Mmeslay

base, sortie = sys.argv[1], sys.argv[2]

m = Mmeslay()
m.load_state_dict(torch.load(os.path.join(base, "ressources/e2e_model/squeezeformer"),
                             map_location="cpu"))
m.eval()


class Emballage(torch.nn.Module):
    """Son brut -> logits. La longueur se deduit du tenseur, pas d'un second argument."""

    def __init__(self, modele):
        super().__init__()
        self.m = modele

    def forward(self, audio):
        lengths = torch.tensor([audio.shape[1]], dtype=torch.int64)
        return self.m(audio, lengths)


w = Emballage(m).eval()
exemple = torch.randn(1, 16000 * 3)
with torch.no_grad():
    print("reference torch :", tuple(w(exemple).shape))

with tempfile.TemporaryDirectory() as tmp:
    provisoire = os.path.join(tmp, "mmeslay.onnx")
    torch.onnx.export(
        w, (exemple,), provisoire,
        input_names=["audio"], output_names=["logits"],
        dynamic_axes={"audio": {1: "echantillons"}, "logits": {1: "trames"}},
        opset_version=17, do_constant_folding=True,
    )
    graphe = onnx.load(provisoire)  # charge aussi d'eventuelles donnees externes
    onnx.save(graphe, sortie, save_as_external_data=False)

print("exporte : %s (%.1f Mio)" % (sortie, os.path.getsize(sortie) / 1048576))
