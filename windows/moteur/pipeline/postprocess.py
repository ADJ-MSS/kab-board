"""État d'annexion et possessifs, après le décodage."""
import re
from typing import Dict, List, Optional, Set, Tuple

import config
from normalisation import PARTICULES_KABYLE, POSSESSIFS_KABYLE

CONS_PATTERN = r'[bcdfghjklmnpqrstvwxyzɣɛḍṭṛṣẓčšžɣ]'
_VOYELLES_ETENDUES = set("aeiouɛ")

NOMS_INVARIABLES = {
    "laẓ", "fad", "seksu", "kra", "tala", "tileft", "tizya",
    "lmakla", "lmal", "lxedma", "lqahwa", "lḥlib", "lɛasel",
    "ssuq", "ssif", "nnif", "lkul", "lɛmer", "lɣaci",
    "izimmer", "imaziɣen", "iberber",
    "tuššent", "tizi",
    "taddart",
    "wul",
    "aṭas", "drus", "akka", "akken",
    "sdat", "sdeffir", "simal", "ticki", "ladɣa",
    "ayen", "win", "tin", "wid", "tid", "acu",
    # Les noms de parenté ne prennent jamais l'annexion. Le regex en ^ye…
    # attrapait « yemma » et sortait « imma », ce qui n'existe pas.
    "yemma", "baba", "jeddi", "setti", "nanna", "xali", "xalti", "ɛemmi",
}

PREP_ANNEXION = {
    "n", "i", "gg", "deg", "g", "ɣef", "ddaw", "nnig",
    "ɣer", "fell", "di", "si", "afella", "tama", "idis",
}
PREP_LIBRE       = {"ar"}
ETAT_LIBRE_FORCE = {"d", "ur", "mačči"}

VERBES_WHITELIST = set([
    "yella", "yellan", "yettili", "yegra-d", "yeččur", "yexla", "yemmed", "yemmed-d",
    "iruh", "iruḥ", "iruh-d", "iruḥ-d",
    "yusa", "yusa-d", "yusan-d", "yettas-d",
    "yuɣal", "yuɣalen", "yuɣal-d", "yettuɣal", "yettuɣal-d",
    "yekcer", "yekcem", "yukcem", "yekcem-d",
    "yeffeɣ", "yeffɣen", "yeffeɣ-d",
    "yuli", "yuli-d", "yulin-d", "yettali", "yettali-d",
    "yader", "yader-d", "yettader", "yettader-d",
    "yedda", "yeddan", "yeddu", "yedda-d",
    "yekker", "yekkren", "yekker-d", "yettakker-d",
    "yewweḍ", "yewwed", "yewweḍ-d",
    "yuzzel", "yuzzel-d", "yettazzal",
    "yers", "yers-d", "yeqqim", "yeqqim-d",
    "yextit", "yextit-d",
    "yewhem", "yessewham", "yurar", "yecba", "yecfa", "yeẓẓi", "yettru",
    "yesber", "yettaɛraq", "yuggad", "yeḍseḍ", "yerrfa", "yezhu", "yennuɣna",
    "yefreḥ", "yeḥzen",
    "yedder", "yedder-d", "yettidir", "yemmut", "yehlek", "yeḥla", "yelluẓ", "yeffud",
    "yens", "yeggun", "yettargu", "yettargu-d", "yettmeslay", "yettmeslay-d",
    "yewwet-d", "yeqquṛ", "yebzeg", "yeḥma", "yessemmeḍ", "yeḍra", "yeḍra-d",
    "yemmuger", "yennulfa-d", "yefruri-d", "yegman-d", "yefsex-d",
    "tella", "tuɣal", "tewwi", "tekker", "tufa", "tenna", "tusa",
    "truh", "truḥ", "tekcem", "teffeɣ", "tuli", "tegla", "tebɣa", "teqqar",
    "tedda", "tuɣ", "tewt", "tekfa", "teẓra", "tesɣa", "tenɣa",
    "teddu", "teṭṭef", "tettru", "tettili", "tellel",
    "llan", "uɣalen", "wwten", "kkren", "ffɣen", "qqaren", "slan",
    "ddan", "kecmen", "ulin", "eglan", "bɣan", "ran", "qqiman",
    "ẓran", "esɣan", "nɣan", "rran", "kksen", "ǧǧan", "fkan",
    "yenna-yas", "tenna-yas", "yewwi-d", "yusa-d", "yuɣal-d",
    "d-yuɣal", "d-tuɣal", "d-yusa", "d-tusa", "d-yeffeɣ", "d-teffeɣ",
    "ad", "ar", "ur", "ara", "ulac", "mačči", "ala", "ihi",
    "d", "iga", "tga", "gan",
])

