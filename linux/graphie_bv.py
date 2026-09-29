"""Deux graphies en sortie : b et v.

Le kabyle note par un seul b ce que certains écrivent v. Ce module n'en décide
pas : il réécrit ce que le correcteur a produit, selon le réglage. Rien en
amont n'est touché, aucun objet reçu n'est modifié.

Trois modes : DEUX (les deux graphies), B, V.

La table ne liste que des formes de base. Un mot fléchi y est ramené par les
segments d'un mot à tirets, l'état d'annexion, l'annexion en we- et le pluriel
i…en ; sans quoi une phrase mêle les deux graphies. Restent dehors les emprunts
que la liste écarte, « belli », « ṛebbi », « mebla ».
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

DEUX = "deux"
B = "b"
V = "v"


def _appliquer_casse(modele: str, mot: str) -> str:
    """Reporte la casse de `modele` sur `mot` : Abrid -> Avrid, ABRID -> AVRID."""
    if modele.isupper() and len(modele) > 1:
        return mot.upper()
    if modele[:1].isupper():
        return mot[:1].upper() + mot[1:]
    return mot


# Les consonnes, comme dans le correcteur (postprocess.CONS_PATTERN).
_CONS = "[bcdfghjklmnpqrstvwxyzɣɛḍṭṛṣẓčšžɣ]"

# L'état libre, comme postprocess._vers_libre, plus la règle we-. Ces règles ne
# fabriquent qu'une clé de recherche : une réduction fausse manque la table.
_VERS_LIBRE = (
    (re.compile("^wu" + _CONS), lambda m: "u" + m[2:]),
    (re.compile("^wa"),         lambda m: "a" + m[2:]),
    (re.compile("^we" + _CONS), lambda m: "a" + m[2:]),   # weqbu -> aqbu
    (re.compile("^ye" + _CONS), lambda m: "i" + m[2:]),
    (re.compile("^yi"),         lambda m: "i" + m[2:]),
    (re.compile("^u" + _CONS),  lambda m: "a" + m[1:]),
    (re.compile("^te" + _CONS), lambda m: "ta" + m[2:]),
)
_RE_T_CONS = re.compile("^t" + _CONS)
_RE_TAIU = re.compile("^(ta|ti|tu)")
# Le pluriel des noms masculins : iɣriben <- aɣrib, ibridan <- abrid.
_RE_PLURIEL = re.compile("^i(" + _CONS + ".+?)(en|an)$")


def _reductions(mot: str) -> Iterable[str]:
    """Les formes de base que ce mot pourrait fléchir, la plus sûre d'abord."""
    vues = {mot}
    for etape in (mot,):
        for regle, refaire in _VERS_LIBRE:
            if regle.match(etape):
                vues.add(refaire(etape))
                break
        else:
            if _RE_T_CONS.match(etape) and not _RE_TAIU.match(etape):
                vues.add("ta" + etape[1:])
    for base in list(vues):                      # le pluriel d'une forme annexée
        m = _RE_PLURIEL.match(base)
        if m:
            vues.add("a" + m.group(1))
    return [c for c in vues if c != mot and len(c) >= 3]


def _lettres_basculees(mot: str, vers_v: bool) -> str:
    """Tous les b en v, ou l'inverse : la table ne fait jamais autre chose."""
    if vers_v:
        return mot.replace("b", "v").replace("B", "V")
    return mot.replace("v", "b").replace("V", "B")


@dataclass
class Choix:
    """Un mot que l'utilisateur peut écrire de deux façons."""
    index: int          # rang du mot dans le texte
    forme_b: str
    forme_v: str
    lemme: str = ""     # le verbe d'origine, quand la forme vient d'un paradigme


@dataclass
class SortieBV:
    """Le texte dans la graphie demandée, et les choix laissés ouverts."""
    texte: str
    choix: List[Choix] = field(default_factory=list)


