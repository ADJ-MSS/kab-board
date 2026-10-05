#!/usr/bin/env python3
"""Le moteur du greffon Word, en service local.

Le greffon est en C# et le correcteur en Python : ils se parlent par une prise
TCP sur 127.0.0.1, une requête JSON par ligne, une réponse JSON par ligne. Rien
ne sort de la machine, aucune connexion n'est ouverte vers l'extérieur.

    python3 word/moteur/service.py [port]

Le port est écrit dans %LOCALAPPDATA%\\kab-board\\port (ou ~/.config sur Linux)
pour que le greffon sache où frapper, et la prise n'écoute que la boucle locale.

Requêtes :

    {"quoi": "etat"}
    {"quoi": "relire", "texte": "...", "graphie": "b"}
    {"quoi": "ajouter", "mot": "..."}
    {"quoi": "oublier", "mot": "..."}
    {"quoi": "dicter", "fichier": "...wav", "graphie": "v"}
"""
import json
import os
import re
import socket
import socketserver
import sys
import threading
from pathlib import Path

ICI = Path(__file__).resolve().parent
# Dans le dépôt, le code du correcteur est dans linux/ ; dans le paquet Windows,
# il est copié à côté de ce fichier.
LINUX = ICI / "linux" if (ICI / "linux" / "correcteur_bv.py").exists() else ICI.parent.parent / "linux"
DEPOT = LINUX.parent

# Ressources livrees avec le paquet.
_livrees = ICI.parent / "modeles"
if _livrees.is_dir() and "KAB_BOARD_MODELES" not in os.environ:
    os.environ["KAB_BOARD_MODELES"] = str(_livrees)

# Modele vocal livre avec le paquet.
_voix = ICI.parent / "modeles" / "voix"
if _voix.is_dir() and "KAB_BOARD_VOIX" not in os.environ:
    os.environ["KAB_BOARD_VOIX"] = str(_voix)

# Sous Windows, onnxruntime avant tout le reste. Il lui faut un msvcp140.dll
# recent (le sien, 14.44) ; l'etiqueteur charge celui de Windows (14.29) s'il
# passe le premier, et onnxruntime plante alors a l'import (violation d'acces,
# le moteur entier tombe). Charge d'abord, le sien sert a tous.
if os.name == "nt" and _voix.is_dir():
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        pass

sys.path[:0] = [str(LINUX), str(LINUX / "pipeline")]

MOT = re.compile(r"[\w\-ɣɛḍḥṭẓṣǧčṛ]+", re.UNICODE)
NB_PROPOSITIONS = 6
CONTEXTE_MAX = 60

if os.name == "nt":
    CONFIG = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "kab-board"
else:
    CONFIG = Path.home() / ".config" / "kab-board"
MES_MOTS = CONFIG / "mots-a-moi.txt"
PORT_ECRIT = CONFIG / "port"

correcteur = None
graphie = None
pret = threading.Event()
verrou = threading.Lock()

# La dictee a son propre verrou : une transcription n'attend pas une relecture.
transcripteur = None
verrou_dictee = threading.Lock()
_dictee_possible = None


def preparer_chemins():
    """Les mêmes ressources que l'application de bureau."""
    import chemins, config
    d = chemins.correcteur()
    if d is None:
        raise SystemExit(chemins.manquant())
    config.BASE = d
    config.KENLM_BIN = d / "kabyle_3gram.binary"
    config.AMYAG_FORMES = d / "amyag_formes.txt"
    config.POS_MODEL = d / "kab-POS-tagl.joblib"
    config.LEXCAT_FILE = LINUX / "data" / "lexique_categories.txt"
    config.WORDNET_JSON = d / "wordnet" / "dictionnaire_sémantique_racinale_kabyle_V1.json"


def charger():
    global correcteur, graphie
    preparer_chemins()
    from correcteur_bv import CorrecteurBV
    correcteur = CorrecteurBV.charger(mode="b")
    graphie = correcteur.graphie
    pret.set()


def mes_mots():
    try:
        return {l.strip().lower() for l in MES_MOTS.read_text(encoding="utf-8").splitlines() if l.strip()}
    except OSError:
        return set()


