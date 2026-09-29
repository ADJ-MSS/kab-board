"""Normalisation, découpage, clitiques."""
import re
import unicodedata
from typing import List, Tuple

NORM_TABLE = {"gh": "ɣ", "aa": "ɛ", "ou": "u", "dh": "ḍ", "th": "t", "kh": "x", "ch": "c"}

# Consonnes labialisées : géminées → ww, simples → suppression du ʷ
_LABIALIZED_TABLE = [
    ("ggʷ", "ww"), ("bbʷ", "ww"), ("ppʷ", "ww"),
    ("gʷ",  "g"),  ("bʷ",  "b"),  ("pʷ",  "p"),
]

TOKEN_RE = re.compile(
    r"[a-zàâæçéèêëîïôœùûüÿɣɛḍṭxṛṣẓčšžɣḥǧ'\-]+",
    re.IGNORECASE | re.UNICODE
)

PARTICULES_KABYLE = {"n", "d", "i", "g", "s", "w"}
# Tokens d'une lettre conservés à la tokenisation (particules + abréviation ɣ)
_UN_CHAR_GARDES = PARTICULES_KABYLE | {"ɣ"}

POSSESSIFS_KABYLE = {"iw", "ik", "im", "is", "nneɣ", "nwen", "nkent", "nsen", "nsent"}

# Clitiques suffixaux : détachés avant correction, recollés après.
CLITIQUES_SUFF = POSSESSIFS_KABYLE | {
    "d",                                  # directionnel
    "yas", "yasen", "yasent",             # datif 3e personne
    "yi",                                 # datif 1sg
    "ak", "am",                           # datif 2sg m/f
    "nni", "ni",                          # démonstratif / restrictif
}

PREFIXES_DIRECTIONNELS = {"d", "as", "aɣ", "iyi", "ak", "am", "ay"}


def normalize(t: str) -> str:
    t = unicodedata.normalize("NFC", t.lower().strip())
    for k, v in _LABIALIZED_TABLE:
        t = t.replace(k, v)
    for k, v in NORM_TABLE.items():
        t = t.replace(k, v)
    return t


def tokenize(t: str) -> List[str]:
    return [x for x in TOKEN_RE.findall(normalize(t))
            if len(x) >= 2 or x in _UN_CHAR_GARDES]


def detacher_clitique(tok: str) -> Tuple[str, str, str]:
    """Retourne (prefixe, base, suffixe), tiret compris."""
    # Suffixe clitique : "axxam-iw", "yewwi-d"
    pos = tok.rfind("-")
    if pos > 1:
        base, suf = tok[:pos], tok[pos + 1:]
        if suf in CLITIQUES_SUFF:
            return "", base, "-" + suf
    # Préfixe directionnel : "d-yeddem"
    if tok.count("-") == 1:
        pref, base = tok.split("-", 1)
        if pref in PREFIXES_DIRECTIONNELS and len(base) >= 2:
            return pref + "-", base, ""
    return "", tok, ""


def rejoindre_possessifs(tokens: List[str]) -> List[str]:
    """Joint les suffixes possessifs au mot précédent avec un tiret."""
    if len(tokens) < 2:
        return tokens
    out: List[str] = []
    for i, tok in enumerate(tokens):
        if i > 0 and tok in POSSESSIFS_KABYLE and out:
            out[-1] = out[-1] + "-" + tok
        else:
            out.append(tok)
    return out
