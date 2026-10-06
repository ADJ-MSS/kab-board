"""ONNX Runtime par ctypes, quand le module Python manque."""
import ctypes
import os
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parent.parent.parent


def _chemins_possibles():
    nom = "libkab_onnx.so"
    depuis_env = os.environ.get("KAB_ONNX_PONT")
    if depuis_env:
        yield Path(depuis_env)
    ici = Path(__file__).resolve().parent
    yield ici / nom
    yield RACINE / "natif" / "pont" / nom
    yield Path(nom)


def _charger_bibliotheque():
    derniere = None
    for chemin in _chemins_possibles():
        try:
            return ctypes.CDLL(str(chemin))
        except OSError as erreur:
            derniere = erreur
    raise ImportError(f"pont ONNX Runtime introuvable ({derniere})")


_lib = _charger_bibliotheque()

_flottants = ctypes.POINTER(ctypes.c_float)
_lib.kab_onnx_ouvrir.argtypes = [ctypes.c_char_p]
_lib.kab_onnx_ouvrir.restype = ctypes.c_void_p
_lib.kab_onnx_fermer.argtypes = [ctypes.c_void_p]
_lib.kab_onnx_executer.argtypes = [ctypes.c_void_p, _flottants, ctypes.c_int64,
                                   ctypes.POINTER(_flottants),
                                   ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64)]
_lib.kab_onnx_executer.restype = ctypes.c_int
_lib.kab_onnx_liberer.argtypes = [_flottants]


class Session:

    def __init__(self, chemin):
        self.path = str(chemin)
        self._ptr = _lib.kab_onnx_ouvrir(self.path.encode("utf-8"))
        if not self._ptr:
            raise OSError(f"modèle ONNX illisible : {self.path}")

    def executer(self, echantillons: np.ndarray) -> np.ndarray:
        """Les logits [T, V]."""
        audio = np.ascontiguousarray(echantillons, dtype=np.float32).ravel()
        sortie = _flottants()
        trames, classes = ctypes.c_int64(), ctypes.c_int64()
        code = _lib.kab_onnx_executer(self._ptr, audio.ctypes.data_as(_flottants), audio.size,
                                      ctypes.byref(sortie), ctypes.byref(trames),
                                      ctypes.byref(classes))
        if code != 0:
            raise RuntimeError("ONNX Runtime : échec de l'inférence")
        try:
            vue = np.ctypeslib.as_array(sortie, shape=(trames.value, classes.value))
            return vue.copy()
        finally:
            _lib.kab_onnx_liberer(sortie)

    def __del__(self):
        if getattr(self, "_ptr", None):
            _lib.kab_onnx_fermer(self._ptr)
            self._ptr = None
