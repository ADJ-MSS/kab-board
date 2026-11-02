/*
 * Où tourne le correcteur, sous Chrome : dans un document hors écran (horsecran/), le seul
 * endroit d'une extension où un fil de calcul et le micro survivent au fond, qui
 * s'endort. Il s'ouvre au premier champ où l'on écrit et se ferme au bout de vingt
 * minutes sans requête. Ce qu'il annonce (son état, la dictée) arrive au fond par des
 * messages.
 *
 * Firefox a le sien (firefox/plateforme.js) : le fond y est une page, qui porte elle-même
 * le correcteur.
 */
(function (racine) {
  "use strict";

  const HORS_ECRAN = "horsecran/horsecran.html";

  async function ouvert() {
    const existants = await chrome.runtime.getContexts({
      contextTypes: ["OFFSCREEN_DOCUMENT"], documentUrls: [chrome.runtime.getURL(HORS_ECRAN)],
    });
    return existants.length > 0;
  }

  async function ouvrir() {
    try {
      await chrome.offscreen.createDocument({
        url: HORS_ECRAN, reasons: ["WORKERS", "USER_MEDIA"],
        justification: "Le correcteur kabyle, chargé une fois pour toutes les pages, et le micro de la dictée.",
      });
    } catch (erreur) {
      // Ouvert entre-temps par un autre appel : c'est ce qu'on voulait.
      if (!/single offscreen/i.test(String(erreur && erreur.message || erreur))) throw erreur;
    }
  }

  async function fermer() {
    try {
      await chrome.offscreen.closeDocument();
    } catch (erreur) {
      // déjà fermé
    }
  }

  /** L'état du correcteur, s'il répond. */
  function etat() {
    return chrome.runtime.sendMessage({ cible: "horsecran", type: "etat" }).catch(() => null);
  }

  function requete(requete) {
    return chrome.runtime.sendMessage({ cible: "horsecran", type: "requete", requete });
  }

  /** Le micro : commencer (dureeMax, graphie), arreter, annuler. */
  function micro(type, options) {
    return chrome.runtime.sendMessage({ cible: "horsecran", type, ...options });
  }

  /** Ce que le correcteur annonce passe ici par les messages du fond. */
  function ecouter() {}

  racine.KabPlateforme = { ouvert, ouvrir, fermer, etat, requete, micro, ecouter };
})(globalThis);
