"""Génération des candidats."""
import math
from dataclasses import dataclass, field
from typing import List

import config
from phonologie import distance_kabyle, soundex_kabyle
from ressources import Ressources, RAPIDFUZZ_OK, POS_VERB_TAGS, POS_NOUN_TAGS
from postprocess import MOTS_INTOUCHABLES
from normalisation import PARTICULES_KABYLE, POSSESSIFS_KABYLE

if RAPIDFUZZ_OK:
    from rapidfuzz import process, distance as rf_dist


@dataclass
class Candidat:
    forme:    str
    source:   str          # "keep" | "amyag" | "lexcat_<cat>" | "lexique" | "abrev"
    dist_p:   float        # distance pondérée kabyle
    dist:     int          # distance DL brute
    freq:     int
    nsrc:     int
    meme_sdx: bool
    score:    float = 0.0


def _source_de(forme: str, res: Ressources) -> str:
    if forme in res.amyag:
        return "amyag"
    if forme in res.lexcat:
        return f"lexcat_{res.lexcat[forme]}"
    if res.wn is not None and forme in res.wn.formes:
        return "wordnet"
    return "lexique"


def _est_dico(source: str) -> bool:
    return (source == "amyag" or source == "wordnet"
            or source.startswith("lexcat_"))


def _scorer(c: Candidat, res: Ressources, pos_tag: str, bonus_keep: float) -> float:
    if c.source == "keep":
        return (bonus_keep
                + config.W_FREQ * min(math.log10(c.freq + 1) / 6.0, 1.0)
                + config.W_NSRC * min(c.nsrc, 8) / 8.0)
    est_verbal  = c.source == "amyag"
    est_nominal = c.source.startswith("lexcat_")
    est_dico    = _est_dico(c.source)
    # Une forme de dictionnaire absente du lexique a freq 0 : plancher
    freq = max(c.freq, config.FREQ_PLANCHER_DICO) if est_dico else c.freq
    nsrc = max(c.nsrc, config.NSRC_PLANCHER_DICO) if est_dico else c.nsrc

    s = -config.W_DIST * c.dist_p
    s += config.W_FREQ * min(math.log10(freq + 1) / 6.0, 1.0)
    s += config.W_NSRC * min(nsrc, 8) / 8.0
    if c.meme_sdx:
        s += config.W_SDX
    # Graphie avec diacritiques d'un mot tapé en ASCII : lhif -> lḥif
    if est_dico and c.meme_sdx and c.dist_p <= config.VAR_MAX_DIST_P:
        s += config.BONUS_VARIANTE
    # Porte POS de la v1, devenue une pénalité
    if pos_tag in POS_NOUN_TAGS and est_verbal and not est_nominal:
        s -= config.W_POS
    if pos_tag in POS_VERB_TAGS and est_nominal and not est_verbal:
        s -= config.W_POS
    # Peu attesté et absent des dictionnaires : on s'en méfie
    if c.source == "lexique" and c.nsrc < config.MIN_SOURCES_FIABLE:
        s -= config.PEN_DOUTEUX
    return s


def generer(token: str, res: Ressources, pos_tag: str = "",
            nb_max: int = 24, large: bool = False) -> List[Candidat]:
    """Candidats triés, « garder » compris. large=True pour le top-5."""
    keep = Candidat(
        forme=token, source="keep", dist_p=0.0, dist=0,
        freq=res.freq.get(token, 0), nsrc=res.nsrc.get(token, 0), meme_sdx=True,
    )

    # Mots grammaticaux et tokens trop courts : on n'y touche pas
    if (token in MOTS_INTOUCHABLES or token in PARTICULES_KABYLE
            or token in POSSESSIFS_KABYLE or len(token) < 2) \
            and token not in config.ABREVIATIONS:
        keep.score = _scorer(keep, res, pos_tag, config.BONUS_KEEP_DICO)
        if not large:
            return [keep]

    # Seul le niveau dico restreint la recherche au groupe sonore : un token
    # multi-sources peut être une faute tombée sur un autre mot réel.
    if token in config.ABREVIATIONS:
        # « ɣ » seul n'est pas un mot, le LM tranchera
        bonus_keep = config.BONUS_KEEP_OOV
        niveau_dico = False
    elif token in res.amyag or token in res.lexcat \
            or (res.wn is not None and token in res.wn.formes):
        bonus_keep = config.BONUS_KEEP_DICO
        niveau_dico = True
    elif res.nsrc.get(token, 0) >= config.MIN_SOURCES_FIABLE \
            or res.freq.get(token, 0) >= config.FREQ_FIABLE:
        bonus_keep = config.BONUS_KEEP_SEMI
        niveau_dico = False
    elif res.valide_par_affixe(token):
        bonus_keep = config.BONUS_KEEP_VALIDE
        niveau_dico = False
    else:
        bonus_keep = config.BONUS_KEEP_OOV
        niveau_dico = False
    keep.score = _scorer(keep, res, pos_tag, bonus_keep)

    if not RAPIDFUZZ_OK or not res.pool:
        return [keep]

    sdx_tok = soundex_kabyle(token)
    formes = set()

    # Groupe sonore : rattrape ce que la distance seule rate
    for cand in res.sdx_index.get(sdx_tok, ()):
        if cand != token and rf_dist.DamerauLevenshtein.distance(
                token, cand, score_cutoff=config.MAX_DIST_BRUTE) \
                <= config.MAX_DIST_BRUTE:
            formes.add(cand)

    # Pas de recherche large sur un mot de dictionnaire : seules les
    # variantes de son groupe sonore peuvent le détrôner
    if (large or not niveau_dico) and len(token) >= 2:
        for cand, d, _ in process.extract(
                token, res.pool,
                scorer=rf_dist.DamerauLevenshtein.distance,
                score_cutoff=config.MAX_DIST_BRUTE,
                limit=config.LIMIT_EXTRACT * (2 if large else 1)):
            if cand != token:
                formes.add(cand)

    # Abréviations : ɣ -> ɣer ou ɣef, le LM choisit
    abrevs = set(config.ABREVIATIONS.get(token, ()))
    formes |= abrevs

    seuil = config.seuil_dist_ponderee(len(token)) * (1.4 if large else 1.0)
    cands: List[Candidat] = [keep]
    for f in formes:
        dp = 0.5 if f in abrevs else distance_kabyle(token, f)
        if f not in abrevs and dp > seuil:
            continue
        c = Candidat(
            forme=f,
            source="abrev" if f in abrevs else _source_de(f, res),
            dist_p=round(dp, 3),
            dist=rf_dist.DamerauLevenshtein.distance(token, f),
            freq=res.freq.get(f, 0),
            nsrc=res.nsrc.get(f, 0),
            meme_sdx=(soundex_kabyle(f) == sdx_tok),
        )
        c.score = _scorer(c, res, pos_tag, bonus_keep)
        cands.append(c)

    cands.sort(key=lambda c: c.score, reverse=True)
    return cands[:nb_max]
