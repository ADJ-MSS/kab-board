"""Le service du correcteur, avec un correcteur miniature à la place du vrai.

Le vrai pèse 600 Mo : il est vérifié à part, sur Windows, dans le paquet
(paquet/verifier.py). Ici, on vérifie ce que le service en fait : la casse, la
graphie b ou v, le possessif rattaché, la virgule, la complétion, la relecture.
"""
import re
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace

import commun  # noqa: F401
import lieux
import service


class Resultat:
    def __init__(self, texte, couverture=1):
        self.texte_corrige = texte
        self.couverture_fin = couverture


class FauxCorrecteur:
    """Corrige d'après une table ; rattache « iw » au mot d'avant, comme le vrai,
    sans voir la ponctuation, comme le vrai."""

    CORRECTIONS = {"ruhagh": "ruḥeɣ", "ghar": "ɣer", "tamettut": "tameṭṭut",
                   "abrid": "abrid", "avrid": "abrid"}
    CANDIDATS = {"ruhagh": ["ruḥeɣ", "ruḥ", "ruḥeɣt"], "abrid": ["abrid", "abrid-is"],
                 "tamettut": ["tameṭṭut"], "iw": ["iw", "is"]}

    def __init__(self):
        self.res = SimpleNamespace(kenlm=None)

    def corriger(self, texte):
        jetons = re.findall(r"[\wɣɛḍḥṭẓṣǧčṛ\-]+", texte.lower())
        if len(jetons) >= 2 and jetons[-1] == "iw":
            return Resultat(" ".join(jetons[:-2] + [jetons[-2] + "-iw"]), 2)
        return Resultat(" ".join(jetons[:-1] + [self.CORRECTIONS.get(jetons[-1], jetons[-1])]))

    def top_candidats(self, mot, nb=5):
        return [{"candidat": c} for c in self.CANDIDATS.get(mot.lower(), [])][:nb]


class FausseCompletion:
    def barre(self, contexte, tape):
        from completion import cede_a_la_correction       # la règle de kab-board
        if cede_a_la_correction(contexte, tape):
            return None
        if tape == "ta":
            return ["tamurt", "tameṭṭut", "tabrat"]
        if tape == "iw":
            return ["iw", "iwakken", "iwumi"]
        return None


def moteur_de_test(completion=None):
    m = service.Moteur()
    m.charger_graphie()
    m.correcteur = FauxCorrecteur()
    m.completion = completion
    m.pret.set()
    return m


class LesPropositions(unittest.TestCase):

    def setUp(self):
        self.m = moteur_de_test()

    def test_correction_en_tete_puis_candidats(self):
        r = self.m.proposer("", "ruhagh", "v")
        self.assertEqual(r, {"nature": "prop", "formes": ["ruḥeɣ", "ruḥ", "ruḥeɣt"],
                             "mots_avant": 0})

    def test_la_casse_du_mot_tape(self):
        self.assertEqual(self.m.proposer("", "Ruhagh", "v")["formes"][0], "Ruḥeɣ")
        self.assertEqual(self.m.proposer("", "RUHAGH", "v")["formes"][0], "RUḤEƔ")

    def test_graphie_b_ou_v(self):
        self.assertEqual(self.m.proposer("", "abrid", "v")["formes"], ["avrid", "avrid-is"])
        self.assertEqual(self.m.proposer("", "abrid", "b")["formes"], ["abrid", "abrid-is"])

    def test_possessif_rattache(self):
        r = self.m.proposer("ruḥeɣ ɣer tamurt ", "iw", "v")
        self.assertEqual(r["formes"][0], "tamurt-iw")
        self.assertEqual(r["mots_avant"], 1)
        self.assertEqual(self.m.proposer("Tamurt ", "iw", "v")["formes"][0], "Tamurt-iw")

    def test_jamais_par_dessus_une_virgule(self):
        r = self.m.proposer("tamurt, ", "iw", "v")
        self.assertEqual(r["formes"][0], "iw")
        self.assertEqual(r["mots_avant"], 0)

    def test_completion(self):
        m = moteur_de_test(FausseCompletion())
        r = m.proposer("", "Ta", "v")
        self.assertEqual(r["nature"], "comp")
        self.assertEqual(r["formes"], ["Tamurt", "Tameṭṭut", "Tavrat"])
        self.assertEqual(m.proposer("", "ruhagh", "v")["nature"], "prop")

    def test_possessif_court_avant_la_completion(self):
        """« iw » n'a que deux lettres : la complétion le prendrait, et « tamurt iw »
        ne deviendrait jamais « tamurt-iw »."""
        m = moteur_de_test(FausseCompletion())
        r = m.proposer("ruḥeɣ ɣer tamurt ", "iw", "v")
        self.assertEqual(r["nature"], "prop")
        self.assertEqual(r["formes"], ["tamurt-iw", "iw", "is"])
        self.assertEqual(r["mots_avant"], 1)
        self.assertEqual(m.proposer("Tamurt ", "iw", "v")["formes"][0], "Tamurt-iw")

    def test_possessif_court_jamais_par_dessus_une_virgule(self):
        m = moteur_de_test(FausseCompletion())
        r = m.proposer("tamurt, ", "iw", "v")
        self.assertEqual(r["nature"], "comp")
        self.assertEqual(r["formes"][0], "iw")

    def test_possessif_court_en_debut_de_phrase(self):
        m = moteur_de_test(FausseCompletion())
        self.assertEqual(m.proposer("", "iw", "v")["nature"], "comp")

    def test_pas_encore_pret(self):
        m = service.Moteur()
        m.charger_graphie()
        self.assertEqual(m.proposer("", "ruhagh", "v")["formes"], [])
        self.assertEqual(m.predire("ruḥeɣ ", "v"), [])


