#!/usr/bin/env python3
"""Référence KenLM : BaseScore mot à mot et score() de phrase entière."""
import sys, json
from pathlib import Path
RACINE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(RACINE / "pipeline" / "v2"))
import kenlm, config
from normalisation import tokenize

cfg = kenlm.Config(); cfg.load_method = kenlm.LoadMethod.LAZY
m = kenlm.Model(str(config.KENLM_BIN), cfg)
print(f"  ordre du modèle : {m.order}")

phrases = []
with open(RACINE / "data" / "corpus_kabylen.txt", encoding="utf-8") as f:
    for i, l in enumerate(f):
        if i % 11 == 0 and l.strip(): phrases.append(l.strip())
        if len(phrases) >= 1500: break

sortie = []
for p in phrases:
    toks = tokenize(p)
    if not toks: continue
    # BaseScore pas à pas, exactement comme le décodeur
    e = kenlm.State(); m.BeginSentenceWrite(e)
    pas = []
    for t in toks:
        s = kenlm.State()
        pas.append(round(m.BaseScore(e, t, s), 6))
        e = s
    fin = kenlm.State()
    pas.append(round(m.BaseScore(e, "</s>", fin), 6))
    sortie.append({
        "toks": toks,
        "base": pas,
        "s_bos_eos": round(m.score(" ".join(toks), bos=True, eos=True), 6),
        "s_nu":      round(m.score(" ".join(toks), bos=False, eos=False), 6),
    })
(SORTIE / "17_kenlm.json").write_text(json.dumps(sortie, ensure_ascii=False), encoding="utf-8")
print(f"  17_kenlm.json   {len(sortie):,} phrases, "
      f"{sum(len(x['base']) for x in sortie):,} appels BaseScore")
