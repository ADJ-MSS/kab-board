#!/usr/bin/env python3
"""Une fenêtre pour écrire et relire.

Les lettres kabyles sous les doigts, la barre des six propositions et le réglage
b ou v, comme la fenêtre Linux (bureau/kab_bureau.py). Clavier physique ou
touches à l'écran, les deux alimentent le même texte, par la même frappe que le
clavier système (frappe.py) : digrammes, chiffres de 1 à 6, possessif rattaché.
« Relire » parcourt le texte et propose, mot par mot, de remplacer.

Le correcteur est celui du service (service.py) : lancé s'il ne tourne pas, et
partagé avec le clavier kabyle s'il est allumé.

    pythonw windows/kab_bureau.py
"""
import os
import queue
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lieux  # noqa: E402

lieux.preparer()

import ecran  # noqa: E402
import liaison  # noqa: E402
import processus  # noqa: E402
import reglages as R  # noqa: E402
from disposition import FONCTIONS, KABYLES, RANGEES, SYMBOLES, Majuscules, couleur  # noqa: E402
from frappe import (Frappe, Touche, VK_BACK, VK_DELETE, VK_ESCAPE, VK_RETURN,  # noqa: E402
                    VK_TAB)

WINDOWS = os.name == "nt"
TITRE = "Kab-board : Écrire et relire"
NAVIGATION = {"Left": 0x25, "Right": 0x27, "Up": 0x26, "Down": 0x28, "Home": 0x24,
              "End": 0x23, "Prior": 0x21, "Next": 0x22, "Insert": 0x2D}
SPECIALES = {"BackSpace": VK_BACK, "Return": VK_RETURN, "KP_Enter": VK_RETURN, "Tab": VK_TAB,
             "Escape": VK_ESCAPE, "Delete": VK_DELETE}


