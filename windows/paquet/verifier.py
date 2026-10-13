"""Vérifie un paquet construit, avec le vrai correcteur et ses vraies ressources.

    sortie\\Kab-board\\python\\python.exe paquet\\verifier.py sortie\\Kab-board

À lancer avec le Python du paquet : c'est lui qu'on vérifie, ses modules et ses
DLL. Deux temps : le moteur dans ce processus (proposer, prédire, relire, fiche,
dictée), puis le service tel qu'il tourne pour de bon, lancé à part et
interrogé par la liaison locale.
"""
import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

RACINE = Path(sys.argv[1]).resolve()
os.environ["KAB_BOARD_DONNEES"] = tempfile.mkdtemp(prefix="kab-verif-")
os.environ["KAB_BOARD_PORTABLE"] = "0"
sys.path.insert(0, str(RACINE / "windows"))

import lieux  # noqa: E402
import processus  # noqa: E402

processus.sorties_sures()
assert lieux.RACINE == RACINE, (lieux.RACINE, RACINE)
lieux.preparer()

ok, rates = 0, []


def verifie(intitule, condition, detail=""):
    global ok
    if condition:
        ok += 1
        print(f"  ok      {intitule}")
    else:
        rates.append(intitule)
        print(f"  ÉCHEC   {intitule}  {detail}")


# Les modules et les ponts
import onnxruntime  # noqa: E402,F401  (d'abord, comme dans le service)
import numpy  # noqa: E402,F401
import rapidfuzz  # noqa: E402
import tkinter  # noqa: E402,F401

verifie("rapidfuzz 3.14.5", rapidfuzz.__version__ == "3.14.5", rapidfuzz.__version__)
import pont_kenlm  # noqa: E402
import pont_crf  # noqa: E402

verifie("pont KenLM chargé", pont_kenlm._lib is not None)
verifie("pont CRFsuite chargé", pont_crf._lib is not None)
for f in ("kabyle_lexicon_v4.csv", "kabyle_3gram.binary", "amyag_formes.txt", "pos_kab.crfsuite"):
    verifie(f"modeles/{f}", (RACINE / "modeles" / f).exists())
for f in ("moteur/wordnet.formes", "moteur/wordnet.gloses", "moteur/pool.frequents",
          "voix/mmeslay.onnx", "voix/jetons.txt"):
    verifie(f"assets/{f}", (RACINE / "assets" / f).exists())

# Le moteur, ici
import service  # noqa: E402

