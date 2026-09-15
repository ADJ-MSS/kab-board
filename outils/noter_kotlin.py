#!/usr/bin/env python3
"""Rejoue eval_v2 avec les réponses du Kotlin, notées par le code d'origine."""
import sys, json
from pathlib import Path
RACINE, REF, KOT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(RACINE / "pipeline" / "v2"))
sys.path.insert(0, str(RACINE / "pipeline" / "v1"))

import config
config.LIMIT_EXTRACT = 10**9
import importlib.util, sys as _s
_p = RACINE / "pipeline" / "v2" / "candidats.py"
_src = _p.read_text(encoding="utf-8").replace("for f in formes:", "for f in sorted(formes):")
_spec = importlib.util.spec_from_file_location("candidats", str(_p))
_m = importlib.util.module_from_spec(_spec); _s.modules["candidats"] = _m
exec(compile(_src, "candidats.py", "exec"), _m.__dict__)

rep = json.loads(KOT.read_text(encoding="utf-8"))
rc, rt = rep["corriger"], rep["top5"]
manquants = {"c": 0, "t": 0}

from correcteur import KabyleCorrecteurV2
_oc, _ot = KabyleCorrecteurV2.corriger, KabyleCorrecteurV2.top_candidats

def corriger(self, texte):
    r = _oc(self, texte)                     # pour la structure du résultat
    if texte in rc:
        r.texte_corrige = rc[texte]
    else:
        manquants["c"] += 1
    return r

def top_candidats(self, mot, nb=5):
    cle = f"{mot}\t{nb}"
    if cle not in rt:
        manquants["t"] += 1
        return _ot(self, mot, nb)
    return [{"candidat": c, "distance": 0, "dist_ponderee": 0.0,
             "frequence": 0, "score": 0.0, "source": "", "glose": ""}
            for c in rt[cle]]

KabyleCorrecteurV2.corriger = corriger
KabyleCorrecteurV2.top_candidats = top_candidats

import runpy
_s.argv = ["eval_v2.py"]
runpy.run_path(str(RACINE / "pipeline" / "v2" / "eval_v2.py"), run_name="__main__")
print(f"\n  entrées non fournies par le Kotlin : "
      f"{manquants['c']} corriger, {manquants['t']} top-5")
