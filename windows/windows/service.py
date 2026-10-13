#!/usr/bin/env python3
"""Le correcteur, en service local : un seul processus le charge pour tous.

Le clavier (kab_saisie.py) et la fenêtre « Écrire et relire » (kab_bureau.py) lui
demandent leurs propositions par la liaison locale (liaison.py). Le correcteur
pèse lourd et se charge en une dizaine de secondes : il est chargé une fois, à
part, pour que la frappe ne l'attende jamais.

Ce que fait chaque requête est ce que fait le clavier Linux (kab_ibus.py), à la
lettre : la complétion de 1 à 3 lettres, puis la correction en contexte en tête
et les cinq candidats du mot isolé, la casse du mot tapé, la graphie b ou v, la
prédiction du mot suivant, la fiche, la recherche depuis le français, le mot du
jour, la relecture (celle du complément Word) et la dictée.

Le service vit tant qu'un de ses clients vit : chacun s'y attache par son PID.

    pythonw windows/service.py
"""
import datetime
import os
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lieux  # noqa: E402

lieux.preparer()

# Sous Windows, onnxruntime avant tout le reste, comme dans le moteur Word : il
# lui faut un msvcp140.dll récent, et celui que chargerait l'étiqueteur avant lui
# le ferait planter à l'import.
if lieux.WINDOWS and lieux.voix() is not None:
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        pass

import liaison  # noqa: E402
import processus  # noqa: E402
from saisie import longueur_mots_avant  # noqa: E402

NB_PROPOSITIONS = 6
CONTEXTE_MAX = 60
MOT = re.compile(r"[\w\-ɣɛḍḥṭẓṣǧčṛ]+", re.UNICODE)
TEXTE_MAX = 20000
RELIRE_MOTS_MAX = 400


def casser_comme(modele: str, mot: str) -> str:
    """La casse du mot tapé : le correcteur ne rend que des minuscules."""
    if len(modele) > 1 and modele == modele.upper() and modele.lower() != modele:
        return mot.upper()
    if modele[:1].isupper():
        return mot[:1].upper() + mot[1:]
    return mot


def graphie_demandee(valeur) -> str:
    return "b" if valeur == "b" else "v"


def rang_de(portee: str, texte: str, debut: int) -> int:
    """Combien de fois la même suite de mots apparaît avant debut."""
    motif = re.compile(r"(?<![\w\-])" + re.escape(portee) + r"(?![\w\-])", re.IGNORECASE)
    return sum(1 for x in motif.finditer(texte) if x.start() < debut)


