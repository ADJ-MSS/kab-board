// Postprocess.kt : l'état d'annexion (Chaker 1988) et le rattachement des possessifs.

import { lignes } from "./ressources.js";

const CONS = "[bcdfghjklmnpqrstvwxyzɣɛḍṭṛṣẓčšžɣ]";
const VOYELLES_ETENDUES = new Set(["a", "e", "i", "o", "u", "ɛ"]);
const LM_REJET_CHAKER = 2.5;

const R = (motif) => new RegExp(motif, "u");
const R_U_CONS = R(`^u${CONS}`);
const R_A_GEM_SOURDE = R("^a(xx|ɣɣ|qq|ṭṭ|ḍḍ|ẓẓ|čč|šš|ṛṛ|ṣṣ)");
const R_A_GEM_AUTRE = R("^a(ss|mm|ff|bb|nn|ll|rr|tt|dd|gg|kk|ww)");
const R_AM_VOY = R("^am[aeiou]");
const R_A_CONS = R(`^a${CONS}`);
const R_I_CONS_EN = R(`^i${CONS}.+en$`);
const R_I_LRFWMNB = R("^i[lrfwmnb]");
const R_TA_CONS = R(`^ta${CONS}`);
const R_TI_CONS = R(`^ti${CONS}`);
const R_TU_CONS = R(`^tu${CONS}`);
const R_WU_CONS = R(`^wu${CONS}`);
const R_WA = R("^wa");
const R_YE_CONS = R(`^ye${CONS}`);
const R_YI = R("^yi");
const R_TE_CONS = R(`^te${CONS}`);
const R_T_CONS = R(`^t${CONS}`);
const R_TAIU = R("^(ta|ti|tu)");
const R_I_CONS = R(`^i${CONS}`);
const R_REPETE = /(.)\1+/gu;

export const LEXCAT_NOMINAL = new Set(["masc", "fem", "fem_pl", "adj_masc", "adj_fem", "ambig"]);

export class Postprocess {
  /** listes : les octets de listes.txt ; lm : le modèle de langue, ou null. */
  constructor(listes, lm) {
    this.lm = lm;
    const m = new Map();
    let courante = null;
    for (const l of lignes(listes)) {
      if (l.startsWith("[") && l.endsWith("]")) {
        const nom = l.slice(1, l.length - 1);
        if (!m.has(nom)) m.set(nom, new Set());
        courante = m.get(nom);
      } else if (l.length && courante) courante.add(l);
    }
    const liste = (n) => m.get(n) ?? new Set();
    this.verbesWhitelist = liste("verbes_whitelist");
    this.nomsInvariables = liste("noms_invariables");
    this.numeraux = liste("numeraux");
    this.prepAnnexion = liste("prep_annexion");
    this.prepLibre = liste("prep_libre");
    this.etatLibreForce = liste("etat_libre_force");
  }

  static aTripleConsonne(motIn) {
    const mot = motIn.replace(R_REPETE, "$1");
    let n = 0;
    for (let i = 0; i < mot.length; i++) {
      if (!VOYELLES_ETENDUES.has(mot[i])) { n++; if (n >= 3) return true; } else n = 0;
    }
    return false;
  }

  versAnnexionBase(base) {
    if (this.verbesWhitelist.has(base) || this.numeraux.has(base)) return base;
    if (R_U_CONS.test(base)) return "wu" + base.slice(1);
    if (R_A_GEM_SOURDE.test(base)) return "wu" + base.slice(1);
    if (R_A_GEM_AUTRE.test(base)) return "wa" + base.slice(1);
    if (R_AM_VOY.test(base)) return "wa" + base.slice(1);
    if (R_A_CONS.test(base)) return "u" + base.slice(1);
    if (R_I_CONS_EN.test(base)) return "ye" + base.slice(1);
    if (R_I_LRFWMNB.test(base)) return "yi" + base.slice(1);
    if (R_TA_CONS.test(base)) {
      const cand = "t" + base.slice(2);
      return Postprocess.aTripleConsonne(cand) ? "te" + base.slice(2) : cand;
    }
    if (R_TI_CONS.test(base)) return "te" + base.slice(2);
    return base;
  }

  versLibreBase(base) {
    if (this.verbesWhitelist.has(base) || this.numeraux.has(base)) return base;
    if (R_WU_CONS.test(base)) return "u" + base.slice(2);
    if (R_WA.test(base)) return "a" + base.slice(2);
    if (R_YE_CONS.test(base)) return "i" + base.slice(2);
    if (R_YI.test(base)) return "i" + base.slice(2);
    if (R_U_CONS.test(base)) return "a" + base.slice(1);
    if (R_TE_CONS.test(base)) return "ta" + base.slice(2);
    if (R_T_CONS.test(base) && !R_TAIU.test(base)) return "ta" + base.slice(1);
    return base;
  }

