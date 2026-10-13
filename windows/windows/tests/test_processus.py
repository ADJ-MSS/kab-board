"""Les processus : le journal d'un morceau lancé sans console."""
import os
import subprocess
import sys
import unittest

import commun


class LeJournal(unittest.TestCase):

    def test_lance_vers_nul_il_ecrit_quand_meme(self):
        """Comme lancer() : la sortie vers NUL, que Python prend pour un terminal
        sous Windows. Le journal doit se remplir."""
        code = ("import sys; sys.path.insert(0, %r); import lieux, processus; "
                "processus.journal('essai'); print('bonjour', flush=True)") % str(commun.WINDOWS)
        env = dict(os.environ, KAB_BOARD_DONNEES=str(commun.TEMP))
        subprocess.run([sys.executable, "-c", code], env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
                       timeout=60)
        journal = commun.TEMP / "essai.log"
        self.assertIn("bonjour", journal.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
