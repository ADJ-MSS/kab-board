"""Sous Windows seulement : les appels du système, puis le clavier kabyle pour de
vrai, dans le Bloc-notes.

Le bout en bout tape des touches comme un clavier physique (SendInput, sans
notre marque), les laisse passer par le crochet, et lit le texte du Bloc-notes.
"""
import ctypes
import os
import platform
import subprocess
import sys
import time
import unittest

import commun  # noqa: F401

WINDOWS = os.name == "nt"
if WINDOWS:
    from ctypes import wintypes

    import win32


@unittest.skipUnless(WINDOWS, "Windows seulement")
class LesStructures(unittest.TestCase):
    """Une structure de la mauvaise taille, et Windows lit à côté."""

    def test_tailles(self):
        self.assertEqual(ctypes.sizeof(win32.INPUT), 40)
        self.assertEqual(ctypes.sizeof(win32.KBDLLHOOKSTRUCT), 24)
        self.assertEqual(ctypes.sizeof(win32.MSLLHOOKSTRUCT), 32)
        self.assertEqual(ctypes.sizeof(win32.GUITHREADINFO), 72)
        self.assertEqual(ctypes.sizeof(win32.NOTIFYICONDATAW), 976)
        self.assertEqual(ctypes.sizeof(win32.VARIANT), 24)
        self.assertEqual(ctypes.sizeof(win32.MSG), 48)

    def test_entrees(self):
        liste = win32.entrees(2, "ɣ\nḍ")
        self.assertEqual(len(liste), 4 + 2 + 2 + 2)
        self.assertEqual(liste[4].ki.wScan, ord("ɣ"))
        self.assertEqual(liste[6].ki.wVk, win32.VK_RETURN)
        self.assertTrue(all(e.ki.dwExtraInfo == win32.MARQUE for e in liste))


@unittest.skipUnless(WINDOWS, "Windows seulement")
class LesDispositions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        charger = win32.user32.LoadKeyboardLayoutW
        charger.argtypes = [wintypes.LPCWSTR, wintypes.UINT]
        charger.restype = wintypes.HKL
        cls.azerty = charger("0000040C", 0x80)        # KLF_NOTELLSHELL
        cls.qwerty = charger("00000409", 0x80)

    def test_azerty(self):
        c = win32.caractere
        self.assertEqual(c(0x41, 0x10, False, False, False, self.azerty), (1, "a"))
        self.assertEqual(c(0x41, 0x10, True, False, False, self.azerty), (1, "A"))
        self.assertEqual(c(0x32, 0x03, False, False, False, self.azerty), (1, "é"))
        self.assertEqual(c(0x32, 0x03, True, False, False, self.azerty), (1, "2"))
        self.assertEqual(c(0x45, 0x12, False, False, True, self.azerty), (1, "€"))
        self.assertTrue(win32.a_altgr(self.azerty))

    def test_touche_morte(self):
        n, _ = win32.caractere(0xDD, 0x1A, False, False, False, self.azerty)    # ^
        self.assertLess(n, 0)
        # Sans changer l'état du clavier : la touche suivante reste une lettre.
        self.assertEqual(win32.caractere(0x45, 0x12, False, False, False, self.azerty), (1, "e"))

    def test_la_touche_d_un_caractere(self):
        t = win32.touche_de
        self.assertEqual(t("a", self.azerty), (0x41, False))
        self.assertEqual(t("A", self.azerty), (0x41, True))
        self.assertEqual(t("é", self.azerty), (0x32, False))
        self.assertEqual(t("1", self.azerty), (0x31, True))       # Maj + &
        self.assertEqual(t("-", self.qwerty), (0xBD, False))
        for c in ("ɣ", "ḍ", "€", "ê", "\n"):                      # Unicode, AltGr, morte
            self.assertIsNone(t(c, self.azerty), c)
        self.assertIsNone(t("a", None))

    def test_vraies_touches_et_unicode(self):
        """Un remplacement en AZERTY : les caractères du clavier en touches, ɣ en
        Unicode, la majuscule avec Maj."""
        e = win32.entrees(1, "a-ɣ A", self.azerty)
        vk = [(x.ki.wVk, x.ki.wScan, x.ki.dwFlags) for x in e]
        haut, uni = win32.KEYEVENTF_KEYUP, win32.KEYEVENTF_UNICODE
        self.assertEqual(vk[:2], [(win32.VK_BACK, 0, 0), (win32.VK_BACK, 0, haut)])
        self.assertEqual(vk[2:4], [(0x41, 0, 0), (0x41, 0, haut)])
        self.assertEqual(vk[4:6], [(0x36, 0, 0), (0x36, 0, haut)])            # - en AZERTY
        self.assertEqual(vk[6:8], [(0, ord("ɣ"), uni), (0, ord("ɣ"), uni | haut)])
        self.assertEqual(vk[8:10], [(0x20, 0, 0), (0x20, 0, haut)])
        self.assertEqual([v[0] for v in vk[10:14]], [win32.VK_LSHIFT, 0x41, 0x41, win32.VK_LSHIFT])
        self.assertEqual(len(vk), 14)
        self.assertTrue(all(x.ki.dwExtraInfo == win32.MARQUE for x in e))

    def test_qwerty_sans_altgr(self):
        self.assertFalse(win32.a_altgr(self.qwerty))
        self.assertEqual(win32.caractere(0x47, 0x22, False, True, False, self.qwerty), (1, "G"))


