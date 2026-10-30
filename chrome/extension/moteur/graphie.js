// GraphieBV.kt : les mots qui s'écrivent avec b ou avec v, selon le réglage.
//
// En aval du moteur : on reçoit des formes déjà calculées, on rend les mêmes
// autrement écrites. La table ne liste que des formes de base, alors un mot fléchi
// est ramené à l'une d'elles : segments d'un mot à tirets, état d'annexion, annexion
// en we-, pluriel i…en. Un mot inconnu de la table ressort tel quel.

import { distincts, estMajuscule, majusculeChar } from "./kotlin.js";

const CONS = "[bcdfghjklmnpqrstvwxyzɣɛḍṭṛṣẓčšžɣ]";
const R = (motif) => new RegExp(motif, "u");
const R_WU_CONS = R(`^wu${CONS}`);
const R_WA = R("^wa");
const R_WE_CONS = R(`^we${CONS}`);
const R_YE_CONS = R(`^ye${CONS}`);
const R_YI = R("^yi");
const R_U_CONS = R(`^u${CONS}`);
const R_TE_CONS = R(`^te${CONS}`);
const R_T_CONS = R(`^t${CONS}`);
const R_TAIU = R("^(ta|ti|tu)");
// Le pluriel des noms masculins : iɣriben <- aɣrib, ibridan <- abrid.
const R_PLURIEL = R(`^i(${CONS}.+?)(en|an)$`);
const MOTS = /[\p{L}-]+/gu;

/** Reporte la casse du modèle : Abrid -> Avrid, ABRID -> AVRID. */
function casserComme(modele, mot) {
  if (modele.length > 1 && modele === modele.toUpperCase()) return mot.toUpperCase();
  if (modele.length && estMajuscule(modele[0])) return mot ? majusculeChar(mot[0]) + mot.slice(1) : mot;
  return mot;
}

export class GraphieBV {
  /** lignes : celles de graphie/table_bv.tsv. */
  constructor(lignes) {
    this.versV = new Map();
    this.versB = new Map();
    for (const ligne of lignes) {
      if (!ligne || ligne.startsWith("forme_b")) continue;
      const champs = ligne.split("\t");
      if (champs.length < 2) continue;
      const [fb, fv] = champs;
      if (!fb || !fv) continue;
      this.versV.set(fb, fv);
      this.versB.set(fv, fb);
    }
  }

  /** Les deux formes du mot, dans sa casse, ou null s'il n'alterne pas. */
  paire(mot) {
    const m = mot.toLowerCase();
    if (this.versV.has(m)) return [casserComme(mot, m), casserComme(mot, this.versV.get(m))];
    if (this.versB.has(m)) return [casserComme(mot, this.versB.get(m)), casserComme(mot, m)];
    if (mot.includes("-")) return this.paireATirets(mot);
    return this.paireFlechie(mot, m);
  }

  /** Chaque segment pour son compte : baba-s -> vava-s, d-nebder -> d-nevder. */
  paireATirets(mot) {
    const segments = mot.split("-");
    const paires = segments.map((s) => (s ? this.paire(s) : null));
    if (paires.every((p) => p === null)) return null;
    const b = segments.map((s, i) => (paires[i] ? paires[i][0] : s)).join("-");
    const v = segments.map((s, i) => (paires[i] ? paires[i][1] : s)).join("-");
    return [b, v];
  }

  /** Forme fléchie : la table donne le lexème, l'annexion ne déplace jamais le b. */
  paireFlechie(mot, m) {
    for (const cle of GraphieBV.reductions(m)) {
      if (this.versV.has(cle)) return [mot, GraphieBV.lettresBasculees(mot, true)];
      if (this.versB.has(cle)) return [GraphieBV.lettresBasculees(mot, false), mot];
    }
    return null;
  }

  /** Les formes de base que ce mot pourrait fléchir, la plus sûre d'abord. */
  static reductions(mot) {
    const vues = new Set();
    if (R_WU_CONS.test(mot)) vues.add("u" + mot.slice(2));
    else if (R_WA.test(mot)) vues.add("a" + mot.slice(2));
    else if (R_WE_CONS.test(mot)) vues.add("a" + mot.slice(2));
    else if (R_YE_CONS.test(mot)) vues.add("i" + mot.slice(2));
    else if (R_YI.test(mot)) vues.add("i" + mot.slice(2));
    else if (R_U_CONS.test(mot)) vues.add("a" + mot.slice(1));
    else if (R_TE_CONS.test(mot)) vues.add("ta" + mot.slice(2));
    else if (R_T_CONS.test(mot) && !R_TAIU.test(mot)) vues.add("ta" + mot.slice(1));
    for (const base of [...vues, mot]) {            // le pluriel d'une forme annexée
      const m = R_PLURIEL.exec(base);
      if (m) vues.add("a" + m[1]);
    }
    return [...vues].filter((v) => v !== mot && v.length >= 3);
  }

  /** Tous les b en v, ou l'inverse : la table ne fait jamais autre chose. */
  static lettresBasculees(mot, enV) {
    return enV ? mot.replaceAll("b", "v").replaceAll("B", "V") : mot.replaceAll("v", "b").replaceAll("V", "B");
  }

  /** Le mot dans la graphie réglée (b ou v). Inchangé s'il n'alterne pas. */
  basculer(mot, mode) {
    const p = this.paire(mot);
    if (!p) return mot;
    return mode === "v" ? p[1] : p[0];
  }

  /** Une liste de propositions. Deux formes qui se rejoignent libèrent une place. */
  appliquer(formes, mode) {
    return distincts(formes.map((f) => this.basculer(f, mode)));
  }

  /** Un texte entier, mot à mot : la dictée, dont le modèle vocal ne connaît que le b. */
  appliquerTexte(texte, mode) {
    return texte.replace(MOTS, (m) => this.basculer(m, mode));
  }
}
