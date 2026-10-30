/* Demande une fois l'accès au micro pour l'extension : le document hors écran qui
 * enregistre la dictée ne peut pas poser la question lui-même. */
"use strict";

const resultat = document.getElementById("resultat");

async function autoriser() {
  try {
    const flux = await navigator.mediaDevices.getUserMedia({ audio: true });
    for (const piste of flux.getTracks()) piste.stop();
    resultat.textContent = "C'est fait : vous pouvez fermer cet onglet et dicter (Alt+Maj+D, ou 🎤 dans la barre).";
  } catch (erreur) {
    resultat.textContent = erreur.name === "NotFoundError"
      ? "Aucun micro n'est branché à cet ordinateur."
      : "Le micro a été refusé. Cliquez sur l'icône du micro barré, dans la barre d'adresse, pour l'autoriser, puis réessayez.";
  }
}

document.getElementById("autoriser").addEventListener("click", autoriser);
autoriser();