class LaRelecture(unittest.TestCase):

    def setUp(self):
        self.m = moteur_de_test()
        if lieux.MES_MOTS.exists():
            lieux.MES_MOTS.unlink()

    def test_les_mots_signales(self):
        texte = "ruhagh ghar tamettut"
        signales = self.m.relire(texte, "v")
        self.assertEqual([s["mot"] for s in signales], ["ruhagh", "ghar", "tamettut"])
        self.assertEqual(signales[0]["propositions"][0], "ruḥeɣ")
        self.assertEqual(signales[0]["natures"][0], "contexte")
        for s in signales:
            self.assertEqual(texte[s["debut"]:s["fin"]], s["mot"])

    def test_mon_dictionnaire(self):
        service.ajouter_mot("ghar")
        self.assertEqual([s["mot"] for s in self.m.relire("ruhagh ghar", "v")], ["ruhagh"])
        service.oublier_mot("ghar")
        self.assertEqual(len(self.m.relire("ruhagh ghar", "v")), 2)

    def test_mon_dictionnaire_avec_un_bom(self):
        """Ouvert et enregistré à la main : le premier mot compte quand même."""
        lieux.MES_MOTS.parent.mkdir(parents=True, exist_ok=True)
        lieux.MES_MOTS.write_bytes("﻿ghar\r\nruhagh\r\n".encode("utf-8"))
        self.assertEqual(service.mes_mots(), {"ghar", "ruhagh"})

    def test_mon_dictionnaire_dans_un_autre_codage(self):
        lieux.MES_MOTS.parent.mkdir(parents=True, exist_ok=True)
        lieux.MES_MOTS.write_bytes("tamaziɣt\nété\n".encode("utf-16"))
        self.assertEqual(service.mes_mots(), set())
        self.assertEqual(len(self.m.relire("ruhagh ghar", "v")), 2)

    def test_possessif_dans_la_relecture(self):
        signales = self.m.relire("ruḥeɣ ɣer tamurt iw", "v")
        self.assertEqual(signales[-1]["mot"], "tamurt iw")
        self.assertEqual(signales[-1]["propositions"], ["tamurt-iw"])


class LesRequetes(unittest.TestCase):

    def setUp(self):
        self.s = service.Service(moteur_de_test())

    def test_etat(self):
        r = self.s.traiter({"quoi": "etat"})
        self.assertTrue(r["pret"])
        self.assertGreater(r["formes"], 12000)

    def test_basculer(self):
        r = self.s.traiter({"quoi": "basculer", "texte": "baba yusa-d, abrid.", "graphie": "v"})
        self.assertEqual(r["texte"], "vava yusa-d, avrid.")

    def test_graphie_abimee_donne_v(self):
        r = self.s.traiter({"quoi": "proposer", "mot": "abrid", "graphie": "z"})
        self.assertEqual(r["formes"][0], "avrid")

    def test_inconnue(self):
        self.assertIn("erreur", self.s.traiter({"quoi": "rien"}))

    def test_texte_trop_long(self):
        r = self.s.traiter({"quoi": "relire", "texte": "a" * 30000})
        self.assertEqual(r["erreur"], "texte trop long")

    def test_dictee_sans_fichier(self):
        self.s.moteur._dictee_possible = True
        r = self.s.traiter({"quoi": "dicter", "fichier": str(commun.TEMP / "absent.wav")})
        self.assertEqual(r["erreur"], "enregistrement introuvable")


class LaVieDuService(unittest.TestCase):

    def test_s_arrete_quand_le_client_meurt(self):
        s = service.Service(moteur_de_test())
        client = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"])
        s.traiter({"quoi": "attacher", "pid": client.pid})
        t0 = time.time()
        s.veiller(periode=0.1)
        client.wait()
        self.assertLess(time.time() - t0, 5)

    def test_quitter(self):
        s = service.Service(moteur_de_test())
        s.traiter({"quoi": "quitter"})
        s.veiller(periode=0.05)


if __name__ == "__main__":
    unittest.main()
