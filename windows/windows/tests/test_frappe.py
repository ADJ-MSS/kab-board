"""La frappe, touche par touche, dans une application imaginaire.

L'application reçoit ce que le crochet laisse passer, puis ce qu'il écrit à la
place (effacer n caractères, taper un texte). Après chaque suite de touches, on
regarde son texte : c'est ce que l'utilisateur verrait à l'écran.

    python -m unittest windows.tests.test_frappe
"""
import unittest

import commun  # noqa: F401
from frappe import (Frappe, Touche, VK_BACK, VK_RETURN, VK_SPACE, VK_TAB, VK_ESCAPE)

VK_CONTROL, VK_SHIFT, VK_GAUCHE = 0x11, 0x10, 0x25


def touche_de(c: str) -> Touche:
    if c == " ":
        return Touche(VK_SPACE, " ", " ")
    vk = ord(c.upper()) if c.isascii() and c.isalnum() else 0xBC
    return Touche(vk, c, c)


class Appli:
    """Une zone de texte : le curseur est toujours à la fin."""

    def __init__(self, frappe: Frappe):
        self.frappe = frappe
        self.texte = ""

    def appliquer(self, action):
        if action.effacer:
            self.texte = self.texte[:-action.effacer]
        self.texte += action.texte
        return action

    def touche(self, t: Touche):
        action = self.frappe.touche(t)
        if not action.bloquer:
            if t.vk == VK_BACK:
                self.texte = self.texte[:-1]
            elif t.vk == VK_RETURN:
                self.texte += "\n"
            elif t.caractere and not t.ctrl and not t.morte:
                self.texte += t.caractere
        return self.appliquer(action)

    def taper(self, texte: str):
        action = None
        for c in texte:
            action = self.touche(touche_de(c))
        return action

    def effacer(self, n=1):
        for _ in range(n):
            action = self.touche(Touche(VK_BACK))
        return action

    def proposer(self, formes, nature="prop", mots_avant=0):
        """Ce que répondrait le correcteur, pour le mot en cours."""
        return self.frappe.montrer(self.frappe.generation, formes, nature, mots_avant)


class LesLettresKabyles(unittest.TestCase):

    def setUp(self):
        self.a = Appli(Frappe())

    def test_digrammes(self):
        for tape, attendu in (("ruhagh", "ruhaɣ"), ("adhar", "aḍar"), ("khedmegh", "xedmeɣ"),
                              ("laada", "lɛda"), ("aourar", "aurar"), ("Ghef", "Ɣef")):
            a = Appli(Frappe())
            a.taper(tape)
            self.assertEqual(a.texte, attendu, tape)
            self.assertEqual(a.frappe.mot, attendu, tape)

    def test_une_lettre_ordinaire_passe(self):
        action = self.a.taper("a")
        self.assertFalse(action.bloquer)
        self.assertTrue(action.proposer)

    def test_la_conversion_efface_et_tape(self):
        self.a.taper("g")
        action = self.a.touche(touche_de("h"))
        self.assertTrue(action.bloquer)
        self.assertEqual((action.effacer, action.texte), (1, "ɣ"))

    def test_effacement_defait_la_conversion(self):
        self.a.taper("agh")
        self.assertEqual(self.a.texte, "aɣ")
        self.a.effacer()
        self.assertEqual(self.a.texte, "agh")
        self.a.effacer()
        self.assertEqual(self.a.texte, "ag")
        self.assertEqual(self.a.frappe.mot, "ag")

    def test_altgr(self):
        self.a.taper("ruhe")
        action = self.a.touche(Touche(ord("G"), "", "g", altgr=True))
        self.assertTrue(action.bloquer)
        self.assertEqual(self.a.texte, "ruheɣ")
        self.a.touche(Touche(ord("G"), "", "G", altgr=True))
        self.assertEqual(self.a.texte, "ruheɣƔ")

    def test_altgr_sans_lettre_kabyle(self):
        self.a.taper("abrid")
        action = self.a.touche(Touche(0x30, "@", "à", altgr=True))
        self.assertFalse(action.bloquer)
        self.assertEqual(self.a.texte, "abrid@")
        self.assertEqual(self.a.frappe.mot, "")

    def test_sans_translitteration(self):
        a = Appli(Frappe(translitteration=False))
        a.taper("ruhagh")
        self.assertEqual(a.texte, "ruhagh")


