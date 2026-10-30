// L'étiqueteur morphosyntaxique : Etiqueteur.kt, sur le pont WebAssembly de CRFsuite
// (kab_crf.wasm).

const encodeur = new TextEncoder();
const CHIFFRE = /^\p{Nd}$/u;

/** Char.uppercaseChar de Kotlin : une lettre pour une lettre, sinon la même. */
function majusculeChar(c) {
  const m = c.toUpperCase();
  return m.length === 1 ? m : c;
}

export class Etiqueteur {
  constructor(m, h) {
    this.m = m;
    this.h = h;
    const n = m._kab_crf_nb_etiquettes(h);
    const tampon = m._malloc(256);
    this.etiquettes = [];
    for (let i = 0; i < n; i++) {
      m._kab_crf_etiquette(h, i, tampon, 256);
      this.etiquettes.push(m.UTF8ToString(tampon));
    }
    m._free(tampon);
  }

  static async ouvrir(fabrique, octets, options = {}) {
    const m = await fabrique(options);
    const chemin = "/pos_kab.crfsuite";
    m.FS.writeFile(chemin, octets);
    const n = m.lengthBytesUTF8(chemin) + 1;
    const p = m._malloc(n);
    m.stringToUTF8(chemin, p, n);
    const h = m._kab_crf_ouvrir(p);
    m._free(p);
    m.FS.unlink(chemin);
    if (!h) throw new Error("CRFsuite : ouverture impossible du modèle");
    return new Etiqueteur(m, h);
  }

  get nbEtiquettes() {
    return this.etiquettes.length;
  }

  /** Traits d'un mot, exactement ceux de _pos_features. */
  static traits(phrase, i, noms, poids) {
    const w = phrase[i];
    const chaine = (k, v) => { noms.push(`${k}:${v}`); poids.push(1.0); };
    const bool = (k, v) => { noms.push(k); poids.push(v ? 1.0 : 0.0); };
    const fin = (n) => (n >= w.length ? w : w.slice(w.length - n));

    chaine("word", w);
    bool("is_one_letter", w.length === 1);
    bool("is_first", i === 0);
    bool("is_last", i === phrase.length - 1);
    bool("is_capitalized", w.length > 0 && majusculeChar(w[0]) === w[0]);
    bool("is_all_caps", w.toUpperCase() === w);
    bool("is_all_lower", w.toLowerCase() === w);
    chaine("prefix-1", w.slice(0, 1));
    chaine("prefix-2", w.slice(0, 2));
    chaine("prefix-3", w.slice(0, 3));
    chaine("prefix-4", w.slice(0, 4));
    chaine("prefix-5", w.slice(0, 5));
    chaine("suffix-1", fin(1));
    chaine("suffix-2", fin(2));
    chaine("suffix-3", fin(3));
    chaine("suffix-4", fin(4));
    chaine("prev_word", i === 0 ? "" : phrase[i - 1]);
    chaine("next_word", i === phrase.length - 1 ? "" : phrase[i + 1]);
    bool("is_numeric", w.length > 0 && [...w].every((c) => c.length === 1 && CHIFFRE.test(c)));
    bool("capitals_inside", w.slice(1).toLowerCase() !== w.slice(1));
  }

  /** Une étiquette par mot. */
  etiqueter(phrase) {
    if (!phrase.length) return [];
    const noms = [];
    const poids = [];
    const bornes = new Int32Array(phrase.length);
    for (let i = 0; i < phrase.length; i++) {
      Etiqueteur.traits(phrase, i, noms, poids);
      bornes[i] = noms.length;
    }
    const m = this.m;
    const octets = encodeur.encode(noms.join("\0") + "\0");
    const pNoms = m._malloc(octets.length);
    const pPoids = m._malloc(poids.length * 8);
    const pBornes = m._malloc(bornes.length * 4);
    const pSortie = m._malloc(phrase.length * 4);
    try {
      m.HEAPU8.set(octets, pNoms);
      m.HEAPF64.set(poids, pPoids / 8);
      m.HEAP32.set(bornes, pBornes / 4);
      m._kab_crf_etiqueter(this.h, pNoms, pPoids, pBornes, phrase.length, pSortie);
      return Array.from(m.HEAP32.subarray(pSortie / 4, pSortie / 4 + phrase.length), (k) => this.etiquettes[k]);
    } finally {
      m._free(pNoms);
      m._free(pPoids);
      m._free(pBornes);
      m._free(pSortie);
    }
  }

  close() {
    this.m._kab_crf_fermer(this.h);
    this.h = 0;
  }
}
