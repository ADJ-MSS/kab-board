"""Une fenêtre tient dans l'écran : rien ne passe sous la barre des tâches.

Un portable en 1366 × 768 n'a que 720 pixels au-dessus de la barre des tâches :
une fenêtre plus haute y cache ses derniers boutons.
"""
import os

WINDOWS = os.name == "nt"
CADRE = 40            # la barre de titre et les bords que Windows ajoute


def zone(fenetre):
    """Le rectangle utile (gauche, haut, droite, bas) de l'écran de la fenêtre."""
    if WINDOWS:
        import win32
        x = fenetre.winfo_pointerx() if fenetre.winfo_ismapped() else 0
        y = fenetre.winfo_pointery() if fenetre.winfo_ismapped() else 0
        return win32.zone_de_travail(x, y)
    return 0, 0, fenetre.winfo_screenwidth(), fenetre.winfo_screenheight()


def tenir(fenetre, largeur=None, hauteur=None):
    """Taille voulue (ou demandée par le contenu), ramenée à l'écran, et centrée
    dans sa partie utile. Rend la hauteur retenue."""
    fenetre.update_idletasks()
    g, h, d, b = zone(fenetre)
    largeur = min(largeur or fenetre.winfo_reqwidth(), d - g - 16)
    hauteur = min(hauteur or fenetre.winfo_reqheight(), b - h - CADRE)
    x = g + max(0, (d - g - largeur) // 2)
    y = h + max(0, (b - h - CADRE - hauteur) // 2)
    fenetre.geometry(f"{largeur}x{hauteur}+{x}+{y}")
    return hauteur
