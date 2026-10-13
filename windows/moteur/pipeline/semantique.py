"""Graphe sémantique : racines, mots, concepts WOLF."""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from normalisation import normalize

_FORME_SIMPLE = re.compile(r"[a-zɣɛḥḍṭẓṛṣšžčǧ]{2,}")

# Poids des niveaux de confiance d'ancrage concept
_CONF_POIDS = {"A+": 1.0, "A": 1.0, "A-": 0.8, "B": 0.6, "B-": 0.5}


class WordNetKabyle:

    def __init__(self):
        self.formes: Set[str] = set()               # formes normalisées
        self.mot2sids: Dict[str, Dict[str, float]] = {}   # forme → {sid: poids}
        self.sid_voisins: Dict[str, Set[str]] = {}  # sid → sids reliés (1 saut)
        self.gloses: Dict[str, str] = {}            # forme → glose française
        self.mot2racines: Dict[str, List[str]] = {}

    def charger(self, path, verbose: bool = True) -> Optional["WordNetKabyle"]:
        path = Path(path)          # on accepte aussi bien une chaîne qu'un Path
        if not path.exists():
            if verbose:
                print(f"  WordNet kabyle absent ({path.name}) → sémantique désactivée")
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for cle, entree in data.get("mots", {}).items():
            sids = {c["sid"]: _CONF_POIDS.get(c.get("conf", "B"), 0.5)
                    for c in entree.get("concepts", [])}
            racines = [r["racine"] for r in entree.get("racines", [])]
            glose = next((g["fr"] for g in entree.get("gloses_fr", [])
                          if g.get("fr") and len(g["fr"]) < 80), "")
            for forme in entree.get("formes", [cle]):
                fn = normalize(forme)
                if not _FORME_SIMPLE.fullmatch(fn):
                    continue
                self.formes.add(fn)
                if sids:
                    cible = self.mot2sids.setdefault(fn, {})
                    for sid, p in sids.items():
                        cible[sid] = max(cible.get(sid, 0.0), p)
                if racines:
                    self.mot2racines.setdefault(fn, racines)
                if glose and fn not in self.gloses:
                    self.gloses[fn] = glose

        # Voisinage à un saut, symétrisé : si A pointe vers B, B voisine A
        for sid, c in data.get("concepts", {}).items():
            for cibles in c.get("relations", {}).values():
                for t in cibles:
                    self.sid_voisins.setdefault(sid, set()).add(t)
                    self.sid_voisins.setdefault(t, set()).add(sid)

        if verbose:
            print(f"  WordNet kabyle : {len(self.formes):,} formes, "
                  f"{len(self.mot2sids):,} ancrées à des concepts, "
                  f"{len(self.sid_voisins):,} concepts reliés")
        return self

    def sids(self, forme: str) -> Dict[str, float]:
        return self.mot2sids.get(forme, {})

    def glose(self, forme: str) -> str:
        return self.gloses.get(forme, "")

    def coherence(self, forme: str, contexte_sids: Set[str]) -> float:
        """Lien sémantique [0..1] : 1.0 si concept partagé, 0.7 si relié."""
        if not contexte_sids:
            return 0.0
        meilleur = 0.0
        vide: Set[str] = set()
        for sid, poids in self.sids(forme).items():
            if sid in contexte_sids:
                return poids
            if self.sid_voisins.get(sid, vide) & contexte_sids:
                meilleur = max(meilleur, 0.7 * poids)
        return meilleur

    def contexte(self, formes: List[str], exclure: int = -1) -> Set[str]:
        """Union des concepts des formes de la phrase (position `exclure` omise)."""
        ctx: Set[str] = set()
        for i, f in enumerate(formes):
            if i == exclure:
                continue
            ctx.update(self.mot2sids.get(f, ()))
        return ctx
