"""Vérifications de la saisie, hors session IBus.

    python3 test_saisie.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from saisie import longueur_mots_avant, Saisie, est_lettre, choix_par_chiffre, graphie_reglee

ok, rates = 0, []


def verifie(intitule, obtenu, attendu):
    global ok
    if obtenu == attendu:
        ok += 1
    else:
        rates.append(f"{intitule}\n    attendu : {attendu!r}\n    obtenu  : {obtenu!r}")


def taper(mot, **kw):
    s = Saisie(**kw)
    for c in mot:
        s.lettre(c)
    return s


# les lettres kabyles sur un clavier physique
verifie("gh donne ɣ", taper("ruhagh").tampon, "ruhaɣ")
verifie("dh donne ḍ", taper("adhar").tampon, "aḍar")
verifie("kh donne x", taper("khedmegh").tampon, "xedmeɣ")
verifie("aa donne ɛ", taper("laada").tampon, "lɛda")
verifie("ou donne u", taper("aourar").tampon, "aurar")
verifie("la casse suit", taper("Ghef").tampon, "Ɣef")

s = Saisie()
for c, a in [("r", False), ("u", False), ("h", False), ("e", False), ("g", True)]:
    s.lettre(c, altgr=a)
verifie("AltGr+g donne ɣ", s.tampon, "ruheɣ")

# la conversion se défait
s = taper("gh")
verifie("conversion faite", s.tampon, "ɣ")
s.effacer()
verifie("effacement immédiat la défait", s.tampon, "gh")
s.effacer()
verifie("l'effacement suivant efface vraiment", s.tampon, "g")

# sans la translittération
verifie("réglage coupé", taper("ruhagh", translitteration=False).tampon, "ruhagh")

# le mot en cours
s = taper("abrid")
verifie("mot en cours", s.tampon, "abrid")
verifie("vider rend le mot", s.vider(), "abrid")
verifie("puis le tampon est vide", s.vide, True)
verifie("effacer sur du vide rend False", Saisie().effacer(), False)

# ce qui est une lettre
verifie("ɣ est une lettre", est_lettre("ɣ"), True)
verifie("le trait d'union aussi", est_lettre("-"), True)
verifie("l'espace non", est_lettre(" "), False)
verifie("le point non", est_lettre("."), False)

# le choix par chiffre
props = ["ruḥeɣ", "ruḥ", "ruḥeɣt"]
verifie("touche 1", choix_par_chiffre(1, props), "ruḥeɣ")
verifie("touche 3", choix_par_chiffre(3, props), "ruḥeɣt")
verifie("touche 5 sans candidat", choix_par_chiffre(5, props), None)

# La graphie de depart
verifie("sans reglage, le v", graphie_reglee({}), "v")
verifie("fichier absent, le v", graphie_reglee(None), "v")
verifie("b seulement s'il est choisi", graphie_reglee({"graphie": "b"}), "b")
verifie("v quand il est choisi", graphie_reglee({"graphie": "v"}), "v")
verifie("valeur abimee, le v", graphie_reglee({"graphie": "n'importe quoi"}), "v")
verifie("autre reglage sans effet", graphie_reglee({"translitteration": False}), "v")

# Le mot d'avant que rattache un possessif : « tamurt iw » → « tamurt-iw »
verifie("le mot d'avant et son espace", longueur_mots_avant("tamurt ", 1), 7)
verifie("au milieu d'une phrase", longueur_mots_avant("ruḥeɣ ɣer tamurt ", 1), 7)
verifie("plusieurs blancs", longueur_mots_avant("tamurt  ", 1), 8)
verifie("deux mots", longueur_mots_avant("ruḥeɣ ɣer axxam nneɣ ", 2), len("axxam nneɣ "))
verifie("sans blanc, pas de fusion", longueur_mots_avant("tamurt", 1), -1)
verifie("une virgule l'interdit", longueur_mots_avant("tamurt, ", 1), -1)
verifie("pas assez de mots", longueur_mots_avant("tamurt ", 2), -1)
verifie("texte vide", longueur_mots_avant("", 1), -1)

print(f"{ok} vérifications passées, {len(rates)} échec(s)")
for r in rates:
    print("  ÉCHEC " + r)
sys.exit(1 if rates else 0)