@unittest.skipUnless(WINDOWS, "Windows seulement")
class LeSysteme(unittest.TestCase):

    def test_fenetre_sans_focus(self):
        import tkinter as tk
        r = tk.Tk()
        try:
            r.overrideredirect(True)
            r.update_idletasks()
            hwnd = win32.sans_focus(r.winfo_id())
            style = win32._lire_style(hwnd, win32.GWL_EXSTYLE)
            self.assertTrue(style & win32.WS_EX_NOACTIVATE)
            self.assertTrue(style & win32.WS_EX_TOPMOST)
        finally:
            r.destroy()

    def test_mot_de_passe_et_curseur(self):
        win32.initialiser_com()
        self.assertIn(win32.mot_de_passe(), (True, False))
        position = win32.curseur()
        self.assertTrue(position is None or len(position) == 3)

    def test_zone_de_travail(self):
        g, h, d, b = win32.zone_de_travail(10, 10)
        self.assertGreater(d, g)
        self.assertGreater(b, h)

    def test_ecriture_permise_chez_soi(self):
        self.assertTrue(win32.peut_ecrire_dans(win32.fenetre_active() or 0))

    def test_ecart_par_dessus_le_tour_du_compteur(self):
        self.assertEqual(win32.ecart(0x10, 0xFFFFFFF0), 0x20)
        self.assertEqual(win32.ecart(1000, 3000), -2000)
        self.assertGreater(win32.derniere_entree(), 0)

    def test_la_veille_voit_un_crochet_retire(self):
        """Une entrée que Windows a reçue et que nos crochets n'ont pas vue : une
        seule fois, pas plus."""
        c = win32.Crochets(lambda *a: False, lambda *a: None, lambda *a: None)
        vraie = win32.derniere_entree
        try:
            win32.derniere_entree = lambda: 100000
            c.vu = 100000 - 200                  # vue à temps
            self.assertFalse(c.verifier())
            c.vu = 100000 - 5000                 # cinq secondes sans nous
            self.assertTrue(c.verifier())
            self.assertFalse(c.verifier())
            win32.derniere_entree = lambda: 0x10  # le compteur a fait le tour
            c.vu = 0xFFFFFF00
            self.assertFalse(c.verifier())
        finally:
            win32.derniere_entree = vraie


# Le bout en bout

