"""Recherche en faisceau sur la phrase, scorée par KenLM."""
from typing import List

import config
from candidats import Candidat

try:
    import kenlm as _kenlm
    KENLM_OK = True
except ImportError:
    # Pas de module compilé : le pont ctypes vers la bibliothèque natif/pont
    # rend le même service, et n'exige aucun compilateur sur la machine.
    try:
        import pont_kenlm as _kenlm
        KENLM_OK = True
    except Exception:
        KENLM_OK = False


def decoder(cands_par_pos: List[List[Candidat]], kenlm_model,
            w_lm: float = None, beam: int = None) -> List[Candidat]:
    """Un candidat par position, maximise score local + w_lm × log P(KenLM)."""
    if w_lm is None:
        w_lm = config.W_LM
    if beam is None:
        beam = config.BEAM

    if not cands_par_pos:
        return []

    # Pas de LM : on prend le meilleur score local, la liste est déjà triée
    if kenlm_model is None or not KENLM_OK or w_lm <= 0:
        return [cs[0] for cs in cands_par_pos]

    etat0 = _kenlm.State()
    kenlm_model.BeginSentenceWrite(etat0)
    faisceau = [(0.0, etat0, [])]          # (score cumulé, état LM, chemin)

    for cands in cands_par_pos:
        nouveaux = []
        for sc, etat, chemin in faisceau:
            for c in cands:
                sortie = _kenlm.State()
                lp = kenlm_model.BaseScore(etat, c.forme, sortie)
                nouveaux.append((sc + c.score + w_lm * lp, sortie, chemin + [c]))
        nouveaux.sort(key=lambda x: x[0], reverse=True)
        faisceau = nouveaux[:beam]

    # Fin de phrase
    meilleur = None
    for sc, etat, chemin in faisceau:
        sortie = _kenlm.State()
        lp = kenlm_model.BaseScore(etat, "</s>", sortie)
        total = sc + w_lm * lp
        if meilleur is None or total > meilleur[0]:
            meilleur = (total, chemin)
    return meilleur[1]
