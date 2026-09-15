#!/usr/bin/env python3
"""Référence top-5 déterministe : vivier balayé entièrement, ex æquo triés."""
import sys, json
from pathlib import Path
RACINE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(RACINE / "pipeline" / "v2"))

import config
config.LIMIT_EXTRACT = 10**9

# On rend l'itération de `formes` déterministe : le Python la laisse à
# l'ordre d'un set, donc au hachage, ce qui décide de la troncature à nb_max.
import importlib.util, sys as _sys
_spec = importlib.util.spec_from_file_location(
    "candidats", str(RACINE / "pipeline" / "v2" / "candidats.py"))
_src = (RACINE / "pipeline" / "v2" / "candidats.py").read_text(encoding="utf-8")
assert "for f in formes:" in _src
_src = _src.replace("for f in formes:", "for f in sorted(formes):")
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["candidats"] = _mod
exec(compile(_src, "candidats.py", "exec"), _mod.__dict__)

from correcteur import KabyleCorrecteurV2
cor = KabyleCorrecteurV2(verbose=False); cor.charger()

# le tri final reproduit celui de Candidats.kt, dernier critère = la forme
def top5(mot):
    from normalisation import normalize
    m = normalize(mot)
    cs = [c for c in cor._generer(m, "", large=True) if c.forme != m]
    def freq_aff(c):
        return max(c.freq, config.FREQ_PLANCHER_DICO) if c.source not in ("lexique","keep") else c.freq
    cs.sort(key=lambda c: (c.dist, -freq_aff(c), c.dist_p, c.forme))
    return [{"forme": c.forme, "source": c.source, "dist": c.dist,
             "dist_p": round(c.dist_p, 3), "freq": c.freq, "nsrc": c.nsrc,
             "score": round(c.score, 6)} for c in cs[:5]]

mots = [e["mot"] for e in json.load(open(SORTIE / "07_top5.json", encoding="utf-8"))]
out = [{"mot": m, "cands": top5(m)} for m in mots]
(SORTIE / "16_top5_deterministe.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"  16_top5_deterministe.json   {len(out):,} mots")
