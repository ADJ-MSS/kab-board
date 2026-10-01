#!/usr/bin/env python3
"""La methode de saisie : le clavier kabyle dans toutes les applications.

Le mot en cours est souligne, ses six propositions dans le panneau ; les touches
1 a 6 en choisissent une, l'espace garde ce qui a ete tape. Digrammes et AltGr
donnent les lettres kabyles. Installation : README.md du meme dossier.
"""
import os
import socket
import sys
import threading
import time
from pathlib import Path

import gi
gi.require_version("IBus", "1.0")
from gi.repository import IBus, GLib

RACINE = Path(__file__).resolve().parent.parent          # le dossier linux/
DEPOT = RACINE.parent                                    # la racine de kab-board
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphie_bv import GraphieBV, B, V
from saisie import Saisie, est_lettre, choix_par_chiffre, graphie_reglee, ALTGR
sys.path.insert(0, str(RACINE / "bureau"))
from ressources_kab import Ressources as RessourcesOutils

import chemins
DONNEES = chemins.correcteur()
NB_PROPOSITIONS = 6
CONTEXTE_MAX = 60

# Le clavier flottant parle au moteur par cette prise : lui seul a le droit
# d'ecrire dans l'application active, et il l'a deja.
PRISE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "kab-board.sock"
REGLAGES = Path.home() / ".config" / "kab-board" / "reglages.json"


def lire_reglages():
    """Ce que l'application a regle. Des valeurs sures si le fichier manque."""
    import json
    try:
        return json.loads(REGLAGES.read_text(encoding="utf-8"))
    except Exception:
        return {"graphie": "v", "translitteration": True}


def casser_comme(modele: str, mot: str) -> str:
    """La casse du mot tape : le correcteur ne rend que des minuscules."""
    if len(modele) > 1 and modele == modele.upper():
        return mot.upper()
    if modele[:1].isupper():
        return mot[:1].upper() + mot[1:]
    return mot


def preparer_chemins():
    import config
    config.BASE = DONNEES
    config.KENLM_BIN = DONNEES / "kabyle_3gram.binary"
    config.AMYAG_FORMES = DONNEES / "amyag_formes.txt"
    config.POS_MODEL = DONNEES / "kab-POS-tagl.joblib"
    config.LEXCAT_FILE = RACINE / "data" / "lexique_categories.txt"
    config.WORDNET_JSON = DONNEES / "wordnet" / "dictionnaire_sémantique_racinale_kabyle_V1.json"


