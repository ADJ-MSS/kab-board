// Ressources.kt : le lexique, les formes verbales, les catégories, le graphe
// sémantique et le vivier, lus dans les fichiers exportés pour l'application.

import { RechercheFrancais } from "./recherche_francais.js";
import { MotDuJour } from "./mot_du_jour.js";

const MAGIC = 0x4c425154;   // « TQBL » en petit-boutiste
const BLOC = 16;
// Comme Java, qui garde une marque d'ordre en tête de fichier.
const utf8 = new TextDecoder("utf-8", { ignoreBOM: true });

function vue(octets) {
  return new DataView(octets.buffer, octets.byteOffset, octets.byteLength);
}

/** Les lignes d'un fichier texte, comme File.readLines. */
export function lignes(octets) {
  const t = utf8.decode(octets);
  if (!t) return [];
  const l = t.split(/\r\n|\n|\r/);
  if (l[l.length - 1] === "") l.pop();
  return l;
}

/** Liste de mots triés, préfixes factorisés par blocs de 16. */
export class ListeMots {
  constructor(octets, nom = "") {
    this.o = octets;
    this.d = vue(octets);
    if (this.d.getInt32(0, true) !== MAGIC) throw new Error(`signature absente : ${nom}`);
    this.taille = this.d.getInt32(6, true);
    this.nbBlocs = this.d.getInt32(10, true);
    this.debutOffsets = 14;
    this.debutDonnees = this.debutOffsets + this.nbBlocs * 4;
    this._premiers = null;
  }

  /** Premier mot de chaque bloc, gardé en clair. */
  get premiers() {
    if (!this._premiers) {
      this._premiers = new Array(this.nbBlocs);
      for (let b = 0; b < this.nbBlocs; b++) this._premiers[b] = this.bloc(b)[0];
    }
    return this._premiers;
  }

  bloc(nb) {
    const d = this.d;
    let p = this.debutDonnees + d.getInt32(this.debutOffsets + nb * 4, true);
    const n = Math.min(BLOC, this.taille - nb * BLOC);
    const out = new Array(n);
    let prec = "";
    for (let j = 0; j < n; j++) {
      if (j === 0) {
        const len = d.getUint16(p, true); p += 2;
        prec = utf8.decode(this.o.subarray(p, p + len));
        p += len;
      } else {
        const c = d.getUint8(p); p += 1;
        const len = d.getUint16(p, true); p += 2;
        prec = prec.slice(0, c) + utf8.decode(this.o.subarray(p, p + len));
        p += len;
      }
      out[j] = prec;
    }
    return out;
  }

  get(i) {
    return this.bloc(Math.floor(i / BLOC))[i % BLOC];
  }

  /** Index du mot, ou -1. Recherche binaire sur les blocs puis balayage. */
  indexDe(mot) {
    const p = this.premiers;
    let lo = 0;
    let hi = this.nbBlocs - 1;
    let cible = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >>> 1;
      if (p[mid] <= mot) { cible = mid; lo = mid + 1; } else hi = mid - 1;
    }
    const b = this.bloc(cible);
    for (let j = 0; j < b.length; j++) if (b[j] === mot) return cible * BLOC + j;
    return -1;
  }

  has(mot) {
    return this.indexDe(mot) >= 0;
  }

  /** Parcours séquentiel. */
  forEachIndexed(action) {
    let i = 0;
    for (let nb = 0; i < this.taille; nb++) {
      for (const m of this.bloc(nb)) action(i++, m);
    }
  }
}

class TableauU32 {
  constructor(octets) {
    this.d = vue(octets);
    this.taille = this.d.getInt32(6, true);
  }

  get(i) {
    return this.d.getInt32(10 + i * 4, true);
  }
}

class TableauU8 {
  constructor(octets) {
    this.o = octets;
    this.taille = vue(octets).getInt32(6, true);
  }

  get(i) {
    return this.o[10 + i];
  }
}

export const Config = {
  MIN_SOURCES_FIABLE: 3,
  FREQ_FIABLE: 300,
  FREQ_MIN_CANDIDAT: 10,
};

const CONTENT_CATS = new Set(["masc", "fem", "fem_pl", "adj_masc", "adj_fem", "adverb", "ambig"]);
const PREF = ["y", "t", "n", "tt", "d", "i", "a", "u", "m", "ms", "s"];
const SUFF = ["en", "ent", "iɣ", "eɣ", "aɣ", "iḍ", "id", "an", "in"];

/**
 * fichier(nom) rend les octets d'un fichier du dossier des ressources, ou null s'il
 * n'y est pas.
 */
