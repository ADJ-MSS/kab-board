"""Où trouver les ressources : réglages, KAB_BOARD_MODELES, le dossier de
l'utilisateur, celui du système, puis les dossiers de développement. Quand rien
n'est trouvé, l'application le dit et renvoie au dépôt Zenodo.
"""
import json
import os
from pathlib import Path

DOI = "10.5281/zenodo.22112059"

# Sur Windows, le greffon Word range tout dans %LOCALAPPDATA%.
if os.name == "nt":
    CONFIG = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "kab-board"
else:
    CONFIG = Path.home() / ".config" / "kab-board"

REGLAGES = CONFIG / "reglages.json"

# Le dossier du dépôt ou du paquet : linux/ est dedans.
RACINE = Path(__file__).resolve().parent
DEPOT = RACINE.parent

def _table_bv():
    """La table des graphies, où qu'elle soit posée."""
    for candidat in (DEPOT / "app" / "src" / "main" / "assets" / "graphie" / "table_bv.tsv",
                     RACINE / "graphie" / "table_bv.tsv",
                     DEPOT / "graphie" / "table_bv.tsv",
                     CONFIG / "graphie" / "table_bv.tsv"):
        if candidat.exists():
            return candidat
    return DEPOT / "app" / "src" / "main" / "assets" / "graphie" / "table_bv.tsv"


TABLE_BV = _table_bv()


def _regle(cle):
    try:
        return json.loads(REGLAGES.read_text(encoding="utf-8")).get(cle)
    except Exception:
        return None


def _premier_existant(candidats):
    for c in candidats:
        if c and Path(c).exists():
            return Path(c)
    return None


def correcteur():
    """Le dossier des ressources du correcteur : lexique, modèle de langue, CRF."""
    return _premier_existant([
        _regle("modeles"),
        os.environ.get("KAB_BOARD_MODELES"),
        CONFIG / "modeles",
        Path.home() / ".local" / "share" / "kab-board" / "modeles",
        Path("/usr/share/kab-board/modeles"),
        DEPOT / "modeles",
        # Postes de développement.
        Path.home() / "Téléchargements/Téléchargements/OneDrive_2_02-04-2026/correcteur_kabyle",
    ])


def actifs_android():
    """Les ressources exportées pour le téléphone : gloses, catégories, vivier."""
    return _premier_existant([
        _regle("actifs"),
        os.environ.get("KAB_BOARD_ACTIFS"),
        DEPOT / "assets" / "moteur",                      # dans le paquet
        DEPOT / "app" / "src" / "main" / "assets" / "moteur",
        Path.home() / ".local" / "share" / "kab-board" / "assets" / "moteur",
        Path("/usr/share/kab-board/assets/moteur"),
        Path.home() / "kbd-taqbaylit" / "app" / "src" / "main" / "assets" / "moteur",
    ])


def voix():
    """Le modèle vocal et son jeu de jetons."""
    return _premier_existant([
        _regle("voix"),
        os.environ.get("KAB_BOARD_VOIX"),
        DEPOT / "assets" / "voix",                        # dans le paquet
        DEPOT / "app" / "src" / "main" / "assets" / "voix",
        Path.home() / ".local" / "share" / "kab-board" / "assets" / "voix",
        Path("/usr/share/kab-board/assets/voix"),
        Path.home() / "kbd-taqbaylit" / "app" / "src" / "main" / "assets" / "voix",
    ])


def manquant(quoi="les ressources du correcteur"):
    """Le message à montrer quand elles sont introuvables."""
    return (f"Kab-board n'a pas trouvé {quoi}. Elles ne sont pas dans le paquet : "
            f"elles pèsent plus de 600 Mo. Déposez-les dans "
            f"~/.local/share/kab-board/modeles, ou indiquez leur dossier dans "
            f"~/.config/kab-board/reglages.json (clé « modeles »). "
            f"Elles sont publiées sur Zenodo : doi.org/{DOI}")
