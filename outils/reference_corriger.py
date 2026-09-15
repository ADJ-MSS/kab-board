#!/usr/bin/env python3
"""Référence de la chaîne complète : corriger() sur des phrases réelles."""
import sys, json
from pathlib import Path
RACINE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(RACINE / "pipeline" / "v2"))
sys.path.insert(0, str(RACINE / "pipeline" / "v1"))
import config
config.LIMIT_EXTRACT = 10**9      # balayage exhaustif, comme le portage

# itération déterministe de `formes`, comme Candidats.kt
import importlib.util, sys as _s
_p = RACINE / "pipeline" / "v2" / "candidats.py"
_src = _p.read_text(encoding="utf-8").replace("for f in formes:", "for f in sorted(formes):")
_spec = importlib.util.spec_from_file_location("candidats", str(_p))
_m = importlib.util.module_from_spec(_spec); _s.modules["candidats"] = _m
exec(compile(_src, "candidats.py", "exec"), _m.__dict__)

from correcteur import KabyleCorrecteurV2
from eval_metrics import TESTS
cor = KabyleCorrecteurV2(verbose=False); cor.charger()

phrases = [t[0] for t in TESTS]
with open(RACINE / "data" / "corpus_kabylen.txt", encoding="utf-8") as f:
    for i, l in enumerate(f):
        if i % 13 == 0 and l.strip(): phrases.append(l.strip())
        if len(phrases) >= 800: break

out = [{"in": p, "out": cor.corriger(p).texte_corrige} for p in phrases]
(SORTIE / "19_corriger.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"  19_corriger.json   {len(out):,} phrases")