  avecSuffixe(mot, f) {
    if (this.nomsInvariables.has(mot)) return mot;
    const p = mot.split("-");
    const suf = p.length > 1 ? "-" + p.slice(1).join("-") : "";
    return f(p[0]) + suf;
  }

  versAnnexion(mot) {
    return this.avecSuffixe(mot, (b) => this.versAnnexionBase(b));
  }

  versLibre(mot) {
    return this.avecSuffixe(mot, (b) => this.versLibreBase(b));
  }

  /** [est un nom, état, type] */
  identifierNomEtat(mot) {
    const base = mot.split("-")[0];
    if (this.verbesWhitelist.has(base)) return [false, null, null];
    if (this.numeraux.has(base)) return [false, null, null];
    if (this.nomsInvariables.has(base)) return [true, "invariable", "syncrétisme"];
    if (R_WU_CONS.test(base)) return [true, "annexion", "Type3"];
    if (R_WA.test(base)) return [true, "annexion", "Type2"];
    if (R_YE_CONS.test(base)) return [true, "annexion", "Type4"];
    if (R_YI.test(base)) return [true, "annexion", "Type5"];
    if (R_U_CONS.test(base)) return [true, "annexion", "Type1"];
    if (R_A_CONS.test(base)) return [true, "libre", "Type1/2"];
    if (R_I_CONS.test(base)) return [true, "libre", "Type4/5/6"];
    if (R_TE_CONS.test(base)) return [true, "annexion", "Type7/10"];
    if (R_T_CONS.test(base) && !R_TAIU.test(base)) return [true, "annexion", "Type7"];
    if (R_TA_CONS.test(base)) return [true, "libre", "Type7"];
    if (R_TI_CONS.test(base)) return [true, "libre", "Type10/11"];
    if (R_TU_CONS.test(base)) return [true, "libre", "Type9"];
    return [false, null, null];
  }

  contexteAnnexion(tokens, idx) {
    if (idx === 0) return ["libre", "sujet initial"];
    const prec = tokens[idx - 1].split("-")[0].toLowerCase();
    if (this.etatLibreForce.has(prec)) return ["libre", `après '${prec}'`];
    if (this.prepLibre.has(prec)) return ["libre", `après '${prec}' (exception Chaker)`];
    if (this.prepAnnexion.has(prec)) return ["annexion", `après préposition '${prec}'`];
    if (this.numeraux.has(prec)) return ["annexion", `après numéral '${prec}'`];
    if (this.verbesWhitelist.has(prec)) return ["annexion", `sujet post-verbal après '${prec}'`];
    return [null, null];
  }

  /** verbes : un ensemble (has), ou null ; lexcat : mot -> catégorie, ou null. */
  propositionsChaker(tokens, verbes, lexcat) {
    const out = [];
    tokens.forEach((tok, i) => {
      if (verbes && (verbes.has(tok) || verbes.has(tok.split("-")[0]))) return;
      let [estN, etat] = this.identifierNomEtat(tok);
      const cat = lexcat ? lexcat(tok) : null;
      if (cat !== null && LEXCAT_NOMINAL.has(cat)) {
        estN = true;
        if (etat === "invariable") etat = "libre";
      }
      if (!estN || etat === "invariable") return;
      const [requis, raison] = this.contexteAnnexion(tokens, i);
      if (requis === null) return;
      let forme;
      if (requis === "annexion" && etat === "libre") forme = this.versAnnexion(tok);
      else if (requis === "libre" && etat === "annexion") forme = this.versLibre(tok);
      else return;
      if (forme !== tok) out.push({ idx: i, avant: tok, apres: forme, raison: raison ?? "" });
    });
    return out;
  }

  /** Chaker, chaque réécriture annulée si le modèle de langue chute de trop. */
  appliquerChakerValideLm(tokens, verbes, lexcat) {
    const corrigee = tokens.slice();
    const corrections = [];
    for (const p of this.propositionsChaker(tokens, verbes, lexcat)) {
      if (this.lm) {
        const avantS = corrigee.join(" ");
        const essai = corrigee.slice();
        essai[p.idx] = p.apres;
        // Float - Float en Kotlin : la différence est arrondie en 32 bits.
        const delta = Math.fround(this.lm.score(essai.join(" "), true, true) - this.lm.score(avantS, true, true));
        if (delta < -LM_REJET_CHAKER) continue;
      }
      corrigee[p.idx] = p.apres;
      corrections.push(p);
    }
    return [corrigee, corrections];
  }
}
