#!/usr/bin/env python3
"""Kab-board : l'application.

Deux interrupteurs, le clavier et le clavier a l'ecran, puis la graphie b ou v
et « ecrire comme on parle ». L'etat va dans ~/.config/kab-board/reglages.json,
que le moteur relit.
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

RACINE = Path(__file__).resolve().parent.parent          # le dossier linux/
DEPOT = RACINE.parent                                    # la racine de kab-board
MOTEUR = RACINE / "ibus" / "kab_ibus.py"
FLOTTANT = RACINE / "bureau" / "clavier_flottant.py"
REGLAGES = Path.home() / ".config" / "kab-board" / "reglages.json"
AUTOSTART = Path.home() / ".config" / "autostart" / "kab-board.desktop"
PRISE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "kab-board.sock"

# La disposition a rendre quand on eteint : celle de la session, pas celle du
# moteur. Sans cela, couper le clavier kabyle laisserait un clavier americain.
DISPOSITION_PAR_DEFAUT = "xkb:fr:latin9:fra"


def lire_reglages():
    try:
        return json.loads(REGLAGES.read_text(encoding="utf-8"))
    except Exception:
        return {"graphie": "v", "translitteration": True, "demarrage": False}


def ecrire_reglages(reglages):
    REGLAGES.parent.mkdir(parents=True, exist_ok=True)
    REGLAGES.write_text(json.dumps(reglages, indent=2), encoding="utf-8")


def parler(commande):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as lien:
            lien.settimeout(1.0)
            lien.connect(str(PRISE))
            lien.sendall(commande.encode("utf-8"))
            return lien.recv(4096).decode("utf-8", "replace")
    except OSError:
        return ""


def tous_les_processus(motif):
    """Tous les processus Python dont la ligne de commande porte ce motif."""
    trouves = []
    for pid in subprocess.run(["pgrep", "-f", motif], capture_output=True,
                              text=True).stdout.split():
        pid = int(pid)
        if pid == os.getpid():
            continue
        try:
            argv = open(f"/proc/{pid}/cmdline", "rb").read().decode().split("\0")
        except OSError:
            continue
        if argv and argv[0].endswith("python3"):
            trouves.append(pid)
    return trouves


def processus(motif):
    """Le PID du processus dont la ligne de commande contient le motif, ou 0."""
    try:
        sortie = subprocess.run(["pgrep", "-f", motif], capture_output=True, text=True)
        for ligne in sortie.stdout.split():
            if int(ligne) != os.getpid():
                return int(ligne)
    except Exception:
        pass
    return 0


class Fenetre(Gtk.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title="Kab-board")
        self.set_default_size(460, 430)
        self.reglages = lire_reglages()

        tete = Gtk.HeaderBar()
        self.set_titlebar(tete)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0,
                       margin_start=18, margin_end=18, margin_top=18, margin_bottom=18)
        self.set_child(page)

        page.append(self._titre("Le clavier"))
        self.inter_moteur = self._interrupteur(
            page, "Clavier kabyle",
            "Corrige et propose dans toutes les applications.",
            self._basculer_moteur)
        self.inter_flottant = self._interrupteur(
            page, "Clavier à l'écran",
            "Les touches, posées au-dessus des autres fenêtres.",
            self._basculer_flottant)

        page.append(self._titre("L'écriture"))
        boite = Gtk.Box(spacing=0, css_classes=["linked"], margin_bottom=6)
        self.bouton_b = Gtk.ToggleButton(label="Écrire avec b")
        self.bouton_v = Gtk.ToggleButton(label="Écrire avec v")
        self.bouton_b.set_active(self.reglages.get("graphie", "v") == "b")
        self.bouton_v.set_active(not self.bouton_b.get_active())
        self.bouton_b.connect("toggled", self._changer_graphie, "b")
        self.bouton_v.connect("toggled", self._changer_graphie, "v")
        boite.append(self.bouton_b); boite.append(self.bouton_v)
        page.append(boite)
        page.append(self._petit("Certains écrivent abrid, d'autres avrid. "
                                "Le réglage vaut pour les six propositions."))
        self.inter_translit = self._interrupteur(
            page, "Écrire comme on parle",
            "gh donne ɣ, dh donne ḍ, kh donne x, aa donne ɛ, ou donne u.",
            self._basculer_translit,
            actif=self.reglages.get("translitteration", True))

        page.append(self._titre("Au démarrage"))
        self.inter_demarrage = self._interrupteur(
            page, "Démarrer avec la session",
            "Le clavier sera prêt sans ouvrir cette fenêtre.",
            self._basculer_demarrage,
            actif=AUTOSTART.exists())

        self.etat = Gtk.Label(label="", xalign=0, wrap=True, margin_top=14,
                              css_classes=["dim-label"])
        page.append(self.etat)

        self.maj_en_cours = False      # la surveillance ne declenche pas les bascules
        self._relever()
        GLib.timeout_add_seconds(2, self._relever)

    # Fabrique

    def _titre(self, texte):
        return Gtk.Label(label=texte, xalign=0, margin_top=10, margin_bottom=6,
                         css_classes=["heading"])

    def _petit(self, texte):
        return Gtk.Label(label=texte, xalign=0, wrap=True, margin_bottom=10,
                         css_classes=["dim-label"])

    def _interrupteur(self, page, titre, detail, rappel, actif=False):
        ligne = Gtk.Box(spacing=12, margin_bottom=2)
        colonne = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        colonne.append(Gtk.Label(label=titre, xalign=0))
        colonne.append(Gtk.Label(label=detail, xalign=0, wrap=True,
                                 css_classes=["dim-label"]))
        ligne.append(colonne)
        inter = Gtk.Switch(valign=Gtk.Align.CENTER, active=actif)
        inter.connect("state-set", rappel)
        ligne.append(inter)
        page.append(ligne)
        page.append(Gtk.Separator(margin_top=8, margin_bottom=8))
        return inter

    # Les bascules

    def _basculer_moteur(self, _inter, actif):
        if self.maj_en_cours:
            return False
        if actif:
            subprocess.Popen([sys.executable, str(MOTEUR)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            self._dire("Démarrage du clavier… le correcteur charge en quelques secondes.")
        else:
            self._eteindre()
        return False

    def _eteindre(self):
        """Arrete tous les processus, la prise, et rend la disposition : en tuer un seul
        laissait la frappe en panne."""
        for motif in ("kab_ibus.py", "clavier_flottant.py"):
            for pid in tous_les_processus(motif):
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for _ in range(20):                       # on attend la fin, sans bloquer longtemps
            if not tous_les_processus("kab_ibus.py"):
                break
            time.sleep(0.1)
        for pid in tous_les_processus("kab_ibus.py"):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if PRISE.exists():
            PRISE.unlink(missing_ok=True)
        # La disposition de la session est rendue : sans cela l'utilisateur
        # garderait une source de saisie morte, donc un clavier muet.
        subprocess.run(["ibus", "engine", DISPOSITION_PAR_DEFAUT], capture_output=True)
        self.maj_en_cours = True
        self.inter_flottant.set_active(False)
        self.maj_en_cours = False
        self._dire("Clavier arrêté, disposition de la session rendue.")

    def _basculer_flottant(self, _inter, actif):
        if self.maj_en_cours:
            return False
        if actif:
            subprocess.Popen([sys.executable, str(FLOTTANT)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        else:
            pid = processus("clavier_flottant.py")
            if pid:
                os.kill(pid, signal.SIGTERM)
        return False

    def _changer_graphie(self, bouton, valeur):
        if not bouton.get_active():
            return
        (self.bouton_v if valeur == "b" else self.bouton_b).set_active(False)
        self.reglages["graphie"] = valeur
        ecrire_reglages(self.reglages)
        parler(f"GRAPHIE {valeur}")

    def _basculer_translit(self, _inter, actif):
        self.reglages["translitteration"] = bool(actif)
        ecrire_reglages(self.reglages)
        parler(f"TRANSLIT {'1' if actif else '0'}")
        return False

    def _basculer_demarrage(self, _inter, actif):
        if actif:
            AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
            AUTOSTART.write_text(
                "[Desktop Entry]\nType=Application\nName=Kab-board\n"
                f"Exec={sys.executable} {MOTEUR}\n"
                "X-GNOME-Autostart-enabled=true\nNoDisplay=true\n",
                encoding="utf-8")
        elif AUTOSTART.exists():
            AUTOSTART.unlink()
        self.reglages["demarrage"] = bool(actif)
        ecrire_reglages(self.reglages)
        return False

    # Etat

    def _relever(self):
        moteur = processus("kab_ibus.py")
        flottant = processus("clavier_flottant.py")
        self.maj_en_cours = True
        self.inter_moteur.set_active(bool(moteur))
        self.inter_flottant.set_active(bool(flottant))
        self.maj_en_cours = False
        if not moteur:
            self._dire("Clavier arrêté.")
        else:
            reponse = parler("ETAT")
            if reponse in ("", "SANS-CHAMP"):
                self._dire("Clavier démarré. Cliquez dans un champ de texte pour écrire.")
            else:
                mot = reponse.split("\t")[0]
                self._dire(f"Clavier actif. Mot en cours : « {mot} »" if mot
                           else "Clavier actif, prêt à écrire.")
        return True

    def _dire(self, message):
        self.etat.set_text(message)


class Application(Gtk.Application):

    def __init__(self):
        super().__init__(application_id="taqbaylit.kabboard.appli")

    def do_activate(self):
        Fenetre(self).present()


if __name__ == "__main__":
    sys.exit(Application().run(sys.argv))
