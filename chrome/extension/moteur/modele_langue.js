// Le modèle de langue (KenLM, 3-grammes) dans le navigateur : ModeleLangue.kt, sur le
// pont WebAssembly (kab_lm.wasm) au lieu du pont JNI.

export class Etat {
  constructor(lm, p) {
    this.lm = lm;
    this.p = p;
  }

  close() {
    if (this.p) this.lm.m._kab_etat_liberer(this.p);
    this.p = 0;
  }
}

export class ModeleLangue {
  constructor(m, h) {
    this.m = m;
    this.h = h;
    this.index = new Map();
  }

  /** Ouvre le modèle à partir de ses octets, que le module garde le temps de le lire. */
  static async ouvrir(fabrique, octets, options = {}) {
    const m = await fabrique(options);
    const chemin = "/kabyle_3gram.binary";
    m.FS.writeFile(chemin, octets, { canOwn: true });
    const h = m._kab_lm_ouvrir(ModeleLangue.chaine(m, chemin));
    m.FS.unlink(chemin);
    if (!h) throw new Error("KenLM : ouverture impossible du modèle");
    return new ModeleLangue(m, h);
  }

  static chaine(m, texte) {
    const n = m.lengthBytesUTF8(texte) + 1;
    const p = m._malloc(n);
    m.stringToUTF8(texte, p, n);
    return p;
  }

  get ordre() {
    return this.m._kab_lm_ordre(this.h);
  }

  etat() {
    return new Etat(this, this.m._kab_etat_neuf(this.h));
  }

  debutPhrase(e) {
    this.m._kab_debut_phrase(this.h, e.p);
  }

  contexteVide(e) {
    this.m._kab_contexte_vide(this.h, e.p);
  }

  copier(src, dst) {
    this.m._kab_etat_copier(this.h, src.p, dst.p);
  }

  memeEtat(a, b) {
    return this.m._kab_etat_egal(this.h, a.p, b.p) !== 0;
  }

  /** L'index d'un mot dans le vocabulaire, gardé pour les fois suivantes. */
  indexDe(mot) {
    let i = this.index.get(mot);
    if (i === undefined) {
      const p = ModeleLangue.chaine(this.m, mot);
      i = this.m._kab_lm_index(this.h, p) >>> 0;
      this.m._free(p);
      if (this.index.size > 500000) this.index.clear();
      this.index.set(mot, i);
    }
    return i;
  }

  /** log10 P(mot | entrée), et écrit l'état résultant dans sortie. */
  baseScore(entree, mot, sortie) {
    return this.m._kab_base_score_index(this.h, entree.p, this.indexDe(mot), sortie.p);
  }

  /** kenlm.Model.score(phrase, bos, eos). */
  score(phrase, bos = true, eos = true) {
    const p = ModeleLangue.chaine(this.m, phrase);
    try {
      return this.m._kab_score_phrase(this.h, p, bos ? 1 : 0, eos ? 1 : 0);
    } finally {
      this.m._free(p);
    }
  }

  close() {
    this.m._kab_lm_fermer(this.h);
    this.h = 0;
  }
}
