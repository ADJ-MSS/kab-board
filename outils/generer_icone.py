#!/usr/bin/env python3
"""Genere l'icone de kab-board a partir de l'image source."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

RACINE = Path(__file__).resolve().parents[1]
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else RACINE / "outils" / "icone" / "kab-board.jpg"
RES = Path(sys.argv[2]) if len(sys.argv) > 2 else RACINE / "app" / "src" / "main" / "res"
APERCU = Path(sys.argv[3]) if len(sys.argv) > 3 else None

DENSITES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}

# Le fond de la source est un noir texture : max RVB de 11 a 48 sur les bords
# (mesure). Sous BAS c'est du fond, au-dessus de HAUT le symbole est plein.
BAS, HAUT = 62, 120

# Icone adaptative : 108 dp de cote, dont seul le disque central de 66 dp est garanti visible quel
# que soit le masque du lanceur.
ADAPTATIVE_DP, SYMBOLE_DP = 108, 58
CLASSIQUE_DP = 48


def detourer(chemin):
    """Le symbole sur fond transparent, rogne a son emprise."""
    src = Image.open(chemin).convert("RGB")
    out = Image.new("RGBA", src.size)
    pi, po = src.load(), out.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b = pi[x, y]
            a = min(1.0, max(0.0, (max(r, g, b) - BAS) / (HAUT - BAS)))
            if a == 0.0:
                po[x, y] = (0, 0, 0, 0)
                continue
            # La source est le symbole pose sur du noir.
            po[x, y] = (min(255, round(r / a)), min(255, round(g / a)),
                        min(255, round(b / a)), round(a * 255))
    return out.crop(out.getbbox())


def reduire(im, hauteur):
    """Redimensionne en alpha premultiplie : sans cela les bords transparents se melangent au noir des pixels vides et le contour s'assombrit."""
    k = hauteur / im.height
    taille = (max(1, round(im.width * k)), max(1, round(hauteur)))
    return im.convert("RGBa").resize(taille, Image.LANCZOS).convert("RGBA")


def centrer(sym, cote):
    toile = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    toile.alpha_composite(sym, ((cote - sym.width) // 2, (cote - sym.height) // 2))
    return toile


def silhouette(sym):
    """Le symbole en blanc plein. Une fermeture morphologique bouche les fines rayures du motif, qui trouent la silhouette sinon."""
    a = sym.getchannel("A").point(lambda v: 255 if v > 64 else 0)
    a = a.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    blanc = Image.new("RGBA", sym.size, (255, 255, 255, 0))
    blanc.putalpha(a)
    return blanc


def classique(sym, cote, rond):
    """Icone d'Android 7 : fond noir carre arrondi ou rond, symbole au centre."""
    toile = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    masque = Image.new("L", (cote, cote), 0)
    d = ImageDraw.Draw(masque)
    if rond:
        d.ellipse((0, 0, cote - 1, cote - 1), fill=255)
    else:
        d.rounded_rectangle((0, 0, cote - 1, cote - 1), radius=round(cote * 0.18), fill=255)
    toile.paste((0, 0, 0, 255), (0, 0, cote, cote), masque)
    # Dans le rond, le symbole doit tenir dans le disque : 75 % de la hauteur.
    return Image.alpha_composite(toile, centrer(reduire(sym, cote * (0.75 if rond else 0.80)), cote))


ADAPTATIVE_XML = """<?xml version="1.0" encoding="utf-8"?>
<!-- Genere par outils/generer_icone.py : ne pas modifier a la main. -->
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@android:color/black" />
    <foreground android:drawable="@mipmap/ic_launcher_premier_plan" />
    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />
</adaptive-icon>
"""


def main():
    sym = detourer(SOURCE)
    print(f"symbole detoure : {sym.width} x {sym.height} px")
    muet = silhouette(sym)
    for nom, d in DENSITES.items():
        dossier = RES / f"mipmap-{nom}"
        dossier.mkdir(parents=True, exist_ok=True)
        cote, haut = round(ADAPTATIVE_DP * d), SYMBOLE_DP * d
        centrer(reduire(sym, haut), cote).save(dossier / "ic_launcher_premier_plan.png", optimize=True)
        centrer(reduire(muet, haut), cote).save(dossier / "ic_launcher_monochrome.png", optimize=True)
        c = round(CLASSIQUE_DP * d)
        classique(sym, c, rond=False).save(dossier / "ic_launcher.png", optimize=True)
        classique(sym, c, rond=True).save(dossier / "ic_launcher_round.png", optimize=True)
    v26 = RES / "mipmap-anydpi-v26"
    v26.mkdir(parents=True, exist_ok=True)
    for nom in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (v26 / nom).write_text(ADAPTATIVE_XML, encoding="utf-8")
    print(f"ecrit dans {RES}")

    if APERCU:
        # Ce que montreront les lanceurs : l'adaptative sous un masque rond et un
        # masque carre arrondi, l'icone a theme, et les deux classiques.
        n = 240
        fond = Image.open(RES / "mipmap-xxxhdpi" / "ic_launcher_premier_plan.png").resize((n, n), Image.LANCZOS)
        muette = Image.open(RES / "mipmap-xxxhdpi" / "ic_launcher_monochrome.png").resize((n, n), Image.LANCZOS)
        feuille = Image.new("RGBA", (6 * (n + 20) + 20, n + 40), (236, 239, 241, 255))
        def masque(forme):
            m = Image.new("L", (n, n), 0); dr = ImageDraw.Draw(m)
            # le lanceur montre les 72 dp centraux des 108
            b = round(n * 18 / 108); boite = (b, b, n - b, n - b)
            if forme == "rond": dr.ellipse(boite, fill=255)
            else: dr.rounded_rectangle(boite, radius=round(n * 0.16), fill=255)
            return m
        for i, forme in enumerate(("rond", "carre")):
            t = Image.new("RGBA", (n, n), (0, 0, 0, 255)); t.alpha_composite(fond)
            case = Image.new("RGBA", (n, n), (0, 0, 0, 0)); case.paste(t, (0, 0), masque(forme))
            feuille.alpha_composite(case, (20 + i * (n + 20), 20))
        theme = Image.new("RGBA", (n, n), (208, 188, 255, 255))
        teinte = Image.new("RGBA", (n, n), (56, 30, 114, 255)); teinte.putalpha(muette.getchannel("A"))
        theme.alpha_composite(teinte)
        case = Image.new("RGBA", (n, n), (0, 0, 0, 0)); case.paste(theme, (0, 0), masque("rond"))
        feuille.alpha_composite(case, (20 + 2 * (n + 20), 20))
        for i, nom in enumerate(("ic_launcher.png", "ic_launcher_round.png")):
            feuille.alpha_composite(Image.open(RES / "mipmap-xxxhdpi" / nom).resize((n, n), Image.LANCZOS), (20 + (3 + i) * (n + 20), 20))
        src = Image.open(SOURCE).convert("RGBA"); src.thumbnail((n, n))
        feuille.alpha_composite(src, (20 + 5 * (n + 20) + (n - src.width) // 2, 20))
        feuille.save(APERCU)
        print(f"apercu : {APERCU}")


if __name__ == "__main__":
    main()