class LeMotEtSonContexte(unittest.TestCase):

    def setUp(self):
        self.a = Appli(Frappe())

    def test_l_espace_ecrit_le_mot_tel_quel(self):
        action = self.a.taper("ruhagh ")
        self.assertFalse(action.bloquer)
        self.assertTrue(action.predire)
        self.assertEqual(self.a.texte, "ruhaɣ ")
        self.assertEqual(self.a.frappe.contexte, "ruhaɣ ")
        self.assertEqual(self.a.frappe.mot, "")

    def test_ponctuation(self):
        self.a.taper("abrid,")
        self.assertEqual(self.a.frappe.contexte, "abrid,")
        self.assertEqual(self.a.frappe.mot, "")

    def test_effacer_l_espace_reprend_le_mot(self):
        self.a.taper("ruḥeɣ abrid ")
        action = self.a.effacer()
        self.assertTrue(action.proposer)
        self.assertEqual(self.a.texte, "ruḥeɣ abrid")
        self.assertEqual(self.a.frappe.mot, "abrid")
        self.assertEqual(self.a.frappe.contexte, "ruḥeɣ ")

    def test_entree_repart_de_zero(self):
        self.a.taper("azul fell-awen")
        self.a.touche(Touche(VK_RETURN, "\r"))
        self.assertEqual(self.a.frappe.contexte, "")
        self.assertEqual(self.a.frappe.mot, "")

    def test_raccourci_repart_de_zero(self):
        self.a.taper("azul abr")
        action = self.a.touche(Touche(ord("V"), "\x16", "v", ctrl=True))
        self.assertTrue(action.cacher)
        self.assertEqual((self.a.frappe.contexte, self.a.frappe.mot), ("", ""))

    def test_les_modificateurs_ne_changent_rien(self):
        self.a.taper("abr")
        generation = self.a.frappe.generation
        for vk in (VK_SHIFT, VK_CONTROL, 0xA0, 0xA5, 0x14):
            self.a.touche(Touche(vk))
        self.assertEqual(self.a.frappe.mot, "abr")
        self.assertEqual(self.a.frappe.generation, generation)

    def test_fleches_tabulation_echap(self):
        for vk in (VK_GAUCHE, VK_TAB, VK_ESCAPE):
            a = Appli(Frappe())
            a.taper("azul abr")
            a.touche(Touche(vk))
            self.assertEqual((a.frappe.contexte, a.frappe.mot), ("", ""), hex(vk))

    def test_touche_morte(self):
        self.a.taper("abr")
        self.a.touche(Touche(0xDD, "", "", morte=True))
        self.assertEqual(self.a.frappe.mot, "")
        self.a.touche(Touche(ord("E"), "ê", "e"))      # composée par l'application
        self.assertEqual(self.a.frappe.mot, "")
        self.a.taper("gh")
        self.assertEqual(self.a.frappe.mot, "ɣ")

    def test_clic_ailleurs(self):
        self.a.taper("azul abr")
        self.a.frappe.reinitialiser()
        self.assertEqual((self.a.frappe.contexte, self.a.frappe.mot), ("", ""))