m = service.Moteur()
t0 = time.time()
m.charger()
verifie(f"correcteur chargé en {time.time() - t0:.0f} s", m.pret.is_set(), m.erreur)
if m.pret.is_set():
    res = m.correcteur.res
    verifie("modèle de langue", res.kenlm is not None)
    verifie("étiqueteur", res.pos_model is not None)
    verifie("graphe sémantique", res.wn is not None)

    r = m.proposer("", "ruhagh", "v")
    verifie("« ruhagh » : ruḥeɣ proposé", "ruḥeɣ" in r["formes"], r)
    # De 1 à 3 lettres, la barre complète (« ghar » devient « ɣar », 3 lettres) ;
    # la correction en contexte se voit donc sur un mot plus long.
    r = m.proposer("ruḥeɣ ɣer ", "tamettut", "v")
    verifie("« ɣer tamettut » : la correction en contexte", r["nature"] == "prop"
            and r["formes"] and "ṭṭ" in r["formes"][0], r)
    print(f"          ruḥeɣ ɣer tamettut → {r['formes'][:3]}")
    r = m.proposer("", "Ruhagh", "v")
    verifie("la casse du mot tapé", r["formes"] and r["formes"][0][0] == "R", r)
    # La graphie : en v, chaque forme proposée est écrite avec v ; en b, avec b.
    rv, rb = m.proposer("", "abrid", "v"), m.proposer("", "abrid", "b")
    g = m.graphie
    verifie("graphie v partout", rv["formes"] and all(g.basculer(f, "v") == f for f in rv["formes"]), rv)
    verifie("graphie b partout", rb["formes"] and all(g.basculer(f, "b") == f for f in rb["formes"]), rb)
    verifie("les deux graphies diffèrent", rv["formes"] != rb["formes"], (rv, rb))
    # Le possessif rattaché, dans la barre comme dans la relecture : les courts
    # (« iw », 2 lettres) passent devant la complétion.
    r = m.proposer("tamurt ", "nneɣ", "v")
    verifie("barre : « tamurt nneɣ » → « tamurt-nneɣ »", r["formes"][:1] == ["tamurt-nneɣ"]
            and r["mots_avant"] == 1, r)
    r = m.proposer("tamurt ", "iw", "v")
    verifie("barre : « tamurt iw » → « tamurt-iw »", r["formes"][:1] == ["tamurt-iw"]
            and r["mots_avant"] == 1 and r["nature"] == "prop", r)
    r = m.proposer("ruḥeɣ ɣer tamurt ", "iw", "v")
    verifie("barre : « ɣer tamurt iw » → « tmurt-iw »", r["formes"][:1] == ["tmurt-iw"]
            and r["mots_avant"] == 1, r)
    r = m.proposer("tamurt, ", "nneɣ", "v")
    verifie("jamais par-dessus une virgule", r["mots_avant"] == 0, r)
    r = m.proposer("tamurt, ", "iw", "v")
    verifie("ni pour un possessif court", r["mots_avant"] == 0, r)
    # Après « ɣer », l'état d'annexion s'ajoute au rattachement : « tmurt-iw ».
    s_ = m.relire("ruḥeɣ ɣer tamurt iw", "v")
    verifie("relire : « ɣer tamurt iw » → « tmurt-iw »", any(
        x["mot"] == "tamurt iw" and x["propositions"][:1] == ["tmurt-iw"] for x in s_), s_)
    r = m.proposer("", "tam", "v")
    verifie("complétion de 1 à 3 lettres", r["nature"] == "comp" and r["formes"], r)
    p = m.predire("ruḥeɣ ", "v")
    verifie("prédiction du mot suivant", len(p) > 0, p)
    s = m.relire("ruhagh ghar tamettut", "v")
    verifie("relecture", len(s) >= 2, s)
    f = m.fiche("aɣrum", "v")
    verifie("fiche d'aɣrum", bool(f.get("glose")), f)
    verifie("du français au kabyle", len(m.chercher("pain", "v")) > 0)
    verifie("mot du jour", bool(m.mot_du_jour("v")["forme"]))
    verifie("dictée installée", m.dictee_possible())
    if m.dictee_possible():
        silence = Path(tempfile.mkdtemp()) / "silence.wav"
        with wave.open(str(silence), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\0\0" * 16000)
        t0 = time.time()
        texte = m.dicter(str(silence), "v")
        verifie(f"dictée d'une seconde de silence en {time.time() - t0:.1f} s",
                isinstance(texte, str), texte)

# Le service, à part, comme pour de bon
import liaison  # noqa: E402

pythonw = RACINE / "python" / ("pythonw.exe" if os.name == "nt" else "python")
service_lance = subprocess.Popen([str(pythonw), str(RACINE / "windows" / "service.py")])
client = liaison.Client("service", 5.0)
fin, etat = time.time() + 300, {}
while time.time() < fin:
    client.appeler("attacher", pid=os.getpid())
    etat = client.appeler("etat") or {}
    if etat.get("pret") or etat.get("erreur"):
        break
    time.sleep(1)
verifie(f"service prêt ({etat.get('chargement')} s)", etat.get("pret"), etat)
r = client.appeler("proposer", contexte="", mot="ruhagh", graphie="v") or {}
verifie("service : propositions", "ruḥeɣ" in (r.get("formes") or []), r)
client.appeler("quitter")
try:
    service_lance.wait(30)
    verifie("service arrêté", True)
except subprocess.TimeoutExpired:
    service_lance.kill()
    verifie("service arrêté", False)

print(f"\n{ok} vérifications passées, {len(rates)} échec(s)")
for r in rates:
    print(f"  ÉCHEC {r}")
sys.exit(1 if rates else 0)
