#!/usr/bin/env python3
"""Référence de l'étiqueteur : séquences d'étiquettes du correcteur V2."""
import sys, json
from pathlib import Path
RACINE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(RACINE / "pipeline" / "v2"))
import config, joblib
from ressources import _pos_features
from normalisation import tokenize

m = joblib.load(str(config.POS_MODEL))
print(f"  étiquettes : {len(m.classes_)}")

phrases = []
with open(RACINE / "data" / "corpus_kabylen.txt", encoding="utf-8") as f:
    for i, l in enumerate(f):
        if i % 7 == 0 and l.strip():
            t = tokenize(l.strip())
            if t: phrases.append(t)
        if len(phrases) >= 2000: break

out = []
for toks in phrases:
    feats = [_pos_features(toks, i) for i in range(len(toks))]
    tags = list(m.predict([feats])[0])
    out.append({"toks": toks, "tags": tags})
(SORTIE / "18_pos.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"  18_pos.json   {len(out):,} phrases, {sum(len(x['toks']) for x in out):,} mots")
