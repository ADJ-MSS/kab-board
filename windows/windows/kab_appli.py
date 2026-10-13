#!/usr/bin/env python3
"""Kab-board : l'application.

Comme sous Linux : deux interrupteurs, le clavier kabyle et le clavier à
l'écran, puis la graphie b ou v et « écrire comme on parle ». S'y ajoutent ce
qui est propre à Windows : la barre sous le curseur, les chiffres qui
choisissent, et le démarrage avec Windows. L'état va dans reglages.json, que le
clavier relit aussitôt.

    pythonw windows/kab_appli.py [--allumer]
"""
import os
import sys
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

WINDOWS = os.name == "nt"
TITRE = "Kab-board"
CLE_DEMARRAGE = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOM_DEMARRAGE = "Kab-board"
VERT, DISCRET = "#00843F", "#5F6B76"


def commande_demarrage() -> str:
    """Ce que Windows lance à l'ouverture de session : le clavier seul, sans
    cette fenêtre."""
    exe = lieux.RACINE / "Kab-board.exe"
    if exe.exists():
        return f'"{exe}" --clavier'
    return f'"{lieux.python_sans_console()}" "{lieux.ICI / "kab_saisie.py"}"'


def demarrage_actif() -> bool:
    if not WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_DEMARRAGE) as cle:
            valeur, _ = winreg.QueryValueEx(cle, NOM_DEMARRAGE)
            return bool(valeur)
    except OSError:
        return False


def changer_demarrage(actif: bool):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLE_DEMARRAGE) as cle:
        if actif:
            winreg.SetValueEx(cle, NOM_DEMARRAGE, 0, winreg.REG_SZ, commande_demarrage())
        else:
            try:
                winreg.DeleteValue(cle, NOM_DEMARRAGE)
            except OSError:
                pass


