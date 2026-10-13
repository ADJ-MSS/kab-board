"""La liaison entre les morceaux de Kab-board : une prise sur la boucle locale.

Le correcteur, le clavier et l'application sont des processus distincts. Ils se
parlent par TCP sur 127.0.0.1, une requête JSON par ligne, une réponse JSON par
ligne, comme le complément Word et son moteur. Rien ne sort de la machine.

Chaque serveur écrit dans le dossier des données un fichier `<nom>.liaison` :
son port, son PID et un jeton tiré au hasard. Le jeton accompagne chaque
requête. Ce dossier n'est lisible que par l'utilisateur : un autre compte de la
même machine ne peut donc pas faire écrire le clavier à sa place.

    serveur = Serveur("saisie", traiter)      # traiter(requete) -> reponse
    serveur.demarrer()
    Client("saisie").appeler("etat")          # -> {"mot": ..., ...} ou None
"""
import hmac
import json
import os
import secrets
import socket
import socketserver
import threading

import lieux

TAILLE_MAX = 1 << 20          # une requête : un texte à relire, pas davantage


def fichier(nom: str):
    return lieux.DONNEES / f"{nom}.liaison"


def lire_fiche(nom: str):
    """Ce qu'un serveur a annoncé : port, jeton, pid. None s'il n'y en a pas."""
    try:
        fiche = json.loads(fichier(nom).read_text(encoding="utf-8"))
        return fiche if {"port", "jeton", "pid"} <= set(fiche) else None
    except Exception:
        return None


class _Echange(socketserver.StreamRequestHandler):

    def setup(self):
        super().setup()
        with self.server.verrou:
            self.server.connexions.add(self.request)

    def finish(self):
        with self.server.verrou:
            self.server.connexions.discard(self.request)
        try:
            super().finish()
        except OSError:
            pass

    def handle(self):
        serveur = self.server
        while True:
            try:
                ligne = self.rfile.readline(TAILLE_MAX + 1)
            except OSError:
                return
            if not ligne:
                return
            if len(ligne) > TAILLE_MAX:
                self._repondre({"erreur": "requête trop longue"})
                return
            try:
                requete = json.loads(ligne.decode("utf-8"))
                if not isinstance(requete, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                self._repondre({"erreur": "JSON invalide"})
                continue
            jeton = requete.pop("jeton", "")
            if not isinstance(jeton, str) or not hmac.compare_digest(
                    jeton.encode("utf-8"), serveur.jeton.encode("utf-8")):
                self._repondre({"erreur": "jeton"})
                return
            try:
                reponse = serveur.traiter(requete)
            except Exception as erreur:          # une requête ratée ne tue pas le serveur
                reponse = {"erreur": f"{type(erreur).__name__}: {erreur}"}
            if not self._repondre(reponse if isinstance(reponse, dict) else {}):
                return

    def _repondre(self, reponse) -> bool:
        try:
            self.wfile.write(json.dumps(reponse, ensure_ascii=False).encode("utf-8") + b"\n")
            self.wfile.flush()
            return True
        except OSError:
            return False


class _Prise(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False

    def server_bind(self):
        # Sous Windows, personne d'autre ne doit pouvoir écouter sur ce port.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Serveur:

    def __init__(self, nom: str, traiter):
        self.nom = nom
        self.prise = _Prise(("127.0.0.1", 0), _Echange)
        self.prise.jeton = secrets.token_hex(16)
        self.prise.traiter = traiter
        self.prise.connexions = set()
        self.prise.verrou = threading.Lock()
        self.port = self.prise.server_address[1]

    def demarrer(self):
        threading.Thread(target=self.prise.serve_forever, args=(0.1,),
                         name=f"liaison-{self.nom}", daemon=True).start()
        lieux.DONNEES.mkdir(parents=True, exist_ok=True)
        cible = fichier(self.nom)
        provisoire = cible.with_suffix(".tmp")
        # Créé d'emblée en lecture seule pour l'utilisateur (le dossier l'est
        # déjà sous Windows ; sous Linux, c'est ce mode qui protège le jeton).
        fd = os.open(provisoire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"port": self.port, "jeton": self.prise.jeton, "pid": os.getpid()}, f)
        os.replace(provisoire, cible)
        return self

    def arreter(self):
        fiche = lire_fiche(self.nom)
        if fiche and fiche.get("pid") == os.getpid():
            try:
                fichier(self.nom).unlink()
            except OSError:
                pass
        self.prise.shutdown()
        self.prise.server_close()
        # Les connexions ouvertes se ferment aussi : un client ne doit pas parler
        # à un serveur arrêté.
        with self.prise.verrou:
            ouvertes = list(self.prise.connexions)
        for connexion in ouvertes:
            try:
                connexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


class Client:
    """Une connexion gardée ouverte, refaite au besoin. Sûre entre fils."""

    def __init__(self, nom: str, delai: float = 2.0):
        self.nom = nom
        self.delai = delai
        self._prise = None
        self._lecteur = None
        self._jeton = ""
        self._verrou = threading.Lock()

    def _ouvrir(self):
        fiche = lire_fiche(self.nom)
        if fiche is None:
            return False
        prise = socket.create_connection(("127.0.0.1", int(fiche["port"])), timeout=self.delai)
        self._prise, self._lecteur, self._jeton = prise, prise.makefile("rb"), fiche["jeton"]
        return True

    def fermer(self):
        for objet in (self._lecteur, self._prise):
            try:
                if objet is not None:
                    objet.close()
            except OSError:
                pass
        self._prise = self._lecteur = None

    def appeler(self, quoi: str, delai: float = None, **parametres):
        """La réponse du serveur, ou None s'il ne répond pas."""
        requete = dict(parametres, quoi=quoi)
        with self._verrou:
            # Une connexion périmée (le serveur a redémarré) se refait une fois. Une
            # réponse qui tarde, elle, ne se redemande pas : la requête est peut-être
            # déjà faite, et une lettre ne doit pas s'écrire deux fois.
            for _essai in range(2):
                try:
                    if self._prise is None and not self._ouvrir():
                        return None
                    self._prise.settimeout(delai or self.delai)
                    requete["jeton"] = self._jeton
                    self._prise.sendall(json.dumps(requete, ensure_ascii=False).encode("utf-8")
                                        + b"\n")
                    ligne = self._lecteur.readline(TAILLE_MAX + 1)
                except socket.timeout:
                    self.fermer()
                    return None
                except OSError:
                    self.fermer()
                    continue
                if not ligne:                    # fermée sans répondre : rien n'a été fait
                    self.fermer()
                    continue
                try:
                    reponse = json.loads(ligne.decode("utf-8"))
                except ValueError:
                    self.fermer()
                    return None
                if reponse.get("erreur") == "jeton":
                    self.fermer()                # nouveau serveur, nouveau jeton
                    continue
                return reponse
        return None


def joignable(nom: str, delai: float = 1.0) -> bool:
    c = Client(nom, delai)
    try:
        return c.appeler("etat") is not None
    finally:
        c.fermer()
