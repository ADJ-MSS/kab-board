#!/usr/bin/env python3
"""Capture les entrées que eval_v2 donne au correcteur, et ses réponses."""
import sys, json
from pathlib import Path
RACINE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
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

from correcteur import KabyleCorrecteurV2

appels_corriger = {}
appels_top5 = {}

_oc = KabyleCorrecteurV2.corriger
_ot = KabyleCorrecteurV2.top_candidats

def corriger(self, texte):
    r = _oc(self, texte)
    appels_corriger[texte] = r.texte_corrige
    return r

def top_candidats(self, mot, nb=5):
    r = _ot(self, mot, nb)
    appels_top5[f"{mot}\t{nb}"] = [c["candidat"] for c in r]
    return r

KabyleCorrecteurV2.corriger = corriger
KabyleCorrecteurV2.top_candidats = top_candidats

import runpy
_s.argv = ["eval_v2.py"]
runpy.run_path(str(RACINE / "pipeline" / "v2" / "eval_v2.py"), run_name="__main__")

(SORTIE / "20_eval_entrees.json").write_text(json.dumps({
    "corriger": sorted(appels_corriger),
    "top5": sorted(appels_top5),
}, ensure_ascii=False), encoding="utf-8")
(SORTIE / "21_eval_python.json").write_text(json.dumps({
    "corriger": appels_corriger, "top5": appels_top5,
}, ensure_ascii=False), encoding="utf-8")
print(f"\n  capturé : {len(appels_corriger):,} appels corriger, "
      f"{len(appels_top5):,} appels top_candidats")
