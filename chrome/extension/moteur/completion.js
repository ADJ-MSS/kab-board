// Completion.kt : la complétion du mot en cours, de 1 à 3 lettres tapées.

import { POSSESSIFS, tokenize } from "./normalisation.js";
import { comparerChaines, comparerDouble, estLettre, rognerFin } from "./kotlin.js";

export class Completion {
  constructor(mots, freqs) {
    // Trié ici, dans l'ordre de compareTo, pour que la recherche binaire soit juste.
    const ordre = mots.map((_, i) => i).sort((a, b) => comparerChaines(mots[a], mots[b]));
    this.mots = ordre.map((i) => mots[i]);
    this.freqs = Int32Array.from(ordre, (i) => freqs[i]);
  }

  static SEUIL = 3;            // complétion jusqu'à 3 lettres tapées, correction ensuite
  static LONGUEUR_MIN = 4;     // jamais vers un mot de 2 ou 3 lettres
  static FREQ_MIN = 50;        // assez fréquent pour être proposé sans être tapé
  static PAR_PREFIXE = 400;    // les plus fréquents d'un début, avant le modèle de langue

  /** « tamurt iw » : un possessif tapé juste après un mot se rattache à lui. */
  static cedeALaCorrection(contexteGauche, tape) {
    if (!POSSESSIFS.has(tape)) return false;
    const fin = rognerFin(contexteGauche);
    return fin.length > 0 && estLettre(fin[fin.length - 1]);
  }

  static motDeDictionnaire(res) {
    return (m) => res.lexcat(m) !== null || res.amyag.has(m);
  }

  /** Les mots fiables de 4 lettres ou plus du lexique. */
  static depuis(res) {
    const mots = [];
    const freqs = [];
    res.lexique.forEachIndexed((i, m) => {
      if (m.length >= Completion.LONGUEUR_MIN) {
        const f = res.freqParIndex(i);
        if (f >= Completion.FREQ_MIN) { mots.push(m); freqs.push(f); }
      }
    });
    return new Completion(mots, freqs);
  }

  get taille() {
    return this.mots.length;
  }

  /** Les mots qui commencent par prefixe, les plus fréquents d'abord. */
  candidats(prefixe) {
    if (!prefixe) return [];
    let lo = 0;
    let hi = this.mots.length;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (this.mots[mid] < prefixe) lo = mid + 1; else hi = mid;
    }
    const tranche = [];
    for (let i = lo; i < this.mots.length && this.mots[i].startsWith(prefixe); i++) tranche.push(i);
    return tranche.sort((a, b) => this.freqs[b] - this.freqs[a])
      .slice(0, Completion.PAR_PREFIXE).map((i) => this.mots[i]);
  }

  /** Les nb mots qui commencent par prefixe et vont le mieux après contexteGauche. */
  completer(contexteGauche, prefixe, nb, lm) {
    const cands = this.candidats(prefixe);
    if (!cands.length || !lm) return cands.slice(0, nb);
    const tokens = tokenize(contexteGauche).slice(-2);
    const entree = lm.etat();
    const sortie = lm.etat();
    try {
      lm.debutPhrase(entree);
      for (const t of tokens) { lm.baseScore(entree, t, sortie); lm.copier(sortie, entree); }
      return cands.map((m) => [m, lm.baseScore(entree, m, sortie)])
        .sort((a, b) => comparerDouble(b[1], a[1]))
        .slice(0, nb)
        .map((x) => x[0]);
    } finally {
      entree.close();
      sortie.close();
    }
  }

  /**
   * Ce que montre la barre pour un mot de 1 à SEUIL lettres : le mot tapé s'il est déjà
   * un mot, puis les complétions. null quand rien ne commence ainsi.
   */
  barre(contexteGauche, tape, nb, lm, estUnMot) {
    if (!tape || tape.length > Completion.SEUIL || Completion.cedeALaCorrection(contexteGauche, tape)) return null;
    const comp = this.completer(contexteGauche, tape, nb, lm);
    if (!comp.length) return null;
    const tete = estUnMot(tape) ? [tape] : [];
    return [...tete, ...comp.filter((m) => m !== tape)].slice(0, nb);
  }
}