class Fenetre:

    def __init__(self, racine):
        self.racine = racine
        self.reglages = R.lire()
        self.saisie = liaison.Client("saisie", 1.0)
        self.maj_en_cours = False
        racine.title(TITRE)
        racine.minsize(480, 0)
        icone = lieux.RACINE / "lanceur" / "kab-board.ico"
        if WINDOWS and icone.exists():
            try:
                racine.iconbitmap(default=str(icone))
            except tk.TclError:
                pass
        self.titre_police = tkfont.Font(family="Segoe UI", size=12, weight="bold")
        self.police = tkfont.Font(family="Segoe UI", size=10)
        self.petite = tkfont.Font(family="Segoe UI", size=9)
        style = ttk.Style()
        style.configure("TCheckbutton", font=self.police)
        style.configure("TRadiobutton", font=self.police)

        page = ttk.Frame(racine, padding=18)
        page.pack(fill="both", expand=True)
        # Deux colonnes : la fenêtre tient sur un écran de 768 pixels de haut.
        colonnes = ttk.Frame(page)
        colonnes.pack(fill="both", expand=True)
        gauche = ttk.Frame(colonnes)
        gauche.grid(row=0, column=0, sticky="nw", padx=(0, 28))
        droite = ttk.Frame(colonnes)
        droite.grid(row=0, column=1, sticky="nw")

        self._titre(gauche, "Le clavier")
        self.v_clavier = tk.BooleanVar()
        self._interrupteur(gauche, self.v_clavier, "Clavier kabyle",
                           "Corrige et propose dans toutes les applications : vous tapez "
                           "sur votre clavier, comme d'habitude.",
                           self._basculer_clavier)
        self.v_ecran = tk.BooleanVar(value=self.reglages.get("clavier_ecran", False))
        self._interrupteur(gauche, self.v_ecran, "Clavier à l'écran",
                           "Si vous le voulez : des touches à cliquer, posées au-dessus des "
                           "autres fenêtres.",
                           self._basculer_ecran)

        self._titre(gauche, "Au démarrage")
        self.v_demarrage = tk.BooleanVar(value=demarrage_actif())
        detail = "Le clavier sera prêt sans ouvrir cette fenêtre."
        inter = self._interrupteur(gauche, self.v_demarrage, "Démarrer avec Windows", detail,
                                   self._basculer_demarrage)
        if not WINDOWS:
            inter.state(["disabled"])

        self._titre(droite, "L'écriture")
        ligne = ttk.Frame(droite)
        ligne.pack(fill="x", pady=(0, 2))
        self.v_graphie = tk.StringVar(value=self.reglages["graphie"])
        for valeur, texte in (("v", "Écrire avec v"), ("b", "Écrire avec b")):
            ttk.Radiobutton(ligne, text=texte, value=valeur, variable=self.v_graphie,
                            command=self._changer_graphie).pack(side="left", padx=(0, 16))
        self._petit(droite, "Certains écrivent abrid, d'autres avrid. Le réglage vaut pour "
                            "les six propositions, la prédiction, la fiche et la dictée, et "
                            "pour Kab-board pour Word.")
        self.v_translit = tk.BooleanVar(value=self.reglages["translitteration"])
        self._interrupteur(droite, self.v_translit, "Écrire comme on parle",
                           "gh donne ɣ, dh donne ḍ, kh donne x, aa donne ɛ, ou donne u. "
                           "AltGr + g, e, d, h, t, z, s, c, j, r donne ɣ ɛ ḍ ḥ ṭ ẓ ṣ č ǧ ṛ.",
                           lambda: self._reglage("translitteration", self.v_translit.get()))
        self.v_barre = tk.BooleanVar(value=self.reglages.get("barre", True))
        self._interrupteur(droite, self.v_barre, "La barre sous le curseur",
                           "Les six propositions du mot en cours, juste sous lui.",
                           lambda: self._reglage("barre", self.v_barre.get()))
        self.v_chiffres = tk.BooleanVar(value=self.reglages.get("chiffres", True))
        self._interrupteur(droite, self.v_chiffres, "Les chiffres 1 à 6 choisissent",
                           "Pendant qu'un mot s'écrit, 1 écrit la première proposition, 2 la "
                           "deuxième… En AZERTY, avec Maj, comme pour tout chiffre, ou "
                           "avec le pavé numérique. Rien n'est corrigé d'office.",
                           lambda: self._reglage("chiffres", self.v_chiffres.get()))

        boutons = ttk.Frame(page)
        boutons.pack(fill="x", pady=(14, 0))
        ttk.Button(boutons, text="Écrire et relire",
                   command=lambda: processus.lancer("kab_bureau.py")).pack(side="left")
        ttk.Button(boutons, text="Mon dictionnaire",
                   command=self._mon_dictionnaire).pack(side="left", padx=8)

        self.etat = tk.Label(page, text="", anchor="w", justify="left", fg=DISCRET,
                             font=self.petite, wraplength=760)
        self.etat.pack(fill="x", pady=(14, 0))

        self._relever()
        ecran.tenir(racine)

    # Fabrique

    def _titre(self, page, texte):
        tk.Label(page, text=texte, anchor="w", font=self.titre_police).pack(
            fill="x", pady=(10, 4))

    def _petit(self, page, texte, largeur=360):
        tk.Label(page, text=texte, anchor="w", justify="left", fg=DISCRET, font=self.petite,
                 wraplength=largeur).pack(fill="x", pady=(0, 6))

    def _interrupteur(self, page, variable, titre, detail, rappel):
        bouton = ttk.Checkbutton(page, text=titre, variable=variable,
                                 command=lambda: None if self.maj_en_cours else rappel())
        bouton.pack(fill="x", anchor="w")
        tk.Label(page, text=detail, anchor="w", justify="left", fg=DISCRET, font=self.petite,
                 wraplength=340).pack(fill="x", padx=(22, 0), pady=(0, 6))
        return bouton

    # Les bascules

    def _clavier_allume(self) -> bool:
        return self.saisie.appeler("etat") is not None

    def _basculer_clavier(self):
        if self.v_clavier.get():
            processus.lancer("kab_saisie.py")
            self._dire("Démarrage du clavier… le correcteur se prépare en quelques secondes.")
        else:
            self._eteindre()

    def _eteindre(self):
        """Arrête le clavier. Les touches repartent telles quelles dans les applications."""
        fiche = liaison.lire_fiche("saisie")
        if self.saisie.appeler("quitter") is None and fiche:
            processus.terminer(int(fiche.get("pid", 0)))
        self._dire("Clavier arrêté.")

    def _basculer_ecran(self):
        montrer = self.v_ecran.get()
        self.reglages = R.changer(clavier_ecran=montrer)
        if self.saisie.appeler("clavier", montrer=montrer) is None and montrer:
            processus.lancer("kab_saisie.py")
            self.v_clavier.set(True)

    def _changer_graphie(self):
        self._reglage("graphie", self.v_graphie.get())

    def _reglage(self, cle, valeur):
        self.reglages = R.changer(**{cle: valeur})
        self.saisie.appeler("reglages")

    def _basculer_demarrage(self):
        try:
            changer_demarrage(self.v_demarrage.get())
        except OSError as erreur:
            self._dire(f"Impossible de régler le démarrage : {erreur}")

    def _mon_dictionnaire(self):
        """Les mots que la relecture ne signale plus : un fichier texte à vous,
        le même que celui de Kab-board pour Word."""
        lieux.MES_MOTS.parent.mkdir(parents=True, exist_ok=True)
        if not lieux.MES_MOTS.exists():
            lieux.MES_MOTS.write_text("", encoding="utf-8")
        if WINDOWS:
            os.startfile(str(lieux.MES_MOTS))       # noqa: S606 (le Bloc-notes, rien d'autre)
        else:
            self._dire(str(lieux.MES_MOTS))

    # L'état

    def _relever(self):
        etat = self.saisie.appeler("etat")
        self.maj_en_cours = True
        self.v_clavier.set(etat is not None)
        if etat is not None:
            self.v_ecran.set(bool(etat.get("clavier")))
        self.maj_en_cours = False
        if etat is None:
            self._dire("Clavier arrêté.")
        else:
            service = etat.get("service") or {}
            if not etat.get("crochet", True):
                self._dire("Windows a refusé le clavier kabyle : redémarrez Kab-board.")
            elif service.get("erreur"):
                self._dire(f"Correcteur indisponible : {service['erreur']}")
            elif not service.get("pret"):
                depuis = service.get("depuis")
                self._dire("Clavier allumé. Le correcteur se prépare"
                           + (f" ({depuis:.0f} s)…" if depuis else "…")
                           + " La frappe fonctionne déjà, sans propositions.")
            elif etat.get("mot"):
                self._dire(f"Clavier actif. Mot en cours : « {etat['mot']} »")
            else:
                self._dire("Clavier actif, prêt à écrire dans toutes les applications.")
        self.racine.after(2000, self._relever)

    def _dire(self, message):
        self.etat.configure(text=message)


def principal(argv) -> int:
    if not processus.instance_unique("appli"):
        if WINDOWS:
            import win32
            win32.montrer_fenetre(TITRE)
        return 0
    processus.journal("appli")
    if WINDOWS:
        import win32
        win32.net_sur_tous_les_ecrans()
    racine = tk.Tk()
    fenetre = Fenetre(racine)
    if "--allumer" in argv and not fenetre._clavier_allume():
        # Ouvrir Kab-board allume le clavier.
        processus.lancer("kab_saisie.py")
        fenetre.v_clavier.set(True)
        fenetre._dire("Démarrage du clavier… le correcteur se prépare en quelques secondes.")
    racine.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
