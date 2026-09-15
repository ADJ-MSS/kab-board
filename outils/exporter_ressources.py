#!/usr/bin/env python3
"""Exporte les ressources du correcteur V2 en binaire lisible par Kotlin."""
import sys, csv, json, struct
from pathlib import Path

RACINE = Path(sys.argv[1])
SORTIE = Path(sys.argv[2])
SORTIE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(RACINE / "pipeline" / "v2"))
csv.field_size_limit(10**9)

import config
from normalisation import normalize
from phonologie import soundex_kabyle
from semantique import WordNetKabyle

MAGIC = b"TQBL"
VERSION = 1
BLOC = 16          # mots par bloc à préfixes factorisés


def ecrire_mots(chemin: Path, mots: list) -> None:
    """Liste triée, préfixes factorisés par blocs de 16."""
    data = bytearray()
    offsets = []
    for i in range(0, len(mots), BLOC):
        offsets.append(len(data))
        prec = ""
        for j, m in enumerate(mots[i:i + BLOC]):
            b = m.encode("utf-8")
            if j == 0:
                data += struct.pack("<H", len(b)) + b
            else:
                c = 0
                lim = min(len(prec), len(m), 255)
                while c < lim and prec[c] == m[c]:
                    c += 1
                r = m[c:].encode("utf-8")
                data += struct.pack("<BH", c, len(r)) + r
            prec = m
    with open(chemin, "wb") as f:
        f.write(MAGIC + struct.pack("<HII", VERSION, len(mots), len(offsets)))
        f.write(struct.pack(f"<{len(offsets)}I", *offsets))
        f.write(data)
    print(f"  {chemin.name:<26} {len(mots):>9,} mots  "
          f"{chemin.stat().st_size/1048576:6.2f} Mio")


def ecrire_u32(chemin: Path, vals: list) -> None:
    with open(chemin, "wb") as f:
        f.write(MAGIC + struct.pack("<HI", VERSION, len(vals)))
        f.write(struct.pack(f"<{len(vals)}I", *vals))
    print(f"  {chemin.name:<26} {len(vals):>9,} valeurs {chemin.stat().st_size/1048576:6.2f} Mio")


def ecrire_u8(chemin: Path, vals: list) -> None:
    with open(chemin, "wb") as f:
        f.write(MAGIC + struct.pack("<HI", VERSION, len(vals)))
        f.write(bytes(min(v, 255) for v in vals))
    print(f"  {chemin.name:<26} {len(vals):>9,} valeurs {chemin.stat().st_size/1048576:6.2f} Mio")


# ---------------------------------------------------------------- lexique
print("\n  Lecture des ressources V2\n")
freq, nsrc = {}, {}
chemin_lex = None
for fname in config.LEXICON_FILES:
    p = config.BASE / fname
    if p.exists():
        chemin_lex = p
        break
