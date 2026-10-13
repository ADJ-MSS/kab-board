"""La liaison locale : le jeton, les reconnexions, les requêtes abîmées."""
import json
import socket
import unittest

import commun  # noqa: F401
import liaison


class LaLiaison(unittest.TestCase):

    def setUp(self):
        self.recus = []

        def traiter(requete):
            self.recus.append(requete)
            if requete.get("quoi") == "panne":
                raise RuntimeError("en panne")
            return {"echo": requete}

        self.traiter = traiter
        self.serveur = liaison.Serveur("essai", traiter).demarrer()
        self.client = liaison.Client("essai")

    def tearDown(self):
        self.client.fermer()
        self.serveur.arreter()

    def test_aller_retour(self):
        r = self.client.appeler("etat", mot="ɣer")
        self.assertEqual(r, {"echo": {"quoi": "etat", "mot": "ɣer"}})
        self.assertNotIn("jeton", self.recus[0])

    def test_connexion_gardee(self):
        for i in range(20):
            self.assertEqual(self.client.appeler("n", i=i)["echo"]["i"], i)

    def test_une_requete_en_panne_ne_tue_pas_le_serveur(self):
        self.assertIn("en panne", self.client.appeler("panne")["erreur"])
        self.assertIsNotNone(self.client.appeler("etat"))

    def test_sans_le_jeton(self):
        fiche = liaison.lire_fiche("essai")
        with socket.create_connection(("127.0.0.1", fiche["port"]), timeout=2) as s:
            s.sendall(json.dumps({"quoi": "etat", "jeton": "faux"}).encode() + b"\n")
            reponse = json.loads(s.makefile("rb").readline())
        self.assertEqual(reponse, {"erreur": "jeton"})
        self.assertEqual(self.recus, [])

    def test_json_abime(self):
        fiche = liaison.lire_fiche("essai")
        with socket.create_connection(("127.0.0.1", fiche["port"]), timeout=2) as s:
            s.sendall(b"pas du json\n")
            reponse = json.loads(s.makefile("rb").readline())
        self.assertEqual(reponse, {"erreur": "JSON invalide"})

    def test_le_serveur_redemarre(self):
        self.assertIsNotNone(self.client.appeler("etat"))
        self.serveur.arreter()
        self.serveur = liaison.Serveur("essai", self.traiter).demarrer()
        self.assertEqual(self.client.appeler("etat")["echo"]["quoi"], "etat")

    def test_personne(self):
        self.serveur.arreter()
        self.serveur = liaison.Serveur("autre", self.traiter).demarrer()
        self.assertIsNone(liaison.Client("essai", 0.5).appeler("etat"))
        self.assertFalse(liaison.joignable("essai"))
        self.assertTrue(liaison.joignable("autre"))

    def test_la_fiche_est_privee(self):
        import os
        if os.name == "nt":
            self.skipTest("sous Windows, c'est le dossier qui protège")
        mode = liaison.fichier("essai").stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
