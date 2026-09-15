#!/usr/bin/env python3
"""Vidage canonique des structures de ressources, pour comparaison Kotlin."""
import sys, csv
from pathlib import Path
RACINE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(RACINE / "pipeline" / "v2"))
csv.field_size_limit(10**9)
import config
from ressources import Ressources
r = Ressources(verbose=False)
r._charger_lexique(); r._charger_amyag(); r._charger_lexcat()
from semantique import WordNetKabyle
r.wn = WordNetKabyle().charger(config.WORDNET_JSON, verbose=False)
r._construire_pool()

with open(SORTIE / "09_lexique.tsv", "w", encoding="utf-8") as f:
    for m in sorted(r.freq):
        f.write(f"{m}\t{r.freq[m]}\t{r.nsrc[m]}\n")
print(f"  09_lexique.tsv        {len(r.freq):>9,}")

with open(SORTIE / "10_pool.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(r.pool))
print(f"  10_pool.txt           {len(r.pool):>9,}")

with open(SORTIE / "11_sdx.tsv", "w", encoding="utf-8") as f:
    for k in sorted(r.sdx_index):
        f.write(k + "\t" + " ".join(r.sdx_index[k]) + "\n")
print(f"  11_sdx.tsv            {len(r.sdx_index):>9,}")

with open(SORTIE / "12_amyag.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(sorted(r.amyag)))
print(f"  12_amyag.txt          {len(r.amyag):>9,}")

with open(SORTIE / "13_lexcat.tsv", "w", encoding="utf-8") as f:
    for m in sorted(r.lexcat):
        f.write(f"{m}\t{r.lexcat[m]}\n")
print(f"  13_lexcat.tsv         {len(r.lexcat):>9,}")

with open(SORTIE / "14_predicats.tsv", "w", encoding="utf-8") as f:
    for m in r.pool:
        f.write(f"{m}\t{int(r.fiable(m))}\t{int(r.valide_par_affixe(m))}\n")
print(f"  14_predicats.tsv      {len(r.pool):>9,}")

with open(SORTIE / "15_wordnet.tsv", "w", encoding="utf-8") as f:
    for m in sorted(r.wn.formes):
        g = r.wn.gloses.get(m, "").replace("\t", " ").replace("\n", " ")
        f.write(f"{m}\t{g}\n")
print(f"  15_wordnet.tsv        {len(r.wn.formes):>9,}")
