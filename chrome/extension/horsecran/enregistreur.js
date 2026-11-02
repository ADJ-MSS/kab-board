/*
 * Le micro de la dictée, dans le document hors écran : le seul endroit d'une
 * extension où l'on peut écouter sans ouvrir de fenêtre. Firefox n'en a pas : il
 * écoute dans une petite fenêtre de l'extension (horsecran/dictee.html).
 *
 * L'enregistrement se fait en 16 kHz mono, le format du modèle vocal Mmeslay :
 * Chrome y ramène le micro, comme Android le fait pour l'application. S'il donnait
 * un autre taux, logique.js l'y ramènerait. Il est transcrit par le correcteur de ce
 * document (demander, dans horsecran.js) : la voix ne quitte jamais l'ordinateur.
 * 30 secondes au plus, comme sur le téléphone.
 */
"use strict";

const L = globalThis.KabLogique;
const TAUX_MODELE = 16000;

let flux = null;
let contexte = null;
let morceaux = [];
let total = 0;
let niveau = 0;
let dureeMax = 30;
let graphie = "v";
let minuterie = null;
let fini = false;

function dire(message) {
  chrome.runtime.sendMessage(message).catch(() => {});
}

/** Un contexte audio au taux voulu (0 : celui du micro), son capteur prêt. */
async function preparerContexte(taux) {
  const c = taux ? new AudioContext({ sampleRate: taux }) : new AudioContext();
  await c.audioWorklet.addModule("capteur.js");
  const capteur = new AudioWorkletNode(c, "capteur");
  capteur.port.onmessage = (e) => {
    if (fini || c !== contexte) return;
    const morceau = e.data;
    morceaux.push(morceau);
    total += morceau.length;
    let somme = 0;
    for (let i = 0; i < morceau.length; i++) somme += morceau[i] * morceau[i];
    niveau = Math.max(niveau * 0.8, Math.sqrt(somme / morceau.length));
    if (total >= c.sampleRate * dureeMax) arreter();
  };
  capteur.connect(c.destination);       // tiré par le graphe ; il reste muet
  return { c, capteur };
}

async function commencer(duree, g) {
  dureeMax = Math.min(30, Math.max(1, duree || 30));
  graphie = g === "b" ? "b" : "v";
  morceaux = [];
  total = 0;
  fini = false;
  // Le capteur est prêt avant que le micro s'ouvre : rien de ce qui est dit dès
  // l'ouverture ne se perd.
  let prepare;
  try {
    prepare = await preparerContexte(TAUX_MODELE);
  } catch (erreur) {
    return { erreur: "Le micro ne répond pas : " + erreur.message };
  }
  contexte = prepare.c;
  try {
    // Le son brut, comme la source VOICE_RECOGNITION de l'application Android
    // (Ecouteur.kt) : ni réduction du bruit, ni gain automatique.
    flux = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
  } catch (erreur) {
    liberer();
    contexte = null;
    if (erreur.name === "NotAllowedError" || erreur.name === "SecurityError") return { erreur: "micro-refuse" };
    if (erreur.name === "NotFoundError") return { erreur: "Aucun micro n'est branché." };
    return { erreur: "Le micro ne répond pas : " + erreur.message };
  }
  try {
    let source;
    try {
      source = contexte.createMediaStreamSource(flux);
    } catch (erreur) {
      // Un navigateur qui ne relie pas un micro à un contexte d'un autre taux : celui du
      // micro, alors, et arreter() ramène à 16 kHz.
      contexte.close().catch(() => {});
      prepare = await preparerContexte(0);
      contexte = prepare.c;
      source = contexte.createMediaStreamSource(flux);
    }
    source.connect(prepare.capteur);
    if (contexte.state !== "running") await demarrer(contexte);
  } catch (erreur) {
    liberer();
    contexte = null;
    return { erreur: "Le micro ne répond pas : " + erreur.message };
  }
  minuterie = setInterval(() => {
    if (!contexte) return;
    dire({ type: "horsecran-progres", secondes: total / contexte.sampleRate, niveau });
  }, 250);
  return { ok: true, taux: contexte.sampleRate };
}

/**
 * Fait tourner le contexte. Sans sortie audio, Firefox ne le lance jamais : au bout de
 * 5 s, on le dit, plutôt que d'écouter un micro dont rien n'arrive.
 */
function demarrer(c) {
  let minuterie;
  const delai = new Promise((_, rejeter) => {
    minuterie = setTimeout(() => rejeter(new Error("le son ne passe pas (aucune sortie audio ?)")), 5000);
  });
  return Promise.race([c.resume(), delai]).finally(() => clearTimeout(minuterie));
}

function liberer() {
  clearInterval(minuterie);
  minuterie = null;
  if (flux) for (const piste of flux.getTracks()) piste.stop();
  flux = null;
  if (contexte) contexte.close().catch(() => {});
}

function arreter() {
  if (fini || !contexte) return;
  fini = true;
  const taux = contexte.sampleRate;
  liberer();
  contexte = null;
  const tout = new Float32Array(total);
  let position = 0;
  for (const morceau of morceaux) {
    tout.set(morceau, position);
    position += morceau.length;
  }
  morceaux = [];
  const limite = Math.min(tout.length, taux * dureeMax);
  const voix = L.reechantillonner(tout.subarray(0, limite), taux, TAUX_MODELE);
  dire({ type: "horsecran-transcription", secondes: voix.length / TAUX_MODELE });
  demander({ audio: voix, graphie }).then((r) => {
    if (r.erreur) dire({ type: "horsecran-erreur", erreur: r.erreur });
    else dire({ type: "horsecran-fini", texte: r.texte || "" });
  });
}

function annuler() {
  fini = true;
  liberer();
  contexte = null;
  morceaux = [];
  dire({ type: "horsecran-erreur", erreur: "Dictée annulée." });
}

chrome.runtime.onMessage.addListener((m, _expediteur, repondre) => {
  if (!m || m.cible !== "horsecran") return false;
  if (m.type === "commencer") {
    commencer(m.dureeMax, m.graphie).then(repondre);
    return true;
  }
  if (m.type !== "arreter" && m.type !== "annuler") return false;
  if (m.type === "arreter") arreter();
  else annuler();
  repondre({ ok: true });
  return false;
});
