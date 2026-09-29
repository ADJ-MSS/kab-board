"""Vérifications de la couche des graphies : python3 test_graphie_bv.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graphie_bv import GraphieBV, DEUX, B, V, Choix

TABLE = (Path(__file__).resolve().parent.parent
         / "app" / "src" / "main" / "assets" / "graphie" / "table_bv.tsv")
g = GraphieBV.charger(TABLE)
ok = 0
rates = []


def verifie(intitule, obtenu, attendu):
    global ok
    if obtenu == attendu:
        ok += 1
    else:
        rates.append(f"{intitule}\n    attendu : {attendu!r}\n    obtenu  : {obtenu!r}")


# la table elle-même
verifie("table chargée", len(g.vers_v) > 12000, True)
verifie("paire de la liste", g.variantes("abrid"), ["abrid", "avrid"])
verifie("paire propagée", g.variantes("neḍleb"), ["neḍleb", "neḍlev"])
verifie("entrée en v reconnue", g.variantes("avrid"), ["avrid", "abrid"])
verifie("lemme conservé", g.lemmes.get("neḍleb"), "ḍleb")

# un mot qui n'alterne pas
verifie("mot hors table intact", g.variantes("axxam"), ["axxam"])
verifie("mot hors table, mode V", g.variantes("axxam", V), ["axxam"])
verifie("mot sans b ni v", g.alterne("tameṭṭut"), False)

# les modes
verifie("mode B", g.variantes("avrid", B), ["abrid"])
verifie("mode V", g.variantes("abrid", V), ["avrid"])
verifie("bascule", g.basculer("abrid", V), "avrid")
verifie("bascule sans effet", g.basculer("axxam", V), "axxam")

# la casse
verifie("majuscule initiale", g.variantes("Abrid"), ["Abrid", "Avrid"])
verifie("tout en capitales", g.variantes("ABRID"), ["ABRID", "AVRID"])
verifie("capitales, mode V", g.basculer("Abrid", V), "Avrid")

# les candidats du correcteur
cands = [{"candidat": "abrid", "distance": 1, "score": 2.5, "source": "lexique"},
         {"candidat": "axxam", "distance": 2, "score": 1.0, "source": "lexique"}]
avant = [dict(c) for c in cands]
sortie = g.enrichir_candidats(cands)
verifie("entrée non modifiée", cands, avant)
verifie("variante insérée", [c["candidat"] for c in sortie],
        ["abrid", "avrid", "axxam"])
verifie("champs conservés", sortie[1]["score"], 2.5)
verifie("variante marquée", sortie[1]["variante_de"], "abrid")
verifie("mot hors table non marqué", "graphie" in sortie[2], False)
verifie("mot alternant marqué", sortie[0]["graphie"], "b")
verifie("variante marquée v", sortie[1]["graphie"], "v")
verifie("candidats en mode B", [c["candidat"] for c in g.enrichir_candidats(cands, B)],
        ["abrid", "axxam"])
verifie("pas de doublon", len(g.enrichir_candidats(
    [{"candidat": "abrid"}, {"candidat": "avrid"}])), 2)

# un texte entier
s = g.enrichir_texte("ruḥeɣ ɣer webrid")
verifie("texte inchangé en mode DEUX", s.texte, "ruḥeɣ ɣer webrid")
verifie("un choix relevé", [(c.index, c.forme_b, c.forme_v) for c in s.choix],
        [(2, "webrid", "wevrid")])
verifie("texte réécrit en mode V", g.enrichir_texte("ruḥeɣ ɣer webrid", V).texte,
        "ruḥeɣ ɣer wevrid")
verifie("ponctuation préservée", g.enrichir_texte("yusa-d webrid.", V).texte,
        "yusa-d wevrid.")
verifie("aucun choix en mode B", g.enrichir_texte("webrid", B).choix, [])


# les formes fléchies, que la table ne liste pas
# Mesuré le 28/09/2026 : la liste donne « ubrid » et « webrid » mais pas
# « wabrid », ni aucun mot à tiret. Les règles comblent, sans les inventer.
verifie("annexion wa- absente de la table", "wabrid" in g.vers_v, False)
verifie("annexion wa- basculée", g.basculer("wabrid", V), "wavrid")
verifie("annexion u- d'un mot non listé", g.basculer("uɣbalu", V), "uɣvalu")
verifie("annexion we- non listée", g.basculer("weqbu", V), "weqvu")
verifie("annexion t- du féminin", g.basculer("tbadut", V), "tvadut")
verifie("annexion yi-", g.basculer("yiɣbu", V), "yiɣvu")
verifie("pluriel du singulier listé", g.basculer("iɣriben", V), "iɣriven")
verifie("pluriel en -an", g.basculer("ibridan", V), "ivridan")
verifie("retour à la graphie b", g.basculer("uvrid", B), "ubrid")

# les mots à tirets
verifie("possessif accroché", g.basculer("baba-s", V), "vava-s")
verifie("nom annexé et possessif", g.basculer("abrid-is", V), "avrid-is")
verifie("verbe et particule -d", g.basculer("yettban-d", V), "yettvan-d")
verifie("particule en tête", g.basculer("d-nebder", V), "d-nevder")
verifie("segment seul qui alterne", g.basculer("aqrab-nni", V), "aqrav-nni")
verifie("tiret, retour en b", g.basculer("vava-k", B), "baba-k")
verifie("casse d'un mot à tirets", g.basculer("Baba-s", V), "Vava-s")
verifie("capitales d'un mot à tirets", g.basculer("BABA-S", V), "VAVA-S")
verifie("aucun segment n'alterne", g.basculer("yusa-d", V), "yusa-d")

# ce qui ne doit surtout pas basculer
# Des emprunts fréquents que la liste écarte : leur b ne se spirantise pas.
for mot in ("belli", "ṛebbi", "mebla", "beṛa", "ṣebba", "boston"):
    verifie(f"{mot} reste en b", g.basculer(mot, V), mot)
verifie("mot court sans rapport", g.basculer("ib", V), "ib")
verifie("texte mêlé recomposé", g.enrichir_texte("baba-s yettban-d deg ubrid", V).texte,
        "vava-s yettvan-d deg uvrid")
verifie("belli dans un texte", g.enrichir_texte("yenna-d belli ubrid", V).texte,
        "yenna-d belli uvrid")

class FauxResultat:
    texte_corrige = "abrid"
    nb_corrections = 1


verifie("ResultatV2 accepté", g.enrichir_resultat(FauxResultat()).texte, "abrid")
verifie("ResultatV2 non modifié", FauxResultat.texte_corrige, "abrid")

print(f"{ok} vérifications passées, {len(rates)} échec(s)")
for r in rates:
    print("  ÉCHEC " + r)
sys.exit(1 if rates else 0)
