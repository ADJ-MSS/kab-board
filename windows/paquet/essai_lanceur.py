"""Kab-board.exe --clavier, comme Windows le lance à l'ouverture de session :
le clavier doit répondre, avec son crochet posé et son correcteur prêt, puis
s'arrêter proprement, service compris.

    sortie\\Kab-board\\python\\python.exe paquet\\essai_lanceur.py sortie\\Kab-board
"""
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(RACINE / "windows"))
import lieux  # noqa: E402,F401
import liaison  # noqa: E402
import processus  # noqa: E402

processus.sorties_sures()

subprocess.Popen([str(RACINE / "Kab-board.exe"), "--clavier"])
saisie = liaison.Client("saisie", 3.0)
fin, etat = time.time() + 300, None
while time.time() < fin:
    etat = saisie.appeler("etat")
    if etat and ((etat.get("service") or {}).get("pret") or (etat.get("service") or {}).get("erreur")):
        break
    time.sleep(2)
print(etat)
assert etat is not None, "le clavier ne répond pas"
assert etat["crochet"], "le crochet clavier n'est pas posé"
assert etat["service"].get("pret"), f"le correcteur n'est pas prêt : {etat['service']}"
pid_service = etat["service"]["pid"]

saisie.appeler("quitter")
fin = time.time() + 60
while time.time() < fin and (processus.vivant(etat["pid"]) or processus.vivant(pid_service)):
    time.sleep(1)
assert not processus.vivant(etat["pid"]), "le clavier ne s'arrête pas"
assert not processus.vivant(pid_service), "le correcteur survit au clavier"
print("Kab-board.exe : clavier allumé, correcteur prêt, puis tout arrêté.")
