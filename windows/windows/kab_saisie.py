#!/usr/bin/env python3
"""Le clavier kabyle de Windows : il écrit dans toutes les applications.

Le pendant de la méthode de saisie IBus de Linux. Un crochet voit chaque touche
avant l'application active ; la frappe (frappe.py) décide de la laisser passer
ou d'écrire autre chose à sa place. Les six propositions du mot en cours
s'affichent dans une barre sous le curseur ; un chiffre de 1 à 6, ou un clic, en
choisit une. Rien n'est corrigé d'office.

Le même processus porte le clavier à l'écran, l'icône près de l'horloge, et la
liaison par laquelle l'application de réglages lui parle. Le correcteur, lourd,
tourne à part (service.py) : la frappe ne l'attend jamais.

    pythonw windows/kab_saisie.py [--clavier]
"""
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lieux  # noqa: E402

lieux.preparer()

import liaison  # noqa: E402
import processus  # noqa: E402
import reglages as R  # noqa: E402
from barre import Barre  # noqa: E402
from clavier_ecran import ClavierEcran  # noqa: E402
from frappe import MODIFICATEURS, VK_RETURN, VK_TAB, Action, Frappe, Touche  # noqa: E402

WINDOWS = os.name == "nt"
if WINDOWS:
    import win32

ICONE = lieux.RACINE / "lanceur" / "kab-board.ico"
TITRES_A_NOUS = ("Kab-board",)        # nos fenêtres Tk : le clavier s'y tait


