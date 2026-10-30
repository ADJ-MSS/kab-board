// Decodeur.kt : recherche en faisceau sur la phrase.

import { comparerDouble } from "./kotlin.js";

export const Decodeur = {
  W_LM: 0.5,            // poids du log10 KenLM (un Float, exact en 32 bits)
  BEAM: 8,              // largeur du faisceau
  MAX_CAND_BEAM: 6,     // candidats par position entrant dans le faisceau

  /** Un candidat par position, qui maximise score local + W_LM × log P(KenLM). */
  decoder(candsParPos, lm, wLm = this.W_LM, beam = this.BEAM) {
    if (!candsParPos.length) return [];
    // Pas de modèle de langue : le meilleur score local, la liste est déjà triée
    if (!lm || wLm <= 0) return candsParPos.map((c) => c[0]);

    const aLiberer = [];
    const etat = () => {
      const e = lm.etat();
      aLiberer.push(e);
      return e;
    };
    try {
      const e0 = etat();
      lm.debutPhrase(e0);
      let faisceau = [{ score: 0.0, etat: e0, suite: [] }];
      for (const cands of candsParPos) {
        const nouveaux = [];
        for (const ch of faisceau) {
          for (const c of cands) {
            const sortie = etat();
            const lp = lm.baseScore(ch.etat, c.forme, sortie);
            nouveaux.push({ score: ch.score + c.score + Math.fround(wLm * lp), etat: sortie, suite: [...ch.suite, c] });
          }
        }
        nouveaux.sort((a, b) => comparerDouble(b.score, a.score));
        faisceau = nouveaux.slice(0, beam);
      }
      let meilleurScore = -Infinity;
      let meilleur = [];
      for (const ch of faisceau) {
        const sortie = etat();
        const total = ch.score + Math.fround(wLm * lm.baseScore(ch.etat, "</s>", sortie));
        if (total > meilleurScore) { meilleurScore = total; meilleur = ch.suite; }
      }
      return meilleur;
    } finally {
      for (const e of aLiberer) e.close();
    }
  },
};
