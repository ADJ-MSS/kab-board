"""Le clavier à l'écran, posé au-dessus des autres fenêtres.

Repris du clavier flottant de Linux : la disposition AZERTY et ses appuis longs,
les six propositions, la rangée d'outils (dicter, gh → ɣ, Asegzawal, fr → kab,
relire, mot du jour) et les panneaux qui prennent la place des touches.

Il ne prend jamais le focus : un clic sur une touche laisse le curseur dans
l'application où l'on écrit, et c'est le clavier kabyle (le noyau) qui y écrit
la lettre. On le déplace en tirant sa barre de titre.
"""
import os
import threading
import tkinter as tk
import tkinter.font as tkfont

from disposition import FONCTIONS, KABYLES, RANGEES, SYMBOLES, Majuscules, couleur

FOND, TOUCHE, TOUCHE_APPUI, FONCTION = "#E9ECEF", "#FFFFFF", "#D0D7DE", "#DDE2E7"
TEXTE, DISCRET, VERT = "#1E1E1E", "#6B7280", "#00843F"
APPUI_LONG_MS = 450


class ClavierEcran:

    def __init__(self, noyau):
        self.noyau = noyau
        self.racine = noyau.racine
        self.symboles = False
        self.maj = Majuscules()
        self.micro = None                    # l'enregistrement en cours
        self.recherche = None                # le texte de fr → kab, tapé ici
        self.hwnd = None
        self.visible = False
        self._depart = None
        self._appui = None                   # (minuterie, touche) d'un appui en cours
        self._volante = None                 # la fenêtre des variantes

        f = self.fen = tk.Toplevel(self.racine)
        f.withdraw()
        f.overrideredirect(True)
        f.attributes("-topmost", True)
        f.configure(bg=FOND, highlightthickness=1, highlightbackground="#B8C0C8")
        self.police = tkfont.Font(family="Segoe UI", size=14)
        self.police_petite = tkfont.Font(family="Segoe UI", size=10)
        self.police_variante = tkfont.Font(family="Segoe UI", size=7)
        self.police_prop = tkfont.Font(family="Segoe UI", size=12)

        colonne = tk.Frame(f, bg=FOND)
        colonne.pack(fill="both", expand=True, padx=6, pady=6)
        self._tete(colonne)
        self._outils(colonne)
        self.barre = tk.Frame(colonne, bg=FOND)
        self.barre.pack(fill="x", pady=(4, 4))
        for i in range(6):
            self.barre.columnconfigure(i, weight=1, uniform="prop")
        self.zone = tk.Frame(colonne, bg=FOND)
        self.zone.pack(fill="both", expand=True)
        self.touches = tk.Frame(self.zone, bg=FOND)
        self.panneau = tk.Frame(self.zone, bg=FOND)
        self.touches.pack(fill="both", expand=True)
        self._dessiner()
        self.montrer_propositions([], "prop")

    # La fenêtre

    def afficher(self):
        if self.visible:
            return
        if self.hwnd is None:
            self.fen.update_idletasks()
            if os.name == "nt":
                import win32
                self.hwnd = win32.sans_focus(self.fen.winfo_id())
            self._se_placer()
        self.fen.deiconify()
        self.fen.attributes("-topmost", True)
        self.visible = True

    def masquer(self):
        if self.visible:
            self.fen.withdraw()
            self.visible = False
        self._fermer_volante()

    def _se_placer(self):
        """En bas de l'écran, centré, comme un clavier à l'écran doit l'être."""
        self.fen.update_idletasks()
        largeur = max(self.fen.winfo_reqwidth(), 720)
        hauteur = self.fen.winfo_reqheight()
        if os.name == "nt":
            import win32
            g, _h, d, b = win32.zone_de_travail(*win32.souris())
        else:
            g, _h, d, b = 0, 0, self.fen.winfo_screenwidth(), self.fen.winfo_screenheight()
        self.fen.geometry(f"{largeur}x{hauteur}+{g + (d - g - largeur) // 2}+{b - hauteur - 12}")

    def _tete(self, parent):
        """L'état, le choix de graphie, et de quoi déplacer ou fermer. Sans barre de
        titre, c'est elle qui sert de poignée."""
        ligne = tk.Frame(parent, bg=FOND)
        ligne.pack(fill="x")
        self.etat = tk.Label(ligne, text="Kab-board", anchor="w", bg=FOND, fg=DISCRET,
                             font=self.police_petite, cursor="fleur")
        self.etat.pack(side="left", fill="x", expand=True)
        for w in (ligne, self.etat):
            w.bind("<ButtonPress-1>", self._prendre)
            w.bind("<B1-Motion>", self._glisser)
            w.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_depart", None))
        self.boutons_graphie = {}
        for valeur in ("b", "v"):
            b = self._bouton(ligne, f"Graphie {valeur}",
                             lambda v=valeur: self.noyau.changer_graphie(v))
            b.pack(side="left", padx=2)
            self.boutons_graphie[valeur] = b
        self._bouton(ligne, "✕", self.noyau.basculer_clavier).pack(side="left", padx=(6, 0))
        self.marquer_graphie(self.noyau.reglages["graphie"])

    def marquer_graphie(self, valeur):
        for v, b in self.boutons_graphie.items():
            b.configure(fg=VERT if v == valeur else TEXTE,
                        font=tkfont.Font(family="Segoe UI", size=10,
                                         weight="bold" if v == valeur else "normal"))

    def _prendre(self, e):
        self._depart = (e.x_root - self.fen.winfo_rootx(), e.y_root - self.fen.winfo_rooty())

    def _glisser(self, e):
        if self._depart:
            dx, dy = self._depart
            self.fen.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    def _bouton(self, parent, texte, action, fond=FONCTION, police=None):
        """Un bouton qui agit au relâcher, et ne prend jamais le focus."""
        b = tk.Label(parent, text=texte, bg=fond, fg=TEXTE, font=police or self.police_petite,
                     padx=8, pady=3, cursor="hand2")
        b.bind("<ButtonPress-1>", lambda _e: b.configure(bg=TOUCHE_APPUI))
        b.bind("<ButtonRelease-1>", lambda _e: (b.configure(bg=fond), action()))
        return b

    # Les outils

    def _outils(self, parent):
        ligne = tk.Frame(parent, bg=FOND)
        ligne.pack(fill="x", pady=(4, 0))
        self.bouton_dicter = None
        for libelle, action in (("Dicter", self._dicter), ("gh → ɣ", self._translit),
                                ("Asegzawal", lambda: self.fiche("")),
                                ("fr → kab", self._recherche), ("Relire", self._relire),
                                ("Mot du jour", self._mot_du_jour),
                                ("Réglages", self.noyau.ouvrir_appli), ("✕", self.fermer_panneau)):
            b = self._bouton(ligne, libelle, action)
            b.pack(side="left", fill="x", expand=True, padx=2)
            if libelle == "Dicter":
                self.bouton_dicter = b

    def _panneau(self, titre, garder_touches=False):
        """Vide le panneau. Les touches cèdent la place, sauf pour la recherche."""
        for enfant in self.panneau.winfo_children():
            enfant.destroy()
        self.recherche = None
        if garder_touches:
            self.panneau.pack_forget()
            self.touches.pack_forget()
            self.panneau.pack(fill="x")
            self.touches.pack(fill="both", expand=True)
        else:
            self.touches.pack_forget()
            self.panneau.pack(fill="both", expand=True)
        tk.Label(self.panneau, text=titre, anchor="w", bg=FOND, fg=TEXTE,
                 font=tkfont.Font(family="Segoe UI", size=11, weight="bold")).pack(fill="x")
        return self.panneau

    def fermer_panneau(self):
        for enfant in self.panneau.winfo_children():
            enfant.destroy()
        self.recherche = None
        self.panneau.pack_forget()
        self.touches.pack(fill="both", expand=True)

    def _ligne(self, texte, action=None):
        if action is None:
            tk.Label(self.panneau, text=texte, anchor="w", justify="left", bg=FOND, fg=TEXTE,
                     font=self.police_petite, wraplength=680).pack(fill="x", pady=1)
            return
        self._bouton(self.panneau, texte, action, fond=TOUCHE,
                     police=self.police_prop).pack(fill="x", pady=1)

    def _en_fond(self, travail, puis):
        """travail() dans un fil, puis puis(resultat) dans celui de l'interface."""
        def fil():
            try:
                resultat = travail()
            except Exception as erreur:
                resultat = {"erreur": str(erreur)}
            self.noyau.planifier(puis, resultat)
        threading.Thread(target=fil, daemon=True).start()

    def _translit(self):
        actif = self.noyau.basculer_translit()
        self._panneau("Écrire comme on parle", garder_touches=True)
        self._ligne("Activé : gh → ɣ, dh → ḍ, kh → x, aa → ɛ, ou → u" if actif else "Désactivé.")

    # La dictée

    def _dicter(self):
        """Un clic écoute, un second transcrit. La dictée n'est jamais corrigée d'office."""
        if self.micro is not None:
            self._fin_dictee()
            return
        self._panneau("Dictée")
        try:
            import micro
            self.micro = micro.Micro()
            self.micro.demarrer()
        except Exception as erreur:
            self.micro = None
            self._ligne(f"Le micro ne répond pas : {erreur}")
            return
        self.bouton_dicter.configure(text="● Arrêter", fg="#C62828")
        self._ligne("J'écoute… parlez en kabyle, puis cliquez sur « ● Arrêter » (30 s au plus).")
        self._surveiller_micro()

    def _surveiller_micro(self):
        if self.micro is None:
            return
        if self.micro.fini:
            self._fin_dictee()
            return
        self.etat.configure(text=f"Dictée : {self.micro.secondes:.0f} s")
        self.racine.after(250, self._surveiller_micro)

    def _fin_dictee(self):
        import micro
        enregistrement, self.micro = self.micro, None
        self.bouton_dicter.configure(text="Dicter", fg=TEXTE)
        fichier = enregistrement.arreter()
        self._panneau("Dictée")
        self._ligne("Transcription…")

        def transcrire():
            try:
                return self.noyau.service("dicter", delai=180, fichier=str(fichier))
            finally:
                micro.effacer(fichier)

        self._en_fond(transcrire, self._dictee_finie)

    def _dictee_finie(self, reponse):
        self._panneau("Dictée")
        if not reponse:
            self._ligne("Le correcteur ne répond pas : est-il allumé ?")
            return
        if reponse.get("erreur"):
            self._ligne(f"Dictée impossible : {reponse['erreur']}")
            return
        texte = (reponse.get("texte") or "").strip()
        if not texte:
            self._ligne("Rien entendu. Si Windows bloque le micro : Paramètres > "
                        "Confidentialité et sécurité > Microphone, autorisez les "
                        "applications de bureau.")
            return
        self.noyau.ecrire(texte, dictee=True)
        self._ligne(f"« {texte} »")
        self._ligne("Relire la dictée", lambda: self._relire_texte(texte, "Relire la dictée"))

    # Asegzawal, fr → kab, mot du jour

    def fiche(self, mot=""):
        mot = mot or self.noyau.frappe.mot
        self.afficher()
        self._panneau("Asegzawal")
        if not mot:
            self._ligne("Tapez un mot, puis rouvrez la fiche.")
            return
        self._en_fond(lambda: self.noyau.service("fiche", mot=mot), self._fiche_reponse)

    def _fiche_reponse(self, r):
        if not r or not r.get("mot"):
            self._ligne("Fiche indisponible : le correcteur se charge encore.")
            return
        self._ligne(f"{r['mot']}   {r.get('glose') or 'sans glose'}")
        if r.get("categorie"):
            self._ligne(f"catégorie : {r['categorie']}")
        if r.get("libre"):
            self._ligne(f"état libre : {r['libre']}", lambda f=r["libre"]: self.noyau.ecrire(f))
        if r.get("annexion"):
            self._ligne(f"état d'annexion : {r['annexion']}",
                        lambda f=r["annexion"]: self.noyau.ecrire(f))

    def _recherche(self):
        """Le champ se remplit par les touches à l'écran : sans focus, le clavier
        physique ne l'atteint pas."""
        p = self._panneau("Du français au kabyle", garder_touches=True)
        self.recherche = ""
        self.champ = tk.Label(p, text="tapez sur les touches…", anchor="w", bg=TOUCHE,
                              fg=DISCRET, font=self.police_prop, padx=6, pady=3)
        self.champ.pack(fill="x", pady=2)
        ligne = tk.Frame(p, bg=FOND)
        ligne.pack(fill="x")
        self._bouton(ligne, "Chercher", self._chercher).pack(side="left", fill="x", expand=True,
                                                             padx=2)
        self._bouton(ligne, "Effacer", lambda: self._taper_recherche(None)).pack(
            side="left", fill="x", expand=True, padx=2)
        self.resultats = tk.Frame(p, bg=FOND)
        self.resultats.pack(fill="x")

    def _taper_recherche(self, c):
        if c is None:
            self.recherche = ""
        elif c == "⌫":
            self.recherche = self.recherche[:-1]
        else:
            self.recherche += c
        self.champ.configure(text=self.recherche or "tapez sur les touches…",
                             fg=TEXTE if self.recherche else DISCRET)

    def _chercher(self):
        requete = (self.recherche or "").strip()
        if len(requete) < 2:
            return
        self._en_fond(lambda: self.noyau.service("chercher", requete=requete),
                      self._resultats_recherche)

    def _resultats_recherche(self, r):
        if self.recherche is None:
            return
        for enfant in self.resultats.winfo_children():
            enfant.destroy()
        trouves = (r or {}).get("trouves") or []
        if not trouves:
            tk.Label(self.resultats, text="Aucun résultat.", bg=FOND, anchor="w",
                     font=self.police_petite).pack(fill="x")
            return
        for forme, glose in trouves[:6]:
            self._bouton(self.resultats, f"{forme} · {glose[:60]}",
                         lambda f=forme: (self.noyau.ecrire(f + " "), self.fermer_panneau()),
                         fond=TOUCHE).pack(fill="x", pady=1)

    def _mot_du_jour(self):
        self._panneau("Mot du jour")
        self._en_fond(lambda: self.noyau.service("motdujour"), self._mot_du_jour_reponse)

    def _mot_du_jour_reponse(self, r):
        forme = (r or {}).get("forme")
        if not forme:
            self._ligne("Ressources indisponibles.")
            return
        self._ligne(forme)
        self._ligne(r.get("glose", ""))
        self._ligne("Insérer", lambda: (self.noyau.ecrire(forme + " "), self.fermer_panneau()))

    # Relire

    def _relire(self):
        """Relire le presse-papiers : aucune application ne laisse lire son texte."""
        try:
            texte = self.racine.clipboard_get()
        except tk.TclError:
            texte = ""
        if not texte.strip():
            self._panneau("Relire le presse-papiers")
            self._ligne("Copiez d'abord le texte à relire (Ctrl+C), puis cliquez « Relire ».")
            return
        self._relire_texte(texte, "Relire le presse-papiers", copier=True)

    def _relire_texte(self, texte, titre, copier=False):
        self._panneau(titre)
        self._ligne("Relecture…")
        self._en_fond(lambda: self.noyau.service("relire", delai=120, texte=texte[:20000]),
                      lambda r: self._relecture(r, texte, titre, copier))

    def _relecture(self, r, texte, titre, copier):
        self._panneau(titre)
        if not r or r.get("erreur"):
            self._ligne((r or {}).get("erreur") or "Le correcteur ne répond pas.")
            return
        signales = r.get("signales") or []
        if not signales:
            self._ligne("Rien à signaler.")
            return
        for s in signales[:8]:
            self._ligne(f"{s['mot']}  →  {'  ·  '.join(s['propositions'][:3])}")
        if len(signales) > 8:
            self._ligne(f"… et {len(signales) - 8} autre(s).")
        if copier:
            self._ligne("Copier le texte corrigé (première proposition partout)",
                        lambda: self._copier_corrige(texte, signales))

    def _copier_corrige(self, texte, signales):
        for s in sorted(signales, key=lambda s: s["debut"], reverse=True):
            texte = texte[:s["debut"]] + s["propositions"][0] + texte[s["fin"]:]
        self.racine.clipboard_clear()
        self.racine.clipboard_append(texte)
        self._panneau("Relire le presse-papiers")
        self._ligne("Le texte corrigé est dans le presse-papiers : collez-le (Ctrl+V).")

    # Les touches

    def _dessiner(self):
        for enfant in self.touches.winfo_children():
            enfant.destroy()
        for rangee in (SYMBOLES if self.symboles else RANGEES):
            ligne = tk.Frame(self.touches, bg=FOND)
            ligne.pack(fill="both", expand=True, pady=2)
            for touche in rangee:
                self._touche(ligne, touche)

    def _touche(self, ligne, touche):
        libelle = touche[0]
        fonction = libelle in FONCTIONS
        texte = {"␣": "Taqbaylit", "⇧": self.maj.libelle}.get(libelle, libelle)
        cadre = tk.Frame(ligne, bg=FONCTION if fonction else TOUCHE,
                         highlightthickness=2 if libelle in KABYLES else 0,
                         highlightbackground=VERT, cursor="hand2")
        cadre.pack(side="left", fill="both", expand=True, padx=2)
        if libelle == "␣":
            cadre.pack_configure(ipadx=60)
        etiquette = tk.Label(cadre, text=texte, bg=cadre["bg"], fg=TEXTE,
                             font=self.police_petite if fonction and libelle != "␣" else self.police,
                             pady=6)
        etiquette.pack(fill="both", expand=True)
        if len(touche) > 1:
            tk.Label(cadre, text=" ".join(touche[1:]), bg=cadre["bg"], fg=DISCRET,
                     font=self.police_variante).place(relx=1.0, x=-2, y=1, anchor="ne")
        for w in [cadre] + cadre.winfo_children():
            w.bind("<ButtonPress-1>", lambda _e, t=touche, c=cadre: self._enfoncer(t, c))
            w.bind("<ButtonRelease-1>", lambda _e, t=touche, c=cadre: self._relacher(t, c))

    def _enfoncer(self, touche, cadre):
        self._fermer_volante()
        for w in [cadre] + cadre.winfo_children():
            w.configure(bg=TOUCHE_APPUI)
        long_possible = len(touche) > 1 or touche[0] == "⌫"
        minuterie = (self.racine.after(APPUI_LONG_MS, lambda: self._appui_long(touche, cadre))
                     if long_possible else None)
        self._appui = (minuterie, touche, False)

    def _relacher(self, touche, cadre):
        fond = FONCTION if touche[0] in FONCTIONS else TOUCHE
        for w in [cadre] + cadre.winfo_children():
            w.configure(bg=fond)
        appui, self._appui = self._appui, None
        if appui is None:
            return
        minuterie, _t, long_fait = appui
        if minuterie:
            self.racine.after_cancel(minuterie)
        if not long_fait:
            self._pressee(touche)

    def _appui_long(self, touche, cadre):
        if self._appui is None:
            return
        self._appui = (None, touche, True)
        if touche[0] == "⌫":
            self.noyau.effacer_mot()
            return
        self._variantes(touche, cadre)

    def _variantes(self, touche, cadre):
        """Toutes les variantes, à choisir, et non la première d'office."""
        v = self._volante = tk.Toplevel(self.fen)
        v.overrideredirect(True)
        v.attributes("-topmost", True)
        v.configure(bg="#B8C0C8")
        for variante in touche[1:]:
            b = tk.Label(v, text=variante, bg=TOUCHE, fg=TEXTE, font=self.police, padx=10, pady=6,
                         cursor="hand2")
            b.pack(side="left", padx=1, pady=1)
            b.bind("<ButtonRelease-1>", lambda _e, c=variante: (self._fermer_volante(),
                                                                self._envoyer(c)))
        v.update_idletasks()
        if os.name == "nt":
            import win32
            win32.sans_focus(v.winfo_id())
        v.geometry(f"+{cadre.winfo_rootx()}+{cadre.winfo_rooty() - v.winfo_reqheight() - 4}")
        self.racine.after(4000, self._fermer_volante)

    def _fermer_volante(self):
        if self._volante is not None:
            try:
                self._volante.destroy()
            except tk.TclError:
                pass
            self._volante = None

    def _pressee(self, touche):
        libelle = touche[0]
        if libelle == "⇧":
            self.maj.appuyer()
            self._dessiner()
            return
        if libelle in ("123", "ABC"):
            self.symboles = not self.symboles
            self._dessiner()
            return
        if libelle == "⌫":
            if self.recherche is not None:
                self._taper_recherche("⌫")
            else:
                self.noyau.effacer()
            return
        if libelle == "␣":
            if self.recherche is not None:
                self._taper_recherche(" ")
            else:
                self.noyau.ecrire(" ")
            return
        if libelle == "⏎":
            if self.recherche is not None:
                self._chercher()
            else:
                self.noyau.ecrire("\n")
            return
        self._envoyer(libelle)

    def _envoyer(self, c):
        avant = self.maj.libelle
        c = self.maj.appliquer(c)
        if self.maj.libelle != avant:
            self._dessiner()
        if self.recherche is not None:
            self._taper_recherche(c)
            return
        self.noyau.lettre(c)

    # Les propositions

    def montrer_propositions(self, formes, nature, mot=""):
        for enfant in self.barre.winfo_children():
            enfant.destroy()
        self.etat.configure(text=f"« {mot} »" if mot else
                            f"Kab-board · graphie {self.noyau.reglages['graphie']}")
        for rang in range(6):
            forme = formes[rang] if rang < len(formes) else ""
            case = tk.Frame(self.barre, bg=TOUCHE if forme else FOND)
            case.grid(row=0, column=rang, sticky="ew", padx=2)
            mot_ = tk.Label(case, text=forme or " ", bg=case["bg"], fg=TEXTE,
                            font=self.police_prop, pady=2)
            mot_.pack(fill="x")
            tk.Frame(case, bg=couleur(nature, rang) if forme else FOND, height=3).pack(fill="x")
            if forme:
                for w in (case, mot_):
                    w.configure(cursor="hand2")
                    w.bind("<ButtonRelease-1>", lambda _e, f=forme: self.noyau.choisir_forme(f))
                    w.bind("<ButtonRelease-3>", lambda _e, f=forme: self.fiche(f))