MOTS_INTOUCHABLES = (
    PREP_ANNEXION | PREP_LIBRE | ETAT_LIBRE_FORCE | PARTICULES_KABYLE | POSSESSIFS_KABYLE
    | {
        "nekk", "nekki", "kečč", "kemmi", "netta", "nettat", "nekni", "kunwi",
        "kunemti", "nutni", "nutenti", "nekenti",
        "wagi", "tagi", "wid", "tid", "win", "tin", "acu", "ma", "anda", "akken",
        "ad", "ara", "ur", "ulac", "ala", "ihi", "aṭas", "drus", "am", "mara",
        "ticki", "af", "khati",
        "ladɣa", "ɣas", "wissen", "sɣur", "acku", "imi", "mi", "yal",
        "kra", "yiwen", "yiwet",
    }
)

NUMERAUX = {
    "yiwen", "yiwet", "sin", "snat", "tlata", "tlatin",
    "rebɛa", "xemsa", "setta", "sebɛa", "tamanya", "tẓa", "mraw",
    "wis", "tis", "iẓd",
}


def _has_triple_cons(mot: str) -> bool:
    mot = re.sub(r"(.)\1+", r"\1", mot)
    count = 0
    for c in mot:
        if c not in _VOYELLES_ETENDUES:
            count += 1
            if count >= 3:
                return True
        else:
            count = 0
    return False


def _vers_annexion(base):
    if base in VERBES_WHITELIST or base in NUMERAUX: return base
    if re.match(r'^u' + CONS_PATTERN, base):                           return "wu" + base[1:]
    if re.match(r'^a(xx|ɣɣ|qq|ṭṭ|ḍḍ|ẓẓ|čč|šš|ṛṛ|ṣṣ)', base):        return "wu" + base[1:]
    if re.match(r'^a(ss|mm|ff|bb|nn|ll|rr|tt|dd|gg|kk|ww)', base):    return "wa" + base[1:]
    if re.match(r'^am[aeiou]', base):                                  return "wa" + base[1:]
    if re.match(r'^a' + CONS_PATTERN, base):                           return "u"  + base[1:]
    if re.match(r'^i' + CONS_PATTERN + r'.+en$', base):                return "ye" + base[1:]
    if re.match(r'^i[lrfwmnb]', base):                                 return "yi" + base[1:]
    if re.match(r'^ta' + CONS_PATTERN, base):
        candidate = "t" + base[2:]
        return "te" + base[2:] if _has_triple_cons(candidate) else candidate
    if re.match(r'^ti' + CONS_PATTERN, base):                          return "te" + base[2:]
    return base


def _vers_libre(base):
    if base in VERBES_WHITELIST or base in NUMERAUX: return base
    if re.match(r'^wu' + CONS_PATTERN, base):                          return "u"  + base[2:]
    if re.match(r'^wa', base):                                         return "a"  + base[2:]
    if re.match(r'^ye' + CONS_PATTERN, base):                          return "i"  + base[2:]
    if re.match(r'^yi', base):                                         return "i"  + base[2:]
    if re.match(r'^u' + CONS_PATTERN, base):                           return "a"  + base[1:]
    if re.match(r'^te' + CONS_PATTERN, base):                          return "ta" + base[2:]
    if re.match(r'^t' + CONS_PATTERN, base) and not re.match(r'^(ta|ti|tu)', base):
        return "ta" + base[1:]
    return base


def vers_annexion(mot):
    if mot in NOMS_INVARIABLES: return mot
    p = mot.split("-")
    suf = ("-" + "-".join(p[1:])) if len(p) > 1 else ""
    return _vers_annexion(p[0]) + suf


def vers_libre(mot):
    if mot in NOMS_INVARIABLES: return mot
    p = mot.split("-")
    suf = ("-" + "-".join(p[1:])) if len(p) > 1 else ""
    return _vers_libre(p[0]) + suf


