// La transcription de la parole kabyle : Transcripteur.kt, sur onnxruntime-web au lieu
// d'onnxruntime pour Android. Le modèle vient de Mmeslay (G1ya777, GPL-3).

import { lignes } from "./ressources.js";
import { rogner } from "./kotlin.js";

const NOM_ENTREE = "audio";
const BLANC = "_";
const SILENCE = "|";
const DEBUT_DE_MOT = "▁";
// \s de Java, sans UNICODE_CHARACTER_CLASS : les seuls blancs ASCII.
const BLANCS = /[ \t\n\x0B\f\r]+/g;

/** Un dixième de seconde : en dessous, il n'y a pas de parole à chercher. */
const MIN_ECHANTILLONS = 1600;

export const TAUX = 16000;

/** Ce que capte le téléphone : des entiers 16 bits, ramenés entre -1 et 1. */
export function commeLeMicro(echantillons) {
  const sortie = new Float32Array(echantillons.length);
  for (let i = 0; i < echantillons.length; i++) {
    const v = Math.max(-1, Math.min(1, echantillons[i]));
    const entier = v < 0 ? Math.max(-32768, Math.round(v * 32768)) : Math.min(32767, Math.round(v * 32768));
    sortie[i] = entier / 32768;
  }
  return sortie;
}

export class Transcripteur {
  constructor(session, jetons) {
    this.session = session;
    this.jetons = jetons;
  }

  /** ort : le module onnxruntime-web ; modele : les octets de mmeslay.onnx ; jetons : ceux de jetons.txt. */
  static async ouvrir(ort, modele, jetons, options = {}) {
    const liste = lignes(jetons).map((j) => rogner(j));
    if (liste.length < 2) throw new Error("jeu de jetons vide");
    const session = await ort.InferenceSession.create(modele, {
      executionProviders: ["wasm"], graphOptimizationLevel: "all", ...options,
    });
    return new Transcripteur(session, liste);
  }

  /** Les échantillons en 16 kHz, mono, entre -1 et 1. */
  async transcrire(ort, echantillons) {
    if (echantillons.length < MIN_ECHANTILLONS) return "";
    const entree = new ort.Tensor("float32", echantillons, [1, echantillons.length]);
    const sortie = await this.session.run({ [NOM_ENTREE]: entree });
    const logits = sortie[this.session.outputNames[0]];
    const texte = this.decoder(logits.data, logits.dims[1], logits.dims[2]);
    entree.dispose?.();
    logits.dispose?.();
    return texte;
  }

  /** Décodage CTC glouton : le meilleur jeton par trame, les répétitions fondues, le blanc retiré. */
  decoder(donnees, trames, taille) {
    let sb = "";
    let precedent = -1;
    for (let t = 0; t < trames; t++) {
      const o = t * taille;
      let meilleur = 0;
      let score = donnees[o];
      for (let i = 1; i < taille; i++) if (donnees[o + i] > score) { score = donnees[o + i]; meilleur = i; }
      if (meilleur !== precedent) {
        const j = this.jetons[meilleur];
        if (j !== undefined && j !== BLANC && j !== SILENCE) sb += j;
      }
      precedent = meilleur;
    }
    return rogner(sb.replaceAll(DEBUT_DE_MOT, " ").replace(/-{2,}/g, "-")).replace(BLANCS, " ");
  }
}