def _touche_physique(vk, haut=False):
    i = win32.INPUT()
    i.type = win32.INPUT_KEYBOARD
    i.ki = win32.KEYBDINPUT(vk, win32.user32.MapVirtualKeyW(vk, 0), 0x2 if haut else 0, 0, 0)
    return i


def taper_physique(touches, pause=0.0, pomper=None):
    """Des touches comme un vrai clavier : elles passent par le crochet. Sans
    pause, toutes d'un coup (une rafale) ; avec, une à une, comme une main."""
    if not pause:
        liste = []
        for vk in touches:
            liste += [_touche_physique(vk), _touche_physique(vk, True)]
        tableau = (win32.INPUT * len(liste))(*liste)
        return win32.user32.SendInput(len(liste), tableau, ctypes.sizeof(win32.INPUT))
    for vk in touches:
        for haut in (False, True):
            entree = (win32.INPUT * 1)(_touche_physique(vk, haut))
            win32.user32.SendInput(1, entree, ctypes.sizeof(win32.INPUT))
            (pomper or time.sleep)(pause / 2)
    return 2 * len(touches)


def zone_de_texte(fenetre):
    """La zone de texte du Bloc-notes, l'ancien (Edit) comme le nouveau
    (RichEditD2DPT, rangée plus profond)."""
    trouvees = []
    rappel_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def rappel(hwnd, _l):
        if win32.classe(hwnd) in ("Edit", "RichEditD2DPT"):
            trouvees.append(hwnd)
            return False
        return True

    win32.user32.EnumChildWindows.argtypes = [wintypes.HWND, rappel_t, wintypes.LPARAM]
    win32.user32.EnumChildWindows(fenetre, rappel_t(rappel), 0)
    return trouvees[0] if trouvees else None


