// Le correcteur, dans un fil à part du document hors écran : il charge le moteur une
// fois (les ressources de l'application, 300 Mo), puis répond aux requêtes, une à la
// fois. La dictée aussi passe ici, le modèle vocal chargé à la première ; l'audio
// arrive en 16 kHz, et passe par les 16 bits du micro du téléphone.

import KenLM from "./kab_lm.mjs";
import CRFsuite from "./kab_crf.mjs";
import { Moteur, TABLE_BV } from "./moteur.js";
import { Transcripteur, commeLeMicro } from "./transcripteur.js";

const RESSOURCES = new URL("../ressources/", import.meta.url);

async function octets(url) {
  const r = await fetch(url);
  if (!r.ok) return null;
  return new Uint8Array(await r.arrayBuffer());
}

function lire(nom) {
  return octets(new URL(nom === TABLE_BV ? `graphie/${nom}` : `moteur/${nom}`, RESSOURCES));
}

let moteur = null;
const debut = performance.now();
const pret = (async () => {
  postMessage({ etat: "chargement" });
  moteur = await Moteur.charger(lire, {
    KenLM, CRFsuite,
    optionsKenLM: { wasmBinary: await octets(new URL("kab_lm.wasm", import.meta.url)) },
    optionsCRF: { wasmBinary: await octets(new URL("kab_crf.wasm", import.meta.url)) },
  });
  // Ce que le moteur construit à la première demande l'est avant la première frappe.
  moteur.traiter({ quoi: "proposer", contexte: "", mot: "azul" });
  moteur.traiter({ quoi: "juger", texte: "azul fell-awen", avant: "" });
  postMessage({ etat: "pret", secondes: (performance.now() - debut) / 1000 });
})().catch((erreur) => {
  postMessage({ etat: "panne", erreur: String(erreur && erreur.message || erreur) });
  throw erreur;
});

let ort = null;
let transcripteur = null;

async function dicter(audio, graphie) {
  if (!transcripteur) {
    ort = await import("../ort/ort.wasm.min.mjs");
    ort.env.wasm.wasmPaths = new URL("../ort/", import.meta.url).href;
    ort.env.wasm.numThreads = 1;
    transcripteur = await Transcripteur.ouvrir(ort, await octets(new URL("voix/mmeslay.onnx", RESSOURCES)),
      await octets(new URL("voix/jetons.txt", RESSOURCES)));
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