def ajouter_mot(mot):
    CONFIG.mkdir(parents=True, exist_ok=True)
    with open(MES_MOTS, "a", encoding="utf-8") as f:
        f.write(mot.strip() + "\n")


def oublier_mot(mot):
    restants = [m for m in mes_mots() if m != mot.strip().lower()]
    CONFIG.mkdir(parents=True, exist_ok=True)
    MES_MOTS.write_text("\n".join(sorted(restants)) + ("\n" if restants else ""), encoding="utf-8")


def casser_comme(modele, mot):
    """La casse du mot tapé : le correcteur ne rend que des minuscules."""
    if modele.isupper() and len(modele) > 1:
        return mot.upper()
    if modele[:1].isupper():
        return mot[:1].upper() + mot[1:]
    return mot


def longueur_mots_avant(texte_avant, n):
    """Longueur des n mots qui terminent texte_avant, blancs qui les suivent compris :
    ce que la correction remplace en plus du mot quand elle le rattache aux mots
    précédents (« tamurt iw » → « tamurt-iw »). -1 si ces mots ne sont pas là, ou pas
    séparés par de simples blancs. Même règle que le clavier (saisie.py)."""
    i = len(texte_avant)
    for _ in range(n):
        apres_blancs = i
        while i > 0 and texte_avant[i - 1].isspace():
            i -= 1
        if i == apres_blancs:
            return -1
        fin_mot = i
        while i > 0 and (texte_avant[i - 1].isalpha() or texte_avant[i - 1] == "-"):
            i -= 1
        if i == fin_mot:
            return -1
    return len(texte_avant) - i


def rang_de(portee, texte, debut):
    """Combien de fois la même suite de mots apparaît avant debut : le greffon s'en
    sert, comme du rang d'un mot, pour la retrouver dans le document."""
    motif = re.compile(r"(?<![\w\-])" + re.escape(portee) + r"(?![\w\-])", re.IGNORECASE)
    return sum(1 for x in motif.finditer(texte) if x.start() < debut)


def relire(texte, mode):
    """Les mots à signaler, avec leurs propositions et la nature de chacune.

    Le rang dit combien de fois le même mot apparaît avant celui-ci : le greffon
    s'en sert pour retrouver la bonne occurrence dans le document Word.
    """
    connus = mes_mots()
    vus = {}
    signales = []
    with verrou:
        correcteur.mode = mode
        for m in MOT.finditer(texte):
            mot = m.group()
            cle = mot.lower()
            rang = vus.get(cle, 0)
            vus[cle] = rang + 1
            if len(mot) < 2 or cle in connus or mot.isdigit():
                continue
            gauche = texte[:m.start()].strip()[-CONTEXTE_MAX:]
            try:
                res = correcteur.corriger(f"{gauche} {mot}".strip())
            except Exception:
                continue
            corrigee = res.texte.strip().split(" ")[-1] if res.texte else ""
            # Possessif rattaché au mot d'avant (« tamurt iw » → « tamurt-iw ») : la
            # correction couvre les deux mots, sans les candidats du mot seul.
            avant = getattr(res.brut, "couverture_fin", 1) - 1 if res.brut is not None else 0
            if corrigee and avant > 0:
                k = longueur_mots_avant(texte[:m.start()], avant)
                if k <= 0:
                    # Fondu par-dessus une virgule, que le correcteur ne voit pas : le mot seul.
                    corrigee = corrigee.rsplit("-", 1)[-1]
                else:
                    debut = m.start() - k
                    portee = texte[debut:m.end()]
                    fusion = casser_comme(portee, corrigee)
                    if portee.lower() in connus or fusion == portee:
                        continue
                    # Le mot d'avant, s'il était signalé, est repris dans la portée.
                    signales = [s for s in signales if s["debut"] < debut]
                    signales.append({"mot": portee, "rang": rang_de(portee, texte, debut),
                                     "debut": debut, "propositions": [fusion],
                                     "natures": ["contexte"]})
                    continue
            if not corrigee or corrigee.lower() == cle:
                continue
            # Correction en contexte d'abord, puis candidats du mot seul.
            formes, natures = [], []
            for rangf, f in enumerate([corrigee] + [c["candidat"]
                                                    for c in correcteur.top_candidats(mot, 5)]):
                f = casser_comme(mot, f)
                if not f or f.lower() == cle or f in formes:
                    continue
                formes.append(f)
                natures.append("contexte" if rangf == 0 else "candidat")
            if formes:
                signales.append({"mot": mot, "rang": rang, "debut": m.start(),
                                 "propositions": formes[:NB_PROPOSITIONS],
                                 "natures": natures[:NB_PROPOSITIONS]})
    return signales


