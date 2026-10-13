"""Les réglages : un fichier JSON, relu par tous les morceaux de l'application.

Mêmes clés que sous Linux (`graphie`, `translitteration`), et la graphie v au
départ, comme partout dans kab-board. Une valeur abîmée ne change rien.

Quand Kab-board pour Word est installé aussi, le fichier est le sien : il peut
commencer par un BOM (PowerShell en met un) et porter des clés qui ne sont pas
les nôtres (« modeles »). On le lit malgré le BOM, et ses clés restent.

La graphie b ou v est aussi celle de Word, qui la garde dans le registre
(HKCU\\Software\\Kab-board, « Graphie ») : choisie ici ou dans Word, elle vaut
pour les deux.
"""
import json
import os

import lieux

CLE_WORD = r"Software\Kab-board"


def _partage_avec_word() -> bool:
    return (lieux.WINDOWS and not os.environ.get("KAB_BOARD_DONNEES"))


def graphie_de_word():
    """« b » ou « v » si Kab-board pour Word en a retenu une, sinon None."""
    if not _partage_avec_word():
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_WORD) as cle:
            valeur, _ = winreg.QueryValueEx(cle, "Graphie")
    except OSError:
        return None
    return valeur if valeur in ("b", "v") else None


def _graphie_pour_word(graphie: str) -> None:
    if not _partage_avec_word():
        return
    import winreg
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLE_WORD) as cle:
            winreg.SetValueEx(cle, "Graphie", 0, winreg.REG_SZ, graphie)
    except OSError:
        pass


DEFAUTS = {
    "graphie": "v",              # « v » ou « b »
    "translitteration": True,    # gh → ɣ, dh → ḍ, kh → x, aa → ɛ, ou → u
    "barre": True,               # la barre des propositions près du curseur
    "clavier_ecran": False,      # le clavier à l'écran, à l'allumage
    "chiffres": True,            # les touches 1 à 6 choisissent une proposition
}


def lire() -> dict:
    reglages = dict(DEFAUTS)
    try:
        lus = json.loads(lieux.REGLAGES.read_text(encoding="utf-8-sig"))
        if isinstance(lus, dict):
            reglages.update(lus)
    except Exception:
        pass
    reglages["graphie"] = graphie_de_word() or ("b" if reglages.get("graphie") == "b" else "v")
    return reglages


def ecrire(reglages: dict) -> None:
    """Écrit d'un coup : un lecteur ne voit jamais un fichier à moitié écrit."""
    lieux.REGLAGES.parent.mkdir(parents=True, exist_ok=True)
    provisoire = lieux.REGLAGES.with_suffix(".tmp")
    provisoire.write_text(json.dumps(reglages, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(provisoire, lieux.REGLAGES)


def changer(**valeurs) -> dict:
    reglages = lire()
    reglages.update(valeurs)
    ecrire(reglages)
    if "graphie" in valeurs:
        _graphie_pour_word("b" if valeurs["graphie"] == "b" else "v")
    return reglages
