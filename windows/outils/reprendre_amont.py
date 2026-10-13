#!/usr/bin/env python3
"""Reprend le moteur de kab-board dans moteur/, et dit ce qui a changé.

    python outils/reprendre_amont.py ../kab-board

Le correcteur n'est pas réécrit pour Windows : c'est celui de Linux, copié tel
quel. Deux fichiers seulement sont adaptés, et ne sont donc jamais écrasés :
le script signale qu'ils ont bougé en amont, pour qu'on reporte à la main.

    pipeline/ressources.py   le cache du lexique, repris de la version Word
    test_graphie_bv.py       le chemin de la table des graphies
"""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent.parent
MOTEUR = ICI / "moteur"

# destination dans moteur/  <-  source dans kab-board
COPIES = {
    "chemins.py": "linux/chemins.py",
    "graphie_bv.py": "linux/graphie_bv.py",
    "correcteur_bv.py": "linux/correcteur_bv.py",
    "completion.py": "linux/completion.py",
    "saisie.py": "linux/ibus/saisie.py",
    "ressources_kab.py": "linux/bureau/ressources_kab.py",
    "dictee.py": "linux/bureau/dictee.py",
    "test_completion.py": "linux/test_completion.py",
    "test_saisie.py": "linux/ibus/test_saisie.py",
    "data/lexique_categories.txt": "linux/data/lexique_categories.txt",
    "graphie/table_bv.tsv": "app/src/main/assets/graphie/table_bv.tsv",
}
for nom in ("config", "normalisation", "phonologie", "semantique", "candidats",
            "decodeur", "postprocess", "correcteur", "pont_kenlm", "pont_crf"):
    COPIES[f"pipeline/{nom}.py"] = f"linux/pipeline/{nom}.py"

ADAPTES = {
    "pipeline/ressources.py": "linux/pipeline/ressources.py",
    "test_graphie_bv.py": "linux/test_graphie_bv.py",
}


def empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def principal(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    amont = Path(argv[1]).resolve()
    try:
        commit = subprocess.run(["git", "-C", str(amont), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        commit = "inconnu"
    changes = 0
    for dest, src in COPIES.items():
        s, d = amont / src, MOTEUR / dest
        if d.exists() and empreinte(s) == empreinte(d):
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        changes += 1
        print(f"  repris  {dest}")
    trace = ICI / "moteur" / ".amont-adaptes"
    anciennes = {}
    if trace.exists():
        for ligne in trace.read_text(encoding="utf-8").splitlines():
            nom, _, valeur = ligne.partition(" ")
            anciennes[nom] = valeur
    nouvelles = []
    for dest, src in ADAPTES.items():
        e = empreinte(amont / src)
        if anciennes.get(dest) and anciennes[dest] != e:
            print(f"  À REPORTER À LA MAIN : {src} a changé en amont ({dest} est adapté)")
        nouvelles.append(f"{dest} {e}")
    trace.write_text("\n".join(nouvelles) + "\n", encoding="utf-8")
    (MOTEUR / "AMONT-COMMIT").write_text(commit + "\n", encoding="utf-8")
    print(f"{changes} fichier(s) repris de kab-board {commit[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
