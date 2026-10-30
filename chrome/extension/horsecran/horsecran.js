/*
 * Le document hors écran : le correcteur y est chargé une fois pour toutes les pages,
 * dans un fil à part (moteur/travailleur.js). Le fond lui passe les requêtes ; le
 * micro de la dictée est écouté ici aussi (enregistreur.js).
 *
 * Au bout de vingt minutes sans rien demander, il dit au fond qu'il peut le fermer :
 * le correcteur occupe plusieurs centaines de mégaoctets.
 */
"use strict";

const REPOS_MS = 20 * 60 * 1000;

const travailleur = new Worker("../moteur/travailleur.js", { type: "module" });
let etatMoteur = { moteur: "chargement", erreur: "" };
let prochainId = 1;
const attente = new Map();
let derniere = Date.now();

function dire(message) {
  chrome.runtime.sendMessage(message).catch(() => {});
}

function annoncer(etat) {
  etatMoteur = etat;
  dire({ type: "horsecran-etat", etat });
}

travailleur.onmessage = (e) => {
  const m = e.data;
  if (m.etat === "pret") annoncer({ moteur: "pret", erreur: "", secondes: m.secondes });
  else if (m.etat === "panne") annoncer({ moteur: "panne", erreur: m.erreur });
  else if (m.etat) annoncer({ moteur: "chargement", erreur: "" });
  if (m.etat) return;
  const resoudre = attente.get(m.id);
  attente.delete(m.id);
  if (resoudre) resoudre(m.reponse);
};

// Le fil ne démarre même pas (un module introuvable) : rien ne répondra.
travailleur.onerror = (e) => {
  const erreur = e.message || "le correcteur ne se charge pas";
  annoncer({ moteur: "panne", erreur });
  for (const resoudre of attente.values()) resoudre({ erreur });
  attente.clear();
};

/** Une requête au correcteur ; la dictée passe aussi par là : { audio, graphie }. */
function demander(message) {
  derniere = Date.now();
  return new Promise((resoudre) => {
    const id = prochainId++;
    attente.set(id, resoudre);
    travailleur.postMessage({ ...message, id }, message.audio ? [message.audio.buffer] : []);
  });
}

setInterval(() => {
  if (!attente.size && Date.now() - derniere > REPOS_MS) dire({ type: "horsecran-repos" });
}, 60 * 1000);

chrome.runtime.onMessage.addListener((m, _expediteur, repondre) => {
  if (!m || m.cible !== "horsecran") return false;
  derniere = Date.now();
  if (m.type === "etat") {
    repondre(etatMoteur);
    return false;
  }
  if (m.type === "requete") {
    demander({ requete: m.requete }).then(repondre);
    return true;
  }
  return false;
});