class GraphieBV:

    def __init__(self, vers_v: Dict[str, str], lemmes: Optional[Dict[str, str]] = None):
        self.vers_v = vers_v
        self.vers_b = {v: b for b, v in vers_v.items()}
        self.lemmes = lemmes or {}

    @classmethod
    def charger(cls, chemin) -> "GraphieBV":
        vers_v, lemmes = {}, {}
        with open(Path(chemin), encoding="utf-8") as f:
            entete = next(f, "")
            if not entete.startswith("forme_b"):
                raise ValueError(f"en-tête inattendu dans {chemin} : {entete!r}")
            for ligne in f:
                champs = ligne.rstrip("\n").split("\t")
                if len(champs) < 2 or not champs[0] or not champs[1]:
                    continue
                b, v = champs[0], champs[1]
                vers_v[b] = v
                if len(champs) > 3 and champs[3]:
                    lemmes[b] = champs[3]
        return cls(vers_v, lemmes)

    # Un mot

    def alterne(self, mot: str) -> bool:
        return self.paire(mot) is not None

    def paire(self, mot: str):
        """Rend (forme_b, forme_v) dans la casse du mot reçu, ou None."""
        m = mot.lower()
        if m in self.vers_v:
            return _appliquer_casse(mot, m), _appliquer_casse(mot, self.vers_v[m])
        if m in self.vers_b:
            return _appliquer_casse(mot, self.vers_b[m]), _appliquer_casse(mot, m)
        if "-" in mot:
            return self._paire_a_tirets(mot)
        return self._paire_flechie(mot, m)

    def _paire_a_tirets(self, mot: str):
        """Chaque segment pour son compte : baba-s -> vava-s, d-nebder -> d-nevder."""
        segments = mot.split("-")
        paires = [self.paire(s) if s else None for s in segments]
        if not any(paires):
            return None
        b = "-".join(p[0] if p else s for s, p in zip(segments, paires))
        v = "-".join(p[1] if p else s for s, p in zip(segments, paires))
        return b, v

    def _paire_flechie(self, mot: str, m: str):
        """Forme fléchie : la table donne le lexème, l'annexion ne déplace jamais le b."""
        for cle in _reductions(m):
            if cle in self.vers_v:
                return mot, _lettres_basculees(mot, True)
            if cle in self.vers_b:
                return _lettres_basculees(mot, False), mot
        return None

    def variantes(self, mot: str, mode: str = DEUX) -> List[str]:
        """Les graphies à proposer pour ce mot, la première étant celle à retenir."""
        p = self.paire(mot)
        if p is None:
            return [mot]
        b, v = p
        if mode == B:
            return [b]
        if mode == V:
            return [v]
        return [b, v] if mot.lower() == b.lower() else [v, b]

    def basculer(self, mot: str, mode: str) -> str:
        """Le mot écrit dans la graphie demandée. Inchangé s'il n'alterne pas."""
        return self.variantes(mot, mode)[0]

    # Une liste de mots

    def enrichir_candidats(self, candidats: Sequence[dict], mode: str = DEUX,
                           cle: str = "candidat") -> List[dict]:
        """La sortie de top_candidats(), graphies comprises.

        En mode DEUX chaque candidat alternant est suivi de sa variante, marquée
        « graphie » et « variante_de ». Les dictionnaires reçus sont recopiés.
        """
        sortie: List[dict] = []
        vus = set()
        for c in candidats:
            mot = c.get(cle, "")
            if self.paire(mot) is None:          # mot qui n'alterne pas : intact
                if mot.lower() not in vus:
                    vus.add(mot.lower())
                    sortie.append(dict(c))
                continue
            formes = self.variantes(mot, mode)
            premier = dict(c)
            premier[cle] = formes[0]
            premier["graphie"] = B if formes[0].lower() in self.vers_v else V
            if premier[cle].lower() not in vus:
                vus.add(premier[cle].lower())
                sortie.append(premier)
            for autre in formes[1:]:
                if autre.lower() in vus:
                    continue
                vus.add(autre.lower())
                copie = dict(c)
                copie[cle] = autre
                copie["graphie"] = V if autre.lower() in self.vers_b else B
                copie["variante_de"] = mot
                sortie.append(copie)
        return sortie

    # Un texte

    def enrichir_texte(self, texte: str, mode: str = DEUX) -> SortieBV:
        """Le texte dans la graphie demandée, et la liste des mots à double graphie."""
        mots = texte.split(" ")
        choix: List[Choix] = []
        for i, brut in enumerate(mots):
            avant = brut[:len(brut) - len(brut.lstrip("«\"'([")) ]
            apres_len = len(brut) - len(brut.rstrip(".,;:!?»\"')]"))
            noyau = brut[len(avant):len(brut) - apres_len] if apres_len else brut[len(avant):]
            apres = brut[len(brut) - apres_len:] if apres_len else ""
            p = self.paire(noyau)
            if p is None:
                continue
            b, v = p
            mots[i] = avant + (v if mode == V else b) + apres
            if mode == DEUX:
                choix.append(Choix(i, b, v, self.lemmes.get(noyau.lower(), "")))
        return SortieBV(" ".join(mots), choix)

    def enrichir_resultat(self, resultat, mode: str = DEUX) -> SortieBV:
        """Comme enrichir_texte, sur un ResultatV2 dont on ne lit que le texte."""
        texte = getattr(resultat, "texte_corrige", None)
        if texte is None:
            texte = str(resultat)
        return self.enrichir_texte(texte, mode)
