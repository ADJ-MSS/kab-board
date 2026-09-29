"""Les ressources du telephone, lues sur le bureau.

Les outils de kab-board (fiche d'un mot, recherche depuis le francais, mot du
jour) s'appuient sur des ressources que l'application Android
embarque deja : les formes du graphe semantique, leurs gloses, les categories,
les frequences. Elles sont exportees dans `app/src/main/assets/moteur/`.

Plutot que d'en refaire une copie, le bureau lit celles-la. Le format des listes
est celui de l'exporteur : MAGIC, version, nombre de mots, blocs de seize a
prefixes factorises.

    r = Ressources.charger()
    r.glose("aɣrum")          -> 'pain, galette'
    r.categorie("aɣrum")      -> 'masc'
    r.chercher_francais("pain")  -> [('aɣrum', 'pain, galette'), ...]
"""
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import chemins
ACTIFS = chemins.actifs_android() or Path("/inexistant")
MAGIC = b"TQBL"
BLOC = 16


def lire_mots(chemin: Path) -> List[str]:
    """Decode une liste ecrite par `ecrire_mots` : blocs de 16, prefixes factorises."""
    donnees = chemin.read_bytes()
    if donnees[:4] != MAGIC:
        raise ValueError(f"{chemin.name} : ce n'est pas une liste kab-board")
    _version, nb_mots, nb_blocs = struct.unpack_from("<HII", donnees, 4)
    debut_offsets = 4 + 2 + 4 + 4
    offsets = struct.unpack_from(f"<{nb_blocs}I", donnees, debut_offsets)
    base = debut_offsets + nb_blocs * 4
    mots: List[str] = []
    for bloc in range(nb_blocs):
        p = base + offsets[bloc]
        precedent = ""
        for j in range(BLOC):
            if len(mots) >= nb_mots:
                break
            if j == 0:
                (taille,) = struct.unpack_from("<H", donnees, p); p += 2
                mot = donnees[p:p + taille].decode("utf-8"); p += taille
            else:
                commun, taille = struct.unpack_from("<BH", donnees, p); p += 3
                reste = donnees[p:p + taille].decode("utf-8"); p += taille
                mot = precedent[:commun] + reste
            mots.append(mot)
            precedent = mot
    return mots


@dataclass
class Ressources:
    formes: List[str] = field(default_factory=list)
    gloses: Dict[str, str] = field(default_factory=dict)
    categories: Dict[str, str] = field(default_factory=dict)
    frequences: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def charger(cls, actifs: Path = ACTIFS, lexique_categories: Optional[Path] = None):
        r = cls()
        formes_fichier = actifs / "wordnet.formes"
        gloses_fichier = actifs / "wordnet.gloses"
        if formes_fichier.exists():
            r.formes = lire_mots(formes_fichier)
            if gloses_fichier.exists():
                lignes = gloses_fichier.read_text(encoding="utf-8").split("\n")
                r.gloses = {f: g for f, g in zip(r.formes, lignes) if g}
        if lexique_categories and lexique_categories.exists():
            for ligne in lexique_categories.read_text(encoding="utf-8").splitlines():
                mot, _, cat = ligne.partition("\t")
                if mot and cat:
                    r.categories[mot] = cat
        return r

    # Les outils

    def glose(self, mot: str) -> str:
        m = mot.lower()
        return self.gloses.get(m) or self.gloses.get(m.split("-")[0], "")

    def categorie(self, mot: str) -> str:
        m = mot.lower()
        return self.categories.get(m) or self.categories.get(m.split("-")[0], "")

    def chercher_francais(self, requete: str, maximum: int = 8) -> List[Tuple[str, str]]:
        """Les formes dont la glose contient le mot francais. Celles qui commencent par
        lui passent devant."""
        q = requete.strip().lower()
        if len(q) < 2:
            return []
        debut, dedans = [], []
        for forme, glose in self.gloses.items():
            g = glose.lower()
            if g.startswith(q):
                debut.append((forme, glose))
            elif q in g:
                dedans.append((forme, glose))
            if len(debut) >= maximum:
                break
        return (debut + dedans)[:maximum]

    def mot_du_jour(self, jour: int) -> Tuple[str, str]:
        """Un mot par jour, le jour servant d'index : le meme pour tout le monde."""
        courtes = [(f, g) for f, g in self.gloses.items() if 0 < len(g) <= 40]
        if not courtes:
            return ("", "")
        return courtes[jour % len(courtes)]
