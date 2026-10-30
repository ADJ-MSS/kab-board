// Candidats.kt : les candidats d'un mot, du vivier et du lexique, et leur score.

import { Config } from "./ressources.js";
import { normalize, PARTICULES, POSSESSIFS } from "./normalisation.js";
import { Phonologie } from "./phonologie.js";
import { comparerChaines, comparerDouble, log10 } from "./kotlin.js";

export const ConfigCand = {
  MAX_DIST_BRUTE: 2,

  W_DIST: 2.0,
  W_FREQ: 0.6,
  W_NSRC: 0.4,
  W_SDX: 0.35,
  W_POS: 0.5,
  PEN_DOUTEUX: 0.7,

  FREQ_PLANCHER_DICO: 50,
  NSRC_PLANCHER_DICO: 4,

  BONUS_VARIANTE: 1.2,
  VAR_MAX_DIST_P: 0.7,

  BONUS_KEEP_DICO: 2.2,
  BONUS_KEEP_SEMI: 1.2,
  BONUS_KEEP_VALIDE: 0.1,
  BONUS_KEEP_OOV: -1.4,

  ABREVIATIONS: new Map([["ɣ", ["ɣer", "ɣef"]]]),

  seuilDistPonderee(longueur) {
    if (longueur <= 3) return 1.0;
    if (longueur <= 5) return 1.8;
    return 2.4;
  },

  POS_VERB_TAGS: new Set(["VAI", "VP", "VAF", "VPN", "VAIT", "VPPP",
    "VS", "VII", "VPA", "VPPN", "VPAIP", "VPAIN"]),
  POS_NOUN_TAGS: new Set(["NMC", "NMP", "NCM", "NC", "ADJ"]),
};

const PREP_ANNEXION = ["n", "i", "gg", "deg", "g", "ɣef", "ddaw", "nnig",
  "ɣer", "fell", "di", "si", "afella", "tama", "idis"];
const PREP_LIBRE = ["ar"];
const ETAT_LIBRE_FORCE = ["d", "ur", "mačči"];

ConfigCand.MOTS_INTOUCHABLES = new Set([
  ...PREP_ANNEXION, ...PREP_LIBRE, ...ETAT_LIBRE_FORCE, ...PARTICULES, ...POSSESSIFS,
  "nekk", "nekki", "kečč", "kemmi", "netta", "nettat", "nekni", "kunwi",
  "kunemti", "nutni", "nutenti", "nekenti",
  "wagi", "tagi", "wid", "tid", "win", "tin", "acu", "ma", "anda", "akken",
  "ad", "ara", "ur", "ulac", "ala", "ihi", "aṭas", "drus", "am", "mara",
  "ticki", "af", "khati",
  "ladɣa", "ɣas", "wissen", "sɣur", "acku", "imi", "mi", "yal",
  "kra", "yiwen", "yiwet",
]);

/** Un candidat : forme, source, distances, fréquence, sources, même code sonore, score. */
export class Candidat {
  constructor(forme, source, distP, dist, freq, nsrc, memeSdx, score = 0.0) {
    this.forme = forme;
    this.source = source;     // keep, amyag, lexcat_<cat>, wordnet, lexique ou abrev
    this.distP = distP;       // distance pondérée kabyle
    this.dist = dist;         // distance DL brute
    this.freq = freq;
    this.nsrc = nsrc;
    this.memeSdx = memeSdx;
    this.score = score;
  }

  /** copy(score = …) */
  avecScore(score) {
    return new Candidat(this.forme, this.source, this.distP, this.dist, this.freq, this.nsrc, this.memeSdx, score);
  }
}

function bits(x) {
  x -= (x >>> 1) & 0x55555555;
  x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
  return (Math.imul((x + (x >>> 4)) & 0x0f0f0f0f, 0x01010101) >>> 24);
}

/** Signature des caractères d'un mot, un bit par classe, sur 64 bits (deux moitiés). */
function signature(m) {
  let bas = 0;
  let haut = 0;
  for (let i = 0; i < m.length; i++) {
    const k = m.charCodeAt(i) & 63;
    if (k < 32) bas |= 1 << k; else haut |= 1 << (k - 32);
  }
  return [bas >>> 0, haut >>> 0];
}

function estDico(source) {
  return source === "amyag" || source === "wordnet" || source.startsWith("lexcat_");
}

