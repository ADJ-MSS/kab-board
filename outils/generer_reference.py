#!/usr/bin/env python3
"""Produit la référence d'or : ce que le correcteur Python répond, figé."""
import sys, json, random, re
from pathlib import Path

RACINE = Path(sys.argv[1])
SORTIE = Path(sys.argv[2])
sys.path.insert(0, str(RACINE / "pipeline" / "v2"))
sys.path.insert(0, str(RACINE / "pipeline" / "v1"))

from normalisation import normalize, tokenize, detacher_clitique, rejoindre_possessifs
from phonologie import soundex_kabyle, distance_kabyle

random.seed(20260908)
DATA = RACINE / "data"

def ecrire(nom, obj):
    p = SORTIE / nom
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {nom:<28} {len(obj):>7,} cas")

# ---- 1. normalisation, sur du texte réel non normalisé
brut = []
with open(DATA / "corpus_kenlm.txt", encoding="utf-8") as f:
    for i, l in enumerate(f):
        if i % 37 == 0: brut.append(l.strip())
        if len(brut) >= 4000: break
ecrire("01_normalize.json", [{"in": s, "out": normalize(s)} for s in brut])
ecrire("02_tokenize.json",  [{"in": s, "out": tokenize(s)} for s in brut])

# ---- 2. clitiques
toks = sorted({t for s in brut for t in tokenize(s)})
random.shuffle(toks)
ech = toks[:20000]
ecrire("03_clitiques.json", [{"in": t, "out": list(detacher_clitique(t))} for t in ech])
phrases_tok = [tokenize(s) for s in brut[:2000]]
ecrire("04_possessifs.json",
       [{"in": t, "out": rejoindre_possessifs(t)} for t in phrases_tok])

# ---- 3. code sonore
ecrire("05_soundex.json", [{"in": t, "out": soundex_kabyle(t)} for t in ech])

# ---- 4. distance pondérée : paires proches, celles qui comptent
paires = []
for a in ech[:3000]:
    for b in random.sample(ech, 6):
        paires.append((a, b))
for a in ech[:2000]:                       # paires volontairement voisines
    if len(a) > 3:
        i = random.randrange(len(a))
        paires.append((a, a[:i] + random.choice("aeiouɣḥṭḍṣẓ") + a[i+1:]))
ecrire("06_distance.json",
       [{"a": a, "b": b, "d": round(distance_kabyle(a, b), 9)} for a, b in paires])

print("\n  modules purs figés. Chargement du correcteur complet…")
from correcteur import KabyleCorrecteurV2
from eval_metrics import TESTS
cor = KabyleCorrecteurV2(verbose=False); cor.charger()

# ---- 5. top-5, le coeur du clavier
mots5 = ech[:4000]
ecrire("07_top5.json",
       [{"mot": m, "cands": cor.top_candidats(m, nb=5)} for m in mots5])

# ---- 6. correction complete, avec contexte et KenLM
phr = [t[0] for t in TESTS] + brut[:600]
ecrire("08_corriger.json",
       [{"in": p, "out": cor.corriger(p).texte_corrige} for p in phr])
print("\n  référence d'or complète.")
