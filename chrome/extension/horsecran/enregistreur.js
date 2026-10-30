/*
 * Le micro de la dictée, dans le document hors écran : le seul endroit d'une
 * extension où l'on peut écouter sans ouvrir de fenêtre.
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

async function commencer(duree, g) {
  dureeMax = Math.min(30, Math.max(1, duree || 30));
  graphie = g === "b" ? "b" : "v";
  morceaux = [];
  total = 0;
  fini = false;
  try {
    // Le son brut, comme la source VOICE_RECOGNITION de l'application Android
    // (Ecouteur.kt) : ni réduction du bruit, ni gain automatique.
    flux = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
  } catch (erreur) {
    if (erreur.name === "NotAllowedError" || erreur.name === "SecurityError") return { erreur: "micro-refuse" };
    if (erreur.name === "NotFoundError") return { erreur: "Aucun micro n'est branché." };
    return { erreur: "Le micro ne répond pas : " + erreur.message };
  }
  try {
    contexte = new AudioContext({ sampleRate: TAUX_MODELE });
    await contexte.audioWorklet.addModule("capteur.js");
    const source = contexte.createMediaStreamSource(flux);
    const capteur = new AudioWorkletNode(contexte, "capteur");
    capteur.port.onmessage = (e) => {
      if (fini) return;
      const morceau = e.data;
      morceaux.push(morceau);
      total += morceau.length;
      let somme = 0;
      for (let i = 0; i < morceau.length; i++) somme += morceau[i] * morceau[i];
      niveau = Math.max(niveau * 0.8, Math.sqrt(somme / morceau.length));
      if (total >= contexte.sampleRate * dureeMax) arreter();
    };
    source.connect(capteur);
    capteur.connect(contexte.destination);       // tiré par le graphe ; il reste muet
    if (contexte.state !== "running") await contexte.resume();
  } catch (erreur) {
    liberer();
    return { erreur: "Le micro ne répond pas : " + erreur.message };
  }
  minuterie = setInterval(() => {
    if (!contexte) return;
    dire({ type: "horsecran-progres", secondes: total / contexte.sampleRate, niveau });
  }, 250);
  return { ok: true, taux: contexte.sampleRate };
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
