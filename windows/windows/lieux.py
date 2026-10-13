"""Où sont les choses : l'application, ses ressources, et ce qu'elle retient.

Deux façons de l'avoir avec soi :

- **portable** : un fichier `portable.txt` à côté de `Kab-board.exe`. Tout ce
  que l'application retient (réglages, « mon dictionnaire », cache, journal)
  reste dans son dossier, `donnees/`. On copie le dossier sur une clé USB, et
  le clavier kabyle suit d'un ordinateur à l'autre, sans rien installer.
- **installée** : sans ce fichier, elle range ses affaires dans
  `%LOCALAPPDATA%\\kab-board`, comme Kab-board pour Word. « Mon dictionnaire »
  est alors le même dans Word et partout ailleurs.

Les ressources (lexique, modèle de langue, modèle vocal) sont cherchées dans le
dossier de l'application, puis dans celui de Kab-board pour Word s'il est
installé : rien n'est téléchargé.
"""
import os
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent          # windows/
RACINE = ICI.parent                            # le dossier de l'application
MOTEUR = RACINE / "moteur"
PIPELINE = MOTEUR / "pipeline"

WINDOWS = os.name == "nt"


def _portable() -> bool:
    if os.environ.get("KAB_BOARD_PORTABLE") in ("0", "1"):
        return os.environ["KAB_BOARD_PORTABLE"] == "1"
    return (RACINE / "portable.txt").exists()


PORTABLE = _portable()


def _donnees() -> Path:
    if os.environ.get("KAB_BOARD_DONNEES"):
        return Path(os.environ["KAB_BOARD_DONNEES"])
    if PORTABLE:
        return RACINE / "donnees"
    if WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "kab-board"
    return Path.home() / ".config" / "kab-board"


DONNEES = _donnees()
REGLAGES = DONNEES / "reglages.json"
MES_MOTS = DONNEES / "mots-a-moi.txt"       # le même fichier que Kab-board pour Word
JOURNAL = DONNEES / "kab-board-windows.log"

# Kab-board pour Word, s'il est installé : ses modèles servent aussi ici.
WORD = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "Kab-board"


def _premier_dossier(*candidats):
    for c in candidats:
        if c and Path(c).is_dir():
            return Path(c)
    return None


def modeles():
    return _premier_dossier(RACINE / "modeles", WORD / "modeles" if WINDOWS else None)


def actifs():
    return _premier_dossier(RACINE / "assets" / "moteur")


def voix():
    return _premier_dossier(RACINE / "assets" / "voix", RACINE / "modeles" / "voix",
                            WORD / "modeles" / "voix" if WINDOWS else None)


def python_sans_console() -> str:
    """pythonw.exe à côté de l'interpréteur courant : aucune fenêtre noire."""
    exe = Path(sys.executable)
    if WINDOWS:
        w = exe.with_name("pythonw.exe")
        if w.exists():
            return str(w)
    return str(exe)


def preparer():
    """Les chemins du moteur, avant tout import de celui-ci.

    Le moteur de kab-board lit ses dossiers dans des variables d'environnement
    (chemins.py) : on les pose, plutôt que de le modifier. Les processus lancés
    ensuite en héritent.
    """
    for chemin in (PIPELINE, MOTEUR):
        if str(chemin) not in sys.path:
            sys.path.insert(0, str(chemin))
    for variable, dossier in (("KAB_BOARD_MODELES", modeles()),
                              ("KAB_BOARD_ACTIFS", actifs()),
                              ("KAB_BOARD_VOIX", voix())):
        if dossier is not None and not os.environ.get(variable):
            os.environ[variable] = str(dossier)
    if WINDOWS:
        # L'étiqueteur natif : le pont cherche un .so, on lui donne la .dll.
        crf = PIPELINE / "kab_crf.dll"
        if crf.exists() and not os.environ.get("KAB_CRF_PONT"):
            os.environ["KAB_CRF_PONT"] = str(crf)
    if not os.environ.get("KAB_BOARD_CACHE"):
        # Pas le cache/ de Kab-board pour Word : chacun effacerait celui de l'autre.
        os.environ["KAB_BOARD_CACHE"] = str(DONNEES / "cache-clavier")
    DONNEES.mkdir(parents=True, exist_ok=True)


def manquant():
    return ("Kab-board n'a pas trouvé ses ressources (lexique, modèle de langue). "
            f"Elles devraient être dans {RACINE / 'modeles'}. Reprenez le dossier "
            "complet de Kab-board pour Windows, ou installez Kab-board pour Word.")
