#!/usr/bin/env python3
"""Une fenetre pour ecrire et relire.

Les lettres kabyles sous les doigts, la barre des six propositions et le reglage
b ou v. Clavier physique ou touches a l'ecran, les deux alimentent le meme texte.
"""
import re
import sys
import threading
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Pango

RACINE = Path(__file__).resolve().parent.parent          # le dossier linux/
DEPOT = RACINE.parent                                    # la racine de kab-board
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from graphie_bv import GraphieBV, B, V
sys.path.insert(0, str(RACINE / "ibus"))
from saisie import longueur_mots_avant

# Les ressources du correcteur. Le pipeline les attend dans un dossier « data » ;
# ici elles sont a plat, d'ou ces chemins explicites, poses avant tout import du
# pipeline lui-meme.
sys.path.insert(0, str(RACINE))
import chemins
DONNEES = chemins.correcteur()

MOT = re.compile(r"[\w\-ɣɛḍḥṭẓṣǧčṛ]+", re.UNICODE)
NB_PROPOSITIONS = 6

# La disposition de kab-board, rangee par rangee : la lettre, puis ce que
# l'appui long propose. Reprise telle quelle de KeyboardLayoutManager, pour que
# le bureau et le telephone ne divergent pas.
RANGEES = [
    [("a", "â", "à"), ("z", "ẓ"), ("e", "é", "è"), ("r", "ṛ"), ("t", "ṭ"),
     ("y",), ("u", "o", "û"), ("i", "î", "ï"), ("ɣ",), ("p",)],
    [("q",), ("s", "ṣ"), ("d", "ḍ"), ("f",), ("g", "ǧ"), ("h", "ḥ"),
     ("j",), ("k",), ("l",), ("m",)],
    [("⇧",), ("w",), ("x",), ("c", "č"), ("v",), ("b",), ("n",), ("ɛ",), ("⌫",)],
    [("123",), (",", ";", ":"), ("ḍ",), ("-",), ("␣",), ("ḥ",), (".", "!", "?"), ("⏎",)],
]

SYMBOLES = [
    [("1",), ("2",), ("3",), ("4",), ("5",), ("6",), ("7",), ("8",), ("9",), ("0",)],
    [("@",), ("#",), ("€",), ("%",), ("&",), ("*",), ("(",), (")",), ("/",), ("\\",)],
    [("+",), ("=",), ('"',), ("'",), (":",), (";",), ("!",), ("?",), ("⌫",)],
    [("ABC",), (",",), ("_",), ("-",), ("␣",), ("«",), ("»",), ("⏎",)],
]

# Les lettres propres au kabyle, cerclees comme dans le manuel.
KABYLES = {"ɣ", "ɛ", "ḍ", "ḥ"}

CSS = b"""
.touche { font-size: 17px; min-width: 34px; min-height: 42px; padding: 0; }
.touche-kabyle { box-shadow: inset 0 0 0 2px #00843F; font-weight: bold; }
.touche-fonction { font-size: 13px; }
.proposition { font-size: 15px; }
.tete { font-weight: bold; }
"""


def preparer_chemins():
    import config
    config.BASE = DONNEES
    config.KENLM_BIN = DONNEES / "kabyle_3gram.binary"
    config.AMYAG_FORMES = DONNEES / "amyag_formes.txt"
    config.POS_MODEL = DONNEES / "kab-POS-tagl.joblib"
    config.LEXCAT_FILE = RACINE / "data" / "lexique_categories.txt"
    config.WORDNET_JSON = DONNEES / "wordnet" / "dictionnaire_sémantique_racinale_kabyle_V1.json"


