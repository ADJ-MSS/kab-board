"""Ce que tous les tests partagent : les chemins, et un dossier de données jetable."""
import os
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
WINDOWS = ICI.parent
RACINE = WINDOWS.parent
MOTEUR = RACINE / "moteur"

# Jamais les vrais réglages de la machine qui teste.
TEMP = Path(tempfile.mkdtemp(prefix="kab-tests-"))
os.environ["KAB_BOARD_DONNEES"] = str(TEMP)

for chemin in (MOTEUR / "pipeline", MOTEUR, WINDOWS):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))
