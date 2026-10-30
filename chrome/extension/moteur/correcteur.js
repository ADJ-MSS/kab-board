// Correcteur.kt : assemble les étapes.

import { Generateur } from "./candidats.js";
import { Completion } from "./completion.js";
import { Decodeur } from "./decodeur.js";
import { detacherClitique, rejoindrePossessifsPortees, tokenize } from "./normalisation.js";
import { Postprocess } from "./postprocess.js";
import { Ressources } from "./ressources.js";
import { Semantique } from "./semantique.js";
import { comparerDouble } from "./kotlin.js";

const W_SEM = Math.fround(0.6);

export class Correcteur {
  /**
   * octets(nom) : les octets d'un fichier des ressources de l'application (dossier
   * moteur), ou null. lm et tagger : le modèle de langue et l'étiqueteur, déjà ouverts,
   * ou null (la couche manque alors, le moteur reste).
   */
  constructor(octets, lm = null, tagger = null) {
    this.res = new Ressources(octets);
    this.gen = new Generateur(this.res);
    this.sem = new Semantique(octets);
    this.lm = lm;
    this.tagger = tagger;
    this.post = new Postprocess(octets("listes.txt"), lm);
    this._completion = null;
    this.amyagSet = { has: (m) => this.res.amyag.has(m) };
  }

  /** Le modèle de langue, en lecture, pour la prédiction du mot suivant. */
  get modeleLangue() {
    return this.lm;
  }

  /** La complétion du mot en cours, construite à la première demande. */
  get completion() {
    if (!this._completion) this._completion = Completion.depuis(this.res);
    return this._completion;
  }

  get postprocess() {
    return this.post;
  }

  topCandidats(mot, nb = 5) {
    return this.gen.topCandidats(mot, nb);
  }

  corriger(texte) {
    const tokens = tokenize(texte);
    if (!tokens.length) return { texteCorrige: "", tokensEntree: [], nbCorrections: 0, annexions: [], couvertureFin: 1 };

    // Clitiques détachés avant tout calcul de distance, recollés après
    const prefs = [];
    const bases = [];
    const sufs = [];
    for (const t of tokens) {
      const [p, b, s] = detacherClitique(t);
      prefs.push(p); bases.push(b); sufs.push(s);
    }

    const tags = this.tagger ? this.tagger.etiqueter(bases) : [];

    let candsParPos = bases.map((b, i) => this.gen.generer(b, tags[i] ?? "").slice(0, Decodeur.MAX_CAND_BEAM));

    // Cohérence sémantique, sur des copies pour ne pas polluer le cache
    if (bases.length > 1) {
      candsParPos = candsParPos.map((cands, i) => {
        const ctx = this.sem.contexte(bases, i);
        if (!ctx.size) return cands;
        return cands.map((c) => {
          const coh = this.sem.coherence(c.forme, ctx);
          return coh !== 0 ? c.avecScore(c.score + Math.fround(W_SEM * coh)) : c;
        }).sort((a, b) => comparerDouble(b.score, a.score));
      });
    }

    const chemin = Decodeur.decoder(candsParPos, this.lm);

    let nb = 0;
    const corrigee = [];
    chemin.forEach((c, i) => {
      corrigee.push(prefs[i] + c.forme + sufs[i]);
      if (c.forme !== bases[i]) nb++;
    });

    const [apresChaker, corrChaker] = this.post.appliquerChakerValideLm(
      corrigee, this.amyagSet, (m) => this.res.lexcat(m));
    nb += corrChaker.length;

    const finale = rejoindrePossessifsPortees(apresChaker);
    return {
      texteCorrige: finale.map((p) => p[0]).join(" "),
      tokensEntree: tokens,
      nbCorrections: nb,
      annexions: corrChaker,
      couvertureFin: finale.length ? finale[finale.length - 1][1] : 1,
    };
  }
}
