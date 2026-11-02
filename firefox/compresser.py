#!/usr/bin/env python3
"""Les ressources de l'extension pour Firefox : les petites telles quelles, le modèle de
langue et le modèle vocal compressés par xz, pour passer sous les limites de Mozilla.

    python3 firefox/compresser.py <chrome/extension/ressources> <firefox/extension/ressources>

Le modèle de langue perd en plus son vocabulaire : le tableau trié des empreintes de ses
mots (16 Mo, presque aléatoires, incompressibles), que la liste des mots, en fin de
fichier, suffit à refaire. Le correcteur le recalcule (chrome/autonome/xz_wasm.cc).
Le contrôle de Mozilla refuse aussi tout fichier de plus de 100 Mio : le flux xz est
coupé en parties de 64 Mio (<fichier>.xz.1, .xz.2…), que le correcteur relit à la suite.
compresses.json donne, pour chaque fichier compressé, sa taille et son empreinte
d'origine, et le nombre de parties. Une compression déjà faite pour les mêmes octets est
gardée ; ce qui a été compressé est écrit sur la sortie, un fichier par ligne.
"""
import glob
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys

# Le chemin, et s'il faut ôter le vocabulaire.
COMPRESSES = {"moteur/kabyle_3gram.binary": True, "voix/mmeslay.onnx": False}
PARTIE = 64 * 1024 * 1024


def empreinte(chemin: str) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for morceau in iter(lambda: f.read(1 << 22), b""):
            h.update(morceau)
    return h.hexdigest()


def vocabulaire(donnees: bytes):
    """La place du vocabulaire d'un modèle KenLM en trie : son début, sa taille."""
    ordre = donnees[88]
    tete = (88 + 20 + 8 * ordre + 7) & ~7
    n, = struct.unpack_from("<Q", donnees, tete)
    return tete + 8, 8 * n


def principal(argv) -> int:
    source, cible = argv[1:3]
    chemin_json = os.path.join(cible, "compresses.json")
    try:
        with open(chemin_json, encoding="utf-8") as f:
            avant = json.load(f)
    except (OSError, ValueError):
        avant = {}
    infos = {}
    for racine, _, fichiers in os.walk(source):
        for nom in sorted(fichiers):
            chemin = os.path.relpath(os.path.join(racine, nom), source).replace(os.sep, "/")
            de, vers = os.path.join(source, chemin), os.path.join(cible, chemin)
            os.makedirs(os.path.dirname(vers), exist_ok=True)
            if chemin not in COMPRESSES:
                shutil.copyfile(de, vers)
                continue
            info = {"taille": os.path.getsize(de), "sha256": empreinte(de)}
            if COMPRESSES[chemin]:
                info["vocabulaire"] = True
            precedent = avant.get(chemin, {})
            parties = precedent.get("parties", 0)
            if {k: v for k, v in precedent.items() if k != "parties"} == info and parties and all(
                    os.path.exists(f"{vers}.xz.{k}") for k in range(1, parties + 1)):
                infos[chemin] = precedent
                continue
            with open(de, "rb") as f:
                donnees = f.read()
            if COMPRESSES[chemin]:
                debut, taille = vocabulaire(donnees)
                donnees = donnees[:debut] + donnees[debut + taille:]
            xz = subprocess.run(["xz", "-9e", "-T2", "--stdout"], input=donnees, capture_output=True,
                                check=True).stdout
            for ancienne in glob.glob(glob.escape(vers) + ".xz*"):
                os.remove(ancienne)
            info["parties"] = (len(xz) + PARTIE - 1) // PARTIE
            for k in range(info["parties"]):
                with open(f"{vers}.xz.{k + 1}", "wb") as f:
                    f.write(xz[k * PARTIE:(k + 1) * PARTIE])
            infos[chemin] = info
            print(chemin, flush=True)
    with open(chemin_json, "w", encoding="utf-8") as f:
        json.dump(infos, f, indent=2)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
