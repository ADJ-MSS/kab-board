"""Ce que devient une touche : le clavier kabyle, sans rien de Windows.

Le crochet clavier (kab_saisie.py) voit chaque touche avant l'application où
l'on écrit. Ce module décide : la laisser passer, ou l'arrêter et écrire autre
chose à la place (effacer n caractères, puis taper un texte). Il tient le mot en
cours et ce qui a été écrit avant, pour la correction en contexte.

Sous Linux, IBus laisse le clavier composer un mot souligné avant de l'écrire.
Une application Windows, elle, reçoit les lettres une à une : le mot s'écrit
donc au fil de la frappe, et une conversion (gh → ɣ) ou un choix efface ce qui
vient d'être tapé pour le remplacer. Le mot en cours est ainsi toujours ce qui
précède le curseur, lettre pour lettre.

Les règles sont celles du clavier Linux (kab_ibus.py) : rien n'est corrigé
d'office, l'espace écrit le mot tel qu'il a été tapé, une touche de 1 à 6
choisit une proposition, un effacement juste après une conversion la défait.
La saisie elle-même (digrammes, AltGr) est le saisie.py de kab-board, intact.
"""
import threading
from dataclasses import dataclass, field
from typing import List

from saisie import ALTGR, Saisie, est_lettre, longueur_mots_avant

NB_PROPOSITIONS = 6
CONTEXTE_MAX = 60          # ce que voit le correcteur, comme la barre d'Android
CONTEXTE_GARDE = 240       # ce qu'on retient, pour effacer juste

# Les codes de touches virtuelles de Windows dont on a besoin.
VK_BACK, VK_TAB, VK_RETURN, VK_ESCAPE, VK_SPACE = 0x08, 0x09, 0x0D, 0x1B, 0x20
VK_DELETE = 0x2E
# Majuscule, Ctrl, Alt, Windows et leurs versions gauche et droite,
# verrouillages : transparentes, elles ne changent ni le mot ni le texte.
MODIFICATEURS = {0x10, 0x11, 0x12, 0x14, 0x5B, 0x5C, 0x90, 0x91,
                 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}
# Flèches, début, fin, pages, insertion : le curseur bouge, on ne sait plus où.
NAVIGATION = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D}
VK_PROCESSKEY = 0xE5       # une méthode de saisie asiatique compose
VK_PACKET = 0xE7           # un caractère tapé par un autre programme


@dataclass
class Touche:
    """Une touche enfoncée, telle que le crochet la voit."""
    vk: int
    caractere: str = ""    # ce qu'elle écrit, modificateurs compris ("" : rien)
    base: str = ""         # la même sans Ctrl ni Alt : « g » pour AltGr+g
    altgr: bool = False
    ctrl: bool = False     # Ctrl, Alt ou Windows, sans AltGr : un raccourci
    morte: bool = False    # accent circonflexe ou tréma, en attente de sa lettre


@dataclass
class Action:
    """La réponse à une touche."""
    bloquer: bool = False          # l'application ne la reçoit pas
    effacer: int = 0               # puis on efface autant de caractères
    texte: str = ""                # et on tape ceci
    proposer: bool = False         # le mot a changé : ses propositions
    predire: bool = False          # un mot vient de finir : la suite
    cacher: bool = False           # plus rien à proposer

    @property
    def ecrit(self) -> bool:
        return bool(self.effacer or self.texte)


