"""Le correcteur : assemble les étapes."""
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

import config
from normalisation import normalize, tokenize, detacher_clitique, rejoindre_possessifs
from ressources import Ressources
from candidats import generer, Candidat
from decodeur import decoder
from postprocess import appliquer_chaker_valide_lm


@dataclass
class ResultatV2:
    texte_corrige: str
    nb_corrections: int
    # (avant, après, source, détail)
    corrections: List[Tuple] = field(default_factory=list)
    tokens_entree: List[str] = field(default_factory=list)


class KabyleCorrecteurV2:

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.res: Optional[Ressources] = None
        self._cache_gen: Dict[Tuple[str, str], List[Candidat]] = {}

    def charger(self):
        print("━" * 60)
        print("  Chargement pipeline kabyle 2.0…")
        print("━" * 60)
        self.res = Ressources(verbose=True).charger()
        print("━" * 60)
        print("  Pipeline 2.0 prêt !")
        print("━" * 60)
        return self

    # Petit cache : le filet d'évaluation repasse souvent sur les mêmes mots
    def _generer(self, base: str, pos_tag: str, large: bool = False) -> List[Candidat]:
        cle = (base, pos_tag, large)
        cands = self._cache_gen.get(cle)
        if cands is None:
            cands = generer(base, self.res, pos_tag,
                            nb_max=40 if large else 24, large=large)
            if len(self._cache_gen) > 50_000:
                self._cache_gen.clear()
            self._cache_gen[cle] = cands
        return cands

    def top_candidats(self, mot: str, nb: int = 5) -> List[dict]:
        """Les nb meilleures formes pour un mot isolé.

        Tri distance, puis fréquence, puis distance pondérée : devant un
        humain le mot courant doit passer avant les variantes rares.
        """
        if self.res is None:
            raise RuntimeError("Appelez .charger() d'abord !")
        mot = normalize(mot)

        def freq_aff(c):
            if c.source not in ("lexique", "keep"):
                return max(c.freq, config.FREQ_PLANCHER_DICO)
            return c.freq

        cands = sorted(
            (c for c in self._generer(mot, "", large=True) if c.forme != mot),
            key=lambda c: (c.dist, -freq_aff(c), c.dist_p))
        wn = self.res.wn
        return [{"candidat": c.forme, "distance": c.dist,
                 "dist_ponderee": c.dist_p, "frequence": c.freq,
                 "score": round(c.score, 3), "source": c.source,
                 "glose": wn.glose(c.forme) if wn else ""}
                for c in cands[:nb]]

    def corriger(self, texte: str) -> ResultatV2:
        if self.res is None:
            raise RuntimeError("Appelez .charger() d'abord !")
        res = self.res

        tokens = tokenize(texte)
        if not tokens:
            return ResultatV2(texte_corrige="", nb_corrections=0)

        pos_tags = res.pos_tags(tokens)
        if self.verbose and pos_tags:
            print(f"  POS : {[(tokens[i], pos_tags[i]) for i in range(len(tokens))]}")

        prefs, bases, sufs = [], [], []
        for tok in tokens:
            p, b, s = detacher_clitique(tok)
            prefs.append(p); bases.append(b); sufs.append(s)

        cands_par_pos = [
            self._generer(bases[i], pos_tags.get(i, ""))[:config.MAX_CAND_BEAM]
            for i in range(len(bases))
        ]

        # Cohérence sémantique, sur des copies pour ne pas polluer le cache
        if res.wn is not None and len(bases) > 1:
            ajustees = []
            for i, cands in enumerate(cands_par_pos):
                ctx = res.wn.contexte(bases, exclure=i)
                if not ctx:
                    ajustees.append(cands)
                    continue
                copies = []
                for c in cands:
                    coh = res.wn.coherence(c.forme, ctx)
                    copies.append(replace(c, score=c.score + config.W_SEM * coh)
                                  if coh else c)
                copies.sort(key=lambda c: c.score, reverse=True)
                ajustees.append(copies)
            cands_par_pos = ajustees

        chemin = decoder(cands_par_pos, res.kenlm)

        corrigee: List[str] = []
        corrections: List[Tuple] = []
        for i, c in enumerate(chemin):
            forme = prefs[i] + c.forme + sufs[i]
            corrigee.append(forme)
            if c.forme != bases[i]:
                if self.verbose:
                    print(f"  {c.source} : '{tokens[i]}' → '{forme}' "
                          f"(dist_p={c.dist_p}, score={c.score:.2f})")
                detail = {"dist": c.dist, "dist_ponderee": c.dist_p,
                          "freq": c.freq, "nsrc": c.nsrc}
                corrections.append((tokens[i], forme, c.source, detail))

        corrigee, corr_chaker = appliquer_chaker_valide_lm(
            corrigee, res.kenlm, verbes=res.amyag, lexcat_words=res.lexcat,
            verbose=self.verbose)
        for avant, apres, raison in corr_chaker:
            corrections.append((avant, apres, "chaker", {"raison": raison}))

        avant_pos = list(corrigee)
        corrigee = rejoindre_possessifs(corrigee)
        if len(corrigee) != len(avant_pos):
            for tok in corrigee:
                if "-" in tok and tok not in avant_pos:
                    corrections.append(
                        (tok.replace("-", " "), tok, "possessif", {}))

        resultat = " ".join(corrigee)
        if self.verbose:
            print(f"  {texte}  →  {resultat}")
        return ResultatV2(
            texte_corrige=resultat,
            nb_corrections=len(corrections),
            corrections=corrections,
            tokens_entree=tokens,
        )


if __name__ == "__main__":
    cor = KabyleCorrecteurV2(verbose=True).charger()
    print("\nPrêt : phrase kabyle (Ctrl+C pour quitter)\n")
    while True:
        try:
            entree = input("Entrée : ").strip()
            if entree:
                cor.corriger(entree)
                print()
        except KeyboardInterrupt:
            print("\nFin.")
            break