export class Generateur {
  constructor(res) {
    this.res = res;
    const n = res.pool.taille;
    this.poolFreq = new Int32Array(n);
    this.poolNsrc = new Uint8Array(n);
    this.poolSrc = new Array(n);
    this.poolSdx = new Array(n);

    const sigBas = new Uint32Array(n);
    const sigHaut = new Uint32Array(n);
    const len = new Int32Array(n);
    const mots = new Array(n);
    const fq = res.poolFreq();
    const ns = res.poolNsrc();
    const sr = res.poolSrc();
    let maxLocal = 0;
    res.pool.forEachIndexed((i, m) => {
      mots[i] = m;
      const [b, h] = signature(m);
      sigBas[i] = b;
      sigHaut[i] = h;
      len[i] = m.length;
      if (m.length > maxLocal) maxLocal = m.length;
      this.poolFreq[i] = fq ? fq(i) : res.freq(m);
      this.poolNsrc[i] = ns ? ns(i) : res.nsrc(m);
      this.poolSrc[i] = sr ? sr(i) : this.sourceDe(m);
    });
    // Le code sonore se déduit des seaux déjà chargés, sans le recalculer
    for (const [cle, idx] of res.sdxIndex) for (const i of idx) this.poolSdx[i] = cle;

    this.plusLongMot = maxLocal;
    const maxL = maxLocal + 1;
    const comptes = new Int32Array(maxL + 1);
    for (const l of len) comptes[l]++;
    this.debutLongueur = new Int32Array(maxL + 2);
    for (let l = 0; l <= maxL; l++) this.debutLongueur[l + 1] = this.debutLongueur[l] + comptes[l];
    const pos = this.debutLongueur.slice();
    this.ordSigBas = new Uint32Array(n);
    this.ordSigHaut = new Uint32Array(n);
    this.ordMots = new Array(n);
    for (let i = 0; i < n; i++) {
      const p = pos[len[i]]++;
      this.ordSigBas[p] = sigBas[i];
      this.ordSigHaut[p] = sigHaut[i];
      this.ordMots[p] = mots[i];
    }
    this.cote = Math.max(maxLocal, 64);
    this.d = null;
  }

  motVersIndex(forme) {
    return this.res.pool.indexDe(forme);
  }

  sourceDe(forme) {
    const res = this.res;
    if (res.amyag.has(forme)) return "amyag";
    const cat = res.lexcat(forme);
    if (cat !== null) return "lexcat_" + cat;
    if (res.wnFormes.has(forme)) return "wordnet";
    return "lexique";
  }

  scorer(c, posTag, bonusKeep) {
    const C = ConfigCand;
    if (c.source === "keep") {
      return bonusKeep +
        C.W_FREQ * Math.min(log10(c.freq + 1.0) / 6.0, 1.0) +
        C.W_NSRC * Math.min(c.nsrc, 8) / 8.0;
    }
    const estVerbal = c.source === "amyag";
    const estNominal = c.source.startsWith("lexcat_");
    const dico = estDico(c.source);
    const freq = dico ? Math.max(c.freq, C.FREQ_PLANCHER_DICO) : c.freq;
    const nsrc = dico ? Math.max(c.nsrc, C.NSRC_PLANCHER_DICO) : c.nsrc;

    let s = -C.W_DIST * c.distP;
    s += C.W_FREQ * Math.min(log10(freq + 1.0) / 6.0, 1.0);
    s += C.W_NSRC * Math.min(nsrc, 8) / 8.0;
    if (c.memeSdx) s += C.W_SDX;
    if (dico && c.memeSdx && c.distP <= C.VAR_MAX_DIST_P) s += C.BONUS_VARIANTE;
    if (C.POS_NOUN_TAGS.has(posTag) && estVerbal && !estNominal) s -= C.W_POS;
    if (C.POS_VERB_TAGS.has(posTag) && estNominal && !estVerbal) s -= C.W_POS;
    if (c.source === "lexique" && c.nsrc < Config.MIN_SOURCES_FIABLE) s -= C.PEN_DOUTEUX;
    return s;
  }

  /** Damerau-Levenshtein non restreint, celui de rapidfuzz. */
  distBrute(a, b, cutoff) {
    if (a === b) return 0;
    const la = a.length;
    const lb = b.length;
    if (la === 0) return lb;
    if (lb === 0) return la;
    if (Math.abs(la - lb) > cutoff) return cutoff + 1;

    const cote = Math.max(this.cote, la, lb) + 2;
    if (!this.d || this.d.cote < cote) this.d = { cote, t: new Int32Array(cote * cote) };
    const t = this.d.t;
    const L = this.d.cote;
    const maxDist = la + lb;
    t[0] = maxDist;
    for (let i = 0; i <= la; i++) { t[(i + 1) * L] = maxDist; t[(i + 1) * L + 1] = i; }
    for (let j = 0; j <= lb; j++) { t[j + 1] = maxDist; t[L + j + 1] = j; }

    const derniere = new Map();
    for (let i = 1; i <= la; i++) {
      let db = 0;
      let mini = 2147483647;
      for (let j = 1; j <= lb; j++) {
        const k = derniere.get(b[j - 1]) ?? 0;
        const l = db;
        let cout;
        if (a[i - 1] === b[j - 1]) { cout = 0; db = j; } else cout = 1;
        const v = Math.min(
          t[i * L + j] + cout,                               // substitution
          t[(i + 1) * L + j] + 1,                            // insertion
          t[i * L + j + 1] + 1,                              // suppression
          t[k * L + l] + (i - k - 1) + 1 + (j - l - 1));     // transposition
        t[(i + 1) * L + j + 1] = v;
        if (v < mini) mini = v;
      }
      derniere.set(a[i - 1], i);
      if (mini > cutoff) return cutoff + 1;
    }
    return t[(la + 1) * L + lb + 1];
  }

