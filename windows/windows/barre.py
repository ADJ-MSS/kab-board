"""La barre des six propositions, posée sous le curseur de texte.

Sous Linux, IBus affiche sa liste près du mot. Ici, c'est une petite fenêtre
toujours au-dessus des autres, qui ne prend jamais le focus : on clique une
proposition et le curseur reste dans l'application où l'on écrit. Elle suit le
curseur d'une application à l'autre ; quand une application ne dit pas où il
est, elle se pose en bas de l'écran.

Les couleurs sont celles du téléphone : vert pour la correction en contexte,
bleu pour un candidat, ocre pour une prédiction. Le chiffre devant chaque forme
est la touche qui la choisit.
"""
import os
import tkinter as tk
import tkinter.font as tkfont

from disposition import couleur

FOND, BORD, DISCRET, TEXTE = "#FFFFFF", "#C8C8C8", "#8A8A8A", "#1E1E1E"
SURVOL = "#EEF4FA"


class Barre:

    def __init__(self, racine, choisir, fiche):
        self.racine = racine
        self.choisir = choisir              # (forme) -> None
        self.fiche = fiche                  # (forme) -> None, au clic droit
        self.fen = tk.Toplevel(racine)
        self.fen.withdraw()
        self.fen.overrideredirect(True)
        self.fen.attributes("-topmost", True)
        self.fen.configure(bg=BORD)
        self.cadre = tk.Frame(self.fen, bg=FOND)
        self.cadre.pack(padx=1, pady=1)
        self.police = tkfont.Font(family="Segoe UI", size=12)
        self.police_chiffre = tkfont.Font(family="Segoe UI", size=8)
        self.affiche = None                 # (formes, nature) à l'écran
        self.hwnd = None
        self.visible = False

    def _sans_focus(self):
        if self.hwnd is None and os.name == "nt":
            import win32
            self.fen.update_idletasks()
            self.hwnd = win32.sans_focus(self.fen.winfo_id())

    def _remplir(self, formes, nature):
        for enfant in self.cadre.winfo_children():
            enfant.destroy()
        for rang, forme in enumerate(formes):
            case = tk.Frame(self.cadre, bg=FOND, cursor="hand2")
            case.grid(row=0, column=rang, padx=(4 if rang == 0 else 0, 4), pady=3)
            chiffre = tk.Label(case, text=str(rang + 1), font=self.police_chiffre,
                               fg=DISCRET, bg=FOND)
            chiffre.grid(row=0, column=0, sticky="n", padx=(2, 1))
            mot = tk.Label(case, text=forme, font=self.police, fg=TEXTE, bg=FOND, padx=3)
            mot.grid(row=0, column=1)
            trait = tk.Frame(case, bg=couleur(nature, rang), height=3)
            trait.grid(row=1, column=0, columnspan=2, sticky="ew")
            for w in (case, chiffre, mot):
                w.bind("<ButtonRelease-1>", lambda _e, f=forme: self.choisir(f))
                w.bind("<ButtonRelease-3>", lambda _e, f=forme: self.fiche(f))
                w.bind("<Enter>", lambda _e, c=(case, chiffre, mot): self._survol(c, SURVOL))
                w.bind("<Leave>", lambda _e, c=(case, chiffre, mot): self._survol(c, FOND))

    @staticmethod
    def _survol(widgets, fond):
        for w in widgets:
            w.configure(bg=fond)

    def montrer(self, formes, nature, ancre):
        """ancre : (x, y, hauteur) du curseur, ou un point (x, y, 0) où se poser."""
        if not formes:
            self.cacher()
            return
        if self.affiche != (tuple(formes), nature):
            self._remplir(formes, nature)
            self.affiche = (tuple(formes), nature)
        self.placer(ancre)
        if not self.visible:
            self._sans_focus()
            self.fen.deiconify()
            self.fen.attributes("-topmost", True)
            self.visible = True

    def placer(self, ancre):
        self.fen.update_idletasks()
        largeur, hauteur = self.fen.winfo_reqwidth(), self.fen.winfo_reqheight()
        x, y, h = ancre
        gauche, haut, droite, bas = _zone(x, y, self.fen)
        px = min(max(x - 8, gauche), droite - largeur)
        py = y + h + 6
        if py + hauteur > bas:                   # pas la place dessous : au-dessus
            py = y - hauteur - 6
        py = min(max(py, haut), bas - hauteur)
        self.fen.geometry(f"+{int(px)}+{int(py)}")

    def cacher(self):
        if self.visible:
            self.fen.withdraw()
            self.visible = False

    def contient(self, x, y) -> bool:
        if not self.visible:
            return False
        fx, fy = self.fen.winfo_rootx(), self.fen.winfo_rooty()
        return fx <= x < fx + self.fen.winfo_width() and fy <= y < fy + self.fen.winfo_height()


def _zone(x, y, fen):
    if os.name == "nt":
        import win32
        return win32.zone_de_travail(int(x), int(y))
    return 0, 0, fen.winfo_screenwidth(), fen.winfo_screenheight()