def identifier_nom_etat(mot):
    base = mot.split("-")[0]
    if base in VERBES_WHITELIST:                                        return False, None, None
    if base in NUMERAUX:                                                return False, None, None
    if base in NOMS_INVARIABLES:                                        return True, "invariable", "syncrétisme"
    if re.match(r'^wu' + CONS_PATTERN, base):                          return True, "annexion", "Type3"
    if re.match(r'^wa', base):                                         return True, "annexion", "Type2"
    if re.match(r'^ye' + CONS_PATTERN, base):                          return True, "annexion", "Type4"
    if re.match(r'^yi', base):                                         return True, "annexion", "Type5"
    if re.match(r'^u' + CONS_PATTERN, base):                           return True, "annexion", "Type1"
    if re.match(r'^a' + CONS_PATTERN, base):                           return True, "libre",    "Type1/2"
    if re.match(r'^i' + CONS_PATTERN, base):                           return True, "libre",    "Type4/5/6"
    if re.match(r'^te' + CONS_PATTERN, base):                          return True, "annexion", "Type7/10"
    if re.match(r'^t' + CONS_PATTERN, base) and not re.match(r'^(ta|ti|tu)', base):
        return True, "annexion", "Type7"
    if re.match(r'^ta' + CONS_PATTERN, base):                          return True, "libre",    "Type7"
    if re.match(r'^ti' + CONS_PATTERN, base):                          return True, "libre",    "Type10/11"
    if re.match(r'^tu' + CONS_PATTERN, base):                          return True, "libre",    "Type9"
    return False, None, None


def analyser_contexte_annexion(tokens, idx):
    if idx == 0:
        return "libre", "sujet initial"
    prec = tokens[idx - 1].split("-")[0].lower()
    if prec in ETAT_LIBRE_FORCE:    return "libre",    f"après '{prec}'"
    if prec in PREP_LIBRE:          return "libre",    f"après '{prec}' (exception Chaker)"
    if prec in PREP_ANNEXION:       return "annexion", f"après préposition '{prec}'"
    if prec in NUMERAUX:            return "annexion", f"après numéral '{prec}'"
    if prec in VERBES_WHITELIST:    return "annexion", f"sujet post-verbal après '{prec}'"
    return None, None


_LEXCAT_NOMINAL_CATS = {"masc", "fem", "fem_pl", "adj_masc", "adj_fem", "ambig"}


def propositions_chaker(tokens: List[str], verbes: Optional[Set[str]] = None,
                        lexcat_words: Optional[Dict[str, str]] = None
                        ) -> List[Tuple[int, str, str, str]]:
    """Réécritures proposées : (idx, avant, après, raison)."""
    propositions = []
    for i, tok in enumerate(tokens):
        if verbes and (tok in verbes or tok.split("-")[0] in verbes):
            continue
        est_n, etat, _ = identifier_nom_etat(tok)
        if lexcat_words and lexcat_words.get(tok) in _LEXCAT_NOMINAL_CATS:
            est_n = True
            if etat == "invariable":
                etat = "libre"
        if not est_n or etat == "invariable":
            continue
        requis, raison = analyser_contexte_annexion(tokens, i)
        if requis is None:
            continue
        if requis == "annexion" and etat == "libre":
            forme = vers_annexion(tok)
        elif requis == "libre" and etat == "annexion":
            forme = vers_libre(tok)
        else:
            continue
        if forme != tok:
            propositions.append((i, tok, forme, raison))
    return propositions


def appliquer_chaker_valide_lm(tokens: List[str], kenlm_model,
                               verbes=None, lexcat_words=None,
                               verbose: bool = False):
    """Chaker, chaque réécriture annulée si le LM chute de trop."""
    corrigee = list(tokens)
    corrections = []
    for idx, avant, apres, raison in propositions_chaker(
            tokens, verbes=verbes, lexcat_words=lexcat_words):
        if kenlm_model is not None:
            avant_s = " ".join(corrigee)
            essai = list(corrigee)
            essai[idx] = apres
            delta = (kenlm_model.score(" ".join(essai), bos=True, eos=True)
                     - kenlm_model.score(avant_s, bos=True, eos=True))
            if delta < -config.LM_REJET_CHAKER:
                if verbose:
                    print(f"  Chaker annulé par LM : '{avant}' → '{apres}' "
                          f"(Δ={delta:.2f})")
                continue
        if verbose:
            print(f"  Chaker : '{avant}' → '{apres}' [{raison}]")
        corrigee[idx] = apres
        corrections.append((avant, apres, raison))
    return corrigee, corrections