@dataclass
class Frappe:
    translitteration: bool = True
    chiffres: bool = True                 # 1 à 6 choisissent une proposition
    saisie: Saisie = field(default=None)
    contexte: str = ""                    # le texte avant le mot en cours
    propositions: List[str] = field(default_factory=list)
    nature: str = "prop"                  # prop, comp ou pred : la couleur de la barre
    tete_mots_avant: int = 0              # mots d'avant que la tête remplace aussi
    actif: bool = True                    # faux dans un mot de passe ou chez nous
    generation: int = 0                   # change à chaque mot : les réponses en retard se jettent
    derniere_dictee: str = ""
    apres_touche_morte: bool = False
    attendre_blanc: bool = False          # repris en plein mot : on ne suit qu'au suivant
    prudent: bool = False                 # le champ se vérifie : on suit, sans rien réécrire

    def __post_init__(self):
        if self.saisie is None:
            self.saisie = Saisie(translitteration=self.translitteration)
        self.verrou = threading.RLock()

    # L'état

    @property
    def mot(self) -> str:
        return self.saisie.tampon

    def contexte_visible(self) -> str:
        return self.contexte[-CONTEXTE_MAX:]

    def _nouveau(self):
        self.generation += 1
        self.propositions = []
        self.tete_mots_avant = 0

    def _ajouter_contexte(self, texte: str):
        self.contexte = (self.contexte + texte)[-CONTEXTE_GARDE:]

    def reinitialiser(self) -> Action:
        """On ne sait plus ce qui précède le curseur : clic, autre fenêtre, raccourci."""
        with self.verrou:
            self.saisie.vider()
            self.contexte = ""
            self.apres_touche_morte = False
            self._nouveau()
            return Action(cacher=True)

    def activer(self, actif: bool, en_plein_mot: bool = False) -> Action:
        """en_plein_mot : des lettres ont été tapées pendant que le clavier se
        taisait. Le début du mot nous a échappé : on ne le suit pas, ni ne le
        corrige, et l'on reprend au mot suivant."""
        with self.verrou:
            self.actif = actif
            self.prudent = False
            action = self.reinitialiser()
            self.attendre_blanc = actif and en_plein_mot
            return action

    def suspendre(self, garder: bool = False) -> Action:
        """Le focus a changé : le temps de voir si c'est un mot de passe, on suit
        les lettres telles quelles, sans rien convertir ni réécrire, et sans barre.
        Rien n'échappe ainsi au début du mot, et un mot de passe reste intact.

        garder : on tapait dans la même fenêtre il y a un instant (un navigateur
        ouvre ses suggestions sous la frappe) : le mot en cours reste le même."""
        with self.verrou:
            action = Action(cacher=True)
            if garder:
                self._nouveau()
            else:
                action = self.reinitialiser()
            self.actif = True
            self.prudent = True
            self.attendre_blanc = False
            return action

    def reprendre(self, actif: bool) -> Action:
        """Le champ est vu : un mot de passe (ou chez nous), on se tait ; sinon, le
        mot suivi pendant la vérification a ses propositions."""
        with self.verrou:
            if not actif:
                return self.activer(False)
            if not self.prudent:
                self.actif = True
                return Action()
            self.prudent = False
            self.actif = True
            self._nouveau()
            return Action(proposer=not self.saisie.vide)

    def _prudente(self, t: Touche, virtuel: bool) -> Action:
        """Une touche pendant la vérification : suivie, jamais réécrite."""
        if t.vk in MODIFICATEURS:
            return Action()
        if t.vk == VK_BACK:
            self.saisie.derniere_conversion = None
            if self.saisie.tampon:
                self.saisie.tampon = self.saisie.tampon[:-1]
            else:
                self.contexte = self.contexte[:-1]
            return Action(bloquer=virtuel, effacer=1 if virtuel else 0)
        c = t.caractere
        if (t.ctrl or t.morte or t.altgr or not c or t.vk in NAVIGATION
                or t.vk in (VK_PROCESSKEY, VK_PACKET, VK_ESCAPE, VK_RETURN, VK_TAB, VK_DELETE)):
            action = self.reinitialiser()
            if virtuel and c:
                action.bloquer, action.texte = True, c
            return action
        if len(c) == 1 and est_lettre(c):
            self.saisie.derniere_conversion = None
            self.saisie.tampon += c
        else:
            self._ajouter_contexte(self.saisie.vider() + c)
        return Action(bloquer=virtuel, texte=c if virtuel else "")

    def montrer(self, generation: int, formes, nature="prop", mots_avant=0) -> bool:
        """Les propositions arrivent du correcteur. Faux si la frappe a continué."""
        with self.verrou:
            if generation != self.generation or not self.actif or self.prudent:
                return False
            if nature == "pred" and not self.saisie.vide:
                return False
            self.propositions = list(formes)[:NB_PROPOSITIONS]
            self.nature = nature
            self.tete_mots_avant = mots_avant if nature == "prop" else 0
            return True

    # Les touches physiques

    def touche(self, t: Touche) -> Action:
        with self.verrou:
            if not self.actif:
                return Action()
            if self.prudent:
                return self._prudente(t, virtuel=False)
            if t.vk in MODIFICATEURS:
                return Action()
            if t.vk in (VK_PROCESSKEY, VK_PACKET) or t.ctrl:
                # Un raccourci (coller, annuler, tout sélectionner…) ou une saisie
                # d'ailleurs : le texte a pu changer sans nous.
                return self.reinitialiser()
            if t.morte:
                # La lettre qui suit sera composée par l'application (ê, ï) : on ne
                # la suivra pas, le mot recommence après elle.
                self.reinitialiser()
                self.apres_touche_morte = True
                return Action(cacher=True)
            if self.apres_touche_morte:
                self.apres_touche_morte = False
                return self.reinitialiser()
            if t.vk == VK_BACK:
                return self._effacer(virtuel=False)
            if t.vk == VK_ESCAPE:
                return self.reinitialiser()
            if t.vk in NAVIGATION or t.vk == VK_DELETE:
                return self.reinitialiser()
            if t.vk == VK_RETURN:
                # Une ligne de plus, ou un message envoyé : le contexte repart de zéro.
                return self.reinitialiser()
            if t.vk == VK_TAB:
                return self.reinitialiser()       # souvent, le champ suivant
            return self._caractere(t.caractere, t.base, t.altgr, virtuel=False)

    def _caractere(self, c: str, base: str, altgr: bool, virtuel: bool) -> Action:
        # Une touche de 1 à 6 choisit, tant qu'un mot est en cours et proposé.
        if (self.chiffres and c in ("1", "2", "3", "4", "5", "6") and not self.saisie.vide
                and self.propositions and self.nature in ("prop", "comp")):
            rang = int(c) - 1
            if rang < len(self.propositions):
                return self.choisir(rang)
        if altgr:
            lettre = base or c
            if lettre and lettre.lower() in ALTGR:
                if self.attendre_blanc:          # la lettre, sans suivre le mot
                    k = ALTGR[lettre.lower()]
                    return Action(bloquer=True, texte=k.upper() if lettre.isupper() else k)
                avant = self.saisie.tampon
                self.saisie.lettre(lettre, altgr=True)
                if lettre.isupper():
                    self.saisie.tampon = self.saisie.tampon[:-1] + self.saisie.tampon[-1].upper()
                return self._ecart(avant, bloquer=True)
            if not c:
                return Action()
        if not c:
            # Une touche qui n'écrit rien (F1, une touche multimédia…) : elle ne
            # touche pas au texte, mais on ne parie pas sur la suite.
            return Action() if virtuel else self.reinitialiser()
        if self.attendre_blanc:
            if len(c) == 1 and est_lettre(c):
                return Action(bloquer=virtuel, texte=c if virtuel else "")
            self.attendre_blanc = False
        if len(c) == 1 and est_lettre(c):
            avant = self.saisie.tampon
            self.saisie.lettre(c)
            return self._ecart(avant, bloquer=virtuel)
        # Ponctuation, espace, chiffre : le mot finit tel qu'il a été tapé.
        mot = self.saisie.vider()
        self._ajouter_contexte(mot + c)
        self._nouveau()
        action = Action(predire=True, cacher=True)
        if virtuel:
            action.bloquer, action.texte = True, c
        return action

    def _ecart(self, avant: str, bloquer: bool) -> Action:
        """Ce qu'il faut effacer et taper pour passer de `avant` au mot en cours.

        Le plus souvent, la lettre s'ajoute : on la laisse passer, l'application
        l'écrit elle-même. Une conversion (gh → ɣ) efface le g et tape ɣ."""
        apres = self.saisie.tampon
        self._nouveau()
        if not bloquer and apres.startswith(avant) and len(apres) == len(avant) + 1:
            return Action(proposer=True)
        commun = 0
        while commun < min(len(avant), len(apres)) and avant[commun] == apres[commun]:
            commun += 1
        return Action(bloquer=True, effacer=len(avant) - commun, texte=apres[commun:],
                      proposer=bool(apres), cacher=not apres)

    def _effacer(self, virtuel: bool) -> Action:
        avant = self.saisie.tampon
        if self.saisie.effacer():
            if not virtuel and avant[:-1] == self.saisie.tampon:
                self._nouveau()                   # l'application efface elle-même
                return Action(proposer=not self.saisie.vide, cacher=self.saisie.vide)
            return self._ecart(avant, bloquer=True)
        # Rien en cours : l'effacement mange le texte d'avant, que l'on suit.
        self.contexte = self.contexte[:-1]
        self._reprendre_mot()
        self._nouveau()
        action = Action(proposer=not self.saisie.vide, cacher=self.saisie.vide)
        if virtuel:
            action.bloquer, action.effacer = True, 1
        return action

    def _reprendre_mot(self):
        """Effacer l'espace qui suit un mot le rend modifiable : ses propositions
        reviennent, comme sur le téléphone."""
        i = len(self.contexte)
        while i > 0 and est_lettre(self.contexte[i - 1]):
            i -= 1
        if i < len(self.contexte) and (i > 0 or len(self.contexte) < CONTEXTE_GARDE):
            self.saisie.tampon = self.contexte[i:]
            self.saisie.derniere_conversion = None
            self.contexte = self.contexte[:i]

    # Les choix

    def choisir(self, rang: int) -> Action:
        with self.verrou:
            if not 0 <= rang < len(self.propositions):
                return Action()
            return self._choisir(rang, self.propositions[rang])

    def choisir_forme(self, forme: str) -> Action:
        with self.verrou:
            rang = self.propositions.index(forme) if forme in self.propositions else -1
            return self._choisir(rang, forme)

    def _choisir(self, rang: int, forme: str) -> Action:
        """La forme choisie remplace le mot tapé, et une espace la suit. Seule la
        correction en tête peut remplacer aussi les mots d'avant (« tamurt iw »
        → « tamurt-iw »), et jamais par-dessus une virgule."""
        effacer = len(self.saisie.tampon)
        if rang == 0 and self.nature == "prop" and self.tete_mots_avant > 0:
            k = longueur_mots_avant(self.contexte, self.tete_mots_avant)
            if k > 0:
                effacer += k
                self.contexte = self.contexte[:-k]
        texte = forme + " "
        self.saisie.vider()
        self._ajouter_contexte(texte)
        self._nouveau()
        return Action(bloquer=True, effacer=effacer, texte=texte, predire=True, cacher=True)

    # Le clavier à l'écran : rien n'est tapé physiquement, tout s'écrit par nous

    def lettre_ecran(self, c: str) -> Action:
        with self.verrou:
            if not self.actif or not c:
                return Action(bloquer=True, texte=c or "")
            if self.prudent:
                return self._prudente(Touche(0, c, c), virtuel=True)
            self.apres_touche_morte = False
            return self._caractere(c, c, False, virtuel=True)

    def effacer_ecran(self) -> Action:
        with self.verrou:
            if not self.actif:
                return Action(bloquer=True, effacer=1)
            if self.prudent:
                return self._prudente(Touche(VK_BACK), virtuel=True)
            return self._effacer(virtuel=True)

    def effacer_mot_ecran(self) -> Action:
        """L'appui long sur l'effacement : le mot en cours, ou le mot d'avant."""
        with self.verrou:
            n = len(self.saisie.tampon)
            if n == 0:
                k = longueur_mots_avant(self.contexte, 1) if self.contexte else -1
                n = k if k > 0 else 1
                self.contexte = self.contexte[:-n] if self.contexte else ""
            self.saisie.vider()
            self._nouveau()
            return Action(bloquer=True, effacer=n, cacher=True)

    def ecrire(self, texte: str, dictee: bool = False) -> Action:
        """Un texte entier : l'espace ou l'entrée du clavier à l'écran, un mot de la
        fiche, la dictée. Le mot en cours reste tel qu'il a été tapé."""
        with self.verrou:
            if dictee:
                self.derniere_dictee = texte
            mot = self.saisie.vider()
            if "\n" in texte:
                self.contexte = texte.rsplit("\n", 1)[1]
            else:
                self._ajouter_contexte(mot + texte)
            self._nouveau()
            return Action(bloquer=True, texte=texte, predire=True, cacher=True)