  /** Candidats triés, « garder » compris. large pour le top-5. */
  generer(token, posTag = "", nbMax = 24, large = false) {
    const C = ConfigCand;
    const res = this.res;
    const keep = new Candidat(token, "keep", 0.0, 0, res.freq(token), res.nsrc(token), true);

    if ((C.MOTS_INTOUCHABLES.has(token) || PARTICULES.has(token) ||
         POSSESSIFS.has(token) || token.length < 2) && !C.ABREVIATIONS.has(token)) {
      keep.score = this.scorer(keep, posTag, C.BONUS_KEEP_DICO);
      if (!large) return [keep];
    }

    let bonusKeep;
    let niveauDico;
    if (C.ABREVIATIONS.has(token)) {
      bonusKeep = C.BONUS_KEEP_OOV; niveauDico = false;
    } else if (res.amyag.has(token) || res.lexcat(token) !== null || res.wnFormes.has(token)) {
      bonusKeep = C.BONUS_KEEP_DICO; niveauDico = true;
    } else if (res.nsrc(token) >= Config.MIN_SOURCES_FIABLE || res.freq(token) >= Config.FREQ_FIABLE) {
      bonusKeep = C.BONUS_KEEP_SEMI; niveauDico = false;
    } else if (res.valideParAffixe(token)) {
      bonusKeep = C.BONUS_KEEP_VALIDE; niveauDico = false;
    } else {
      bonusKeep = C.BONUS_KEEP_OOV; niveauDico = false;
    }
    keep.score = this.scorer(keep, posTag, bonusKeep);

    const sdxTok = Phonologie.soundexKabyle(token);
    const formes = new Set();

    // Groupe sonore : rattrape ce que la distance seule rate
    const groupe = res.sdxIndex.get(sdxTok);
    if (groupe) {
      for (const i of groupe) {
        const cand = res.pool.get(i);
        if (cand !== token && this.distBrute(token, cand, C.MAX_DIST_BRUTE) <= C.MAX_DIST_BRUTE) formes.add(cand);
      }
    }

    // Balayage du vivier, exhaustif : pas de coupe arbitraire.
    if ((large || !niveauDico) && token.length >= 2) {
      const k = C.MAX_DIST_BRUTE;
      const [tokBas, tokHaut] = signature(token);
      const lenTok = token.length;
      const lo = Math.max(0, lenTok - k);
      const hi = Math.min(this.debutLongueur.length - 2, lenTok + k);
      const fin = this.debutLongueur[hi + 1];
      for (let i = this.debutLongueur[lo]; i < fin; i++) {
        const sb = this.ordSigBas[i];
        const sh = this.ordSigHaut[i];
        if (bits(tokBas & ~sb) + bits(tokHaut & ~sh) <= k && bits(sb & ~tokBas) + bits(sh & ~tokHaut) <= k) {
          const cand = this.ordMots[i];
          if (cand !== token && this.distBrute(token, cand, k) <= k) formes.add(cand);
        }
      }
    }

    const abrevs = new Set(C.ABREVIATIONS.get(token) ?? []);
    for (const a of abrevs) formes.add(a);

    const seuil = C.seuilDistPonderee(token.length) * (large ? 1.4 : 1.0);
    const cands = [keep];
    // Ordre alphabétique : rend les ex æquo de score reproductibles
    for (const f of [...formes].sort(comparerChaines)) {
      const estAbrev = abrevs.has(f);
      const dp = estAbrev ? 0.5 : Phonologie.distanceKabyle(token, f);
      if (!estAbrev && dp > seuil) continue;
      const idx = this.motVersIndex(f);           // -1 : abréviation, hors vivier
      const c = new Candidat(
        f,
        estAbrev ? "abrev" : idx >= 0 ? this.poolSrc[idx] : this.sourceDe(f),
        Math.round(dp * 1000.0) / 1000.0,
        this.distBrute(token, f, 99),
        idx >= 0 ? this.poolFreq[idx] : res.freq(f),
        idx >= 0 ? this.poolNsrc[idx] : res.nsrc(f),
        (idx >= 0 ? this.poolSdx[idx] : Phonologie.soundexKabyle(f)) === sdxTok);
      c.score = this.scorer(c, posTag, bonusKeep);
      cands.push(c);
    }
    return cands.sort((x, y) => comparerDouble(y.score, x.score)).slice(0, nbMax);
  }

  /** Les nb meilleures formes pour un mot isolé. */
  topCandidats(motBrut, nb = 5) {
    const mot = normalize(motBrut);
    const freqAff = (c) => (c.source !== "lexique" && c.source !== "keep"
      ? Math.max(c.freq, ConfigCand.FREQ_PLANCHER_DICO) : c.freq);
    return this.generer(mot, "", 40, true)
      .filter((c) => c.forme !== mot)
      .sort((a, b) => (a.dist - b.dist) || (freqAff(b) - freqAff(a)) ||
        comparerDouble(a.distP, b.distP) || comparerChaines(a.forme, b.forme))
      .slice(0, nb);
  }
}