def dictee_possible():
    """Le modele vocal est-il la, et onnxruntime avec lui ? Vu une seule fois."""
    global _dictee_possible
    if _dictee_possible is None:
        try:
            import dictee
            import onnxruntime  # noqa: F401
            _dictee_possible = dictee.MODELE.exists() and dictee.JETONS.exists()
        except Exception:
            _dictee_possible = False
    return _dictee_possible


def dicter(fichier, mode):
    """Le texte d'un enregistrement, dans la graphie reglee, sans correction."""
    global transcripteur
    import dictee
    with verrou_dictee:
        if transcripteur is None:
            transcripteur = dictee.Transcripteur()
        texte = transcripteur.transcrire(dictee.lire_wav(Path(fichier)))
    # Le modele vocal ne transcrit qu'avec des b : la graphie se fait ici.
    if texte and graphie is not None:
        texte = graphie.enrichir_texte(texte, mode).texte
    return texte


def repondre(requete):
    quoi = requete.get("quoi")
    if quoi == "etat":
        return {"pret": pret.is_set(),
                "formes": len(graphie.vers_v) if graphie else 0,
                "mots_a_moi": len(mes_mots()),
                "dictee": dictee_possible()}
    if quoi == "relire":
        if not pret.is_set():
            return {"erreur": "le correcteur se charge encore"}
        texte = requete.get("texte", "")
        if len(texte) > 20000:
            return {"erreur": "texte trop long"}
        mode = "v" if requete.get("graphie") == "v" else "b"
        return {"signales": relire(texte, mode)}
    if quoi == "ajouter":
        mot = (requete.get("mot") or "").strip()
        if not mot:
            return {"erreur": "mot vide"}
        ajouter_mot(mot)
        return {"ajoute": mot, "total": len(mes_mots())}
    if quoi == "oublier":
        oublier_mot(requete.get("mot") or "")
        return {"total": len(mes_mots())}
    if quoi == "dicter":
        if not pret.is_set():
            return {"erreur": "le correcteur se charge encore"}
        if not dictee_possible():
            return {"erreur": "la dictée n'est pas installée"}
        fichier = requete.get("fichier") or ""
        if not Path(fichier).is_file():
            return {"erreur": "enregistrement introuvable"}
        mode = "v" if requete.get("graphie") == "v" else "b"
        return {"texte": dicter(fichier, mode)}
    return {"erreur": "requête inconnue"}


class Echange(socketserver.StreamRequestHandler):
    """Une ligne JSON reçue, une ligne JSON rendue."""

    def handle(self):
        for ligne in self.rfile:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                requete = json.loads(ligne.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                reponse = {"erreur": "JSON invalide"}
            else:
                try:
                    reponse = repondre(requete)
                except Exception as erreur:
                    reponse = {"erreur": str(erreur)}
            self.wfile.write(json.dumps(reponse, ensure_ascii=False).encode("utf-8") + b"\n")
            self.wfile.flush()


class Service(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    address_family = socket.AF_INET


def main(argv):
    port = int(argv[1]) if len(argv) > 1 else 0
    threading.Thread(target=charger, daemon=True).start()
    service = Service(("127.0.0.1", port), Echange)
    port = service.server_address[1]
    CONFIG.mkdir(parents=True, exist_ok=True)
    PORT_ECRIT.write_text(str(port), encoding="utf-8")
    print(f"  Moteur kab-board sur 127.0.0.1:{port}", flush=True)
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        PORT_ECRIT.unlink(missing_ok=True)


if __name__ == "__main__":
    main(sys.argv)
