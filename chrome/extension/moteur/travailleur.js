// Le correcteur, dans un fil à part (lancé par le document hors écran sous Chrome, par la
// page de fond sous Firefox) : il charge le moteur une fois (les ressources de
// l'application, 300 Mo), puis répond aux requêtes, une à la fois. La dictée aussi passe ici, le modèle vocal chargé à la première ; l'audio
// arrive en 16 kHz, et passe par les 16 bits du micro du téléphone. Pour Firefox, les plus
// grosses ressources sont compressées (compresses.json, compression.js).

import KenLM from "./kab_lm.mjs";
import CRFsuite from "./kab_crf.mjs";
import { Moteur, TABLE_BV } from "./moteur.js";
import { Transcripteur, commeLeMicro } from "./transcripteur.js";
import { erreur, expliquer, journal, mo, noter, noterAppareil } from "./diagnostic.js";

const RESSOURCES = new URL("../ressources/", import.meta.url);

/** Les octets d'un fichier de l'extension, ou null s'il n'y est pas ; le journal dit pourquoi. */
async function octets(url, facultatif = false) {
  const nom = url.href.slice(new URL("../", import.meta.url).href.length);
  let r;
  try {
    r = await fetch(url);
  } catch (e) {
    if (!facultatif) noter(`${nom} : illisible (${e && e.message || e})`);
    return null;
  }
  if (!r.ok) {
    if (!facultatif) noter(`${nom} : absent (HTTP ${r.status})`);
    return null;
  }
  try {
    const o = new Uint8Array(await r.arrayBuffer());
    noter(`${nom} : ${mo(o.length)}`);
    return o;
  } catch (e) {
    // Le navigateur n'a pas pu réserver la place du fichier.
    noter(`${nom} : lecture interrompue (${e && e.name}: ${e && e.message || e})`);
    const taille = Number(r.headers.get("content-length")) || 0;
    throw erreur("memoire", `pas assez de place pour lire ${nom}${taille ? ` (${mo(taille)})` : ""}`, nom);
  }
}

const compresses = octets(new URL("compresses.json", RESSOURCES), true)
  .then((o) => (o ? JSON.parse(new TextDecoder().decode(o)) : {}));
// La taille attendue de chaque ressource, pour reconnaître une archive mal décompressée.
const inventaire = octets(new URL("inventaire.json", RESSOURCES), true)
  .then((o) => (o ? JSON.parse(new TextDecoder().decode(o)) : {}), () => ({}));

/** Un fichier des ressources (moteur/…, voix/…), décompressé s'il le faut. */
async function ressource(chemin) {
  const info = (await compresses)[chemin];
  if (!info) {
    const o = await octets(new URL(chemin, RESSOURCES));
    const attendu = (await inventaire)[chemin];
    if (!o) throw erreur("manquant", `ressources/${chemin}`, chemin);
    if (attendu && o.length !== attendu) {
      throw erreur("incomplet", `ressources/${chemin} (${mo(o.length)} sur ${mo(attendu)})`, chemin);
    }
    return o;
  }
  const [{ default: KabXz }, { ressource: decompresser }] =
    await Promise.all([import("./kab_xz.mjs"), import("./compression.js")]);
  const o = await decompresser(new URL(chemin, RESSOURCES), info, KabXz,
    { wasmBinary: await octets(new URL("kab_xz.wasm", import.meta.url)) });
  noter(`ressources/${chemin} : décompressé, ${mo(o.length)}`);
  return o;
}

function lire(nom) {
  return ressource(nom === TABLE_BV ? `graphie/${nom}` : `moteur/${nom}`);
}

/** Un module WebAssembly du correcteur : sans lui, rien ne démarre. */
async function module(nom) {
  const o = await octets(new URL(nom, import.meta.url));
  if (!o) throw erreur("manquant", `moteur/${nom}`, nom);
  return o;
}

let moteur = null;
const debut = performance.now();
const pret = (async () => {
  postMessage({ etat: "chargement" });
  noter("début du chargement du correcteur");
  noterAppareil();
  moteur = await Moteur.charger(lire, {
    KenLM, CRFsuite,
    optionsKenLM: { wasmBinary: await module("kab_lm.wasm") },
    optionsCRF: { wasmBinary: await module("kab_crf.wasm") },
  });
  noter("modèle de langue et étiqueteur ouverts");
  // Ce que le moteur construit à la première demande l'est avant la première frappe.
  moteur.traiter({ quoi: "proposer", contexte: "", mot: "azul" });
  moteur.traiter({ quoi: "juger", texte: "azul fell-awen", avant: "" });
  noter("correcteur prêt");
  postMessage({ etat: "pret", secondes: (performance.now() - debut) / 1000, journal });
})().catch((e) => {
  noter(`échec : ${e && e.name || "Error"}: ${e && e.message || e}`);
  if (e && e.stack) noter(`pile :\n${e.stack}`);
  const { erreur: cause, conseil } = expliquer(e);
  postMessage({ etat: "panne", erreur: cause, conseil, journal });
  throw e;
});

let ort = null;
let transcripteur = null;

async function dicter(audio, graphie) {
  if (!transcripteur) {
    ort = await import("../ort/ort.wasm.min.mjs");
    ort.env.wasm.wasmPaths = new URL("../ort/", import.meta.url).href;
    ort.env.wasm.numThreads = 1;
    transcripteur = await Transcripteur.ouvrir(ort, await ressource("voix/mmeslay.onnx"),
      await ressource("voix/jetons.txt"));
  }
  const texte = await transcripteur.transcrire(ort, commeLeMicro(audio));
  // Le modèle vocal ne transcrit qu'en b : le texte suit la graphie réglée.
  return moteur.graphie.appliquerTexte(texte, graphie === "b" ? "b" : "v");
}

// Une requête à la fois : la barre, les soulignés et la dictée ne se croisent pas.
let file = Promise.resolve();

onmessage = (e) => {
  const { id, requete, audio, graphie } = e.data;
  file = file.then(async () => {
    try {
      await pret;
      const reponse = audio ? { texte: await dicter(audio, graphie) } : moteur.traiter(requete);
      postMessage({ id, reponse });
    } catch (erreur) {
      postMessage({ id, reponse: { erreur: String(erreur && erreur.message || erreur) } });
    }
  });
};