class LesPropositions(unittest.TestCase):

    def setUp(self):
        self.a = Appli(Frappe())

    def test_choisir_par_chiffre(self):
        self.a.taper("ruhagh")
        self.assertTrue(self.a.proposer(["ruḥeɣ", "ruḥ", "ruḥeɣt"]))
        action = self.a.touche(touche_de("1"))
        self.assertTrue(action.bloquer)
        self.assertTrue(action.predire)
        self.assertEqual(self.a.texte, "ruḥeɣ ")
        self.assertEqual(self.a.frappe.contexte, "ruḥeɣ ")

    def test_choisir_le_troisieme(self):
        self.a.taper("azul ruhagh")
        self.a.proposer(["ruḥeɣ", "ruḥ", "ruḥeɣt"])
        self.a.touche(touche_de("3"))
        self.assertEqual(self.a.texte, "azul ruḥeɣt ")

    def test_chiffre_sans_proposition(self):
        self.a.taper("abrid")
        self.a.proposer(["avrid"])
        self.a.touche(touche_de("4"))
        self.assertEqual(self.a.texte, "abrid4")

    def test_chiffre_desactive(self):
        a = Appli(Frappe(chiffres=False))
        a.taper("abrid")
        a.proposer(["avrid"])
        a.touche(touche_de("1"))
        self.assertEqual(a.texte, "abrid1")

    def test_chiffre_apres_un_mot_fini(self):
        """Une prédiction ne prend pas les chiffres : on écrit encore des nombres."""
        self.a.taper("aseggas ")
        self.assertTrue(self.a.proposer(["n", "agi"], "pred"))
        self.a.taper("2026")
        self.assertEqual(self.a.texte, "aseggas 2026")

    def test_reponse_en_retard(self):
        self.a.taper("abr")
        generation = self.a.frappe.generation
        self.a.taper("i")
        self.assertFalse(self.a.frappe.montrer(generation, ["abrid"]))
        self.assertEqual(self.a.frappe.propositions, [])

    def test_possessif_rattache(self):
        """« tamurt iw » devient « tamurt-iw » en une fois."""
        self.a.taper("ruḥeɣ ɣer tamurt iw")
        self.a.proposer(["tamurt-iw", "iw", "is"], mots_avant=1)
        self.a.touche(touche_de("1"))
        self.assertEqual(self.a.texte, "ruḥeɣ ɣer tamurt-iw ")
        self.assertEqual(self.a.frappe.contexte, "ruḥeɣ ɣer tamurt-iw ")

    def test_possessif_seulement_en_tete(self):
        self.a.taper("tamurt iw")
        self.a.proposer(["tamurt-iw", "is"], mots_avant=1)
        self.a.touche(touche_de("2"))
        self.assertEqual(self.a.texte, "tamurt is ")

    def test_jamais_par_dessus_une_virgule(self):
        self.a.taper("tamurt, iw")
        self.a.proposer(["tamurt-iw"], mots_avant=1)
        self.a.touche(touche_de("1"))
        self.assertEqual(self.a.texte, "tamurt, tamurt-iw ")

    def test_choisir_une_prediction(self):
        self.a.taper("ruḥeɣ ")
        self.a.proposer(["ɣer", "s"], "pred")
        self.a.appliquer(self.a.frappe.choisir(0))
        self.assertEqual(self.a.texte, "ruḥeɣ ɣer ")

    def test_choisir_au_clic(self):
        self.a.taper("tamettut")
        self.a.proposer(["tameṭṭut", "tamettut"])
        self.a.appliquer(self.a.frappe.choisir_forme("tameṭṭut"))
        self.assertEqual(self.a.texte, "tameṭṭut ")

    def test_une_prediction_s_efface_quand_on_tape(self):
        self.a.taper("ruḥeɣ ")
        generation = self.a.frappe.generation
        self.a.taper("ɣ")
        self.assertFalse(self.a.frappe.montrer(generation, ["ɣer"], "pred"))


class LesChampsSensibles(unittest.TestCase):

    def test_mot_de_passe(self):
        a = Appli(Frappe())
        a.frappe.activer(False)
        a.taper("ghxyz1")
        self.assertEqual(a.texte, "ghxyz1")
        self.assertEqual(a.frappe.mot, "")
        self.assertFalse(a.frappe.montrer(a.frappe.generation, ["x"]))
        a.frappe.activer(True)
        a.taper(" gh")
        self.assertEqual(a.texte, "ghxyz1 ɣ")


class RepriseEnPleinMot(unittest.TestCase):

    def test_le_debut_du_mot_a_echappe(self):
        a = Appli(Frappe())
        a.frappe.activer(False)
        a.taper("ab")
        a.frappe.activer(True, en_plein_mot=True)
        a.taper("rid")
        self.assertEqual(a.frappe.mot, "")
        self.assertFalse(a.frappe.montrer(a.frappe.generation, ["avrid"]) and a.frappe.mot)
        a.taper(" ruhagh")
        self.assertEqual(a.frappe.mot, "ruhaɣ")
        self.assertEqual(a.texte, "abrid ruhaɣ")

    def test_altgr_en_plein_mot(self):
        a = Appli(Frappe())
        a.frappe.activer(True, en_plein_mot=True)
        a.touche(Touche(ord("G"), "", "g", altgr=True))
        self.assertEqual(a.texte, "ɣ")
        self.assertEqual(a.frappe.mot, "")