class Moteur:
    """Le correcteur et les outils, chargés une fois."""

    def __init__(self):
        self.correcteur = None
        self.completion = None
        self.outils = None
        self.frequents = []
        self.graphie = None
        self.erreur = ""
        self.pret = threading.Event()
        self.verrou = threading.Lock()          # le correcteur n'est pas fait pour deux fils
        self.verrou_dictee = threading.Lock()   # une dictée n'attend pas une correction
        self.transcripteur = None
        self._dictee_possible = None
        self.debut = time.time()
        self.duree_chargement = 0.0

    # Le chargement

    def charger_graphie(self):
        import chemins
        from graphie_bv import GraphieBV
        self.graphie = GraphieBV.charger(chemins.TABLE_BV)

    def charger(self):
        t0 = time.time()
        try:
            if self.graphie is None:
                self.charger_graphie()
            import chemins
            import config
            donnees = chemins.correcteur()
            if donnees is None:
                raise FileNotFoundError(lieux.manquant())
            config.BASE = donnees
            config.KENLM_BIN = donnees / "kabyle_3gram.binary"
            config.AMYAG_FORMES = donnees / "amyag_formes.txt"
            config.POS_MODEL = donnees / "kab-POS-tagl.joblib"
            config.LEXCAT_FILE = lieux.MOTEUR / "data" / "lexique_categories.txt"
            config.WORDNET_JSON = (donnees / "wordnet"
                                   / "dictionnaire_sémantique_racinale_kabyle_V1.json")
            from correcteur import KabyleCorrecteurV2
            moteur = KabyleCorrecteurV2()
            moteur.charger()
            from completion import Completion
            completion = Completion(moteur.res)
            completion.candidats("a")              # le vocabulaire, construit d'avance
            from ressources_kab import Ressources as RessourcesOutils
            self.outils = RessourcesOutils.charger(
                lexique_categories=lieux.MOTEUR / "data" / "lexique_categories.txt")
            actifs = chemins.actifs_android()
            frequents = (actifs / "pool.frequents") if actifs else None
            if frequents is not None and frequents.exists():
                self.frequents = frequents.read_text(encoding="utf-8").split()
            self.correcteur, self.completion = moteur, completion
            self.duree_chargement = time.time() - t0
            print(f"kab-board : correcteur prêt en {self.duree_chargement:.0f} s", flush=True)
            self.pret.set()
        except BaseException as erreur:          # SystemExit compris : on le dit
            self.erreur = str(erreur) or type(erreur).__name__
            print(f"kab-board : correcteur indisponible ({self.erreur})", flush=True)

    # Les propositions du mot en cours

    def proposer(self, contexte: str, mot: str, mode: str) -> dict:
        """La barre : complétion de 1 à 3 lettres, sinon correction et candidats.
        Un possessif tapé juste après un mot (« tamurt iw ») ne se complète pas :
        la complétion de kab-board lui laisse la place, et la correction le
        rattache (« tamurt-iw »)."""
        vide = {"nature": "prop", "formes": [], "mots_avant": 0}
        if not self.pret.is_set() or not mot:
            return vide
        contexte = contexte[-CONTEXTE_MAX:]
        from normalisation import normalize
        with self.verrou:
            if self.completion is not None:
                try:
                    barre = self.completion.barre(contexte, normalize(mot))
                except Exception:
                    barre = None
                if barre:
                    formes = []
                    for f in barre:
                        g = casser_comme(mot, self.graphie.basculer(f, mode))
                        if g and g not in formes:
                            formes.append(g)
                    return {"nature": "comp", "formes": formes[:NB_PROPOSITIONS],
                            "mots_avant": 0}
            res = self.correcteur.corriger(f"{contexte} {mot}".strip())
            corrigee = res.texte_corrige.strip().split(" ")[-1] if res.texte_corrige else ""
            cinq = [x["candidat"] for x in self.correcteur.top_candidats(mot, 5)]
        # Rattachée aux mots d'avant (« tamurt iw » -> « tamurt-iw »), la tête les
        # remplace aussi, et en prend la casse. Jamais par-dessus une virgule.
        mots_avant = (getattr(res, "couverture_fin", 1) - 1) if corrigee else 0
        if mots_avant > 0 and longueur_mots_avant(contexte, mots_avant) < 0:
            corrigee, mots_avant = corrigee.rsplit("-", 1)[-1], 0
        precedents = contexte.split()
        modele_tete = precedents[-mots_avant] if 0 < mots_avant <= len(precedents) else mot
        # La correction en contexte en tête, même quand elle est le mot lui-même,
        # puis le top-5 du mot isolé, chaque forme à la casse du mot tapé.
        formes = []
        for rang, f in enumerate([corrigee] + cinq):
            if not f:
                continue
            modele = modele_tete if rang == 0 else mot
            g = casser_comme(modele, self.graphie.basculer(f, mode))
            if g and g not in formes:
                formes.append(g)
        return {"nature": "prop", "formes": formes[:NB_PROPOSITIONS],
                "mots_avant": mots_avant if formes and formes[0] else 0}

    def predire(self, contexte: str, mode: str) -> list:
        """Le mot suivant : les fréquents notés par le modèle de langue."""
        c = self.correcteur
        if not self.pret.is_set() or not self.frequents or getattr(c.res, "kenlm", None) is None:
            return []
        from normalisation import tokenize
        from ressources import _kenlm as kenlm
        lm = c.res.kenlm
        with self.verrou:
            entree, sortie = kenlm.State(), kenlm.State()
            lm.BeginSentenceWrite(entree)
            for jeton in tokenize(contexte[-CONTEXTE_MAX:])[-8:]:
                lm.BaseScore(entree, jeton, sortie)
                entree, sortie = sortie, entree
            meilleurs = []
            for mot in self.frequents:
                score = lm.BaseScore(entree, mot, sortie)
                if len(meilleurs) < NB_PROPOSITIONS:
                    meilleurs.append((score, mot))
                    meilleurs.sort(reverse=True)
                elif score > meilleurs[-1][0]:
                    meilleurs[-1] = (score, mot)
                    meilleurs.sort(reverse=True)
        return [self.graphie.basculer(m, mode) for _s, m in meilleurs]

    # Relire

    def relire(self, texte: str, mode: str, mots_max: int = RELIRE_MOTS_MAX) -> list:
        """Les mots à signaler, leurs propositions et la nature de chacune : la
        relecture du complément Word. Les mots de « mon dictionnaire » passent."""
        if not self.pret.is_set():
            return []
        connus = mes_mots()
        vus, signales = {}, []
        for n, m in enumerate(MOT.finditer(texte)):
            if n >= mots_max:
                break
            mot = m.group()
            cle = mot.lower()
            rang = vus.get(cle, 0)
            vus[cle] = rang + 1
            if len(mot) < 2 or cle in connus or mot.isdigit():
                continue
            gauche = texte[:m.start()].strip()[-CONTEXTE_MAX:]
            try:
                with self.verrou:
                    res = self.correcteur.corriger(f"{gauche} {mot}".strip())
                    cinq = [c["candidat"] for c in self.correcteur.top_candidats(mot, 5)]
            except Exception:
                continue
            corrigee = res.texte_corrige.strip().split(" ")[-1] if res.texte_corrige else ""
            corrigee = self.graphie.basculer(corrigee, mode) if corrigee else ""
            avant = getattr(res, "couverture_fin", 1) - 1
            if corrigee and avant > 0:
                k = longueur_mots_avant(texte[:m.start()], avant)
                if k <= 0:
                    corrigee = corrigee.rsplit("-", 1)[-1]
                else:
                    debut = m.start() - k
                    portee = texte[debut:m.end()]
                    fusion = casser_comme(portee, corrigee)
                    if portee.lower() in connus or fusion == portee:
                        continue
                    signales = [s for s in signales if s["debut"] < debut]
                    signales.append({"mot": portee, "rang": rang_de(portee, texte, debut),
                                     "debut": debut, "fin": m.end(), "propositions": [fusion],
                                     "natures": ["contexte"]})
                    continue
            if not corrigee or corrigee.lower() == cle:
                continue
            formes, natures = [], []
            for rangf, f in enumerate([corrigee] + [self.graphie.basculer(c, mode) for c in cinq]):
                f = casser_comme(mot, f)
                if not f or f.lower() == cle or f in formes:
                    continue
                formes.append(f)
                natures.append("contexte" if rangf == 0 else "candidat")
            if formes:
                signales.append({"mot": mot, "rang": rang, "debut": m.start(), "fin": m.end(),
                                 "propositions": formes[:NB_PROPOSITIONS],
                                 "natures": natures[:NB_PROPOSITIONS]})
        return signales

    # Les outils du clavier

    def fiche(self, mot: str, mode: str) -> dict:
        """Asegzawal : glose, catégorie, états libre et d'annexion."""
        if not mot:
            return {}
        outils = self.outils
        glose = outils.glose(mot) if outils else ""
        categorie = outils.categorie(mot) if outils else ""
        libre = annexion = ""
        try:
            from postprocess import identifier_nom_etat, vers_annexion, vers_libre
            etat = identifier_nom_etat(mot.lower())
            if etat == "libre":
                libre, annexion = mot, vers_annexion(mot.lower())
            elif etat == "annexion":
                libre, annexion = vers_libre(mot.lower()), mot
        except Exception:
            pass
        g = (lambda f: self.graphie.basculer(f, mode) if f else "") if self.graphie else str
        return {"mot": g(mot), "glose": glose, "categorie": categorie,
                "libre": g(libre), "annexion": g(annexion)}

    def chercher(self, requete: str, mode: str) -> list:
        trouves = self.outils.chercher_francais(requete.strip(), 8) if self.outils else []
        return [[self.graphie.basculer(f, mode), g] for f, g in trouves]

    def mot_du_jour(self, mode: str, jour: int = None) -> dict:
        if not self.outils:
            return {"forme": "", "glose": ""}
        jour = datetime.date.today().toordinal() if jour is None else jour
        forme, glose = self.outils.mot_du_jour(jour)
        return {"forme": self.graphie.basculer(forme, mode) if forme else "", "glose": glose}

    # La dictée

    def dictee_possible(self) -> bool:
        if self._dictee_possible is None:
            try:
                import onnxruntime  # noqa: F401
                import dictee
                self._dictee_possible = dictee.MODELE.exists() and dictee.JETONS.exists()
            except Exception:
                self._dictee_possible = False
        return self._dictee_possible

    def dicter(self, fichier: str, mode: str) -> str:
        """Le texte d'un enregistrement, dans la graphie réglée, jamais corrigé."""
        import dictee
        with self.verrou_dictee:
            if self.transcripteur is None:
                self.transcripteur = dictee.Transcripteur()
            texte = self.transcripteur.transcrire(dictee.lire_wav(Path(fichier)))
        if texte and self.graphie is not None:
            texte = self.graphie.enrichir_texte(texte, mode).texte
        return texte


