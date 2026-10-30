// RechercheFrancais.kt : trouver un mot kabyle à partir d'un mot français, dans les
// gloses du graphe sémantique.

import { comparerChaines, estLettreOuChiffre, rogner } from "./kotlin.js";

const MARQUE = /^\p{Mn}$/u;
const SEPARATEURS = /[,;.‖()[\]:!?]/;
// \s de Java, sans UNICODE_CHARACTER_CLASS : les seuls blancs ASCII.
const BLANCS = /[ \t\n\x0B\f\r]+/g;

/** Première occurrence de mot en mot entier dans texte, ou -1. */
function occurrence(texte, mot) {
  let i = texte.indexOf(mot);
  while (i >= 0) {
    const fin = i + mot.length;
    const avantLibre = i === 0 || !estLettreOuChiffre(texte[i - 1]);
    const apresLibre = fin === texte.length || !estLettreOuChiffre(texte[fin]);
    if (avantLibre && apresLibre) return i;
    i = texte.indexOf(mot, i + 1);
  }
  return -1;
}

export const RechercheFrancais = {
  /** En dessous de deux lettres, presque toutes les gloses répondraient. */
  REQUETE_MIN: 2,

  /** Minuscules, sans diacritiques, blancs réduits. */
  plier(texte) {
    const decompose = texte.toLowerCase().normalize("NFD");
    let sb = "";
    for (let i = 0; i < decompose.length; i++) {
      const c = decompose[i];
      if (!MARQUE.test(c)) sb += c;
    }
    return rogner(sb).replace(BLANCS, " ");
  },

  /** Place du mot cherché dans une glose, toutes deux pliées ; null s'il n'y est pas en mot entier. */
  rang(glosePliee, requetePliee) {
    if (requetePliee.length < this.REQUETE_MIN) return null;
    if (occurrence(glosePliee, requetePliee) < 0) return null;
    const segments = glosePliee.split(SEPARATEURS).map((s) => rogner(s)).filter((s) => s.length);
    if (!segments.length) return 4;
    const premier = segments[0];
    const dansLePremier = occurrence(premier, requetePliee);
    if (premier === requetePliee) return 0;
    if (segments.some((s) => s === requetePliee)) return 1;
    if (dansLePremier === 0) return 2;
    if (dansLePremier > 0) return 3;
    return 4;
  },

  /** Le meilleur rang d'abord, puis la forme la plus fréquente, puis l'ordre alphabétique. */
  classer(trouves, nb) {
    return trouves.slice().sort((a, b) => (a.rang - b.rang) || (b.frequence - a.frequence) ||
      comparerChaines(a.forme, b.forme)).slice(0, nb);
  },
};
