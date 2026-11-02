// Les ressources compressées de l'extension pour Firefox, dont Mozilla limite la taille :
// décompressées par kab_xz.wasm (xz-embedded), et le vocabulaire du modèle de langue,
// que l'archive omet, recalculé. On retrouve le fichier d'origine, octet pour octet.
//
// Le modèle de langue demande une dizaine de secondes de décompression : le résultat est
// gardé dans IndexedDB, sous son empreinte, et les chargements suivants le relisent.

const MORCEAU = 1 << 20;
const XZ_OK = 0;
const XZ_STREAM_END = 1;
// Assez pour lire l'en-tête d'un modèle KenLM jusqu'à son vocabulaire, à l'ordre 6.
const TETE = 168;

/** Les morceaux de plusieurs fichiers, lus l'un après l'autre comme un seul. */
export async function* morceaux(urls) {
  for (const url of urls) {
    const reponse = await fetch(url);
    if (!reponse.ok) throw new Error(`ressource introuvable : ${url}`);
    const lecteur = reponse.body.getReader();
    for (;;) {
      const { done, value } = await lecteur.read();
      if (done) break;
      yield value;
    }
  }
}

/**
 * Décompresse une ressource. fabrique : le module KabXz (kab_xz.mjs) ; source : ses
 * morceaux compressés (Uint8Array), dans l'ordre ; info : { taille, vocabulaire } (de
 * compresses.json). Rend les octets d'origine, une vue sur la mémoire d'un module à part,
 * qui part avec elle.
 */
export async function restituer(fabrique, options, source, info) {
  const m = await fabrique(options);
  const sortie = m._malloc(info.taille);
  const tampon = m._malloc(MORCEAU);
  const compteurs = m._malloc(8);
  const d = m._kab_xz_neuf();
  if (!sortie || !tampon || !compteurs || !d) throw new Error("décompression : mémoire insuffisante");
  // Le vocabulaire omis : la sortie s'arrête d'abord après l'en-tête, pour lui laisser sa place.
  let trou = info.vocabulaire;
  let fin = trou ? Math.min(TETE, info.taille) : info.taille;
  let ecrit = 0;
  let fini = false;
  try {
    for await (const morceau of source) {
      for (let pos = 0; pos < morceau.length && !fini;) {
        const n = Math.min(MORCEAU, morceau.length - pos);
        m.HEAPU8.set(morceau.subarray(pos, pos + n), tampon);
        pos += n;
        let pris = 0;
        for (;;) {
          const r = m._kab_xz_avancer(d, tampon + pris, n - pris, sortie + ecrit, fin - ecrit,
            compteurs, compteurs + 4);
          pris += m.HEAPU32[compteurs >> 2];
          ecrit += m.HEAPU32[(compteurs + 4) >> 2];
          if (r === XZ_STREAM_END) {
            fini = true;
            break;
          }
          // Une erreur, ou des données en trop : xz-embedded le dit au second appel sans progrès.
          if (r !== XZ_OK) throw new Error(`décompression : erreur ${r}`);
          if (trou && ecrit === fin) {
            ecrit = laisserLaPlace(m, sortie, ecrit);
            fin = info.taille;
            trou = false;
          } else if (pris === n) {
            break;
          }
        }
      }
    }
    if (!fini || ecrit !== info.taille) throw new Error("décompression : fichier incomplet");
    if (info.vocabulaire && !m._kab_kenlm_vocabulaire(sortie, info.taille)) {
      throw new Error("décompression : vocabulaire du modèle introuvable");
    }
  } finally {
    m._kab_xz_fermer(d);
    m._free(tampon);
    m._free(compteurs);
  }
  return m.HEAPU8.subarray(sortie, sortie + info.taille);
}

/** Écarte ce qui suit l'en-tête de la place du vocabulaire ; rend la nouvelle fin écrite. */
function laisserLaPlace(m, sortie, ecrit) {
  const place = m._malloc(8);
  if (!m._kab_kenlm_vocabulaire_place(sortie, place, place + 4)) {
    throw new Error("décompression : en-tête du modèle illisible");
  }
  const debut = m.HEAPU32[place >> 2];
  const taille = m.HEAPU32[(place + 4) >> 2];
  m._free(place);
  m.HEAPU8.copyWithin(sortie + debut + taille, sortie + debut, sortie + ecrit);
  return ecrit + taille;
}

const BASE = "kab-board";
const MAGASIN = "ressources";

function requete(r) {
  return new Promise((resoudre, rejeter) => {
    r.onsuccess = () => resoudre(r.result);
    r.onerror = () => rejeter(r.error);
  });
}

async function cache() {
  const ouverture = indexedDB.open(BASE, 1);
  ouverture.onupgradeneeded = () => ouverture.result.createObjectStore(MAGASIN);
  return requete(ouverture);
}

/**
 * Une ressource compressée : du cache s'il l'a, sinon décompressée (puis gardée).
 * url : celle du fichier, sans .xz ; info : { taille, sha256, parties, vocabulaire } : le
 * flux xz est en parties (<fichier>.xz.1, .xz.2…), le contrôle de Mozilla refusant les
 * fichiers de plus de 100 Mio.
 */
export async function ressource(url, info, fabrique, options) {
  let base = null;
  try {
    base = await cache();
    const blob = await requete(base.transaction(MAGASIN).objectStore(MAGASIN).get(info.sha256));
    if (blob && blob.size === info.taille) {
      const octets = new Uint8Array(await blob.arrayBuffer());
      base.close();
      return octets;
    }
  } catch (erreur) {
    // pas de cache (navigation privée, quota) : on décompresse à chaque fois
  }
  const parties = Array.from({ length: info.parties }, (_, k) => `${url}.xz.${k + 1}`);
  const octets = await restituer(fabrique, options, morceaux(parties), info);
  if (base) {
    try {
      const t = base.transaction(MAGASIN, "readwrite");
      t.objectStore(MAGASIN).put(new Blob([octets]), info.sha256);
      await new Promise((resoudre) => { t.oncomplete = t.onerror = t.onabort = resoudre; });
    } catch (erreur) {
      // le cache est plein : tant pis, la prochaine fois décompressera aussi
    }
    base.close();
  }
  return octets;
}
