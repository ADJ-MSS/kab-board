#!/usr/bin/env python3
"""Vérifications de la complétion, sur le même jeu que CompletionTest.kt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from completion import Completion, SEUIL, LONGUEUR_MIN

ok, rates = 0, []
def verifie(nom, obtenu, attendu):
    global ok
    if obtenu == attendu:
        ok += 1
    else:
        rates.append(f"{nom} : {obtenu!r} au lieu de {attendu!r}")

class Faux:
    """Un lexique minuscule, sans modèle de langue."""
    def __init__(self, fiables):
        self.freq = {"tamurt": 900, "tameṭṭut": 1200, "tamdint": 300, "taqbaylit": 800,
                     "axxam": 2000, "aɣrum": 700, "tamettant": 60,
                     "tam": 5000, "rare": 10}
        self.kenlm = None
        self._fiables = fiables
    def fiable(self, mot):
        return mot in self._fiables

c = Completion(Faux(set()))
verifie("les plus fréquents d'abord", c.candidats("tam"),
        ["tameṭṭut", "tamurt", "tamdint", "tamettant"])
verifie("un début plus long", c.candidats("tame"), ["tameṭṭut", "tamettant"])
verifie("jamais un mot de 3 lettres", "tam" in c.candidats("ta"), False)
verifie("jamais un mot trop rare", c.candidats("rar"), [])
verifie("rien ne commence ainsi", c.candidats("tma"), [])
verifie("sans modèle, la fréquence décide", c.completer("", "tam", 2), ["tameṭṭut", "tamurt"])
verifie("jusqu'à trois lettres, la barre complète", c.barre("", "tam"),
        ["tameṭṭut", "tamurt", "tamdint", "tamettant"])
verifie("au-delà, plus de complétion", c.barre("", "tame"), None)
verifie("faute en tête, on corrige", c.barre("", "tma"), None)
verifie("un mot court sûr reste en tête",
        Completion(Faux({"tam"})).barre("", "tam", 3), ["tam", "tameṭṭut", "tamurt"])
verifie("seuils de la mesure", (SEUIL, LONGUEUR_MIN), (3, 4))

print(f"{ok} vérifications passées, {len(rates)} échec(s)")
for r in rates:
    print("  ÉCHEC " + r)
sys.exit(1 if rates else 0)
