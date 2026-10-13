"""Code sonore et distance d'édition pondérée."""
import re
from functools import lru_cache

VOYELLES = set("aeiou")

# Coûts de substitution, paires symétriques
_PAIRES = {
    # Diacritiques : la faute numéro un, on tape sur un clavier sans ces lettres
    ("t", "ṭ"): 0.25, ("d", "ḍ"): 0.25, ("s", "ṣ"): 0.25, ("z", "ẓ"): 0.25,
    ("r", "ṛ"): 0.25, ("h", "ḥ"): 0.25, ("c", "č"): 0.30, ("g", "ǧ"): 0.35,
    ("s", "š"): 0.35, ("c", "š"): 0.40, ("z", "ž"): 0.35,
    # Gutturales / vélaires proches
    ("x", "ɣ"): 0.50, ("h", "ɛ"): 0.60, ("ḥ", "ɛ"): 0.60, ("q", "ɣ"): 0.60,
    ("k", "g"): 0.50, ("g", "q"): 0.50, ("k", "q"): 0.50,
    # Sourde/voisée
    ("t", "d"): 0.60, ("s", "z"): 0.60, ("f", "b"): 0.65,
    # Semi-voyelles
    ("i", "y"): 0.30, ("u", "w"): 0.30,
    # Voyelles (schwa instable en kabyle)
    ("a", "e"): 0.35, ("e", "i"): 0.40, ("e", "u"): 0.45,
    ("a", "i"): 0.50, ("a", "u"): 0.55, ("i", "u"): 0.50, ("o", "u"): 0.30,
}
_CONF = {}
for (a, b), c in _PAIRES.items():
    _CONF[(a, b)] = c
    _CONF[(b, a)] = c

_COUT_TRANSPOSITION = 0.60


def _cout_sub(a: str, b: str) -> float:
    if a == b:
        return 0.0
    c = _CONF.get((a, b))
    if c is not None:
        return c
    if a in VOYELLES and b in VOYELLES:
        return 0.50
    return 1.0


def _cout_indel(ch: str, geminee: bool) -> float:
    if geminee:
        return 0.25          # tt↔t : gémination instable
    if ch == "e":
        return 0.30          # schwa épenthétique
    if ch in VOYELLES:
        return 0.55
    return 1.0


def distance_kabyle(a: str, b: str) -> float:
    """Damerau-Levenshtein pondérée par les confusions kabyles.

    Appelée sur une liste courte, rapidfuzz ayant déjà dégrossi en C.
    """
    if a == b:
        return 0.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return float(max(la, lb))

    # d[i][j] : ce que coûte le passage de a[:i] à b[:j]
    d = [[0.0] * (lb + 1) for _ in range(la + 1)]
    for i in range(1, la + 1):
        gem = (i >= 2 and a[i - 2] == a[i - 1]) or (i < la and a[i] == a[i - 1])
        d[i][0] = d[i - 1][0] + _cout_indel(a[i - 1], gem)
    for j in range(1, lb + 1):
        gem = (j >= 2 and b[j - 2] == b[j - 1]) or (j < lb and b[j] == b[j - 1])
        d[0][j] = d[0][j - 1] + _cout_indel(b[j - 1], gem)

    for i in range(1, la + 1):
        ca = a[i - 1]
        gem_a = (i >= 2 and a[i - 2] == ca) or (i < la and a[i] == ca)
        for j in range(1, lb + 1):
            cb = b[j - 1]
            gem_b = (j >= 2 and b[j - 2] == cb) or (j < lb and b[j] == cb)
            cout = min(
                d[i - 1][j] + _cout_indel(ca, gem_a),      # suppression
                d[i][j - 1] + _cout_indel(cb, gem_b),      # insertion
                d[i - 1][j - 1] + _cout_sub(ca, cb),       # substitution
            )
            # Transposition adjacente (Damerau)
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb and ca != cb:
                cout = min(cout, d[i - 2][j - 2] + _COUT_TRANSPOSITION)
            d[i][j] = cout
    return d[la][lb]


@lru_cache(maxsize=200_000)
def soundex_kabyle(mot: str, longueur: int = 5) -> str:
    """Code sonore kabyle, table Izemrane (URNOP 2016)."""
    if not mot:
        return ""
    mot = mot.lower()
    # Alignés sur NORM_TABLE, sinon le code dépend de si le mot est normalisé
    for k, v in (("gh", "γ"), ("ɣ", "γ"), ("kh", "x"), ("ch", "c"), ("dj", "ǧ")):
        mot = mot.replace(k, v)
    mot = re.sub(r"(.)\1+", r"\1", mot)
    table = {
        **dict.fromkeys("pb",      "1"),
        **dict.fromkeys("tṭ",      "2"),
        **dict.fromkeys("dḍ",      "3"),
        **dict.fromkeys("kgq",     "4"),
        "f":                       "5",
        **dict.fromkeys("sṣš",     "6"),
        **dict.fromkeys("zẓǧčcj",  "7"),
        **dict.fromkeys("xγhḥɛ",   "8"),
        **dict.fromkeys("lṛr",     "9"),
        **dict.fromkeys("mn",      "0"),
    }
    premiere = mot[0].upper()
    resultat = []
    precedent = ""
    for c in mot[1:]:
        if c in "aeiouwy":
            precedent = ""
            continue
        code = table.get(c, "")
        if code and code != precedent:
            resultat.append(code)
        precedent = code
    return ((premiere + "".join(resultat)) + "0" * longueur)[:longueur]