@unittest.skipUnless(WINDOWS, "Windows seulement")
class DansLeBlocNotes(unittest.TestCase):

    def setUp(self):
        import faulthandler
        import tkinter as tk

        import kab_saisie
        import processus
        # Un blocage ne doit jamais tenir la CI des heures : au bout de deux
        # minutes, la pile de chaque fil est imprimée, et le test s'arrête.
        faulthandler.dump_traceback_later(120, exit=True)
        win32.user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
        win32.user32.SendMessageTimeoutW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPVOID, wintypes.UINT,
            wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        win32.user32.SendMessageTimeoutW.restype = wintypes.LPARAM
        processus.lancer = lambda *a, **k: None
        self.racine = tk.Tk()
        self.racine.withdraw()
        self.noyau = kab_saisie.Noyau(self.racine)
        self.noyau.service_brut = self._service
        self.noyau.icone = None
        self.noyau.crochets = win32.Crochets(self.noyau.sur_touche, self.noyau.sur_clic,
                                             self.noyau.sur_fenetre).demarrer()
        self.assertIsNone(self.noyau.crochets.erreur)
        import threading
        for cible in (self.noyau._proposer_en_fond, self.noyau._verifier_champs):
            threading.Thread(target=cible, daemon=True).start()
        self.bloc = subprocess.Popen(["notepad.exe"])
        self.zone = None
        fin = time.time() + 20
        while time.time() < fin and self.zone is None:
            self.pomper(0.3)
            fenetre = win32.user32.FindWindowW("Notepad", None)
            if fenetre:
                win32.user32.SetForegroundWindow(fenetre)
                self.zone = zone_de_texte(fenetre)
        if self.zone is None:
            self.skipTest("le Bloc-notes ne s'ouvre pas sur cette machine")
        fenetre = win32.racine(self.zone)
        self.attendre(lambda: win32.fenetre_active() == fenetre, 10)
        self.pomper(1.0)                 # le clavier regarde le champ, puis reprend
        self.attendre(lambda: self.noyau.frappe.actif and not self.noyau.frappe.prudent, 10)

    def tearDown(self):
        import faulthandler
        faulthandler.cancel_dump_traceback_later()
        self.noyau.fin.set()
        if self.noyau.crochets:
            self.noyau.crochets.arreter()
        self.bloc.kill()
        self.racine.destroy()

    def _service(self, quoi, delai=3.0, **p):
        if quoi == "proposer":
            return {"nature": "prop", "formes": ["ruḥeɣ", "ruḥ"], "mots_avant": 0}
        if quoi == "predire":
            return {"formes": ["ɣer"]}
        return None

    def pomper(self, duree=0.1):
        fin = time.time() + duree
        while time.time() < fin:
            self.noyau._pomper()
            self.racine.update()
            time.sleep(0.01)

    def attendre(self, condition, duree):
        fin = time.time() + duree
        while time.time() < fin:
            if condition():
                return True
            self.pomper(0.05)
        return condition()

    def message(self, code, wparam, lparam):
        """Un message au Bloc-notes, sans jamais l'attendre plus d'une seconde."""
        resultat = ctypes.c_size_t()
        win32.user32.SendMessageTimeoutW(self.zone, code, wparam, lparam, 0x2, 1000,
                                         ctypes.byref(resultat))      # SMTO_ABORTIFHUNG

    def texte(self):
        tampon = ctypes.create_unicode_buffer(4096)
        self.message(0x000D, 4096, ctypes.cast(tampon, wintypes.LPVOID))      # WM_GETTEXT
        return tampon.value

    def taper(self, texte, pause=0.04):
        return taper_physique([ord(c) if isinstance(c, str) else c for c in texte], pause,
                              self.pomper)

    def vider(self):
        self.message(0x000C, 0, ctypes.cast(ctypes.create_unicode_buffer(""),
                                            wintypes.LPVOID))           # WM_SETTEXT
        self.noyau.appliquer(self.noyau.frappe.reinitialiser())
        self.pomper(0.2)

    def test_ecrire_choisir(self):
        """À la vitesse d'une main rapide : 40 ms par touche."""
        if not self.noyau.frappe.actif or self.noyau.frappe.prudent:
            self.skipTest("le clavier n'a pas vu le Bloc-notes au premier plan")
        print(f"\n    Bloc-notes : {win32.classe(self.zone)}, Windows {platform.version()}",
              file=sys.stderr)
        self.taper("RUHAGH")
        if not self.attendre(lambda: self.texte(), 5):
            self.skipTest("les touches simulées n'arrivent pas au Bloc-notes ici")
        self.assertTrue(self.attendre(lambda: self.texte() == "ruhaɣ", 5), self.texte())
        self.assertTrue(self.attendre(lambda: self.noyau.frappe.propositions, 5))
        self.taper([0x31])                           # la touche 1
        self.assertTrue(self.attendre(lambda: self.texte() == "ruḥeɣ ", 5), self.texte())
        self.taper("AGH")
        self.taper([0x08])                           # l'effacement défait gh → ɣ
        self.assertTrue(self.attendre(lambda: self.texte() == "ruḥeɣ agh", 5), self.texte())

    def test_rafales(self):
        """La même suite en rafale et à plusieurs vitesses, quatre fois chacune.
        À vitesse humaine (20 et 40 ms), tout doit être juste ; plus vite, on ne
        fait qu'imprimer : aucune main ne tape douze touches à la fois."""
        if not self.noyau.frappe.actif or self.noyau.frappe.prudent:
            self.skipTest("le clavier n'a pas vu le Bloc-notes au premier plan")
        for pause in (0.0, 0.005, 0.02, 0.04):
            resultats = []
            for _ in range(4):
                self.vider()
                self.taper("RUHAGH DHAR", pause)
                self.attendre(lambda: self.texte().endswith("ḍar"), 2)
                self.pomper(0.3)
                resultats.append(self.texte())
            justes = sum(r == "ruhaɣ ḍar" for r in resultats)
            print(f"\n    pause {pause * 1000:.0f} ms : {justes}/4 justes {resultats}",
                  file=sys.stderr)
            if pause >= 0.02:
                self.assertEqual(justes, 4, resultats)


if __name__ == "__main__":
    unittest.main()
