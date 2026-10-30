// MotDuJour.kt : un mot courant et sa glose, qui change chaque jour.

import { comparerChaines, distincts, estVide, floorMod, hashCode } from "./kotlin.js";

const MS_PAR_JOUR = 86400000;

export const MotDuJour = {
  /** Longueur maximale d'une glose retenue. */
  GLOSE_MAX: 80,

  /** Les candidats, dans un ordre fixe mais sans rapport avec la fréquence. */
  candidats(frequents, glose) {
    return distincts(frequents)
      .filter((m) => {
        const g = glose(m);
        return !estVide(g) && g.length <= this.GLOSE_MAX;
      })
      .map((m) => [hashCode(m), m])
      .sort((a, b) => (a[0] - b[0]) || comparerChaines(a[1], b[1]))
      .map((x) => x[1]);
  },

  /** Le mot du jour numéro jour, compté en jours depuis l'origine. */
  choisir(candidats, jour) {
    return candidats.length ? candidats[floorMod(jour, candidats.length)] : null;
  },

  /** Le numéro du jour local. */
  jourLocal(maintenantMs, decalageMs) {
    return Math.floor((maintenantMs + decalageMs) / MS_PAR_JOUR);
  },
};
