/*
 * La fenêtre de la dictée, sous Firefox : le micro y est écouté par enregistreur.js,
 * comme dans le document hors écran de Chrome, et la voix part au correcteur, que porte
 * la page de fond (plateforme.js). La fenêtre se ferme quand le texte est parti.
 */
"use strict";

/** Ce qu'appelle enregistreur.js pour transcrire : ici, le fond s'en charge. */
function demander(message) {
  return chrome.runtime.sendMessage({ type: "dictee-transcrire", ...message })
    .then((r) => r || { erreur: "Le correcteur ne répond pas." }, (erreur) => ({ erreur: String(erreur.message || erreur) }));
}

document.getElementById("arreter").addEventListener("click", () => arreter());
document.getElementById("annuler").addEventListener("click", () => annuler());

// L'état et le niveau, d'après enregistreur.js.
setInterval(() => {
  const etat = document.getElementById("etat");
  if (fini) {
    etat.textContent = "Transcription…";
    document.getElementById("arreter").disabled = true;
  } else if (contexte) {
    etat.textContent = `J'écoute… ${Math.floor(total / contexte.sampleRate)} s`;
    document.getElementById("niveau").style.width = `${Math.min(100, Math.round(niveau * 400))}%`;
  }
}, 200);

chrome.runtime.sendMessage({ type: "dictee-prete" }).catch(() => {});
