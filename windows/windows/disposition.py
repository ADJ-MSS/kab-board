"""La disposition de kab-board, rangée par rangée : la lettre, puis ce que l'appui
long propose. Reprise telle quelle du clavier Linux (bureau/clavier_flottant.py),
lui-même repris de KeyboardLayoutManager sur Android : le bureau et le téléphone
ne divergent pas.
"""

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

# Les lettres propres au kabyle, cerclées comme dans le manuel.
KABYLES = {"ɣ", "ɛ", "ḍ", "ḥ"}

FONCTIONS = {"123", "ABC", "⇧", "⌫", "⏎", "␣"}

# Les trois natures des propositions, comme sur le téléphone : vert pour la
# correction en contexte, bleu pour un candidat, ocre pour une prédiction (le mot
# suivant, ou la fin du mot en cours).
VERT, BLEU, OCRE = "#00843F", "#0072BB", "#A86A00"


def couleur(nature: str, rang: int) -> str:
    if nature in ("pred", "comp"):
        return OCRE
    return VERT if rang == 0 else BLEU


class Majuscules:
    """Un appui : la lettre suivante en capitale. Deux : verrouillage. Trois :
    retour aux minuscules. Comme sur le téléphone."""

    def __init__(self):
        self.une = False
        self.verrou = False

    def appuyer(self):
        if self.verrou:
            self.verrou = self.une = False
        elif self.une:
            self.verrou = True
        else:
            self.une = True

    def appliquer(self, c: str) -> str:
        if (self.une or self.verrou) and c.isalpha():
            c = c.upper()
            if not self.verrou:
                self.une = False
        return c

    @property
    def libelle(self) -> str:
        return "⇪" if self.verrou else ("⬆" if self.une else "⇧")
