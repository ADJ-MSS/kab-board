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
  if (m.etat === "pret") annoncer({ moteur: "pret", erreur: "", secondes: m.secondes, journal: m.journal });
  else if (m.etat === "panne") annoncer({ moteur: "panne", erreur: m.erreur, conseil: m.conseil, journal: m.journal });
  else if (m.etat) annoncer({ moteur: "chargement", erreur: "", journal: [] });
  if (m.etat) return;
  const resoudre = attente.get(m.id);
  attente.delete(m.id);
  if (resoudre) resoudre(m.reponse);
};

/** Le premier module du correcteur qui manque ou ne se lit pas, en suivant ses import. */
async function moduleEnCause(url, vus = new Set()) {
  if (vus.has(url)) return "";
  vus.add(url);
  let texte;
  try {
    const r = await fetch(url);
    if (!r.ok) return url;
    texte = await r.text();
  } catch (e) {
    return url;
  }
  for (const [, chemin] of texte.matchAll(/(?:^|[\s;])(?:from|import)\s+["'](\.[^"']+)["']/g)) {
    const manque = await moduleEnCause(new URL(chemin, url).href, vus);
    if (manque) return manque;
  }
  return "";
}

// Le fil ne démarre même pas (un module introuvable) : rien ne répondra.
travailleur.onerror = async (e) => {
  const lieu = e.filename ? ` (${e.filename.replace(/^.*\/\/[^/]+\//, "")}${e.lineno ? `:${e.lineno}` : ""})` : "";
  const manque = await moduleEnCause(new URL("../moteur/travailleur.js", location.href).href);
  const erreur = manque ? `Fichier manquant : ${manque.replace(/^.*\/\/[^/]+\//, "")}`
    : `Le programme du correcteur ne démarre pas : ${e.message || "un de ses fichiers ne se lit pas"}${lieu}`;
  annoncer({
    moteur: "panne", erreur, journal: [erreur, `navigateur : ${navigator.userAgent}`],
    conseil: "Un fichier de l'extension manque ou est abîmé : retéléchargez l'archive, décompressez-la entièrement, puis chargez de nouveau le dossier.",
  });
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