class Noyau:
    """Le clavier kabyle : l'état de la frappe, et tout ce qui le fait vivre."""

    def __init__(self, racine, injecter=None):
        self.racine = racine
        self.reglages = R.lire()
        self.frappe = Frappe(translitteration=self.reglages["translitteration"],
                             chiffres=self.reglages["chiffres"])
        # Le verrouillage des majuscules, nous le suivons nous-mêmes : le fil du
        # crochet ne voit pas l'état du clavier à jour.
        self.injecter = injecter or (
            (lambda e, t: win32.taper(e, t, verr_maj=self.verr_maj)) if WINDOWS
            else (lambda e, t: True))
        self.taches = queue.Queue()            # pour le fil de l'interface
        self.demandes = queue.Queue()          # pour le fil des propositions
        self.verifications = queue.Queue()     # pour le fil qui regarde les champs
        self._clients = threading.local()
        self.bloquees, self.enfoncees = set(), set()
        self.verr_maj = win32.verrouillage_majuscules() if WINDOWS else False
        self.nos_fenetres = []                 # leurs HWND, pour les clics
        self.etat_service = {}
        self.annonce_faite = False
        self.crochets = None
        self.icone = None
        self.serveur = None
        self.fin = threading.Event()
        self._dernier_service_lance = 0.0
        self._derniere_pose = 0.0
        self._derniere_touche = 0.0            # time.monotonic() de la dernière touche suivie
        self._fenetre_frappe = None            # et la fenêtre où elle a été tapée
        self._geste = 0.0                      # le dernier Tab, Entrée ou clic
        self._verifiee = (None, 0.0)           # la dernière fenêtre vue sans mot de passe, et quand
        self._suspensions = 0                  # chaque suspension a son numéro
        self.affiche = ([], "prop", "")
        self.barre = Barre(racine, self.choisir_forme, self.fiche)
        self.clavier = ClavierEcran(self)

    # Les fils

    def planifier(self, fonction, *arguments):
        """Exécute fonction dans le fil de l'interface : tkinter n'en tolère qu'un."""
        self.taches.put((fonction, arguments))

    def _pomper(self):
        """Exécute ce que les autres fils ont demandé à l'interface."""
        try:
            while True:
                fonction, arguments = self.taches.get_nowait()
                try:
                    fonction(*arguments)
                except Exception as erreur:
                    print(f"interface : {erreur!r}", flush=True)
        except queue.Empty:
            pass

    def _pomper_sans_fin(self):
        self._pomper()
        if not self.fin.is_set():
            self.racine.after(15, self._pomper_sans_fin)

    def demarrer(self):
        self.serveur = liaison.Serveur("saisie", self.traiter).demarrer()
        for cible, nom in ((self._proposer_en_fond, "propositions"),
                           (self._veiller_service, "service"),
                           (self._verifier_champs, "champs")):
            threading.Thread(target=cible, name=nom, daemon=True).start()
        if WINDOWS:
            self.crochets = win32.Crochets(self.sur_touche, self.sur_clic, self.sur_fenetre)
            self.crochets.demarrer()
            if self.crochets.erreur:
                win32.message("Kab-board", f"Le clavier kabyle ne peut pas démarrer : "
                                           f"{self.crochets.erreur}")
            self.icone = win32.IconeNotification(
                str(ICONE), "Kab-board : le correcteur se prépare…",
                self._menu, lambda i: self.planifier(self._choix_menu, i),
                lambda: self.planifier(self.ouvrir_appli))
            self.crochets.dans_le_fil(self.icone.creer)
        if self.reglages.get("clavier_ecran") or "--clavier" in sys.argv:
            self.clavier.afficher()
            self._noter_fenetres()
        self.racine.after(15, self._pomper_sans_fin)

    def quitter(self):
        if self.fin.is_set():
            return
        self.fin.set()
        try:
            self.service_brut("detacher", pid=os.getpid())
        except Exception:
            pass
        if self.crochets is not None:
            if self.icone is not None:
                self.crochets.dans_le_fil(self.icone.retirer)
                time.sleep(0.2)
            self.crochets.arreter()
        if self.serveur is not None:
            self.serveur.arreter()
        self.racine.after(50, self.racine.destroy)

    # Le correcteur, à part

    def service_brut(self, quoi, delai=3.0, **parametres):
        client = getattr(self._clients, "client", None)
        if client is None:
            client = self._clients.client = liaison.Client("service", delai)
        return client.appeler(quoi, delai=delai, **parametres)

    def service(self, quoi, delai=3.0, **parametres):
        """Une requête au correcteur, dans la graphie réglée. None s'il ne répond pas."""
        parametres.setdefault("graphie", self.reglages["graphie"])
        return self.service_brut(quoi, delai, **parametres)

    def _veiller_service(self):
        """Le correcteur tourne-t-il ? Sinon on le lance ; s'il tombe, on le relance."""
        while not self.fin.is_set():
            r = self.service_brut("attacher", pid=os.getpid())
            if r is None:
                if time.time() - self._dernier_service_lance > 90:
                    self._dernier_service_lance = time.time()
                    processus.lancer("service.py")
                self.fin.wait(1.0)
                continue
            etat = self.service_brut("etat") or {}
            self.etat_service = etat
            if etat.get("pret") and not self.annonce_faite:
                self.annonce_faite = True
                self._annoncer("Kab-board est prêt",
                               "Le clavier kabyle écrit dans toutes les applications. "
                               "Les chiffres 1 à 6 choisissent une proposition "
                               "(en AZERTY : Maj + 1 à 6).")
            self._infobulle()
            if R.lire()["graphie"] != self.reglages["graphie"]:
                self.planifier(self.relire_reglages)      # changée dans Word
            self.fin.wait(10.0 if etat.get("pret") else 1.0)

    def _infobulle(self):
        if self.icone is None:
            return
        e = self.etat_service
        if e.get("erreur"):
            texte = "Kab-board : correcteur indisponible"
        elif e.get("pret"):
            texte = f"Kab-board : prêt, graphie {self.reglages['graphie']}"
        else:
            texte = "Kab-board : le correcteur se prépare…"
        if self.icone.infobulle != texte:
            self.crochets.dans_le_fil(lambda: self.icone.changer_infobulle(texte))

    def _annoncer(self, titre, texte):
        if self.icone is not None:
            self.crochets.dans_le_fil(lambda: self.icone.annoncer(titre, texte))

    # Les touches (fil des crochets : répondre vite)

    def _touche(self, vk, scan) -> Touche:
        if vk in MODIFICATEURS:
            return Touche(vk)
        m = win32.modificateurs()
        hkl = win32.disposition_active()
        altgr = (m["alt_droite"] or (m["ctrl"] and m["alt"])) and win32.a_altgr(hkl)
        if not altgr and (m["ctrl"] or m["alt"] or m["win"]):
            return Touche(vk, ctrl=True)
        n, c = win32.caractere(vk, scan, m["maj"], self.verr_maj, altgr, hkl)
        if n < 0:
            return Touche(vk, morte=True)
        base = win32.caractere(vk, scan, m["maj"], self.verr_maj, False, hkl)[1] if altgr else c
        return Touche(vk, c, base, altgr=altgr)

    def sur_touche(self, message, k) -> bool:
        vk = k.vkCode
        if message in (win32.WM_KEYUP, win32.WM_SYSKEYUP):
            self.enfoncees.discard(vk)
            if vk in self.bloquees:
                self.bloquees.discard(vk)
                return True
            return False
        repetition = vk in self.enfoncees
        self.enfoncees.add(vk)
        if vk == win32.VK_CAPITAL and not repetition:
            self.verr_maj = not self.verr_maj
        if vk in (VK_TAB, VK_RETURN):
            self._geste = time.monotonic()       # souvent, le champ suivant
        if not self.frappe.actif:
            return False
        self._derniere_touche = time.monotonic()
        self._fenetre_frappe = win32.fenetre_active() if WINDOWS else None
        action = self.frappe.touche(self._touche(vk, k.scanCode))
        if action.bloquer:
            self.bloquees.add(vk)
        self.appliquer(action)
        return action.bloquer

    def sur_clic(self, x, y):
        """Un clic ailleurs que chez nous : le curseur a pu bouger."""
        for hwnd in self.nos_fenetres:
            r = win32.rectangle(hwnd)
            if r and win32.user32.IsWindowVisible(hwnd) and r[0] <= x < r[2] and r[1] <= y < r[3]:
                return
        self._geste = time.monotonic()
        if self.frappe.mot or self.frappe.contexte or self.frappe.propositions:
            self.appliquer(self.frappe.reinitialiser())

    DANS_LA_FRAPPE = 1.5      # s : un focus qui bouge si tôt après une touche vient de la page
    APRES_UN_GESTE = 1.0      # s : Tab, Entrée ou un clic juste avant : un vrai autre champ
    VERIFIEE = 3.0            # s : une fenêtre vue sans mot de passe, il y a si peu

    def sur_fenetre(self, evenement, hwnd):
        """Une autre fenêtre, un autre champ : le temps de voir si c'est un mot de
        passe, le clavier suit les lettres sans rien réécrire, puis reprend.

        Un navigateur, un traitement de texte déplacent le focus d'eux-mêmes
        (des suggestions qui s'ouvrent ; Word, à son démarrage, sans arrêt) :
        dans une fenêtre vue il y a un instant, et sans Tab, Entrée ni clic de
        votre part, le clavier ne s'interrompt pas, et le champ se vérifie quand
        même. En plein mot, le mot reste le même."""
        maintenant = time.monotonic()
        racine = win32.racine(hwnd) if WINDOWS and hwnd else None
        focus = WINDOWS and evenement == win32.EVENT_OBJECT_FOCUS
        geste = maintenant - self._geste < self.APRES_UN_GESTE
        deja_vue = (focus and not geste and racine == self._verifiee[0]
                    and maintenant - self._verifiee[1] < self.VERIFIEE)
        meme = (focus and racine == self._fenetre_frappe
                and maintenant - self._derniere_touche < self.DANS_LA_FRAPPE)
        if not (self.frappe.actif and not self.frappe.prudent and (deja_vue or meme)):
            self._suspensions += 1
            self.appliquer(self.frappe.suspendre(garder=bool(meme)))
        self.verifications.put(evenement)
        if evenement == win32.EVENT_SYSTEM_FOREGROUND and time.time() - self._derniere_pose > 10:
            self._derniere_pose = time.time()
            self.crochets.reposer()

    def _verifier_champs(self):
        if WINDOWS:
            win32.initialiser_com()
        while not self.fin.is_set():
            try:
                self.verifications.get(timeout=1.0)
            except queue.Empty:
                continue
            time.sleep(0.03)                       # la rafale d'évènements passe
            while not self.verifications.empty():
                self.verifications.get_nowait()
            if not WINDOWS:
                self.appliquer(self.frappe.reprendre(True))
                continue
            # Ce que la vérification voit vaut pour toutes les suspensions faites
            # jusqu'ici : une suivante attend la sienne.
            numero = self._suspensions
            try:
                fg = win32.fenetre_active()
                a_nous = (win32.classe(fg) == "TkTopLevel"
                          and win32.titre(fg).startswith(TITRES_A_NOUS))
                actif = (not a_nous and win32.peut_ecrire_dans(fg)
                         and not win32.mot_de_passe())
            except Exception as erreur:
                print(f"champs : {erreur!r}", flush=True)
                fg, actif = None, True
            if not actif:
                self._verifiee = (None, 0.0)
                self.appliquer(self.frappe.reprendre(False))   # un mot de passe : tout de suite
            else:
                self._verifiee = (win32.racine(fg) if fg else None, time.monotonic())
                if numero == self._suspensions:
                    self.appliquer(self.frappe.reprendre(True))

    # Écrire, et demander les propositions

    def appliquer(self, action: Action):
        if action.ecrit:
            self.injecter(action.effacer, action.texte)
        with self.frappe.verrou:
            generation = self.frappe.generation
            contexte, mot = self.frappe.contexte_visible(), self.frappe.mot
        if action.proposer and mot:
            self.demandes.put(("proposer", generation, contexte, mot))
        elif action.predire:
            self.demandes.put(("predire", generation, contexte, ""))
        if action.cacher and not action.proposer:
            self.planifier(self._afficher, [], "prop", "")

    def _proposer_en_fond(self):
        """Une demande à la fois, et seulement la dernière : la frappe va plus vite
        que le correcteur, les réponses périmées ne servent à rien."""
        while not self.fin.is_set():
            try:
                demande = self.demandes.get(timeout=1.0)
            except queue.Empty:
                continue
            while True:
                try:
                    demande = self.demandes.get_nowait()
                except queue.Empty:
                    break
            genre, generation, contexte, mot = demande
            if generation != self.frappe.generation:
                continue
            if genre == "proposer":
                r = self.service("proposer", contexte=contexte, mot=mot) or {}
                formes, nature = r.get("formes") or [], r.get("nature", "prop")
                mots_avant = int(r.get("mots_avant") or 0)
            else:
                r = self.service("predire", contexte=contexte) or {}
                formes, nature, mots_avant = r.get("formes") or [], "pred", 0
            if self.frappe.montrer(generation, formes, nature, mots_avant):
                self.planifier(self._afficher, list(formes), nature, mot)

    # L'interface (fil de tkinter)

    def _afficher(self, formes, nature, mot):
        self.affiche = (formes, nature, mot)
        if formes and self.reglages.get("barre", True) and self.frappe.actif:
            self.barre.montrer(formes, nature, self._ancre())
        else:
            self.barre.cacher()
        if self.clavier.visible:
            self.clavier.montrer_propositions(formes, nature, mot)
        self._noter_fenetres()

    def _ancre(self):
        """Où poser la barre : sous le curseur de texte ; sinon au-dessus du clavier
        à l'écran ; sinon en bas de l'écran de la fenêtre active."""
        if WINDOWS:
            try:
                position = win32.curseur()
            except Exception:
                position = None
            if position:
                return position
        if self.clavier.visible:
            return (self.clavier.fen.winfo_rootx() + 12, self.clavier.fen.winfo_rooty() - 60, 0)
        if WINDOWS:
            g, _h, d, b = win32.zone_de_la_fenetre(win32.fenetre_active())
        else:
            g, _h, d, b = 0, 0, self.racine.winfo_screenwidth(), self.racine.winfo_screenheight()
        return (g + (d - g) // 2 - 200, b - 70, 0)

    def _noter_fenetres(self):
        self.nos_fenetres = [h for h in (self.barre.hwnd, self.clavier.hwnd) if h]
        if self.clavier._volante is not None and WINDOWS:
            try:
                self.nos_fenetres.append(win32.user32.GetParent(self.clavier._volante.winfo_id()))
            except tk.TclError:
                pass

    # Ce que demandent le clavier à l'écran et la barre

    def lettre(self, c):
        self.appliquer(self.frappe.lettre_ecran(c))

    def effacer(self):
        self.appliquer(self.frappe.effacer_ecran())

    def effacer_mot(self):
        self.appliquer(self.frappe.effacer_mot_ecran())

    def ecrire(self, texte, dictee=False):
        self.appliquer(self.frappe.ecrire(texte, dictee=dictee))

    def choisir_forme(self, forme):
        self.appliquer(self.frappe.choisir_forme(forme))

    def fiche(self, forme):
        self.clavier.fiche(forme)
        self._noter_fenetres()

    def changer_graphie(self, valeur):
        self.reglages = R.changer(graphie="b" if valeur == "b" else "v")
        self.clavier.marquer_graphie(self.reglages["graphie"])
        self._infobulle()
        self._reproposer()

    def basculer_translit(self) -> bool:
        actif = not self.reglages["translitteration"]
        self.reglages = R.changer(translitteration=actif)
        self.frappe.saisie.translitteration = actif
        return actif

    def basculer_clavier(self, montrer=None):
        montrer = (not self.clavier.visible) if montrer is None else montrer
        if montrer:
            self.clavier.afficher()
            self.clavier.montrer_propositions(*self.affiche)
        else:
            self.clavier.masquer()
        self.reglages = R.changer(clavier_ecran=bool(montrer))
        self._noter_fenetres()

    def _reproposer(self):
        with self.frappe.verrou:
            g, c, m = self.frappe.generation, self.frappe.contexte_visible(), self.frappe.mot
        if m:
            self.demandes.put(("proposer", g, c, m))

    def relire_reglages(self):
        """L'application a changé un réglage : on le prend en compte tout de suite."""
        avant = self.reglages
        self.reglages = R.lire()
        self.frappe.saisie.translitteration = self.reglages["translitteration"]
        self.frappe.chiffres = self.reglages["chiffres"]
        if avant.get("graphie") != self.reglages["graphie"]:
            self.clavier.marquer_graphie(self.reglages["graphie"])
            self._reproposer()
        if bool(avant.get("clavier_ecran")) != bool(self.reglages.get("clavier_ecran")):
            self.basculer_clavier(bool(self.reglages.get("clavier_ecran")))
        if not self.reglages.get("barre", True):
            self.barre.cacher()
        self._infobulle()

    def ouvrir_appli(self):
        processus.lancer("kab_appli.py")

    def ouvrir_bureau(self):
        processus.lancer("kab_bureau.py")

    # Le menu de l'icône (fil des crochets pour le construire)

    def _menu(self):
        r = self.reglages
        pret = bool(self.etat_service.get("pret"))
        return [(1, "Écrire avec b", r["graphie"] == "b", True),
                (2, "Écrire avec v", r["graphie"] == "v", True),
                None,
                (3, "Écrire comme on parle (gh → ɣ)", r["translitteration"], True),
                (4, "Clavier à l'écran", self.clavier.visible, True),
                (5, "Barre des propositions", r.get("barre", True), True),
                None,
                (6, "Écrire et relire…", False, True),
                (7, "Réglages de Kab-board…", False, True),
                None,
                (9, "Correcteur prêt" if pret else "Correcteur en préparation…", False, False),
                (8, "Arrêter le clavier kabyle", False, True)]

    def _choix_menu(self, ident):
        if ident in (1, 2):
            self.changer_graphie("b" if ident == 1 else "v")
        elif ident == 3:
            self.basculer_translit()
        elif ident == 4:
            self.basculer_clavier()
        elif ident == 5:
            self.reglages = R.changer(barre=not self.reglages.get("barre", True))
            if not self.reglages["barre"]:
                self.barre.cacher()
        elif ident == 6:
            self.ouvrir_bureau()
        elif ident == 7:
            self.ouvrir_appli()
        elif ident == 8:
            self.quitter()

    # La liaison : ce que demande l'application de réglages

    def traiter(self, requete):
        quoi = requete.get("quoi")
        if quoi == "etat":
            f = self.frappe
            return {"actif": f.actif, "mot": f.mot, "nature": f.nature,
                    "propositions": list(f.propositions), "graphie": self.reglages["graphie"],
                    "clavier": self.clavier.visible, "service": self.etat_service,
                    "crochet": bool(self.crochets and not self.crochets.erreur) or not WINDOWS,
                    "pid": os.getpid()}
        if quoi == "reglages":
            self.planifier(self.relire_reglages)
            return {"ok": True}
        if quoi == "clavier":
            self.planifier(self.basculer_clavier, bool(requete.get("montrer", True)))
            return {"ok": True}
        if quoi == "quitter":
            self.planifier(self.quitter)
            return {"ok": True}
        return {"erreur": "requête inconnue"}


def principal(argv) -> int:
    if not processus.instance_unique("saisie"):
        if "--clavier" in argv:
            liaison.Client("saisie").appeler("clavier", montrer=True)
        return 0
    processus.journal("saisie")
    if WINDOWS:
        win32.net_sur_tous_les_ecrans()
    racine = tk.Tk()
    racine.withdraw()
    racine.title("Kab-board, clavier")
    if WINDOWS:
        win32.initialiser_com()
    noyau = Noyau(racine)
    noyau.demarrer()
    print(f"kab-board : clavier kabyle allumé (pid {os.getpid()})", flush=True)
    try:
        racine.mainloop()
    finally:
        noyau.quitter()
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