export class Ressources {
  constructor(fichier) {
    const doit = (nom) => {
      const o = fichier(nom);
      if (!o) throw new Error(`ressource absente : ${nom}`);
      return o;
    };
    this.lexique = new ListeMots(doit("lexique.mots"), "lexique.mots");
    this.lexFreq = new TableauU32(doit("lexique.freq"));
    this.lexNsrc = new TableauU8(doit("lexique.nsrc"));

    this.amyag = new ListeMots(doit("amyag.mots"), "amyag.mots");

    this.lexcatMots = new ListeMots(doit("lexcat.mots"), "lexcat.mots");
    this.lexcatCat = new TableauU8(doit("lexcat.cat"));
    this.catNoms = lignes(doit("lexcat.noms"));

    this.wnFormes = new ListeMots(doit("wordnet.formes"), "wordnet.formes");
    this.wnGloses = lignes(doit("wordnet.gloses"));

    this.pool = new ListeMots(doit("pool.mots"), "pool.mots");
    this.sdxIndex = new Map();
    const sdx = doit("pool.sdx");
    const d = vue(sdx);
    const n = d.getInt32(6, true);
    let p = 10;
    for (let k = 0; k < n; k++) {
      const lk = d.getUint8(p);
      const nb = d.getUint16(p + 1, true);
      p += 3;
      const cle = utf8.decode(sdx.subarray(p, p + lk));
      p += lk;
      const idx = new Int32Array(nb);
      for (let j = 0; j < nb; j++) idx[j] = d.getInt32(p + j * 4, true);
      p += nb * 4;
      this.sdxIndex.set(cle, idx);
    }

    // Tableaux alignés sur le vivier, produits à l'export.
    const pf = fichier("pool.freq");
    const pn = fichier("pool.nsrc");
    const ps = fichier("pool.src");
    const noms = fichier("pool.srcnoms");
    this.pFreq = pf ? new TableauU32(pf) : null;
    this.pNsrc = pn ? new TableauU8(pn) : null;
    this.pSrc = ps ? new TableauU8(ps) : null;
    this.srcNoms = noms ? lignes(noms) : [];

    const fr = fichier("pool.frequents");
    /** Formes les plus fréquentes du vivier, arrêtées à l'export. */
    this.frequents = fr ? lignes(fr) : [];

    this.fiableCache = new Map();
    this._wnListe = null;
    this._glosesPliees = null;
    this._motsDuJour = null;
  }

  poolFreq() {
    return this.pFreq ? (i) => this.pFreq.get(i) : null;
  }

  poolNsrc() {
    return this.pNsrc ? (i) => this.pNsrc.get(i) : null;
  }

  poolSrc() {
    return this.pSrc && this.srcNoms.length ? (i) => this.srcNoms[this.pSrc.get(i)] : null;
  }

  freq(mot) {
    const i = this.lexique.indexDe(mot);
    return i < 0 ? 0 : this.lexFreq.get(i);
  }

  freqParIndex(i) {
    return this.lexFreq.get(i);
  }

  nsrc(mot) {
    const i = this.lexique.indexDe(mot);
    return i < 0 ? 0 : this.lexNsrc.get(i);
  }

  lexcat(mot) {
    const i = this.lexcatMots.indexDe(mot);
    return i < 0 ? null : this.catNoms[this.lexcatCat.get(i)];
  }

  glose(mot) {
    const i = this.wnFormes.indexDe(mot);
    return i < 0 ? "" : this.wnGloses[i];
  }

  /** Les nb formes dont la glose répond le mieux au mot français requete. */
  chercherFrancais(requete, nb) {
    const q = RechercheFrancais.plier(requete);
    if (q.length < RechercheFrancais.REQUETE_MIN) return [];
    if (!this._wnListe) {
      this._wnListe = [];
      this.wnFormes.forEachIndexed((_, f) => this._wnListe.push(f));
      this._glosesPliees = this.wnGloses.map((g) => RechercheFrancais.plier(g));
    }
    const formes = this._wnListe;
    const gloses = this._glosesPliees;
    const trouves = [];
    for (let i = 0; i < Math.min(formes.length, gloses.length); i++) {
      const r = RechercheFrancais.rang(gloses[i], q);
      if (r === null) continue;
      trouves.push({ forme: formes[i], glose: this.wnGloses[i], rang: r, frequence: this.freq(formes[i]) });
    }
    return RechercheFrancais.classer(trouves, nb);
  }

  /** Candidats du mot du jour, calculés au premier appel. */
  get motsDuJour() {
    if (!this._motsDuJour) this._motsDuJour = MotDuJour.candidats(this.frequents, (m) => this.glose(m));
    return this._motsDuJour;
  }

  estContent(mot) {
    return CONTENT_CATS.has(this.lexcat(mot));
  }

  /** Mot de confiance : forme verbale, lexique par catégorie, multi-sources ou très fréquent. */
  fiable(mot) {
    let r = this.fiableCache.get(mot);
    if (r === undefined) {
      r = this.amyag.has(mot) || this.lexcat(mot) !== null ||
        this.nsrc(mot) >= Config.MIN_SOURCES_FIABLE ||
        this.freq(mot) >= Config.FREQ_FIABLE;
      this.fiableCache.set(mot, r);
    }
    return r;
  }

  /** Préfixe ou suffixe productif, et racine fiable. */
  valideParAffixe(mot) {
    for (const p of PREF) {
      if (mot.startsWith(p) && mot.length - p.length >= 2 && this.fiable(mot.slice(p.length))) return true;
    }
    for (const s of SUFF) {
      if (mot.endsWith(s) && mot.length - s.length >= 2 &&
          this.fiable(mot.slice(0, mot.length - s.length))) return true;
    }
    return false;
  }
}
