"""CRFsuite par ctypes, quand sklearn-crfsuite manque.

Lit pos_kab.crfsuite, l'étiqueteur d'Android, avec l'interface du modèle joblib
(classes_, predict). Les traits sont convertis comme le fait python-crfsuite.
"""
import ctypes
import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent


def _chemins_possibles():
    nom = "libkab_crf.so"
    depuis_env = os.environ.get("KAB_CRF_PONT")
    if depuis_env:
        yield Path(depuis_env)
    ici = Path(__file__).resolve().parent
    yield ici / nom
    yield ici.parent / nom
    yield RACINE / "natif" / "pont" / nom
    yield Path(nom)


def _charger_bibliotheque():
    derniere = None
    for chemin in _chemins_possibles():
        try:
            return ctypes.CDLL(str(chemin))
        except OSError as erreur:
            derniere = erreur
    raise ImportError(f"pont CRFsuite introuvable ({derniere})")


_lib = _charger_bibliotheque()

_lib.kab_crf_ouvrir.argtypes = [ctypes.c_char_p]
_lib.kab_crf_ouvrir.restype = ctypes.c_void_p
_lib.kab_crf_fermer.argtypes = [ctypes.c_void_p]
_lib.kab_crf_nb_etiquettes.argtypes = [ctypes.c_void_p]
_lib.kab_crf_nb_etiquettes.restype = ctypes.c_int
_lib.kab_crf_etiquette.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
_lib.kab_crf_etiquette.restype = ctypes.c_int
_lib.kab_crf_etiqueter.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p),
                                   ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int),
                                   ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
_lib.kab_crf_etiqueter.restype = ctypes.c_int


def attributs(traits: dict):
    for cle, valeur in traits.items():
        if isinstance(valeur, str):
            yield f"{cle}:{valeur}", 1.0
        else:
            yield cle, float(valeur)


class Etiqueteur:

    def __init__(self, chemin):
        self.path = str(chemin)
        self._ptr = _lib.kab_crf_ouvrir(self.path.encode("utf-8"))
        if not self._ptr:
            raise OSError(f"étiqueteur illisible : {self.path}")
        tampon = ctypes.create_string_buffer(256)
        self.classes_ = []
        for i in range(_lib.kab_crf_nb_etiquettes(self._ptr)):
            if _lib.kab_crf_etiquette(self._ptr, i, tampon, len(tampon)) >= 0:
                self.classes_.append(tampon.value.decode("utf-8"))

    def etiqueter(self, phrase):
        if not phrase:
            return []
        noms, poids, bornes = [], [], []
        for traits in phrase:
            for nom, valeur in attributs(traits):
                noms.append(nom.encode("utf-8"))
                poids.append(valeur)
            bornes.append(len(noms))
        c_noms = (ctypes.c_char_p * len(noms))(*noms)
        c_poids = (ctypes.c_double * len(poids))(*poids)
        c_bornes = (ctypes.c_int * len(bornes))(*bornes)
        taille = 64 + 32 * len(phrase)
        while True:
            tampon = ctypes.create_string_buffer(taille)
            n = _lib.kab_crf_etiqueter(self._ptr, c_noms, c_poids, c_bornes, len(bornes),
                                       tampon, taille)
            if n >= 0:
                return tampon.value.decode("utf-8").split("\n")
            taille *= 4

    def predict(self, phrases):
        return [self.etiqueter(p) for p in phrases]

    def __del__(self):
        if getattr(self, "_ptr", None):
            _lib.kab_crf_fermer(self._ptr)
            self._ptr = None
