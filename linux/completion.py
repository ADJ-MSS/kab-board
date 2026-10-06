"""La complétion du mot en cours, de 1 à 3 lettres tapées.

Jusqu'à SEUIL lettres, la barre propose les mots qui commencent par ce qui est
tapé ; au-delà, elle corrige comme avant. On ne complète jamais vers un mot de
2 ou 3 lettres : ceux-là, on les a déjà tapés.

Mesuré le 05/10/2026 sur 400 phrases du corpus, tapées lettre par lettre :
24,1 % de frappes en moins avec SEUIL = 3, sans rien changer au filet de
correction (191/200 sur les fautes injectées, comme sans complétion). Compléter
jusqu'à 4 lettres faisait tomber le filet à 90,5 %.

Même règle que taqbaylit.moteur.Completion, côté Android.
"""
import bisect
import threading

SEUIL = 3            # complétion jusqu'à 3 lettres tapées, correction ensuite
LONGUEUR_MIN = 4     # jamais vers un mot de 2 ou 3 lettres
FREQ_MIN = 50        # un mot assez fréquent pour être proposé sans qu'on l'ait tapé
PAR_PREFIXE = 400    # les plus fréquents d'un début, avant le modèle de langue


class Completion:

    def __init__(self, ressources):
        self.res = ressources
        self._mots = None
        self._verrou = threading.Lock()

    def _vocabulaire(self):
        """Construit une fois : les mots fiables de 4 lettres ou plus, triés."""
        with self._verrou:
            if self._mots is None:
                freq = self.res.freq
                self._mots = sorted(m for m, f in freq.items()
                                    if f >= FREQ_MIN and len(m) >= LONGUEUR_MIN)
        return self._mots

    def candidats(self, prefixe):
        """Les mots qui commencent par prefixe, les plus fréquents d'abord."""
        mots = self._vocabulaire()
        i = bisect.bisect_left(mots, prefixe)
        j = bisect.bisect_left(mots, prefixe + "\U0010ffff")
        tranche = sorted(mots[i:j], key=lambda m: -self.res.freq.get(m, 0))
        return tranche[:PAR_PREFIXE]

    def completer(self, contexte, prefixe, nb=6):
        """Les nb mots qui commencent par prefixe et vont le mieux après contexte."""
        cands = self.candidats(prefixe)
        lm = getattr(self.res, "kenlm", None)
        if not cands or lm is None:
            return cands[:nb]
        from ressources import _kenlm as kenlm
        etat, sortie = kenlm.State(), kenlm.State()
        lm.BeginSentenceWrite(etat)
        from normalisation import tokenize
        for t in tokenize(contexte)[-2:]:
            lm.BaseScore(etat, t, sortie)
            etat, sortie = sortie, kenlm.State()
        notes = [(lm.BaseScore(etat, m, kenlm.State()), m) for m in cands]
        notes.sort(key=lambda x: -x[0])
        return [m for _, m in notes[:nb]]

    def mot_de_dictionnaire(self, mot):
        """Le mot tapé reste en tête s'il est déjà un mot des dictionnaires : lexique par
        catégories ou conjugaisons. La fiabilité du correcteur ne suffit pas ici : le
        lexique agrégé compte des bouts de mots, « ẓr » ou « lx », présents dans plus de
        trois sources."""
        return (mot in getattr(self.res, "lexcat", {})
                or mot in getattr(self.res, "amyag", ()))

    def barre(self, contexte, tape, nb=6):
        """Ce que montre la barre pour un mot de 1 à SEUIL lettres : le mot tapé s'il
        est déjà un mot des dictionnaires, puis les complétions. None quand rien ne
        commence ainsi : la barre corrige alors comme avant."""
        if not tape or len(tape) > SEUIL:
            return None
        comp = self.completer(contexte, tape, nb)
        if not comp:
            return None
        tete = [tape] if self.mot_de_dictionnaire(tape) else []
        return (tete + [m for m in comp if m != tape])[:nb]
