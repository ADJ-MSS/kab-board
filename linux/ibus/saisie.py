"""La saisie kabyle, sans IBus : les lettres par digrammes ou AltGr, et le mot en
cours. Le moteur n'est qu'un branchement, tout ce qui décide est ici et se teste.
"""
from dataclasses import dataclass, field
from typing import List, Optional

# « Écrire comme on parle », les cinq conversions du clavier Android.
DIGRAMMES = {"gh": "ɣ", "dh": "ḍ", "kh": "x", "aa": "ɛ", "ou": "u"}

# Accès direct, pour qui connaît son clavier : AltGr + la lettre latine.
ALTGR = {
    "g": "ɣ", "e": "ɛ", "d": "ḍ", "h": "ḥ", "t": "ṭ", "z": "ẓ",
    "s": "ṣ", "c": "č", "j": "ǧ", "r": "ṛ",
}

LETTRES = set("abcdefghijklmnopqrstuvwxyzɣɛḍḥṭẓṣǧčṛ")


@dataclass
class Saisie:
    """Le mot en cours de frappe, et ce qu'il devient."""

    translitteration: bool = True
    tampon: str = ""
    # Ce qui vient d'être converti, pour qu'un effacement immédiat le défasse,
    # comme sur le téléphone : (avant, après).
    derniere_conversion: Optional[tuple] = field(default=None, repr=False)

    # La frappe

    def lettre(self, caractere: str, altgr: bool = False) -> None:
        """Une lettre tapée. AltGr donne directement la lettre kabyle."""
        self.derniere_conversion = None
        if altgr:
            self.tampon += ALTGR.get(caractere.lower(), caractere)
            return
        self.tampon += caractere
        if self.translitteration:
            self._convertir()

    def _convertir(self) -> None:
        fin = self.tampon[-2:].lower()
        if fin in DIGRAMMES:
            avant = self.tampon[-2:]
            remplace = DIGRAMMES[fin]
            if avant[0].isupper():
                remplace = remplace.upper()
            self.tampon = self.tampon[:-2] + remplace
            self.derniere_conversion = (avant, remplace)

    def effacer(self) -> bool:
        """Efface un caractère, en défaisant d'abord la conversion. False s'il n'y avait
        rien : au moteur de laisser l'effacement à l'application."""
        if self.derniere_conversion:
            avant, apres = self.derniere_conversion
            self.tampon = self.tampon[:-len(apres)] + avant
            self.derniere_conversion = None
            return True
        if not self.tampon:
            return False
        self.tampon = self.tampon[:-1]
        return True

    def vider(self) -> str:
        mot, self.tampon = self.tampon, ""
        self.derniere_conversion = None
        return mot

    @property
    def vide(self) -> bool:
        return not self.tampon


def est_lettre(caractere: str) -> bool:
    return caractere.lower() in LETTRES or caractere == "-"


def choix_par_chiffre(chiffre: int, propositions: List[str]) -> Optional[str]:
    """La proposition désignée par une touche de 1 à 6, ou None."""
    if 1 <= chiffre <= len(propositions):
        return propositions[chiffre - 1]
    return None
