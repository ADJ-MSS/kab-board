"""L'interface du clavier, sans le crochet : la barre, le clavier à l'écran, ses
panneaux. Il faut un écran (sous Linux : xvfb-run). Ce que le clavier écrirait
dans l'application active est relevé au lieu d'être tapé.
"""
import os
import time
import unittest

import commun  # noqa: F401

try:
    import tkinter as tk
    _racine = tk.Tk()
    _racine.withdraw()
except Exception as _erreur:              # pas d'écran, ou pas de tkinter
    _racine = None
    _raison = str(_erreur)

if _racine is not None:
    import kab_saisie
    import processus


@unittest.skipIf(_racine is None, "pas d'écran pour tkinter")
class LInterface(unittest.TestCase):

    def setUp(self):
        self.ecrit = []
        processus.lancer = lambda *a, **k: None      # pas de vrai correcteur ici
        self.noyau = kab_saisie.Noyau(_racine, injecter=self.relever)
        self.noyau.service_brut = lambda quoi, delai=3.0, **p: self.repondre(quoi, p)

    def tearDown(self):
        self.noyau.clavier.fen.destroy()
        self.noyau.barre.fen.destroy()

    def relever(self, effacer, texte):
        self.ecrit.append((effacer, texte))
        return True

    def repondre(self, quoi, p):
        if quoi == "fiche":
            return {"mot": p["mot"], "glose": "pain", "categorie": "masc",
                    "libre": "aɣrum", "annexion": "uɣrum"}
        if quoi == "motdujour":
            return {"forme": "aɣrum", "glose": "pain, galette"}
        if quoi == "chercher":
            return {"trouves": [["aɣrum", "pain, galette"]]}
        if quoi == "relire":
            return {"signales": [{"mot": "ghar", "debut": 7, "fin": 11,
                                  "propositions": ["ɣer"], "natures": ["contexte"]}]}
        return None

    def pomper(self, fois=5):
        for _ in range(fois):
            self.noyau._pomper()
            _racine.update()
            time.sleep(0.01)

    def texte(self):
        t = ""
        for effacer, ajout in self.ecrit:
            t = (t[:-effacer] if effacer else t) + ajout
        return t

    def test_le_clavier_ecrit(self):
        c = self.noyau.clavier
        c.afficher()
        for lettre in "ruhagh":
            c._pressee((lettre,))
        c._pressee(("␣",))
        self.assertEqual(self.texte(), "ruhaɣ ")
        c._pressee(("⌫",))
        self.assertEqual(self.noyau.frappe.mot, "ruhaɣ")

    def test_majuscules_et_symboles(self):
        c = self.noyau.clavier
        c.afficher()
        c._pressee(("⇧",))
        c._pressee(("a",))
        c._pressee(("z",))
        c._pressee(("123",))
        c._pressee(("1",))
        self.assertEqual(self.texte(), "Az1")
        c._pressee(("ABC",))

    def test_variantes_appui_long(self):
        c = self.noyau.clavier
        c.afficher()
        _racine.update()
        cadre = c.touches.winfo_children()[0].winfo_children()[0]
        c._variantes(("a", "â", "à"), cadre)
        _racine.update()
        self.assertIsNotNone(c._volante)
        c._fermer_volante()

    def test_la_barre_et_le_choix(self):
        f = self.noyau.frappe
        for lettre in "ruhagh":
            self.noyau.lettre(lettre)
        f.montrer(f.generation, ["ruḥeɣ", "ruḥ"], "prop", 0)
        self.noyau._afficher(["ruḥeɣ", "ruḥ"], "prop", "ruhaɣ")
        _racine.update()
        self.assertTrue(self.noyau.barre.visible)
        self.noyau.choisir_forme("ruḥeɣ")
        self.pomper()
        self.assertEqual(self.texte(), "ruḥeɣ ")
        self.assertFalse(self.noyau.barre.visible)

    def test_les_panneaux(self):
        c = self.noyau.clavier
        c.afficher()
        c.fiche("aɣrum")
        self.pomper(20)
        textes = [w.cget("text") for w in c.panneau.winfo_children()]
        self.assertIn("catégorie : masc", textes)
        c._mot_du_jour()
        self.pomper(20)
        c._recherche()
        for lettre in "pain":
            c._pressee((lettre,))
        self.assertEqual(c.recherche, "pain")
        c._chercher()
        self.pomper(20)
        self.assertTrue(c.resultats.winfo_children())
        c._translit()
        self.assertFalse(self.noyau.frappe.saisie.translitteration)
        c._translit()
        c.fermer_panneau()
        self.assertEqual(self.texte(), "")          # la recherche n'écrit pas ailleurs

    def test_relire_le_presse_papiers(self):
        c = self.noyau.clavier
        c.afficher()
        _racine.clipboard_clear()
        _racine.clipboard_append("ruḥeɣ ghar tmeṭṭut")
        c._relire()
        self.pomper(20)
        boutons = [w for w in c.panneau.winfo_children()
                   if "Copier" in str(w.cget("text"))]
        self.assertTrue(boutons)
        c._copier_corrige("ruḥeɣ ghar tmeṭṭut", [{"debut": 6, "fin": 10,
                                                   "propositions": ["ɣer"]}])
        self.assertEqual(_racine.clipboard_get(), "ruḥeɣ ɣer tmeṭṭut")

    def test_graphie(self):
        self.noyau.changer_graphie("b")
        self.assertEqual(self.noyau.reglages["graphie"], "b")
        self.noyau.changer_graphie("v")

    def test_la_liaison(self):
        r = self.noyau.traiter({"quoi": "etat"})
        self.assertIn("propositions", r)
        self.assertEqual(self.noyau.traiter({"quoi": "?"}), {"erreur": "requête inconnue"})

    def test_menu(self):
        entrees = [e for e in self.noyau._menu() if e]
        self.assertTrue(all(len(e) == 4 for e in entrees))
        self.noyau._choix_menu(4)
        self.assertTrue(self.noyau.clavier.visible)
        self.noyau._choix_menu(4)
        self.assertFalse(self.noyau.clavier.visible)


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(_racine is None, "pas d'écran pour tkinter")
class LesFenetres(unittest.TestCase):

    UTILE_768 = 720       # un portable en 1366 × 768, sous la barre des tâches

    def tient_dans_l_ecran(self, fenetre):
        """Sur cet écran, et sur le plus petit qu'on rencontre encore."""
        import ecran
        fenetre.update()
        self.assertLessEqual(fenetre.winfo_reqheight() + ecran.CADRE, self.UTILE_768)
        _g, h, _d, b = ecran.zone(fenetre)
        self.assertGreaterEqual(fenetre.winfo_rooty(), h)
        self.assertLessEqual(fenetre.winfo_rooty() + fenetre.winfo_height(), b)

    def test_l_application(self):
        import kab_appli
        haut = tk.Toplevel(_racine)
        f = kab_appli.Fenetre(haut)
        _racine.update()
        self.tient_dans_l_ecran(haut)
        self.assertFalse(f.v_clavier.get())          # aucun clavier allumé ici
        f.v_graphie.set("b")
        f._changer_graphie()
        import reglages
        self.assertEqual(reglages.lire()["graphie"], "b")
        f.v_graphie.set("v")
        f._changer_graphie()
        haut.destroy()

    def test_ecrire_et_relire(self):
        import kab_bureau
        processus.lancer = lambda *a, **k: None
        haut = tk.Toplevel(_racine)
        b = kab_bureau.Bureau(haut)
        self.tient_dans_l_ecran(haut)
        for c in "ruhagh":
            b._ecran(c)
        b._touche_ecran(("␣",))
        self.assertEqual(b.texte.get("1.0", "end-1c"), "ruhaɣ ")
        f = b.frappe
        for c in "tamettut":
            b._ecran(c)
        f.montrer(f.generation, ["tameṭṭut"], "prop", 0)
        b._afficher(["tameṭṭut"], "prop")
        b._choisir("tameṭṭut")
        self.assertEqual(b.texte.get("1.0", "end-1c"), "ruhaɣ tameṭṭut ")
        b._montrer_relecture({"signales": [{"mot": "ruhaɣ", "debut": 0, "fin": 5,
                                            "propositions": ["ruḥeɣ"]}]},
                             "ruhaɣ tameṭṭut ")
        b._remplacer(tk.Toplevel(haut), "ruhaɣ tameṭṭut ",
                     {"debut": 0, "fin": 5}, "ruḥeɣ")
        self.assertEqual(b.texte.get("1.0", "end-1c"), "ruḥeɣ tameṭṭut ")
        b.fin.set()
        haut.destroy()
