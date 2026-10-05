"""Prépare le cache des ressources du correcteur.

L'installeur le lance une fois : le premier démarrage du correcteur dans Word
est alors aussi rapide que les suivants (voir pipeline/ressources.py).

    python moteur/preparer_cache.py
"""
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import service  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    service.charger()
