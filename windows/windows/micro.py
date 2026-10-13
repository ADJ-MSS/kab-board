"""Le micro, par l'API waveIn de Windows : 16 kHz, mono, 16 bits, 30 secondes au
plus. C'est le format du modèle vocal Mmeslay, et celui que capte le complément
Word (Micro.cs). L'enregistrement va dans un dossier privé, effacé après la
transcription : la voix ne quitte jamais l'ordinateur.
"""
import os
import tempfile
import threading
import time
import wave
from pathlib import Path

TAUX = 16000
DUREE_MAX_S = 30
MORCEAU_S = 0.25                      # chaque tampon : un quart de seconde

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _winmm = ctypes.WinDLL("winmm")

    class WAVEFORMATEX(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD),
                    ("nSamplesPerSec", wintypes.DWORD), ("nAvgBytesPerSec", wintypes.DWORD),
                    ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                    ("cbSize", wintypes.WORD)]

    class WAVEHDR(ctypes.Structure):
        _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD),
                    ("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t),
                    ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
                    ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]

    _HWAVEIN = wintypes.HANDLE
    _winmm.waveInOpen.argtypes = [ctypes.POINTER(_HWAVEIN), wintypes.UINT,
                                  ctypes.POINTER(WAVEFORMATEX), ctypes.c_size_t,
                                  ctypes.c_size_t, wintypes.DWORD]
    for _nom in ("waveInPrepareHeader", "waveInUnprepareHeader", "waveInAddBuffer"):
        getattr(_winmm, _nom).argtypes = [_HWAVEIN, ctypes.POINTER(WAVEHDR), wintypes.UINT]
    for _nom in ("waveInStart", "waveInStop", "waveInReset", "waveInClose"):
        getattr(_winmm, _nom).argtypes = [_HWAVEIN]
    _winmm.waveInGetNumDevs.restype = wintypes.UINT
    WAVE_MAPPER = 0xFFFFFFFF
    WHDR_DONE = 0x1


def micro_present() -> bool:
    return os.name == "nt" and _winmm.waveInGetNumDevs() > 0


class Micro:
    """Un enregistrement : demarrer(), puis arreter() rend le fichier WAV."""

    def __init__(self):
        if os.name != "nt":
            raise OSError("la dictée par le micro n'existe que sous Windows ici")
        self.morceaux = []
        self.fil = None
        self._fin = threading.Event()
        self.erreur = None
        self.debut = 0.0

    def demarrer(self):
        if not micro_present():
            raise OSError("Aucun micro n'est branché.")
        self._fin.clear()
        self.morceaux = []
        pret = threading.Event()
        self.fil = threading.Thread(target=self._enregistrer, args=(pret,), daemon=True)
        self.fil.start()
        pret.wait(3)
        if self.erreur:
            raise OSError(self.erreur)
        self.debut = time.time()

    @property
    def fini(self) -> bool:
        """Vrai quand l'enregistrement s'est arrêté seul, au bout de 30 secondes."""
        return self._fin.is_set()

    @property
    def secondes(self) -> float:
        return time.time() - self.debut if self.debut else 0.0

    def _enregistrer(self, pret):
        """Tout se passe dans ce fil : ouvrir, tourner, fermer. Les tampons se
        remplissent dans l'ordre, et repartent dès qu'ils sont vidés."""
        format_ = WAVEFORMATEX(1, 1, TAUX, TAUX * 2, 2, 16, 0)       # PCM
        h = _HWAVEIN()
        code = _winmm.waveInOpen(ctypes.byref(h), WAVE_MAPPER, ctypes.byref(format_), 0, 0, 0)
        if code != 0:
            self.erreur = f"Le micro ne s'ouvre pas (code {code})."
            pret.set()
            return
        taille = int(TAUX * 2 * MORCEAU_S)
        tampons = [ctypes.create_string_buffer(taille) for _ in range(8)]
        entetes = []
        for t in tampons:
            e = WAVEHDR()
            e.lpData = ctypes.cast(t, ctypes.c_void_p)
            e.dwBufferLength = taille
            _winmm.waveInPrepareHeader(h, ctypes.byref(e), ctypes.sizeof(WAVEHDR))
            _winmm.waveInAddBuffer(h, ctypes.byref(e), ctypes.sizeof(WAVEHDR))
            entetes.append(e)
        _winmm.waveInStart(h)
        pret.set()
        file_ = list(range(len(entetes)))         # l'ordre dans lequel ils reviennent
        limite = time.time() + DUREE_MAX_S

        def relever(rajouter):
            while file_ and entetes[file_[0]].dwFlags & WHDR_DONE:
                i = file_.pop(0)
                e = entetes[i]
                self.morceaux.append(ctypes.string_at(tampons[i], e.dwBytesRecorded))
                if rajouter:
                    e.dwFlags &= ~WHDR_DONE
                    e.dwBytesRecorded = 0
                    _winmm.waveInAddBuffer(h, ctypes.byref(e), ctypes.sizeof(WAVEHDR))
                    file_.append(i)

        try:
            while not self._fin.wait(0.05) and time.time() < limite:
                relever(True)
            _winmm.waveInStop(h)
            _winmm.waveInReset(h)                 # rend les tampons en cours, à moitié pleins
            time.sleep(0.05)
            relever(False)
        finally:
            for e in entetes:
                _winmm.waveInUnprepareHeader(h, ctypes.byref(e), ctypes.sizeof(WAVEHDR))
            _winmm.waveInClose(h)
            self._fin.set()

    def arreter(self) -> Path:
        """Arrête et écrit le fichier, dans un dossier à part à effacer ensuite."""
        self._fin.set()
        if self.fil is not None:
            self.fil.join(5)
        dossier = Path(tempfile.mkdtemp(prefix="kab-dictee-"))
        return ecrire_wav(dossier / "dictee.wav", b"".join(self.morceaux))


def ecrire_wav(chemin: Path, donnees: bytes) -> Path:
    with wave.open(str(chemin), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(TAUX)
        f.writeframes(donnees)
    return chemin


def effacer(fichier: Path):
    """L'enregistrement et son dossier : rien ne reste de la voix."""
    try:
        fichier.unlink()
        fichier.parent.rmdir()
    except OSError:
        pass
