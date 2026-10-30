// Prediction.kt : le mot suivant, noté par le modèle de langue sur la liste des fréquents.

import { tokenize } from "./normalisation.js";

/** Ce qui suit le dernier point, point d'exclamation ou d'interrogation. */
function dernierePhrase(texte) {
  let coupe = -1;
  for (let i = 0; i < texte.length; i++) if (texte[i] === "." || texte[i] === "!" || texte[i] === "?") coupe = i;
  return coupe >= 0 ? texte.slice(coupe + 1) : texte;
}

export class Prediction {
  constructor(lm, candidats) {
    this.lm = lm;
    this.candidats = candidats;
  }

  get disponible() {
    return this.candidats.length > 0;
  }

  /** Les nb formes les plus probables après contexteGauche. */
  suivants(contexteGauche, nb = 5) {
    if (!this.candidats.length) return [];
    const lm = this.lm;
    const tokens = tokenize(dernierePhrase(contexteGauche));
    const entree = lm.etat();
    const sortie = lm.etat();
    try {
      lm.debutPhrase(entree);
      for (const t of tokens) { lm.baseScore(entree, t, sortie); lm.copier(sortie, entree); }

      // Sélection des nb meilleurs, sans trier les 5 000.
      const tete = new Array(nb).fill(null);
      const scores = new Float32Array(nb).fill(-Infinity);
      let remplis = 0;
      for (const mot of this.candidats) {
        const score = lm.baseScore(entree, mot, sortie);
        if (remplis === nb && score <= scores[nb - 1]) continue;
        let i = Math.min(remplis, nb - 1);
        while (i > 0 && score > scores[i - 1]) {
          scores[i] = scores[i - 1]; tete[i] = tete[i - 1]; i--;
        }
        scores[i] = score; tete[i] = mot;
        if (remplis < nb) remplis++;
      }
      return tete.slice(0, remplis).filter((m) => m !== null);
    } finally {
      entree.close();
      sortie.close();
    }
  }
}