class MoteurKabBoard(IBus.Engine):
    """Le moteur de saisie. Une instance par champ de texte."""

    __gtype_name__ = "MoteurKabBoard"

    correcteur = None          # partage par toutes les instances : charge une fois
    chargement = None
    actif = None               # l'instance qui a le champ de saisie
    dernier = None             # la derniere qui l'a eu, si le focus s'egare
    prise = None               # le serveur du clavier flottant
    outils = None              # gloses, categories : les ressources des outils
    frequents = None           # les mots que la prediction met en concurrence
    derniere_dictee = ""       # ce que la dictee vient d'ecrire, pour le relire

    def __init__(self):
        super().__init__()
        reglages = lire_reglages()
        self.saisie = Saisie(translitteration=reglages.get("translitteration", True))
        self.graphie = GraphieBV.charger(chemins.TABLE_BV)
        self.mode = graphie_reglee(reglages)
        self.propositions = []
        self.nature = "prop"   # « prop » : correction ; « pred » : mot suivant
        self.champ_sensible = False
        self.contexte = ""     # ce qui a ete ecrit avant, pour la correction en contexte
        self.table = IBus.LookupTable.new(NB_PROPOSITIONS, 0, True, True)
        self.table.set_orientation(IBus.Orientation.HORIZONTAL)
        self.proprietes = self._proprietes()
        MoteurKabBoard.charger_correcteur()
        MoteurKabBoard.ouvrir_prise()
        if MoteurKabBoard.outils is None:
            MoteurKabBoard.outils = RessourcesOutils.charger(
                lexique_categories=RACINE / "data" / "lexique_categories.txt")
        if MoteurKabBoard.frequents is None:
            actifs = chemins.actifs_android()
            fichier = (actifs / "pool.frequents") if actifs else Path("/inexistant")
            MoteurKabBoard.frequents = (
                fichier.read_text(encoding="utf-8").split() if fichier.exists() else [])

    # Le moteur

    @classmethod
    def charger_correcteur(cls):
        if cls.correcteur is not None or cls.chargement is not None:
            return
        def travail():
            t0 = time.time()
            try:
                preparer_chemins()
                from correcteur import KabyleCorrecteurV2
                moteur = KabyleCorrecteurV2()
                moteur.charger()
                cls.correcteur = moteur
                print(f"kab-board : correcteur prêt en {time.time() - t0:.0f} s", flush=True)
            except Exception as erreur:
                print(f"kab-board : correcteur indisponible ({erreur})", flush=True)
        cls.chargement = threading.Thread(target=travail, daemon=True)
        cls.chargement.start()

    # Le clavier flottant

    @classmethod
    def ouvrir_prise(cls):
        """Ecoute le clavier a l'ecran : sans focus, il ne peut pas ecrire lui-meme."""
        if cls.prise is not None:
            return
        def servir():
            if PRISE.exists():
                PRISE.unlink()
            serveur = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            serveur.bind(str(PRISE))
            serveur.listen(4)
            cls.prise = serveur
            while True:
                # Un client qui raccroche ne doit pas emporter le serveur avec
                # lui : sans ce filet, une seule deconnexion brutale coupait le
                # clavier flottant pour de bon.
                try:
                    lien, _ = serveur.accept()
                    with lien:
                        donnees = lien.recv(65536).decode("utf-8", "replace").strip()
                        reponse = cls.commande(donnees)
                        if reponse is not None:
                            lien.sendall(reponse.encode("utf-8"))
                except OSError:
                    continue
                except Exception as erreur:
                    print(f"kab-board : commande refusée ({erreur})", flush=True)
        threading.Thread(target=servir, daemon=True).start()

    @classmethod
    def commande(cls, ligne):
        """Une commande du clavier flottant. Rend sa reponse, ou None."""
        # A defaut du champ courant, le dernier qui a eu le curseur : un clavier
        # a l'ecran ne doit pas se taire parce qu'un gestionnaire de fenetres a
        # deplace le focus sous le doigt de l'utilisateur.
        moteur = cls.actif or cls.dernier
        if moteur is None:
            return "SANS-CHAMP"
        verbe, _, reste = ligne.partition(" ")
        if verbe == "LETTRE":
            GLib.idle_add(moteur.touche_flottante, reste)
            return "OK"
        if verbe == "EFFACER-MOT":
            GLib.idle_add(moteur.effacer_mot)
            return "OK"
        if verbe == "EFFACER":
            GLib.idle_add(moteur.effacer_flottant)
            return "OK"
        if verbe == "ECRIRE":
            GLib.idle_add(moteur.ecrire_flottant, reste)
            return "OK"
        if verbe == "CHOISIR":
            GLib.idle_add(moteur.choisir_flottant, reste)
            return "OK"
        if verbe == "GRAPHIE":
            moteur.mode = V if reste.strip() == "v" else B
            return "OK"
        if verbe == "TRANSLIT":
            moteur.saisie.translitteration = reste.strip() == "1"
            return "OK"
        if verbe == "ETAT":
            return "\t".join([moteur.saisie.tampon, moteur.mode, moteur.nature]
                             + moteur.propositions)
        if verbe == "FICHE":
            return moteur.fiche(reste.strip() or moteur.saisie.tampon)
        if verbe == "CHERCHER":
            trouves = cls.outils.chercher_francais(reste.strip(), 8) if cls.outils else []
            return "\n".join(f"{moteur.graphie.basculer(f, moteur.mode)}\t{g}"
                              for f, g in trouves)
        if verbe == "MOTDUJOUR":
            import datetime
            jour = datetime.date.today().toordinal()
            forme, glose = cls.outils.mot_du_jour(jour) if cls.outils else ("", "")
            return f"{moteur.graphie.basculer(forme, moteur.mode)}\t{glose}"
        if verbe == "DICTEE":
            GLib.idle_add(moteur.ecrire_dictee, reste)
            return "OK"
        if verbe == "DERNIERE-DICTEE":
            return cls.derniere_dictee
        if verbe == "RELIRE":
            return moteur.relire(reste)
        return "INCONNU"

    def predire(self):
        """Le mot suivant : les frequents notes par le modele, a score egal le plus frequent."""
        c = MoteurKabBoard.correcteur
        vivier = MoteurKabBoard.frequents or []
        if c is None or not vivier or getattr(c.res, "kenlm", None) is None:
            return []
        import kenlm
        lm = c.res.kenlm
        entree, sortie = kenlm.State(), kenlm.State()
        lm.BeginSentenceWrite(entree)
        for jeton in self.contexte.split()[-8:]:
            lm.BaseScore(entree, jeton, sortie)
            entree, sortie = sortie, entree
        meilleurs = []
        for mot in vivier:
            score = lm.BaseScore(entree, mot, sortie)
            if len(meilleurs) < NB_PROPOSITIONS:
                meilleurs.append((score, mot)); meilleurs.sort(reverse=True)
            elif score > meilleurs[-1][0]:
                meilleurs[-1] = (score, mot); meilleurs.sort(reverse=True)
        return [self.graphie.basculer(m, self.mode) for _s, m in meilleurs]

    def effacer_mot(self):
        """Le mot entier, comme l'appui long sur l'effacement d'Android."""
        if self.saisie.vide:
            for _ in range(24):
                self.forward_key_event(IBus.KEY_BackSpace, 14, 0)
            return False
        self.saisie.vider()
        self._rafraichir()
        return False

    def ecrire_dictee(self, texte):
        """Le texte dicte, ecrit tel quel : la dictee n'est jamais corrigee."""
        if not texte.strip():
            return False
        ecrit = self.graphie.enrichir_texte(texte.strip(), self.mode).texte
        MoteurKabBoard.derniere_dictee = ecrit
        self.saisie.vider()
        self._ecrire(ecrit)
        return False

    def fiche(self, mot):
        """La fiche d'un mot : glose, categorie, etats libre et d'annexion."""
        if not mot:
            return ""
        outils = MoteurKabBoard.outils
        glose = outils.glose(mot) if outils else ""
        categorie = outils.categorie(mot) if outils else ""
        libre = annexion = ""
        try:
            from postprocess import vers_annexion, vers_libre, identifier_nom_etat
            etat = identifier_nom_etat(mot.lower())
            if etat == "libre":
                libre, annexion = mot, vers_annexion(mot.lower())
            elif etat == "annexion":
                libre, annexion = vers_libre(mot.lower()), mot
        except Exception:
            pass
        g = lambda f: self.graphie.basculer(f, self.mode) if f else ""
        return "\t".join([g(mot), glose, categorie, g(libre), g(annexion)])

    def relire(self, texte):
        """Relit le texte recu. Aucune application de bureau ne laisse lire la sienne,
        d'ou le presse-papiers."""
        if MoteurKabBoard.correcteur is None or not texte.strip():
            return ""
        import re as _re
        signales = []
        mots = list(_re.finditer(r"[\w\-ɣɛḍḥṭẓṣǧčṛ]+", texte, _re.UNICODE))
        for m in mots[:40]:
            gauche = texte[:m.start()].strip()[-CONTEXTE_MAX:]
            try:
                res = MoteurKabBoard.correcteur.corriger(f"{gauche} {m.group()}".strip())
            except Exception:
                continue
            corrigee = res.texte_corrige.strip().split(" ")[-1] if res.texte_corrige else ""
            corrigee = self.graphie.basculer(corrigee, self.mode)
            if corrigee and corrigee.lower() != m.group().lower():
                signales.append(f"{m.group()}\t{corrigee}")
        return "\n".join(signales)

    def touche_flottante(self, caractere):
        if not caractere:
            return False
        self.saisie.lettre(caractere)
        self._rafraichir()
        return False

    def effacer_flottant(self):
        if not self.saisie.effacer():
            self.commit_text(IBus.Text.new_from_string(""))
        self._rafraichir()
        return False

    def ecrire_flottant(self, texte):
        """Le mot en cours part tel quel, suivi de ce qui a ete demande."""
        self.saisie.vider()
        self._ecrire(texte)
        return False

    def choisir_flottant(self, forme):
        """Une proposition touchee dans le clavier a l'ecran : espace comprise."""
        self.saisie.vider()
        self._ecrire(forme, espace=True)
        return False

    # Touches

    def do_process_key_event(self, keyval, keycode, state):
        if state & IBus.ModifierType.RELEASE_MASK:
            return False
        controle = state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK)
        if controle:
            return False
        altgr = bool(state & IBus.ModifierType.MOD5_MASK)

        if keyval == IBus.KEY_BackSpace:
            if self.saisie.effacer():
                self._rafraichir()
                return True
            return False

        if keyval in (IBus.KEY_Escape,):
            if not self.saisie.vide:
                self._ecrire(self.saisie.vider())
                return True
            return False

        # Une touche de 1 a 6 choisit une proposition, quand il y en a.
        if self.propositions and IBus.KEY_1 <= keyval <= IBus.KEY_6:
            choix = choix_par_chiffre(keyval - IBus.KEY_1 + 1, self.propositions)
            if choix:
                self.saisie.vider()
                self._ecrire(choix, espace=True)
                return True

        if self.propositions and keyval in (IBus.KEY_Up, IBus.KEY_Down,
                                            IBus.KEY_Left, IBus.KEY_Right):
            if keyval in (IBus.KEY_Down, IBus.KEY_Right):
                self.table.cursor_down()
            else:
                self.table.cursor_up()
            self.update_lookup_table(self.table, True)
            return True

        if self.propositions and keyval in (IBus.KEY_Return, IBus.KEY_KP_Enter):
            # L'entree valide la proposition designee dans le panneau.
            rang = self.table.get_cursor_pos()
            choix = choix_par_chiffre(rang + 1, self.propositions)
            if choix and rang > 0:
                self.saisie.vider()
                self._ecrire(choix, espace=True)
                return True

        if keyval in (IBus.KEY_space, IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_Tab):
            # Rien n'est corrige d'office : le mot part tel qu'il a ete tape.
            if not self.saisie.vide:
                self._ecrire(self.saisie.vider())
            return False

        # keyval_to_unicode rend deja une chaine dans les liaisons Python.
        caractere = IBus.keyval_to_unicode(keyval) or ""
        if caractere and est_lettre(caractere):
            self.saisie.lettre(caractere, altgr=altgr)
            self._rafraichir()
            return True

        if caractere:                      # ponctuation : elle clot le mot
            if not self.saisie.vide:
                self._ecrire(self.saisie.vider())
            return False
        return False

    # Affichage

    def _rafraichir(self):
        mot = self.saisie.tampon
        if not mot:
            self.hide_preedit_text()
            self.hide_lookup_table()
            self.propositions = []
            return
        texte = IBus.Text.new_from_string(mot)
        texte.append_attribute(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE,
                               0, len(mot))
        self.update_preedit_text(texte, len(mot), True)
        self._proposer(mot)

    def _proposer(self, mot):
        if MoteurKabBoard.correcteur is None or self.champ_sensible:
            return
        threading.Thread(target=self._calculer, args=(mot, self.contexte),
                         daemon=True).start()

    def _calculer(self, mot, contexte):
        c = MoteurKabBoard.correcteur
        try:
            res = c.corriger(f"{contexte} {mot}".strip())
            corrigee = res.texte_corrige.strip().split(" ")[-1] if res.texte_corrige else ""
            cinq = [x["candidat"] for x in c.top_candidats(mot, 5)]
        except Exception:
            return
        # La composition de la barre d'Android, sans un ecart : la correction en
        # contexte en tete, meme quand elle est le mot lui-meme, car elle dit
        # alors que le correcteur, contexte compris, l'ecrirait ainsi, puis le
        # top-5 du mot isole, la casse du mot rendue a chaque forme.
        formes = []
        for f in [corrigee] + cinq:
            if not f:
                continue
            g = casser_comme(mot, self.graphie.basculer(f, self.mode))
            if g and g not in formes:
                formes.append(g)
        GLib.idle_add(self._montrer, mot, formes[:NB_PROPOSITIONS])

    def _montrer(self, mot, formes):
        if self.saisie.tampon != mot:        # la frappe a continue
            return False
        self.propositions = formes
        self.nature = "prop"
        self.table.clear()
        for forme in formes:
            self.table.append_candidate(IBus.Text.new_from_string(forme))
        if formes:
            self.update_lookup_table(self.table, True)
        else:
            self.hide_lookup_table()
        return False

    def _espace_manquant(self):
        """Une espace apres la forme choisie, sauf s'il y en a deja une : sinon corriger
        au milieu d'une phrase en laisserait deux."""
        try:
            texte, curseur, _fin = self.get_surrounding_text()
            suite = texte.get_text()[curseur:]
            return not (suite and suite[0].isspace())
        except Exception:
            return True

    def _ecrire(self, texte, espace=False):
        if not texte:
            return
        texte = self.graphie.basculer(texte, self.mode)
        if espace and self._espace_manquant():
            texte += " "
        self.commit_text(IBus.Text.new_from_string(texte))
        self.hide_preedit_text()
        self.hide_lookup_table()
        self.propositions = []
        # Le contexte sert a la correction du mot suivant, comme la barre du
        # clavier Android borne le sien a soixante caracteres.
        self.contexte = f"{self.contexte} {texte}".strip()[-CONTEXTE_MAX:]
        # Comme sur le telephone : le mot ecrit, la barre montre ce qui pourrait
        # suivre, plutot que de rester vide.
        threading.Thread(target=self._predire_en_fond, daemon=True).start()

    def _predire_en_fond(self):
        formes = self.predire()
        GLib.idle_add(self._montrer_predictions, formes)

    def _montrer_predictions(self, formes):
        if not self.saisie.vide:          # la frappe a repris : les propositions priment
            return False
        self.propositions = formes
        self.nature = "pred"
        self.table.clear()
        for forme in formes:
            self.table.append_candidate(IBus.Text.new_from_string(forme))
        if formes:
            self.update_lookup_table(self.table, True)
        else:
            self.hide_lookup_table()
        return False

    # Reglages

    def _proprietes(self):
        liste = IBus.PropList()
        self.prop_graphie = IBus.Property(
            key="graphie", prop_type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("Graphie : b"),
            tooltip=IBus.Text.new_from_string("Écrire avec b ou avec v"),
            sensitive=True, visible=True, state=IBus.PropState.UNCHECKED)
        liste.append(self.prop_graphie)
        self.prop_translit = IBus.Property(
            key="translitteration", prop_type=IBus.PropType.TOGGLE,
            label=IBus.Text.new_from_string("gh → ɣ"),
            tooltip=IBus.Text.new_from_string("Écrire comme on parle"),
            sensitive=True, visible=True, state=IBus.PropState.CHECKED)
        liste.append(self.prop_translit)
        return liste

    def do_focus_in(self):
        MoteurKabBoard.actif = self
        MoteurKabBoard.dernier = self
        self.register_properties(self.proprietes)

    def do_focus_out(self):
        if MoteurKabBoard.actif is self:
            MoteurKabBoard.actif = None
        self.do_reset()

    def do_set_content_type(self, purpose, hints):
        """Rien dans les champs de mot de passe, que le systeme annonce."""
        self.champ_sensible = purpose in (
            IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN)
        if self.champ_sensible:
            self.saisie.vider()
            self.hide_preedit_text()
            self.hide_lookup_table()
            self.propositions = []

    def do_property_activate(self, nom, etat):
        if nom == "graphie":
            self.mode = V if self.mode == B else B
            self.prop_graphie.set_label(
                IBus.Text.new_from_string(f"Graphie : {self.mode}"))
            self.update_property(self.prop_graphie)
        elif nom == "translitteration":
            self.saisie.translitteration = not self.saisie.translitteration

    def do_candidate_clicked(self, index, _bouton, _etat):
        """Le clic sur une proposition du panneau. Sans cette methode, il ne repond pas."""
        choix = choix_par_chiffre(index + 1, self.propositions)
        if choix:
            self.saisie.vider()
            self._ecrire(choix, espace=True)

    def do_cursor_up(self):
        self.table.cursor_up()
        self.update_lookup_table(self.table, True)
        return True

    def do_cursor_down(self):
        self.table.cursor_down()
        self.update_lookup_table(self.table, True)
        return True

    def do_page_up(self):
        self.table.page_up()
        self.update_lookup_table(self.table, True)
        return True

    def do_page_down(self):
        self.table.page_down()
        self.update_lookup_table(self.table, True)
        return True

    def do_reset(self):
        self.saisie.vider()
        self.contexte = ""
        self.hide_preedit_text()
        self.hide_lookup_table()

    def do_disable(self):
        self.do_reset()


def principal():
    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        print("kab-board : aucun démon IBus", file=sys.stderr)
        return 1
    bus.connect("disconnected", lambda _b: IBus.quit())
    fabrique = IBus.Factory.new(bus.get_connection())
    fabrique.add_engine("kab-board", MoteurKabBoard.__gtype__)
    if "--ibus" in sys.argv:
        bus.request_name("taqbaylit.kabboard", 0)
    else:
        composant = IBus.Component.new(
            "taqbaylit.kabboard", "Kab-board", "1.0", "GPL-3.0",
            "Massil Aoudj", "", "", "kab-board")
        moteur = IBus.EngineDesc.new(
            "kab-board", "Kabyle (kab-board)",
            "Correcteur kabyle : six propositions, graphie b ou v",
            "kab", "GPL-3.0", "Massil Aoudj", "", "fr")
        composant.add_engine(moteur)
        bus.register_component(composant)
        bus.set_global_engine_async("kab-board", -1, None, None, None)
    IBus.main()
    return 0


if __name__ == "__main__":
    sys.exit(principal())