# « Mon dictionnaire » : le fichier de Kab-board pour Word, partagé.

def mes_mots() -> set:
    try:
        return {ligne.strip().lower()
                for ligne in lieux.MES_MOTS.read_text(encoding="utf-8-sig").splitlines()
                if ligne.strip()}
    except (OSError, ValueError):           # absent, ou écrit dans un autre codage
        return set()


def ajouter_mot(mot: str) -> None:
    lieux.MES_MOTS.parent.mkdir(parents=True, exist_ok=True)
    with open(lieux.MES_MOTS, "a", encoding="utf-8") as f:
        f.write(mot.strip() + "\n")


def oublier_mot(mot: str) -> None:
    restants = sorted(m for m in mes_mots() if m != mot.strip().lower())
    lieux.MES_MOTS.parent.mkdir(parents=True, exist_ok=True)
    lieux.MES_MOTS.write_text("\n".join(restants) + ("\n" if restants else ""), encoding="utf-8")


class Service:
    """Les requêtes, et la vie du service : il s'arrête quand plus personne ne s'en sert."""

    ATTENTE_PREMIER_CLIENT = 120.0

    def __init__(self, moteur: Moteur):
        self.moteur = moteur
        self.clients = set()
        self.deja_attache = False
        self.verrou = threading.Lock()
        self.fin = threading.Event()

    def traiter(self, requete: dict) -> dict:
        m = self.moteur
        quoi = requete.get("quoi")
        mode = graphie_demandee(requete.get("graphie"))
        if quoi == "etat":
            return {"pret": m.pret.is_set(), "erreur": m.erreur,
                    "formes": len(m.graphie.vers_v) if m.graphie else 0,
                    "chargement": round(m.duree_chargement, 1),
                    "depuis": round(time.time() - m.debut, 1),
                    "dictee": m.dictee_possible() if m.pret.is_set() else False,
                    "pid": os.getpid()}
        if quoi == "attacher":
            pid = int(requete.get("pid") or 0)
            with self.verrou:
                if pid > 0:
                    self.clients.add(pid)
                    self.deja_attache = True
            return {"ok": True}
        if quoi == "detacher":
            with self.verrou:
                self.clients.discard(int(requete.get("pid") or 0))
            return {"ok": True}
        if quoi == "quitter":
            self.fin.set()
            return {"ok": True}
        if quoi == "proposer":
            return m.proposer(str(requete.get("contexte", "")), str(requete.get("mot", "")), mode)
        if quoi == "predire":
            return {"formes": m.predire(str(requete.get("contexte", "")), mode)}
        if quoi == "relire":
            texte = str(requete.get("texte", ""))
            if len(texte) > TEXTE_MAX:
                return {"erreur": "texte trop long"}
            if not m.pret.is_set():
                return {"erreur": "le correcteur se charge encore"}
            return {"signales": m.relire(texte, mode)}
        if quoi == "basculer":
            texte = str(requete.get("texte", ""))
            if m.graphie is None:
                return {"texte": texte}
            return {"texte": MOT.sub(lambda x: m.graphie.basculer(x.group(), mode), texte)}
        if quoi == "fiche":
            return m.fiche(str(requete.get("mot", "")).strip(), mode)
        if quoi == "chercher":
            return {"trouves": m.chercher(str(requete.get("requete", "")), mode)}
        if quoi == "motdujour":
            return m.mot_du_jour(mode)
        if quoi == "ajouter":
            mot = str(requete.get("mot") or "").strip()
            if not mot:
                return {"erreur": "mot vide"}
            ajouter_mot(mot)
            return {"ajoute": mot, "total": len(mes_mots())}
        if quoi == "oublier":
            oublier_mot(str(requete.get("mot") or ""))
            return {"total": len(mes_mots())}
        if quoi == "dicter":
            if not m.pret.is_set():
                return {"erreur": "le correcteur se charge encore"}
            if not m.dictee_possible():
                return {"erreur": "la dictée n'est pas installée"}
            fichier = str(requete.get("fichier") or "")
            if not Path(fichier).is_file():
                return {"erreur": "enregistrement introuvable"}
            return {"texte": m.dicter(fichier, mode)}
        return {"erreur": "requête inconnue"}

    def veiller(self, periode: float = 5.0):
        """Rend la main quand il faut s'arrêter : plus aucun client vivant, ou
        personne venu dans les deux minutes."""
        depart = time.time()
        while not self.fin.wait(periode):
            with self.verrou:
                self.clients = {pid for pid in self.clients if processus.vivant(pid)}
                if self.clients:
                    continue
                if self.deja_attache or time.time() - depart > self.ATTENTE_PREMIER_CLIENT:
                    return


def principal(argv) -> int:
    if not processus.instance_unique("service", par_dossier=True):
        return 0
    processus.journal("service")
    moteur = Moteur()
    moteur.charger_graphie()
    service = Service(moteur)
    serveur = liaison.Serveur("service", service.traiter).demarrer()
    print(f"kab-board : service sur 127.0.0.1:{serveur.port}", flush=True)
    threading.Thread(target=moteur.charger, name="chargement", daemon=True).start()
    try:
        service.veiller()
    finally:
        serveur.arreter()
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