with open(chemin_lex, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        mot = row.get("mot", "")
        if not isinstance(mot, str) or not mot:
            continue
        try:
            fq = int(row["frequence"])
        except (KeyError, ValueError):
            continue
        freq[mot] = fq
        s = row.get("sources") or ""
        nsrc[mot] = (s.count("|") + 1) if s else 0

lex_tries = sorted(freq)                      # point de code, comme Python
ecrire_mots(SORTIE / "lexique.mots", lex_tries)
ecrire_u32(SORTIE / "lexique.freq", [freq[m] for m in lex_tries])
ecrire_u8(SORTIE / "lexique.nsrc", [nsrc[m] for m in lex_tries])

# ---------------------------------------------------------------- amyag
amyag = set()
if config.AMYAG_FORMES.exists():
    with open(config.AMYAG_FORMES, encoding="utf-8") as f:
        for line in f:
            mot = line.strip()
            if len(mot) >= 2:
                amyag.add(normalize(mot))       # normalisé, contrairement au lexique
ecrire_mots(SORTIE / "amyag.mots", sorted(amyag))

# ------------------------------------------------------- lexique catégories
lexcat = {}
if config.LEXCAT_FILE.exists():
    with open(config.LEXCAT_FILE, encoding="utf-8") as f:
        for line in f:
            brut, _, cat = line.rstrip("\n").partition("\t")
            mot = normalize(brut.strip())
            if len(mot) < 2 or " " in mot:
                continue
            if mot not in lexcat:
                lexcat[mot] = cat.strip()
cats = sorted({c for c in lexcat.values()})
lexcat_tries = sorted(lexcat)
ecrire_mots(SORTIE / "lexcat.mots", lexcat_tries)
ecrire_u8(SORTIE / "lexcat.cat", [cats.index(lexcat[m]) for m in lexcat_tries])
(SORTIE / "lexcat.noms").write_text("\n".join(cats), encoding="utf-8")
print(f"  lexcat.noms                {len(cats):>9,} catégories")

# ---------------------------------------------------------------- wordnet
wn = WordNetKabyle().charger(config.WORDNET_JSON, verbose=False)
wn_formes = sorted(wn.formes)
ecrire_mots(SORTIE / "wordnet.formes", wn_formes)
gl = {m: wn.gloses.get(m, "") for m in wn_formes}
(SORTIE / "wordnet.gloses").write_text(
    "\n".join(gl[m].replace("\t", " ").replace("\n", " ") for m in wn_formes),
    encoding="utf-8")
print(f"  wordnet.gloses             {sum(1 for v in gl.values() if v):>9,} gloses")

# ------------------------------------------------------------------ vivier
lexcat_content = {w for w, c in lexcat.items() if c in config.LEXCAT_CONTENT_CATS}
pool = {m for m, f in freq.items() if f >= config.FREQ_MIN_CANDIDAT and len(m) >= 2}
pool |= amyag
pool |= lexcat_content
pool |= wn.formes
pool = sorted(pool)                            # l'ordre décide des ex æquo
ecrire_mots(SORTIE / "pool.mots", pool)

# seaux sonores : clé -> indices dans le vivier, DANS L'ORDRE DU VIVIER
sdx = {}
for i, w in enumerate(pool):
    sdx.setdefault(soundex_kabyle(w), []).append(i)
cles = sorted(sdx)
with open(SORTIE / "pool.sdx", "wb") as f:
    f.write(MAGIC + struct.pack("<HI", VERSION, len(cles)))
    for k in cles:
        kb = k.encode("utf-8")
        f.write(struct.pack("<BH", len(kb), len(sdx[k])) + kb)
        f.write(struct.pack(f"<{len(sdx[k])}I", *sdx[k]))
print(f"  pool.sdx                   {len(cles):>9,} seaux   "
      f"{(SORTIE / 'pool.sdx').stat().st_size/1048576:6.2f} Mio")

total = sum(p.stat().st_size for p in SORTIE.iterdir())
print(f"\n  total exporté : {total/1048576:.2f} Mio\n")

# ------------------------------------------------- graphe : ancrages et voisins
# mot -> {sid: poids} et sid -> voisins, nécessaires à coherence()
sids_tries = sorted({s for d in wn.mot2sids.values() for s in d} |
                    set(wn.sid_voisins))
sid_id = {s: i for i, s in enumerate(sids_tries)}
(SORTIE / "wordnet.sids").write_text("\n".join(sids_tries), encoding="utf-8")

with open(SORTIE / "wordnet.ancrages", "wb") as f:
    formes_ancrees = sorted(wn.mot2sids)
    f.write(MAGIC + struct.pack("<HI", VERSION, len(formes_ancrees)))
    for m in formes_ancrees:
        mb = m.encode("utf-8")
        d = wn.mot2sids[m]
        f.write(struct.pack("<HH", len(mb), len(d)) + mb)
        for s, p in sorted(d.items()):
            f.write(struct.pack("<If", sid_id[s], p))
print(f"  wordnet.ancrages           {len(wn.mot2sids):>9,} formes ancrées")

with open(SORTIE / "wordnet.voisins", "wb") as f:
    cles = sorted(wn.sid_voisins)
    f.write(MAGIC + struct.pack("<HI", VERSION, len(cles)))
    for s in cles:
        v = sorted(sid_id[x] for x in wn.sid_voisins[s] if x in sid_id)
        f.write(struct.pack("<IH", sid_id[s], len(v)))
        f.write(struct.pack(f"<{len(v)}I", *v))
print(f"  wordnet.voisins            {len(wn.sid_voisins):>9,} concepts reliés")
print(f"  wordnet.sids               {len(sids_tries):>9,} identifiants")

# ------------------------------------------- listes closes de postprocess.py Exportées plutôt que
# recopiées.
import postprocess as _pp
from normalisation import PARTICULES_KABYLE, POSSESSIFS_KABYLE
_listes = {
    "verbes_whitelist":  _pp.VERBES_WHITELIST,
    "noms_invariables":  _pp.NOMS_INVARIABLES,
    "numeraux":          _pp.NUMERAUX,
    "prep_annexion":     _pp.PREP_ANNEXION,
    "prep_libre":        _pp.PREP_LIBRE,
    "etat_libre_force":  _pp.ETAT_LIBRE_FORCE,
    "mots_intouchables": _pp.MOTS_INTOUCHABLES,
    "particules":        PARTICULES_KABYLE,
    "possessifs":        POSSESSIFS_KABYLE,
}
with open(SORTIE / "listes.txt", "w", encoding="utf-8") as f:
    for nom, s in _listes.items():
        f.write(f"[{nom}]\n")
        for m in sorted(s):
            f.write(m + "\n")
for nom, s in _listes.items():
    print(f"  liste {nom:<20} {len(s):>6} entrées")

# ------------------------------------------- tableaux alignes sur le vivier Lecon d'AOSP LatinIME :
# rien ne se calcule au demarrage du clavier.
src_noms = ["lexique", "amyag", "wordnet"] + [f"lexcat_{c}" for c in cats]
src_id = {n: i for i, n in enumerate(src_noms)}

def source_de(forme):
    if forme in amyag:            return "amyag"
    if forme in lexcat:           return f"lexcat_{lexcat[forme]}"
    if forme in wn.formes:        return "wordnet"
    return "lexique"

ecrire_u32(SORTIE / "pool.freq", [freq.get(m, 0) for m in pool])
ecrire_u8 (SORTIE / "pool.nsrc", [nsrc.get(m, 0) for m in pool])
ecrire_u8 (SORTIE / "pool.src",  [src_id[source_de(m)] for m in pool])
(SORTIE / "pool.srcnoms").write_text("\n".join(src_noms), encoding="utf-8")
print(f"  pool.srcnoms               {len(src_noms):>9,} sources")

# --- Candidats de prediction ------------------------------------------------
NB_PREDICTION = 5000
frequents = sorted(pool, key=lambda m: -freq.get(m, 0))[:NB_PREDICTION]
(SORTIE / "pool.frequents").write_text("\n".join(frequents), encoding="utf-8")
print(f"  pool.frequents             {len(frequents):>9,} formes   "
      f"{(SORTIE / 'pool.frequents').stat().st_size/1024:6.1f} Kio")
