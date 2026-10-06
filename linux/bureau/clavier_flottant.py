#!/usr/bin/env python3
"""Le clavier a l'ecran, pose au-dessus des autres fenetres.

Il ne prend jamais le focus, donc il n'ecrit pas lui-meme : il envoie ses touches
au moteur de saisie par une prise locale, et c'est lui qui ecrit. Le moteur doit
donc tourner (ibus/kab_ibus.py) et etre la source de saisie active.
"""
import os
import shutil
import socket
import sys
import tempfile
import threading
from pathlib import Path

# Sous Wayland, une fenetre ordinaire ne peut ni se placer, ni rester au-dessus,
# ni refuser le focus : c'est le compositeur qui en decide, et GNOME n'offre pas
# le protocole des claviers a l'ecran. Par Xwayland, les regles de X11
# s'appliquent de nouveau, et ce sont celles dont ce clavier a besoin.
# La session pose souvent GDK_BACKEND=wayland : il faut donc l'ecraser, pas
# seulement le completer.
if os.environ.get("XDG_SESSION_TYPE") == "wayland" and os.environ.get("DISPLAY"):
    os.environ["GDK_BACKEND"] = "x11"

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

PRISE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "kab-board.sock"

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

KABYLES = {"ɣ", "ɛ", "ḍ", "ḥ"}

CSS = b"""
.touche { font-size: 16px; padding: 6px 2px; }
.touche-kabyle { border: 2px solid #00843F; font-weight: bold; }
.fonction { font-size: 12px; }
.proposition { font-size: 14px; padding: 2px 8px; }
.correction { border-bottom: 3px solid #00843F; font-weight: bold; }
.candidat   { border-bottom: 3px solid #0072BB; }
.prediction { border-bottom: 3px solid #A86A00; }
.tete { font-size: 12px; }
"""


