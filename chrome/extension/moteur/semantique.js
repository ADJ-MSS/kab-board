// Semantique.kt : le graphe racines, mots, concepts.

const f32 = Math.fround;
const SEPT_DIXIEMES = f32(0.7);

export class Semantique {
  /** octets(nom) : les octets d'un fichier des ressources, ou null. */
  constructor(octets) {
    // forme -> [identifiants de concepts, poids de confiance]
    this.ancrages = new Map();
    this.voisins = new Map();
    const utf8 = new TextDecoder("utf-8", { ignoreBOM: true });
    const a = octets("wordnet.ancrages");
    if (a) {
      const d = new DataView(a.buffer, a.byteOffset, a.byteLength);
      const n = d.getInt32(6, true);
      let p = 10;
      for (let k = 0; k < n; k++) {
        const lm = d.getUint16(p, true);
        const nd = d.getUint16(p + 2, true);
        p += 4;
        const mot = utf8.decode(a.subarray(p, p + lm));
        p += lm;
        const ids = new Int32Array(nd);
        const poids = new Float32Array(nd);
        for (let j = 0; j < nd; j++) {
          ids[j] = d.getInt32(p, true);
          poids[j] = d.getFloat32(p + 4, true);
          p += 8;
        }
        this.ancrages.set(mot, [ids, poids]);
      }
    }
    const g = octets("wordnet.voisins");
    if (g) {
      const d = new DataView(g.buffer, g.byteOffset, g.byteLength);
      const n = d.getInt32(6, true);
      let p = 10;
      for (let k = 0; k < n; k++) {
        const sid = d.getInt32(p, true);
        const nv = d.getUint16(p + 4, true);
        p += 6;
        const v = new Int32Array(nv);
        for (let j = 0; j < nv; j++) { v[j] = d.getInt32(p, true); p += 4; }
        this.voisins.set(sid, v);
      }
    }
  }

  /** Union des concepts des formes de la phrase, position exclure omise. */
  contexte(formes, exclure = -1) {
    const ctx = new Set();
    formes.forEach((f, i) => {
      if (i === exclure) return;
      const a = this.ancrages.get(f);
      if (a) for (const id of a[0]) ctx.add(id);
    });
    return ctx;
  }

  /** Lien sémantique (un flottant 32 bits, entre 0 et 1) : le poids si un concept est partagé, 0,7 × poids s'il est relié. */
  coherence(forme, contexteSids) {
    if (!contexteSids.size) return 0;
    const a = this.ancrages.get(forme);
    if (!a) return 0;
    let meilleur = 0;
    const [ids, poids] = a;
    for (let k = 0; k < ids.length; k++) {
      const sid = ids[k];
      if (contexteSids.has(sid)) return poids[k];
      const v = this.voisins.get(sid);
      if (!v) continue;
      for (const x of v) {
        if (contexteSids.has(x)) {
          const c = f32(SEPT_DIXIEMES * poids[k]);
          if (c > meilleur) meilleur = c;
          break;
        }
      }
    }
    return meilleur;
  }
}
