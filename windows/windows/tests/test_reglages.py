"""Les réglages, quand Kab-board pour Word est installé à côté : le fichier est
le même, il peut commencer par un BOM et porter des clés qui ne sont pas les
nôtres."""
import json
import unittest

import commun  # noqa: F401
import lieux
import reglages


class LesReglages(unittest.TestCase):

    def setUp(self):
        lieux.REGLAGES.parent.mkdir(parents=True, exist_ok=True)
        if lieux.REGLAGES.exists():
            lieux.REGLAGES.unlink()

    def ecrire_brut(self, texte, bom=False):
        lieux.REGLAGES.write_bytes(("\ufeff" if bom else "").encode("utf-8") + texte.encode("utf-8"))

    def test_sans_fichier(self):
        self.assertEqual(reglages.lire(), reglages.DEFAUTS)

    def test_avec_un_bom(self):
        """PowerShell écrit un BOM : il ne doit pas effacer les réglages."""
        self.ecrire_brut('{"graphie": "b", "translitteration": false}', bom=True)
        r = reglages.lire()
        self.assertEqual(r["graphie"], "b")
        self.assertFalse(r["translitteration"])

    def test_les_cles_de_word_restent(self):
        self.ecrire_brut('{\r\n    "modeles":  "C:\\\\Kab-board\\\\modeles"\r\n}', bom=True)
        reglages.changer(graphie="b")
        lus = json.loads(lieux.REGLAGES.read_text(encoding="utf-8"))
        self.assertEqual(lus["modeles"], "C:\\Kab-board\\modeles")
        self.assertEqual(lus["graphie"], "b")

    def test_fichier_abime(self):
        self.ecrire_brut('{"graphie": ')
        self.assertEqual(reglages.lire(), reglages.DEFAUTS)

    def test_graphie_abimee_donne_v(self):
        self.ecrire_brut('{"graphie": "w"}')
        self.assertEqual(reglages.lire()["graphie"], "v")

    def test_les_tests_ne_touchent_pas_au_registre(self):
        self.assertFalse(reglages._partage_avec_word())
        self.assertIsNone(reglages.graphie_de_word())


@unittest.skipUnless(lieux.WINDOWS, "Windows seulement")
class LaGraphieDeWord(unittest.TestCase):
    """Choisie ici ou dans Word, elle vaut pour les deux. Une clé d'essai, jamais
    celle de Word."""

    def setUp(self):
        import winreg
        self.winreg = winreg
        self.vraie_cle, self.vrai_partage = reglages.CLE_WORD, reglages._partage_avec_word
        reglages.CLE_WORD = r"Software\Kab-board-essais"
        reglages._partage_avec_word = lambda: True
        if lieux.REGLAGES.exists():
            lieux.REGLAGES.unlink()

    def tearDown(self):
        reglages.CLE_WORD, reglages._partage_avec_word = self.vraie_cle, self.vrai_partage
        try:
            self.winreg.DeleteKey(self.winreg.HKEY_CURRENT_USER, r"Software\Kab-board-essais")
        except OSError:
            pass

    def ecrire_word(self, valeur):
        with self.winreg.CreateKey(self.winreg.HKEY_CURRENT_USER, reglages.CLE_WORD) as cle:
            self.winreg.SetValueEx(cle, "Graphie", 0, self.winreg.REG_SZ, valeur)

    def test_choisie_dans_word(self):
        self.assertEqual(reglages.lire()["graphie"], "v")
        self.ecrire_word("b")
        self.assertEqual(reglages.lire()["graphie"], "b")

    def test_choisie_ici(self):
        reglages.changer(graphie="b")
        self.assertEqual(reglages.graphie_de_word(), "b")
        reglages.changer(graphie="v")
        self.assertEqual(reglages.graphie_de_word(), "v")
        self.assertEqual(reglages.lire()["graphie"], "v")

    def test_valeur_de_word_abimee(self):
        self.ecrire_word("x")
        self.assertIsNone(reglages.graphie_de_word())
        self.assertEqual(reglages.lire()["graphie"], "v")


if __name__ == "__main__":
    unittest.main()
