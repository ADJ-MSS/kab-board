"""Le correcteur, avec les deux graphies en sortie.

Enrobage : on appelle le correcteur tel quel, puis on passe sa sortie dans la
couche des graphies. Aucune ligne du pipeline n'est modifiée, aucun de ses
objets non plus. Retirer ce fichier rend le correcteur d'origine, à l'identique.

    from correcteur_bv import CorrecteurBV

    c = CorrecteurBV.charger()              # charge le pipeline puis la table
    r = c.corriger("ruḥeɣ ɣer webrid")
    r.texte                                 # "ruḥeɣ ɣer webrid"
    r.choix                                 # [Choix(index=2, 'webrid', 'wevrid')]
    c.top_candidats("abrid")                # chaque candidat suivi de sa variante

    c.mode = V                              # réglage de l'utilisateur
    c.corriger("ruḥeɣ ɣer webrid").texte    # "ruḥeɣ ɣer wevrid"
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from graphie_bv import GraphieBV, Choix, DEUX, B, V

RACINE = Path(__file__).resolve().parent              # le dossier linux/
DEPOT = RACINE.parent                                 # la racine de kab-board
try:
    import chemins
    TABLE = chemins.TABLE_BV
except Exception:
    TABLE = DEPOT / "app" / "src" / "main" / "assets" / "graphie" / "table_bv.tsv"
PIPELINE = RACINE / "pipeline"


@dataclass
class ResultatBV:
    """Ce que rend le correcteur, plus les choix de graphie."""
    texte: str
    choix: List[Choix] = field(default_factory=list)
    nb_corrections: int = 0
    corrections: List[tuple] = field(default_factory=list)
    brut: Optional[Any] = None      # le ResultatV2 d'origine, intact


class CorrecteurBV:

    def __init__(self, correcteur, graphie: GraphieBV, mode: str = DEUX):
        self.correcteur = correcteur
        self.graphie = graphie
        self.mode = mode

    @classmethod
    def charger(cls, table=TABLE, mode: str = DEUX, pipeline=PIPELINE) -> "CorrecteurBV":
        """Charge le pipeline d'origine, puis la table. L'ordre compte peu."""
        if str(pipeline) not in sys.path:
            sys.path.insert(0, str(pipeline))
        from correcteur import KabyleCorrecteurV2   # le pipeline, non modifié
        moteur = KabyleCorrecteurV2()
        moteur.charger()
        return cls(moteur, GraphieBV.charger(table), mode)

    # -- les deux appels du correcteur, enrobés ----------------------------

    def corriger(self, texte: str) -> ResultatBV:
        res = self.correcteur.corriger(texte)
        sortie = self.graphie.enrichir_resultat(res, self.mode)
        return ResultatBV(texte=sortie.texte,
                          choix=sortie.choix,
                          nb_corrections=getattr(res, "nb_corrections", 0),
                          corrections=list(getattr(res, "corrections", [])),
                          brut=res)

    def top_candidats(self, mot: str, nb: int = 5) -> List[dict]:
        return self.graphie.enrichir_candidats(
            self.correcteur.top_candidats(mot, nb), self.mode)

    # -- le réglage --------------------------------------------------------

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, valeur: str):
        if valeur not in (DEUX, B, V):
            raise ValueError(f"mode inconnu : {valeur!r} (attendu : {DEUX}, {B} ou {V})")
        self._mode = valeur