def parler(commande: str) -> str:
    """Envoie une commande au moteur de saisie. Rend sa réponse, ou ''."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as lien:
            lien.settimeout(1.0)
            lien.connect(str(PRISE))
            lien.sendall(commande.encode("utf-8"))
            return lien.recv(4096).decode("utf-8", "replace")
    except OSError:
        return ""


def bouton_sans_focus(**arguments):
    """Un bouton qui ne prend jamais le focus.

    Le clavier ecrit ailleurs que chez lui : si une touche reclamait le focus,
    l'application ou l'on tape le perdrait, et la saisie n'irait plus nulle part.
    """
    b = Gtk.Button(**arguments)
    b.set_can_focus(False)
    b.set_focus_on_click(False)
    return b


class Clavier(Gtk.Window):

    def __init__(self):
        super().__init__(title="Kab-board")
        self.symboles = False
        self.majuscule = False
        self.verrou = False
        self.enregistrement = None      # le processus arecord, quand il tourne
        self.onde = None
        self.dernieres_propositions = None
        self.translitteration = True
        self.champ_recherche = None     # ou taper, quand fr → kab est ouvert
        self._depart = None             # point de prise, pendant un deplacement

        # Au-dessus de tout, sur tous les bureaux, et surtout : jamais le focus.
        # Sans cela, le clic sur une touche volerait le curseur a l'application
        # dans laquelle on veut ecrire, et la saisie n'irait plus nulle part.
        #
        # accept_focus ne suffit pas : une fenetre ordinaire et decoree, le
        # gestionnaire la focalise quand meme au clic. Le type DOCK, lui, ne se
        # focalise pas ; en echange il n'a pas de barre de titre, alors la tete
        # sert de poignee.
        self.set_keep_above(True)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_can_focus(False)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_default_size(720, 260)
        self.stick()
        # Au premier affichage, pas a la creation : avant d'etre affichee, la
        # fenetre ne connait ni sa taille definitive ni le moniteur.
        self.connect("map-event", self._se_placer)
        self.connect("destroy", Gtk.main_quit)

        fournisseur = Gtk.CssProvider()
        fournisseur.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), fournisseur,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        colonne = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        colonne.set_margin_start(6); colonne.set_margin_end(6)
        colonne.set_margin_top(6); colonne.set_margin_bottom(6)
        self.add(colonne)

        colonne.pack_start(self._tete(), False, False, 0)
        colonne.pack_start(self._outils(), False, False, 0)
        self.barre = Gtk.Box(spacing=6, homogeneous=True)
        colonne.pack_start(self.barre, False, False, 0)
        # Un panneau prend la place des touches, a leur hauteur, comme sur le
        # telephone : la fenetre ne doit pas changer de taille sous le doigt.
        self.panneau = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        colonne.pack_start(self.panneau, True, True, 0)
        self.touches = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        colonne.pack_start(self.touches, True, True, 0)
        self._dessiner()

        # Le mot en cours et ses propositions vivent dans le moteur : on les lui
        # demande, plutot que d'en tenir une seconde copie qui divergerait.
        GLib.timeout_add(250, self._suivre)

    # Tete

    def _tete(self):
        """La tete : l'etat, le choix de graphie, et de quoi deplacer ou fermer.

        Sans barre de titre, c'est elle qui sert de poignee : un glisser dessus
        deplace la fenetre.
        """
        ligne = Gtk.Box(spacing=6)
        poignee = Gtk.EventBox()
        poignee.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                           | Gdk.EventMask.BUTTON_RELEASE_MASK
                           | Gdk.EventMask.POINTER_MOTION_MASK)
        poignee.connect("button-press-event", self._prendre)
        poignee.connect("motion-notify-event", self._glisser)
        poignee.connect("button-release-event", self._lacher)
        self.etat = Gtk.Label(label="…", xalign=0)
        self.etat.get_style_context().add_class("tete")
        poignee.add(self.etat)
        ligne.pack_start(poignee, True, True, 0)
        for libelle, valeur in (("b", "b"), ("v", "v")):
            b = bouton_sans_focus(label=f"Graphie {libelle}")
            b.get_style_context().add_class("fonction")
            b.connect("clicked", lambda _b, v=valeur: parler(f"GRAPHIE {v}"))
            ligne.pack_start(b, False, False, 0)
        fermer = bouton_sans_focus(label="✕")
        fermer.get_style_context().add_class("fonction")
        fermer.connect("clicked", lambda _b: self.destroy())
        ligne.pack_start(fermer, False, False, 0)
        return ligne

    def _se_placer(self, _fenetre, _evenement=None):
        """En bas de l'ecran, centre, comme un clavier a l'ecran doit l'etre.

        Sans barre de titre, le gestionnaire ne place plus la fenetre : elle
        s'en charge, puis l'utilisateur la deplace par la tete s'il veut.
        """
        affichage = Gdk.Display.get_default()
        moniteur = affichage.get_primary_monitor() or affichage.get_monitor(0)
        if moniteur is None:
            return
        zone = moniteur.get_workarea()
        largeur, hauteur = self.get_size()
        self.move(zone.x + (zone.width - largeur) // 2,
                  zone.y + zone.height - hauteur - 20)

    def _prendre(self, _poignee, evenement):
        """Debut du glisser : on retient d'ou l'on part.

        Le gestionnaire de fenetres refuse de deplacer une fenetre de type DOCK
        par la poignee habituelle (begin_move_drag). On la deplace donc
        soi-meme, ce que X autorise.
        """
        if evenement.button != 1:
            return False
        x, y = self.get_position()
        self._depart = (evenement.x_root - x, evenement.y_root - y)
        return True

    def _glisser(self, _poignee, evenement):
        if self._depart is None:
            return False
        dx, dy = self._depart
        self.move(int(evenement.x_root - dx), int(evenement.y_root - dy))
        return True

    def _lacher(self, _poignee, _evenement):
        self._depart = None
        return True

    # Outils

    def _outils(self):
        ligne = Gtk.Box(spacing=4)
        for libelle, action in (("🎤 Dicter", self._dicter),
                                ("gh → ɣ", self._basculer_translit),
                                ("Asegzawal", self._fiche),
                                ("fr → kab", self._recherche),
                                ("Relire", self._relire),
                                ("Mot du jour", self._mot_du_jour),
                                ("✕", self._fermer_panneau)):
            b = bouton_sans_focus(label=libelle)
            b.get_style_context().add_class("fonction")
            b.connect("clicked", lambda _b, a=action: a())
            ligne.pack_start(b, True, True, 0)
        return ligne

    def _basculer_translit(self):
        """La bascule « ecrire comme on parle », la ou elle est sur le telephone."""
        self.translitteration = not self.translitteration
        parler(f"TRANSLIT {'1' if self.translitteration else '0'}")
        p = self._panneau("Écrire comme on parle", garder_touches=True)
        self._ligne(p, "Activé : gh → ɣ, dh → ḍ, kh → x, aa → ɛ, ou → u"
                       if self.translitteration else "Désactivé.")

    def _panneau(self, titre, garder_touches=False):
        """Vide le panneau. Les touches cedent la place, sauf pour la recherche."""
        for enfant in self.panneau.get_children():
            self.panneau.remove(enfant)
        self.champ_recherche = None
        if garder_touches:
            self.touches.show_all()
        else:
            self.touches.hide()
        etiquette = Gtk.Label(xalign=0)
        etiquette.set_markup(f"<b>{GLib.markup_escape_text(titre)}</b>")
        self.panneau.pack_start(etiquette, False, False, 0)
        self.panneau.show_all()
        return self.panneau

    def _fermer_panneau(self):
        for enfant in self.panneau.get_children():
            self.panneau.remove(enfant)
        self.touches.show_all()

    def _ligne(self, panneau, texte, action=None):
        if action is None:
            etiquette = Gtk.Label(label=texte, xalign=0, wrap=True)
            panneau.pack_start(etiquette, False, False, 0)
            panneau.show_all()
            return
        b = bouton_sans_focus(label=texte)
        b.get_style_context().add_class("proposition")
        b.connect("clicked", lambda _b: action())
        panneau.pack_start(b, False, False, 0)
        panneau.show_all()

    def _dicter(self):
        """Un clic ecoute, un second transcrit. Hors de la boucle graphique, qui gelerait."""
        import subprocess
        if self.enregistrement is not None:
            self.enregistrement.terminate()
            self.enregistrement = None
            p = self._panneau("Dictée")
            self._ligne(p, "Transcription…")
            threading.Thread(target=self._transcrire, args=(p,), daemon=True).start()
            return
        # Dossier prive (700), efface apres la transcription.
        self.onde = Path(tempfile.mkdtemp(prefix="kab-dictee-")) / "dictee.wav"
        self.enregistrement = subprocess.Popen(
            ["arecord", "-q", "-f", "S16_LE", "-c", "1", "-r", "16000",
             "-d", "30", str(self.onde)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p = self._panneau("Dictée")
        self._ligne(p, "J'écoute… cliquez de nouveau sur 🎤 pour arrêter.")

    def _transcrire(self, panneau):
        import subprocess
        venv = Path.home() / "correcteur-bv" / ".venv-voix" / "bin" / "python"
        script = Path(__file__).resolve().parent / "dictee.py"
        python = str(venv) if venv.exists() else sys.executable
        texte = ""
        try:
            sortie = subprocess.run([python, str(script), "--fichier", str(self.onde)],
                                    capture_output=True, text=True, timeout=120)
            texte = sortie.stdout.strip()
        except Exception as erreur:
            print(f"dictée : {erreur}", file=sys.stderr)
        finally:
            shutil.rmtree(self.onde.parent, ignore_errors=True)
        GLib.idle_add(self._dictee_finie, panneau, texte)

    def _dictee_finie(self, panneau, texte):
        for enfant in panneau.get_children()[1:]:
            panneau.remove(enfant)
        if not texte:
            self._ligne(panneau, "Rien entendu.")
            return False
        parler(f"DICTEE {texte}")
        self._ligne(panneau, f"« {texte} »")
        # Comme sur le telephone : la dictee n'est pas corrigee d'office.
        self._ligne(panneau, "Relire la dictée", self._relire_dictee)
        return False

    def _relire_dictee(self):
        texte = parler("DERNIERE-DICTEE")
        p = self._panneau("Relire la dictée")
        if not texte:
            self._ligne(p, "Aucune dictée à relire.")
            return
        reponse = parler("RELIRE " + texte)
        if not reponse:
            self._ligne(p, "Rien à signaler.")
            return
        for ligne in reponse.split("\n"):
            mot, _, propose = ligne.partition("\t")
            self._ligne(p, f"{mot}  →  {propose}")

    def _fiche(self, mot=""):
        reponse = parler(f"FICHE {mot}".strip())
        p = self._panneau("Asegzawal")
        if not reponse:
            self._ligne(p, "Tapez un mot, puis rouvrez la fiche.")
            return
        champs = reponse.split("\t")
        mot, glose, categorie = (champs + ["", "", ""])[:3]
        libre, annexion = (champs + ["", "", "", "", ""])[3:5]
        self._ligne(p, f"{mot}   {glose or 'sans glose'}")
        if categorie:
            self._ligne(p, f"catégorie : {categorie}")
        if libre:
            self._ligne(p, f"état libre : {libre}", lambda f=libre: parler(f"ECRIRE {f}"))
        if annexion:
            self._ligne(p, f"état d'annexion : {annexion}",
                        lambda f=annexion: parler(f"ECRIRE {f}"))

    def _recherche(self):
        """Le champ se remplit par les touches a l'ecran : sans focus, le clavier
        physique ne l'atteint pas."""
        p = self._panneau("Du français au kabyle", garder_touches=True)
        self.champ_recherche = Gtk.Entry(placeholder_text="tapez sur les touches…")
        self.champ_recherche.set_editable(False)
        p.pack_start(self.champ_recherche, False, False, 0)
        ligne = Gtk.Box(spacing=4)
        for libelle, action in (("Chercher", lambda: self._chercher(p)),
                                ("Effacer", self._vider_recherche)):
            b = bouton_sans_focus(label=libelle)
            b.get_style_context().add_class("fonction")
            b.connect("clicked", lambda _b, a=action: a())
            ligne.pack_start(b, True, True, 0)
        p.pack_start(ligne, False, False, 0)
        p.show_all()

    def _vider_recherche(self):
        if self.champ_recherche:
            self.champ_recherche.set_text("")

    def _chercher(self, panneau):
        requete = self.champ_recherche.get_text().strip() if self.champ_recherche else ""
        if len(requete) < 2:
            return
        reponse = parler(f"CHERCHER {requete}")
        for enfant in panneau.get_children()[3:]:
            panneau.remove(enfant)
        if not reponse:
            self._ligne(panneau, "Aucun résultat.")
            return
        for ligne in reponse.split("\n")[:8]:
            forme, _, glose = ligne.partition("\t")
            self._ligne(panneau, f"{forme} · {glose[:60]}",
                        lambda f=forme: (parler(f"CHOISIR {f}"), self._fermer_panneau()))

    def _relire(self):
        p = self._panneau("Relire le presse-papiers")
        texte = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() or ""
        if not texte.strip():
            self._ligne(p, "Copiez d'abord le texte à relire.")
            return
        reponse = parler("RELIRE " + texte.replace("\n", " "))
        if not reponse:
            self._ligne(p, "Rien à signaler.")
            return
        for ligne in reponse.split("\n"):
            mot, _, propose = ligne.partition("\t")
            self._ligne(p, f"{mot}  →  {propose}")

    def _mot_du_jour(self):
        p = self._panneau("Mot du jour")
        reponse = parler("MOTDUJOUR")
        forme, _, glose = reponse.partition("\t")
        if not forme:
            self._ligne(p, "Ressources indisponibles.")
            return
        self._ligne(p, f"{forme}")
        self._ligne(p, glose)
        self._ligne(p, "Insérer", lambda: (parler(f"ECRIRE {forme}"), self._fermer_panneau()))

    # Touches

    def _dessiner(self):
        for enfant in self.touches.get_children():
            self.touches.remove(enfant)
        for rangee in (SYMBOLES if self.symboles else RANGEES):
            ligne = Gtk.Box(spacing=4, homogeneous=False)
            for touche in rangee:
                ligne.pack_start(self._touche(touche), True, True, 0)
            self.touches.pack_start(ligne, True, True, 0)
        self.touches.show_all()

    def _touche(self, touche):
        libelle = touche[0]
        bouton = bouton_sans_focus()
        bouton.get_style_context().add_class("touche")
        if libelle == "␣":
            bouton.set_label("Taqbaylit")
            bouton.get_style_context().add_class("fonction")
        elif libelle in ("123", "ABC", "⇧", "⌫", "⏎"):
            bouton.set_label(libelle)
            bouton.get_style_context().add_class("fonction")
        else:
            sup = " ".join(touche[1:])
            etiquette = Gtk.Label()
            etiquette.set_markup(
                f"{GLib.markup_escape_text(libelle)}"
                f"<span size='x-small' alpha='55%'> {GLib.markup_escape_text(sup)}</span>"
                if sup else GLib.markup_escape_text(libelle))
            bouton.add(etiquette)
            if libelle in KABYLES:
                bouton.get_style_context().add_class("touche-kabyle")
        bouton.connect("clicked", self._pressee, touche)
        if libelle == "⌫":
            long_eff = Gtk.GestureLongPress.new(bouton)
            long_eff.connect("pressed", lambda *_a: parler("EFFACER-MOT"))
            bouton._geste = long_eff
        if len(touche) > 1:
            geste = Gtk.GestureLongPress.new(bouton)
            geste.connect("pressed", self._appui_long, touche, bouton)
            bouton._geste = geste          # sinon il serait ramasse
        return bouton

    def _pressee(self, _bouton, touche):
        libelle = touche[0]
        if libelle == "⇧":
            if self.verrou:
                self.verrou = self.majuscule = False
            elif self.majuscule:
                self.verrou = True
            else:
                self.majuscule = True
            return
        if libelle in ("123", "ABC"):
            self.symboles = not self.symboles
            self._dessiner()
            return
        if libelle == "⌫":
            if self.champ_recherche is not None:
                self.champ_recherche.set_text(self.champ_recherche.get_text()[:-1])
                return
            parler("EFFACER")
            return
        if libelle == "␣":
            parler("ECRIRE  ")          # le mot en cours part, suivi d'une espace
            return
        if libelle == "⏎":
            parler("ECRIRE \n")
            return
        self._envoyer(libelle)

    def _appui_long(self, _geste, _x, _y, touche, bouton):
        """Toutes les variantes, a choisir, et non la premiere d'office."""
        fenetre = Gtk.Popover.new(bouton)
        boite = Gtk.Box(spacing=4)
        for variante in touche[1:]:
            b = bouton_sans_focus(label=variante)
            b.get_style_context().add_class("touche")
            b.connect("clicked", lambda _b, v=variante: (self._envoyer(v),
                                                         fenetre.popdown()))
            boite.pack_start(b, True, True, 0)
        boite.show_all()
        fenetre.add(boite)
        fenetre.show_all()

    def _envoyer(self, caractere):
        if (self.majuscule or self.verrou) and caractere.isalpha():
            caractere = caractere.upper()
            if not self.verrou:
                self.majuscule = False
        if self.champ_recherche is not None:
            self.champ_recherche.set_text(self.champ_recherche.get_text() + caractere)
            return
        parler(f"LETTRE {caractere}")

    # Propositions

    def _suivre(self):
        reponse = parler("ETAT")
        if not reponse:
            self.etat.set_text("Correcteur éteint : allumez-le dans Kab-board")
            return True
        if reponse == "SANS-CHAMP":
            self.etat.set_text("Cliquez d'abord dans un champ de texte")
            return True
        champs = reponse.split("\t")
        mot, mode = champs[0], champs[1]
        nature = champs[2] if len(champs) > 2 else "prop"
        propositions = champs[3:]
        self.etat.set_text(f"« {mot} »" if mot else f"Graphie {mode}")
        # Ne rien refaire tant que la liste n'a pas change : sinon les boutons
        # sont detruits entre l'enfoncement et le relachement du doigt, et le
        # clic n'arrive jamais. C'est ce qui empechait de choisir une forme.
        if propositions == self.dernieres_propositions:
            return True
        self.dernieres_propositions = propositions
        for enfant in self.barre.get_children():
            self.barre.remove(enfant)
        for rang, forme in enumerate(propositions[:6]):
            b = bouton_sans_focus(label=forme)
            style = b.get_style_context()
            style.add_class("proposition")
            # Les trois natures du telephone : vert pour la correction en
            # contexte, bleu pour un candidat, ocre pour une prediction, qu'il
            # s'agisse du mot suivant ou de la fin du mot en cours.
            if nature in ("pred", "comp"):
                style.add_class("prediction")
            elif rang == 0:
                style.add_class("correction")
            else:
                style.add_class("candidat")
            b.connect("clicked", lambda _b, f=forme: parler(f"CHOISIR {f}"))
            # Appui long sur une proposition : sa fiche, comme sur Android.
            geste = Gtk.GestureLongPress.new(b)
            geste.connect("pressed", lambda *_a, f=forme: self._fiche(f))
            b._geste = geste
            self.barre.pack_start(b, True, True, 0)
        self.barre.show_all()
        return True


if __name__ == "__main__":
    if not PRISE.exists():
        print("Le correcteur n'est pas allumé.", file=sys.stderr)
        print("Ouvrez Kab-board et mettez « Clavier kabyle » en marche.", file=sys.stderr)
        print(f"(la prise attendue est {PRISE})", file=sys.stderr)
    fenetre = Clavier()
    fenetre.show_all()
    Gtk.main()