class Fenetre(Gtk.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title="Kab-board")
        self.set_default_size(760, 720)
        self.correcteur = None
        self.completion = None
        self.graphie = GraphieBV.charger(chemins.TABLE_BV)
        self.mode = V
        self.calcul = None
        self.dernier_mot = ""
        self.majuscule = False      # une lettre, puis retour aux minuscules
        self.verrou = False         # jusqu'au prochain appui sur la touche
        self.symboles = False

        fournisseur = Gtk.CssProvider()
        fournisseur.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), fournisseur,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self._entete()
        colonne = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(colonne)
        colonne.append(self._zone_texte())
        colonne.append(self._barre_propositions())
        self.clavier = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                               margin_start=6, margin_end=6, margin_bottom=8)
        colonne.append(self.clavier)
        self._dessiner_clavier()
        colonne.append(self._etat())

        threading.Thread(target=self._charger_moteur, daemon=True).start()

    # Interface

    def _entete(self):
        tete = Gtk.HeaderBar()
        self.set_titlebar(tete)
        boite = Gtk.Box(css_classes=["linked"])
        self.bouton_b = Gtk.ToggleButton(label="Écrire avec b")
        self.bouton_v = Gtk.ToggleButton(label="Écrire avec v", active=True)
        self.bouton_b.connect("toggled", self._changer_graphie, B)
        self.bouton_v.connect("toggled", self._changer_graphie, V)
        boite.append(self.bouton_b)
        boite.append(self.bouton_v)
        tete.pack_start(boite)
        relire = Gtk.Button(label="Relire")
        relire.connect("clicked", lambda _b: self._relire())
        tete.pack_end(relire)

    def _zone_texte(self):
        self.tampon = Gtk.TextBuffer()
        self.tampon.connect("changed", self._texte_change)
        self.vue = Gtk.TextView(buffer=self.tampon, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                left_margin=14, right_margin=14,
                                top_margin=14, bottom_margin=14)
        self.vue.get_pango_context().set_font_description(Pango.FontDescription("Sans 15"))
        return Gtk.ScrolledWindow(vexpand=True, child=self.vue)

    def _barre_propositions(self):
        self.barre = Gtk.Box(spacing=6, margin_start=8, margin_end=8,
                             margin_top=6, margin_bottom=6, homogeneous=True)
        cadre = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.NEVER, child=self.barre)
        cadre.set_size_request(-1, 48)
        return cadre

    def _etat(self):
        self.etat = Gtk.Label(label="Chargement du correcteur…", xalign=0,
                              margin_start=12, margin_bottom=6,
                              css_classes=["dim-label"])
        return self.etat

    # Le clavier

    def _dessiner_clavier(self):
        enfant = self.clavier.get_first_child()
        while enfant:
            suivant = enfant.get_next_sibling()
            self.clavier.remove(enfant)
            enfant = suivant
        for rangee in (SYMBOLES if self.symboles else RANGEES):
            ligne = Gtk.Box(spacing=4, homogeneous=False)
            for touche in rangee:
                ligne.append(self._touche(touche))
            self.clavier.append(ligne)

    def _touche(self, touche):
        libelle = touche[0]
        bouton = Gtk.Button(css_classes=["touche"])
        bouton.set_hexpand(True)
        if libelle == "␣":
            bouton.set_label("Taqbaylit")
            bouton.add_css_class("touche-fonction")
            bouton.set_hexpand(True)
            bouton.set_size_request(220, -1)
        elif libelle in ("123", "ABC", "⇧", "⌫", "⏎"):
            bouton.set_label(libelle)
            bouton.add_css_class("touche-fonction")
        else:
            # Les variantes de l'appui long s'annoncent en petit, comme sur le
            # telephone ou elles s'inscrivent dans le coin de la touche.
            sup = " ".join(touche[1:])
            bouton.set_child(Gtk.Label(
                label=f"{libelle}<span size='x-small' alpha='55%'> {sup}</span>"
                      if sup else libelle,
                use_markup=True))
            if libelle in KABYLES:
                bouton.add_css_class("touche-kabyle")
        bouton.connect("clicked", self._touche_pressee, touche)
        if len(touche) > 1:
            appui = Gtk.GestureLongPress()
            appui.connect("pressed", self._appui_long, touche, bouton)
            bouton.add_controller(appui)
        return bouton

    def _touche_pressee(self, _bouton, touche):
        libelle = touche[0]
        if libelle == "⇧":
            # Un appui : la lettre suivante en capitale. Deux : verrouillage.
            # Trois : retour aux minuscules. Comme sur le telephone.
            if self.verrou:
                self.verrou = self.majuscule = False
            elif self.majuscule:
                self.verrou = True
            else:
                self.majuscule = True
            return
        if libelle in ("123", "ABC"):
            self.symboles = not self.symboles
            self._dessiner_clavier()
            return
        if libelle == "⌫":
            self._effacer()
            return
        self._ecrire({"␣": " ", "⏎": "\n"}.get(libelle, libelle))

    def _appui_long(self, _geste, _x, _y, touche, bouton):
        fenetre = Gtk.Popover()
        fenetre.set_parent(bouton)
        boite = Gtk.Box(spacing=4, margin_start=4, margin_end=4,
                        margin_top=4, margin_bottom=4)
        for variante in touche[1:]:
            b = Gtk.Button(label=variante, css_classes=["touche"])
            b.connect("clicked", lambda _b, v=variante: (self._ecrire(v), fenetre.popdown()))
            boite.append(b)
        fenetre.set_child(boite)
        fenetre.popup()

    def _ecrire(self, texte):
        if (self.majuscule or self.verrou) and texte.isalpha():
            texte = texte.upper()
            if not self.verrou:
                self.majuscule = False
        self.tampon.insert_at_cursor(texte)
        self.vue.grab_focus()

    def _effacer(self):
        curseur = self.tampon.get_iter_at_mark(self.tampon.get_insert())
        debut = curseur.copy()
        if debut.backward_char():
            self.tampon.delete(debut, curseur)

    # Moteur

    def _charger_moteur(self):
        t0 = time.time()
        try:
            preparer_chemins()
            from correcteur import KabyleCorrecteurV2
            moteur = KabyleCorrecteurV2()
            moteur.charger()
        except Exception as erreur:
            GLib.idle_add(self._dire, f"Correcteur indisponible : {erreur}")
            return
        self.correcteur = moteur
        from completion import Completion
        self.completion = Completion(moteur.res)
        self.completion.candidats("a")       # le vocabulaire, construit d'avance
        GLib.idle_add(self._dire, f"Correcteur prêt en {time.time() - t0:.0f} s. "
                                  f"{len(self.graphie.vers_v)} formes à double graphie.")

    def _dire(self, message):
        self.etat.set_text(message)
        return False

    # Frappe

    def _texte_change(self, _tampon):
        if self.correcteur is None:
            return
        mot, _debut, _fin = self._mot_courant()
        if mot == self.dernier_mot:
            return
        self.dernier_mot = mot
        if self.calcul:
            GLib.source_remove(self.calcul)
        # Comme sur le telephone : on laisse passer la rafale de frappe.
        self.calcul = GLib.timeout_add(120, self._proposer)

    def _mot_courant(self):
        curseur = self.tampon.get_iter_at_mark(self.tampon.get_insert())
        avant = self.tampon.get_text(self.tampon.get_start_iter(), curseur, False)
        trouve = None
        for m in MOT.finditer(avant):
            trouve = m
        if trouve is None or trouve.end() != len(avant):
            return "", 0, 0
        return trouve.group(), trouve.start(), trouve.end()

    def _proposer(self):
        self.calcul = None
        mot, debut, _fin = self._mot_courant()
        if not mot:
            self._afficher([])
            return False
        gauche = self._texte()[:debut].strip()[-60:]
        threading.Thread(target=self._calculer, args=(gauche, mot), daemon=True).start()
        return False

    def _calculer(self, gauche, mot):
        t0 = time.time()
        # De 1 a 3 lettres, la barre complete le mot, quand quelque chose commence ainsi.
        if self.completion is not None:
            try:
                from normalisation import normalize
                barre = self.completion.barre(gauche, normalize(mot))
            except Exception:
                barre = None
            if barre:
                formes = []
                for f in barre:
                    g = self.graphie.basculer(f, self.mode)
                    if mot[:1].isupper():
                        g = g.upper() if len(mot) > 1 and mot == mot.upper() else g[:1].upper() + g[1:]
                    if g not in formes:
                        formes.append(g)
                GLib.idle_add(self._afficher, formes[:NB_PROPOSITIONS], mot,
                              (time.time() - t0) * 1000, 0, True)
                return
        try:
            res = self.correcteur.corriger(f"{gauche} {mot}".strip())
            corrigee = res.texte_corrige.strip().split(" ")[-1] if res.texte_corrige else ""
            cinq = [c["candidat"] for c in self.correcteur.top_candidats(mot, 5)]
        except Exception as erreur:
            GLib.idle_add(self._dire, f"Erreur du correcteur : {erreur}")
            return
        # Rattachee aux mots d'avant (« tamurt iw » -> « tamurt-iw »), la tete les
        # remplace aussi, et en prend la casse.
        mots_avant = (getattr(res, "couverture_fin", 1) - 1) if corrigee else 0
        if mots_avant > 0 and longueur_mots_avant(gauche + " ", mots_avant) < 0:
            # Fondu par-dessus une virgule, que le correcteur ne voit pas : le mot seul.
            corrigee, mots_avant = corrigee.rsplit("-", 1)[-1], 0
        precedents = gauche.split()
        modele_tete = precedents[-mots_avant] if 0 < mots_avant <= len(precedents) else mot
        # Comme la barre d'Android : la correction en contexte d'abord, puis le
        # top-5, chaque forme a la casse du mot tape.
        formes = []
        for rang, f in enumerate([corrigee] + cinq):
            if not f:
                continue
            modele = modele_tete if rang == 0 else mot
            g = self.graphie.basculer(f, self.mode)
            if modele[:1].isupper():
                g = g.upper() if len(modele) > 1 and modele == modele.upper() else g[:1].upper() + g[1:]
            if g and g not in formes:
                formes.append(g)
        GLib.idle_add(self._afficher, formes[:NB_PROPOSITIONS], mot,
                      (time.time() - t0) * 1000, mots_avant)

    def _afficher(self, formes, mot="", ms=0.0, mots_avant=0, completion=False):
        enfant = self.barre.get_first_child()
        while enfant:
            suivant = enfant.get_next_sibling()
            self.barre.remove(enfant)
            enfant = suivant
        for rang, forme in enumerate(formes):
            b = Gtk.Button(label=forme, css_classes=["proposition"])
            if rang == 0 and not completion:
                b.add_css_class("suggested-action")
            b.connect("clicked", self._remplacer, forme, mots_avant if rang == 0 else 0)
            self.barre.append(b)
        if mot:
            self._dire(f"« {mot} » : {len(formes)} propositions en {ms:.0f} ms")
        return False

    def _remplacer(self, _bouton, forme, mots_avant=0):
        _mot, debut, fin = self._mot_courant()
        if debut == fin:
            return
        if mots_avant > 0:
            k = longueur_mots_avant(self._texte()[:debut], mots_avant)
            if k > 0:
                debut -= k
        i_debut = self.tampon.get_iter_at_offset(debut)
        i_fin = self.tampon.get_iter_at_offset(fin)
        self.tampon.delete(i_debut, i_fin)
        self.tampon.insert(i_debut, forme)
        self.vue.grab_focus()

    # Graphie

    def _changer_graphie(self, bouton, mode):
        if not bouton.get_active():
            return
        self.mode = mode
        (self.bouton_v if mode == B else self.bouton_b).set_active(False)
        self._reecrire_texte()
        self._proposer()

    def _reecrire_texte(self):
        """Le texte deja ecrit suit le reglage, comme les propositions."""
        texte = self._texte()
        if not texte:
            return
        nouveau = MOT.sub(lambda m: self.graphie.basculer(m.group(), self.mode), texte)
        if nouveau != texte:
            self.tampon.set_text(nouveau)

    def _texte(self):
        return self.tampon.get_text(self.tampon.get_start_iter(),
                                    self.tampon.get_end_iter(), False)

    # Relire

    def _relire(self):
        if self.correcteur is None:
            return
        threading.Thread(target=self._relire_fond, args=(self._texte(),), daemon=True).start()

    def _relire_fond(self, texte):
        signales = []
        mots = list(MOT.finditer(texte))
        for m in mots[:40]:
            gauche = texte[:m.start()].strip()[-60:]
            res = self.correcteur.corriger(f"{gauche} {m.group()}".strip())
            corrigee = res.texte_corrige.strip().split(" ")[-1] if res.texte_corrige else ""
            corrigee = self.graphie.basculer(corrigee, self.mode)
            portee = m.group()
            avant = getattr(res, "couverture_fin", 1) - 1
            if avant > 0:
                # « tamurt iw » -> « tamurt-iw » : la correction vaut pour les deux mots.
                k = longueur_mots_avant(texte[:m.start()], avant)
                if k <= 0:
                    continue
                portee = texte[m.start() - k:m.end()]
            if corrigee and corrigee.lower() != portee.lower():
                signales.append((portee, corrigee))
        GLib.idle_add(self._montrer_relecture, signales, len(mots))

    def _montrer_relecture(self, signales, total):
        boite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                        margin_start=16, margin_end=16, margin_top=16, margin_bottom=16)
        if not signales:
            boite.append(Gtk.Label(label="Rien à signaler.", xalign=0))
        for mot, propose in signales:
            boite.append(Gtk.Label(label=f"{mot}  →  {propose}", xalign=0))
        fenetre = Gtk.Window(transient_for=self, modal=True, title="Relecture",
                             default_width=360, default_height=320)
        fenetre.set_child(Gtk.ScrolledWindow(child=boite))
        fenetre.present()
        self._dire(f"Relecture : {len(signales)} mot(s) signalé(s) sur {total}.")
        return False


class Application(Gtk.Application):

    def __init__(self):
        super().__init__(application_id="taqbaylit.kabboard.bureau")

    def do_activate(self):
        Fenetre(self).present()


if __name__ == "__main__":
    sys.exit(Application().run(sys.argv))