class Bureau:

    def __init__(self, racine):
        self.racine = racine
        self.reglages = R.lire()
        self.frappe = Frappe(translitteration=self.reglages["translitteration"],
                             chiffres=self.reglages["chiffres"])
        self.client = liaison.Client("service", 3.0)
        self.client_fond = liaison.Client("service", 120.0)
        self.demandes = queue.Queue()
        self.taches = queue.Queue()
        self.maj = Majuscules()
        self.symboles = False
        self.fin = threading.Event()
        racine.title(TITRE)
        self.police = tkfont.Font(family="Segoe UI", size=14)
        self.petite = tkfont.Font(family="Segoe UI", size=10)

        self._entete()
        # Le bas d'abord : l'état, les touches, la barre. Le texte prend le reste.
        self.etat = tk.Label(racine, text="Le correcteur se prépare…", anchor="w",
                             fg="#5F6B76", font=self.petite)
        self.etat.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        self.clavier = tk.Frame(racine)
        self.clavier.pack(side="bottom", fill="x", padx=6, pady=(0, 4))
        self._dessiner_clavier()
        self.barre = tk.Frame(racine)
        self.barre.pack(side="bottom", fill="x", padx=8, pady=6)
        for i in range(6):
            self.barre.columnconfigure(i, weight=1, uniform="p")
        self.texte = tk.Text(racine, wrap="word", font=self.police, undo=True, padx=14, pady=14,
                             height=8, relief="flat", highlightthickness=1,
                             highlightbackground="#C8C8C8")
        self.texte.pack(side="top", fill="both", expand=True, padx=8, pady=(4, 0))
        self.texte.bind("<KeyPress>", self._touche)
        self.texte.bind("<Button-1>", lambda _e: self._reinitialiser())
        self.texte.bind("<<Paste>>", lambda _e: self._reinitialiser())
        self.texte.bind("<<Cut>>", lambda _e: self._reinitialiser())
        self._afficher([], "prop")
        self.texte.focus_set()
        # 820 × 720 si l'écran le permet ; sinon, le texte cède la place, jamais
        # les touches ni la barre.
        ecran.tenir(racine, 820, 720)

        for cible in (self._proposer_en_fond, self._veiller_service):
            threading.Thread(target=cible, daemon=True).start()
        racine.protocol("WM_DELETE_WINDOW", self.fermer)
        racine.after(15, self._pomper)

    # Interface

    def _entete(self):
        tete = ttk.Frame(self.racine, padding=(8, 8, 8, 0))
        tete.pack(fill="x")
        self.v_graphie = tk.StringVar(value=self.reglages["graphie"])
        for valeur, texte in (("v", "Écrire avec v"), ("b", "Écrire avec b")):
            ttk.Radiobutton(tete, text=texte, value=valeur, variable=self.v_graphie,
                            command=self._changer_graphie).pack(side="left", padx=(0, 12))
        ttk.Button(tete, text="Copier tout", command=self._copier).pack(side="right")
        ttk.Button(tete, text="Relire", command=self._relire).pack(side="right", padx=6)

    def _dessiner_clavier(self):
        for enfant in self.clavier.winfo_children():
            enfant.destroy()
        for rangee in (SYMBOLES if self.symboles else RANGEES):
            ligne = tk.Frame(self.clavier)
            ligne.pack(fill="x", pady=1)
            for touche in rangee:
                libelle = touche[0]
                texte = {"␣": "Taqbaylit", "⇧": self.maj.libelle}.get(libelle, libelle)
                if len(touche) > 1:
                    texte += "  " + " ".join(touche[1:])
                b = tk.Button(ligne, text=texte, takefocus=0, relief="groove",
                              font=self.petite if (libelle in FONCTIONS or len(touche) > 1)
                              else self.police,
                              fg="#00843F" if libelle in KABYLES else "#1E1E1E",
                              command=lambda t=touche: self._touche_ecran(t))
                b.pack(side="left", fill="x", expand=True, padx=1, ipady=4,
                       ipadx=50 if libelle == "␣" else 0)
                if len(touche) > 1:
                    b.bind("<Button-3>", lambda e, t=touche: self._variantes(e, t))

    def _variantes(self, e, touche):
        menu = tk.Menu(self.racine, tearoff=0)
        for v in touche[1:]:
            menu.add_command(label=v, command=lambda c=v: self._ecran(c))
        menu.tk_popup(e.x_root, e.y_root)

    def _afficher(self, formes, nature):
        for enfant in self.barre.winfo_children():
            enfant.destroy()
        for rang in range(6):
            forme = formes[rang] if rang < len(formes) else ""
            case = tk.Frame(self.barre)
            case.grid(row=0, column=rang, sticky="ew", padx=2)
            b = tk.Button(case, text=forme or " ", takefocus=0, relief="flat", font=self.police,
                          state="normal" if forme else "disabled",
                          command=lambda f=forme: self._choisir(f))
            b.pack(fill="x")
            tk.Frame(case, height=3, bg=couleur(nature, rang) if forme else "#F0F0F0").pack(
                fill="x")

    def _dire(self, message):
        self.etat.configure(text=message)

    # Le texte : appliquer ce que décide la frappe

    def _appliquer(self, action):
        if action.ecrit:
            if action.effacer:
                self.texte.delete(f"insert-{action.effacer}c", "insert")
            if action.texte:
                self.texte.insert("insert", action.texte)
            self.texte.see("insert")
        with self.frappe.verrou:
            g, c, m = self.frappe.generation, self.frappe.contexte_visible(), self.frappe.mot
        if action.proposer and m:
            self.demandes.put(("proposer", g, c, m))
        elif action.predire:
            self.demandes.put(("predire", g, c, ""))
        if action.cacher and not action.proposer:
            self._afficher([], "prop")

    def _reinitialiser(self):
        self._appliquer(self.frappe.reinitialiser())

    def _touche(self, e):
        if self.texte.tag_ranges("sel") and e.keysym not in ("Shift_L", "Shift_R"):
            self.frappe.reinitialiser()          # la sélection va être remplacée
        controle = bool(e.state & 0x4)
        if e.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
                        "Caps_Lock", "Num_Lock", "Win_L", "Win_R", "ISO_Level3_Shift"):
            return None
        if controle:
            touche = Touche(0, ctrl=True)
        elif e.keysym in NAVIGATION:
            touche = Touche(NAVIGATION[e.keysym])
        elif e.keysym in SPECIALES:
            touche = Touche(SPECIALES[e.keysym])
        elif e.char and e.char.isprintable():
            touche = Touche(0x41, e.char, e.char)
        else:
            touche = Touche(0)
        action = self.frappe.touche(touche)
        self._appliquer(action)
        return "break" if action.bloquer else None

    def _touche_ecran(self, touche):
        libelle = touche[0]
        if libelle == "⇧":
            self.maj.appuyer()
            self._dessiner_clavier()
        elif libelle in ("123", "ABC"):
            self.symboles = not self.symboles
            self._dessiner_clavier()
        elif libelle == "⌫":
            self._appliquer(self.frappe.effacer_ecran())
        elif libelle == "␣":
            self._appliquer(self.frappe.ecrire(" "))
        elif libelle == "⏎":
            self._appliquer(self.frappe.ecrire("\n"))
        else:
            self._ecran(libelle)
        self.texte.focus_set()

    def _ecran(self, c):
        avant = self.maj.libelle
        c = self.maj.appliquer(c)
        if avant != self.maj.libelle:
            self._dessiner_clavier()
        self._appliquer(self.frappe.lettre_ecran(c))
        self.texte.focus_set()

    def _choisir(self, forme):
        self._appliquer(self.frappe.choisir_forme(forme))
        self.texte.focus_set()

    # Le correcteur

    def service(self, quoi, client=None, **parametres):
        parametres.setdefault("graphie", self.reglages["graphie"])
        return (client or self.client).appeler(quoi, **parametres)

    def _veiller_service(self):
        lance = 0.0
        while not self.fin.is_set():
            r = self.client.appeler("attacher", pid=os.getpid())
            if r is None:
                if time.time() - lance > 90:
                    lance = time.time()
                    processus.lancer("service.py")
                self.fin.wait(1.0)
                continue
            etat = self.client.appeler("etat") or {}
            if etat.get("erreur"):
                self.taches.put((self._dire, (f"Correcteur indisponible : {etat['erreur']}",)))
            elif etat.get("pret"):
                self.taches.put((self._dire, ("Correcteur prêt. Les chiffres 1 à 6 choisissent "
                                              "une proposition.",)))
            else:
                self.taches.put((self._dire, (f"Le correcteur se prépare "
                                              f"({etat.get('depuis', 0):.0f} s)…",)))
            self.fin.wait(10.0 if etat.get("pret") else 1.0)

    def _proposer_en_fond(self):
        client = liaison.Client("service", 3.0)
        while not self.fin.is_set():
            try:
                demande = self.demandes.get(timeout=1.0)
            except queue.Empty:
                continue
            while not self.demandes.empty():
                demande = self.demandes.get_nowait()
            genre, generation, contexte, mot = demande
            if genre == "proposer":
                r = self.service("proposer", client, contexte=contexte, mot=mot) or {}
                formes, nature = r.get("formes") or [], r.get("nature", "prop")
                mots_avant = int(r.get("mots_avant") or 0)
            else:
                r = self.service("predire", client, contexte=contexte) or {}
                formes, nature, mots_avant = r.get("formes") or [], "pred", 0
            if self.frappe.montrer(generation, formes, nature, mots_avant):
                self.taches.put((self._afficher, (formes, nature)))

    def _pomper(self):
        try:
            while True:
                fonction, arguments = self.taches.get_nowait()
                fonction(*arguments)
        except queue.Empty:
            pass
        if not self.fin.is_set():
            self.racine.after(15, self._pomper)

    # La graphie, relire, copier

    def _changer_graphie(self):
        self.reglages = R.changer(graphie=self.v_graphie.get())
        liaison.Client("saisie", 0.5).appeler("reglages")
        texte = self.texte.get("1.0", "end-1c")
        if texte.strip():
            r = self.service("basculer", texte=texte)
            if r and r.get("texte") is not None and r["texte"] != texte:
                # Le texte déjà écrit suit le réglage, comme les propositions.
                self.texte.delete("1.0", "end")
                self.texte.insert("1.0", r["texte"])
        self._reinitialiser()

    def _copier(self):
        self.racine.clipboard_clear()
        self.racine.clipboard_append(self.texte.get("1.0", "end-1c"))
        self._dire("Le texte est dans le presse-papiers.")

    def _relire(self):
        texte = self.texte.get("1.0", "end-1c")
        if not texte.strip():
            return
        self._dire("Relecture…")

        def fond():
            r = self.service("relire", self.client_fond, texte=texte[:20000]) or {}
            self.taches.put((self._montrer_relecture, (r, texte)))

        threading.Thread(target=fond, daemon=True).start()

    def _montrer_relecture(self, r, texte):
        if r.get("erreur") or "signales" not in r:
            self._dire(r.get("erreur") or "Le correcteur ne répond pas.")
            return
        signales = r["signales"]
        self._dire(f"Relecture : {len(signales)} mot(s) à regarder.")
        fen = tk.Toplevel(self.racine)
        fen.title("Kab-board : Relecture")
        fen.transient(self.racine)
        cadre = ttk.Frame(fen, padding=12)
        cadre.pack(fill="both", expand=True)
        if not signales:
            ttk.Label(cadre, text="Rien à signaler.").pack(anchor="w")
        for s in signales[:60]:
            ligne = ttk.Frame(cadre)
            ligne.pack(fill="x", pady=2)
            ttk.Label(ligne, text=f"{s['mot']}  →", width=18).pack(side="left")
            for p in s["propositions"][:4]:
                ttk.Button(ligne, text=p, command=lambda s=s, p=p: self._remplacer(
                    fen, texte, s, p)).pack(side="left", padx=2)
            ttk.Button(ligne, text="Mon dictionnaire", command=lambda s=s: self._garder(
                fen, s)).pack(side="right")

    def _remplacer(self, fen, texte, s, forme):
        """Remplace ce mot-là, s'il est toujours là, puis relit de nouveau."""
        if self.texte.get("1.0", "end-1c") != texte:
            fen.destroy()
            self._relire()
            return
        self.texte.delete(f"1.0+{s['debut']}c", f"1.0+{s['fin']}c")
        self.texte.insert(f"1.0+{s['debut']}c", forme)
        self._reinitialiser()
        fen.destroy()
        self._relire()

    def _garder(self, fen, s):
        self.service("ajouter", mot=s["mot"])
        fen.destroy()
        self._relire()

    def fermer(self):
        self.fin.set()
        self.client.appeler("detacher", pid=os.getpid())
        self.racine.destroy()


def principal(argv) -> int:
    if not processus.instance_unique("bureau"):
        if WINDOWS:
            import win32
            win32.montrer_fenetre(TITRE)
        return 0
    processus.journal("bureau")
    if WINDOWS:
        import win32
        win32.net_sur_tous_les_ecrans()
    racine = tk.Tk()
    Bureau(racine)
    racine.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