class LeFocusQuiBouge(unittest.TestCase):
    """Le temps de vérifier le champ, les lettres sont suivies sans rien réécrire :
    rien n'échappe au début du mot, et un mot de passe reste intact."""

    def test_le_navigateur_ouvre_ses_suggestions(self):
        """Le focus bouge en plein mot, dans la même fenêtre : le mot reste."""
        a = Appli(Frappe())
        a.taper("azul ru")
        a.frappe.suspendre(garder=True)
        a.taper("hagh")
        self.assertEqual(a.texte, "azul ruhagh")          # rien de réécrit pendant ce temps
        self.assertFalse(a.frappe.montrer(a.frappe.generation, ["x"]))
        action = a.frappe.reprendre(True)
        self.assertTrue(action.proposer)
        self.assertEqual(a.frappe.mot, "ruhagh")
        self.assertEqual(a.frappe.contexte, "azul ")
        self.assertTrue(a.proposer(["ruḥeɣ"]))
        a.touche(touche_de("1"))
        self.assertEqual(a.texte, "azul ruḥeɣ ")

    def test_un_autre_champ_commence_au_premier_mot(self):
        """Les premières lettres d'un nouveau champ sont suivies."""
        a = Appli(Frappe())
        a.taper("azul ")
        a.frappe.suspendre(garder=False)
        a.taper("ab")
        a.frappe.reprendre(True)
        a.taper("rid")
        self.assertEqual(a.frappe.mot, "abrid")
        self.assertEqual(a.frappe.contexte, "")
        a.taper(" gh")
        self.assertEqual(a.texte, "azul abrid ɣ")

    def test_un_mot_de_passe_reste_intact(self):
        a = Appli(Frappe())
        a.frappe.suspendre()
        a.taper("ghxyz1")
        a.effacer()
        self.assertEqual(a.texte, "ghxyz")
        a.frappe.reprendre(False)
        self.assertFalse(a.frappe.actif)
        self.assertEqual(a.frappe.mot, "")
        a.taper("gh")
        self.assertEqual(a.texte, "ghxyzgh")

    def test_espace_et_raccourci_pendant_la_verification(self):
        a = Appli(Frappe())
        a.frappe.suspendre()
        a.taper("tamurt ")
        self.assertEqual(a.frappe.contexte, "tamurt ")
        a.touche(Touche(ord("V"), "\x16", "v", ctrl=True))
        self.assertEqual((a.frappe.contexte, a.frappe.mot), ("", ""))
        a.frappe.reprendre(True)
        a.taper("gh")
        self.assertEqual(a.frappe.mot, "ɣ")

    def test_reprendre_sans_suspendre_ne_touche_a_rien(self):
        a = Appli(Frappe())
        a.taper("ruh")
        a.proposer(["ruḥ"])
        self.assertFalse(a.frappe.reprendre(True).ecrit)
        self.assertEqual(a.frappe.propositions, ["ruḥ"])

    def test_clavier_a_l_ecran_pendant_la_verification(self):
        f = Frappe()
        a = Appli(f)
        f.suspendre()
        for c in "gh":
            a.appliquer(f.lettre_ecran(c))
        self.assertEqual(a.texte, "gh")
        a.appliquer(f.effacer_ecran())
        self.assertEqual(a.texte, "g")


class LeClavierALEcran(unittest.TestCase):
    """Rien n'est tapé physiquement : chaque touche s'écrit par le clavier kabyle."""

    def setUp(self):
        self.f = Frappe()
        self.a = Appli(self.f)

    def ecran(self, texte):
        for c in texte:
            action = self.a.appliquer(self.f.ecrire(" ") if c == " " else self.f.lettre_ecran(c))
            self.assertTrue(action.bloquer)

    def test_lettres_et_digrammes(self):
        self.ecran("ruhagh")
        self.assertEqual(self.a.texte, "ruhaɣ")
        self.a.appliquer(self.f.effacer_ecran())
        self.assertEqual(self.a.texte, "ruhagh")
        self.a.appliquer(self.f.effacer_ecran())
        self.assertEqual(self.a.texte, "ruhag")

    def test_espace_et_ponctuation(self):
        self.ecran("azul fellak")
        self.a.appliquer(self.f.lettre_ecran("!"))
        self.assertEqual(self.a.texte, "azul fellak!")
        self.assertEqual(self.f.contexte, "azul fellak!")

    def test_effacer_un_mot(self):
        self.ecran("azul fellak")
        self.a.appliquer(self.f.effacer_mot_ecran())
        self.assertEqual(self.a.texte, "azul ")
        self.a.appliquer(self.f.effacer_mot_ecran())
        self.assertEqual(self.a.texte, "")

    def test_effacer_sans_mot_en_cours(self):
        self.ecran("azul ")
        self.a.appliquer(self.f.effacer_ecran())
        self.assertEqual(self.a.texte, "azul")
        self.assertEqual(self.f.mot, "azul")

    def test_entree(self):
        self.ecran("azul")
        self.a.appliquer(self.f.ecrire("\n"))
        self.assertEqual(self.a.texte, "azul\n")
        self.assertEqual(self.f.contexte, "")

    def test_dictee(self):
        self.ecran("azul ")
        self.a.appliquer(self.f.ecrire("ruḥeɣ ɣer tmeṭṭut", dictee=True))
        self.assertEqual(self.a.texte, "azul ruḥeɣ ɣer tmeṭṭut")
        self.assertEqual(self.f.derniere_dictee, "ruḥeɣ ɣer tmeṭṭut")

    def test_mot_de_passe(self):
        self.f.activer(False)
        self.ecran("gh")
        self.assertEqual(self.a.texte, "gh")


if __name__ == "__main__":
    unittest.main()
