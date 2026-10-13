"""KenLM par ctypes, quand le module compilé manque.

Le module « kenlm » de PyPI n'existe qu'en source : sous Windows, l'installer
demande un compilateur C++ à l'utilisateur. La bibliothèque natif/pont, elle,
est construite une fois pour toutes et se charge sans rien compiler.

L'interface est celle du module d'origine, réduite à ce dont le décodeur se
sert, pour que le pipeline ne fasse pas la différence :

    import pont_kenlm as kenlm
    m = kenlm.Model(chemin)
    e = kenlm.State(); m.BeginSentenceWrite(e)
    lp = m.BaseScore(e, "aɣrum", sortie)
"""
import ctypes
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent    # la racine du dépôt


def _chemins_possibles():
    """Où la bibliothèque peut se trouver, du plus précis au plus général."""
    nom = "kab_lm.dll" if os.name == "nt" else "libkab_lm.so"
    depuis_env = os.environ.get("KAB_LM_PONT")
    if depuis_env:
        yield Path(depuis_env)
    ici = Path(__file__).resolve().parent
    yield ici / nom                          # à côté du pipeline, dans un paquet
    yield ici.parent / nom
    yield RACINE / "natif" / "pont" / nom    # dans le dépôt
    yield Path(nom)                          # au chargeur de se débrouiller


def _charger_bibliotheque():
    derniere = None
    for chemin in _chemins_possibles():
        try:
            return ctypes.CDLL(str(chemin))
        except OSError as erreur:
            derniere = erreur
    raise ImportError(f"pont KenLM introuvable ({derniere})")


_lib = _charger_bibliotheque()

_lib.kab_lm_ouvrir.argtypes = [ctypes.c_char_p]
_lib.kab_lm_ouvrir.restype = ctypes.c_void_p
_lib.kab_lm_fermer.argtypes = [ctypes.c_void_p]
_lib.kab_lm_ordre.argtypes = [ctypes.c_void_p]
_lib.kab_lm_ordre.restype = ctypes.c_int
_lib.kab_etat_neuf.argtypes = [ctypes.c_void_p]
_lib.kab_etat_neuf.restype = ctypes.c_void_p
_lib.kab_etat_liberer.argtypes = [ctypes.c_void_p]
_lib.kab_debut_phrase.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_lib.kab_contexte_vide.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_lib.kab_etat_copier.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_lib.kab_base_score.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
_lib.kab_base_score.restype = ctypes.c_float
_lib.kab_score_phrase.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
_lib.kab_score_phrase.restype = ctypes.c_float


class State:
    """Un état du modèle. Il se réserve à la première utilisation, faute de
    connaître avant cela le format du modèle, qui en fixe la taille."""

    __slots__ = ("_ptr",)

    def __init__(self):
        self._ptr = None

    def _pret(self, modele):
        if self._ptr is None:
            self._ptr = _lib.kab_etat_neuf(modele._ptr)
            if not self._ptr:
                raise MemoryError("état KenLM non alloué")
        return self._ptr

    def __del__(self):
        if getattr(self, "_ptr", None):
            _lib.kab_etat_liberer(self._ptr)
            self._ptr = None


class Model:
    """Un modèle de langue, ouvert en projection mémoire."""

    def __init__(self, chemin):
        self.path = str(chemin)
        self._ptr = _lib.kab_lm_ouvrir(self.path.encode("utf-8"))
        if not self._ptr:
            raise OSError(f"modèle de langue illisible : {self.path}")

    @property
    def order(self):
        return _lib.kab_lm_ordre(self._ptr)

    def BeginSentenceWrite(self, etat):
        _lib.kab_debut_phrase(self._ptr, etat._pret(self))

    def NullContextWrite(self, etat):
        _lib.kab_contexte_vide(self._ptr, etat._pret(self))

    def BaseScore(self, entree, mot, sortie):
        """log10 P(mot | entrée), et écrit l'état résultant."""
        return _lib.kab_base_score(self._ptr, entree._pret(self),
                                   mot.encode("utf-8"), sortie._pret(self))

    def score(self, phrase, bos=True, eos=True):
        return _lib.kab_score_phrase(self._ptr, phrase.encode("utf-8"),
                                     1 if bos else 0, 1 if eos else 0)

    def __del__(self):
        if getattr(self, "_ptr", None):
            _lib.kab_lm_fermer(self._ptr)
            self._ptr = None
