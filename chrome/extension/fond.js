/*
 * Le fond de l'extension : il prépare le correcteur et lui passe les requêtes des
 * pages.
 *
 * Le correcteur tourne dans un document hors écran (horsecran/), ouvert au premier
 * champ où l'on écrit, pas au démarrage du navigateur : il pèse lourd. Ce document
 * écoute aussi le micro de la dictée. Il se ferme au bout de vingt minutes sans
 * rien demander, et se rouvre au besoin.
 *
 * L'état du correcteur va dans chrome.storage.session, que lisent les pages et le
 * script de contenu.
 */
importScripts("commun.js");

const C = globalThis.KabCommun;

const DELAIS = {
  proposer: 6000, predire: 6000, basculer: 6000, juger: 60000, fiche: 12000, chercher: 12000,
  motdujour: 12000,
};
const REQUETES = new Set(Object.keys(DELAIS));
const TEXTE_MAX = 20000;         // ce que l'on relit d'un coup
const HORS_ECRAN = "horsecran/horsecran.html";

let reglages = C.reglagesComplets({});
let etat = { moteur: "arrete", erreur: "" };
let ouverture = null;            // le document hors écran en train de s'ouvrir
let dictee = null;               // { tabId, frameId } : où écrire ce qui sera dit
let dernierChamp = null;         // { tabId, frameId } : le dernier champ où l'on a écrit

chrome.storage.session.setAccessLevel({ accessLevel: "TRUSTED_AND_UNTRUSTED_CONTEXTS" })
  .catch(() => {});
const reglagesLus = chrome.storage.sync.get("reglages").then((r) => {
  reglages = C.reglagesComplets(r.reglages);
  majBadge();
}).catch(() => {});
chrome.storage.session.get("dernierChamp").then((r) => {
  if (r.dernierChamp && !dernierChamp) dernierChamp = r.dernierChamp;
}).catch(() => {});
// Le fond a pu être endormi ; le document hors écran, lui, vit peut-être encore, le
// correcteur prêt. Les requêtes attendent de le savoir.
const etatLu = horsEcranOuvert().then(async (ouvert) => {
  if (!ouvert) {
    publierEtat({ moteur: "arrete", erreur: "" });
    return;
  }
  const e = await chrome.runtime.sendMessage({ cible: "horsecran", type: "etat" }).catch(() => null);
  publierEtat(e || { moteur: "chargement", erreur: "" });
}).catch(() => {});
chrome.storage.onChanged.addListener((changements, zone) => {
  if (zone === "sync" && changements.reglages) {
    reglages = C.reglagesComplets(changements.reglages.newValue);
    majBadge();
  }
});

// L'état

function publierEtat(changements) {
  etat = { ...etat, ...changements };
  chrome.storage.session.set({ etat }).catch(() => {});
  majBadge();
}

function majBadge() {
  let texte = "";
  let couleur = "#5F6B76";
  if (!reglages.allume) {
    texte = "off";
  } else if (etat.moteur === "panne") {
    texte = "!";
    couleur = "#C62828";
  }
  chrome.action.setBadgeText({ text: texte }).catch(() => {});
  chrome.action.setBadgeBackgroundColor({ color: couleur }).catch(() => {});
}

// Le correcteur, dans le document hors écran

async function horsEcranOuvert() {
  const existants = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"], documentUrls: [chrome.runtime.getURL(HORS_ECRAN)],
  });
  return existants.length > 0;
}

/** Ouvre le document hors écran, s'il ne l'est pas : le correcteur s'y charge. */
function preparer() {
  if (ouverture) return ouverture;
  ouverture = (async () => {
    if (await horsEcranOuvert()) return;
    publierEtat({ moteur: "chargement", erreur: "" });
    try {
      await chrome.offscreen.createDocument({
        url: HORS_ECRAN, reasons: ["WORKERS", "USER_MEDIA"],
        justification: "Le correcteur kabyle, chargé une fois pour toutes les pages, et le micro de la dictée.",
      });
    } catch (erreur) {
      const message = String(erreur && erreur.message || erreur);
      if (!/single offscreen/i.test(message)) publierEtat({ moteur: "panne", erreur: message });
    }
  })().finally(() => {
    ouverture = null;
  });
  return ouverture;
}

async function fermer() {
  try {
    await chrome.offscreen.closeDocument();
  } catch (erreur) {
    // déjà fermé
  }
  publierEtat({ moteur: "arrete", erreur: "" });
}

function indisponible() {
  if (etat.moteur === "panne") {
    return { erreur: "Le correcteur ne se charge pas : " + etat.erreur, indisponible: true };
  }
  return { erreur: "Le correcteur se prépare…", indisponible: true };
}

async function envoyer(requete) {
  if (!REQUETES.has(requete.quoi)) return { erreur: "requête inconnue" };
  if (requete.quoi === "juger" && String(requete.texte || "").length > TEXTE_MAX) {
    return { erreur: "Texte trop long : relisez-le par morceaux." };
  }
  await etatLu;
  if (etat.moteur !== "pret") {
    if (etat.moteur === "arrete") preparer();
    return indisponible();
  }
  await reglagesLus;
  const message = {
    cible: "horsecran", type: "requete", requete: { graphie: reglages.graphie, ...requete },
  };
  let minuterie;
  const delai = new Promise((resoudre) => {
    minuterie = setTimeout(() => resoudre({
      erreur: "Le correcteur met trop de temps à répondre.", indisponible: true,
    }), DELAIS[requete.quoi]);
  });
  try {
    return await Promise.race([chrome.runtime.sendMessage(message).then((r) => r || indisponible()), delai]);
  } catch (erreur) {
    // Le document hors écran a été fermé entre-temps : on le rouvre.
    publierEtat({ moteur: "arrete", erreur: "" });
    preparer();
    return indisponible();
  } finally {
    clearTimeout(minuterie);
  }
}

// La dictée : le micro et la transcription dans le document hors écran

function direALaPage(cible, message) {
  if (!cible || cible.tabId === undefined) return;
  chrome.tabs.sendMessage(cible.tabId, message, { frameId: cible.frameId || 0 }).catch(() => {});
}

async function commencerDictee(sender) {
  if (dictee) return { erreur: "Une dictée est déjà en cours." };
  await etatLu;
  if (etat.moteur === "panne") return indisponible();
  dictee = { tabId: sender.tab ? sender.tab.id : undefined, frameId: sender.frameId || 0 };
  try {
    await preparer();                // le correcteur se prépare pendant qu'on parle
    await reglagesLus;
    const r = await chrome.runtime.sendMessage({
      cible: "horsecran", type: "commencer", dureeMax: 30, graphie: reglages.graphie,
    });
    if (!r || r.erreur) {
      dictee = null;
      if (r && r.erreur === "micro-refuse") ouvrirPage("micro");
      return { erreur: r ? r.erreur : "Le micro ne répond pas." };
    }
    return { ok: true };
  } catch (erreur) {
    dictee = null;
    return { erreur: "Le micro ne répond pas : " + (erreur && erreur.message || erreur) };
  }
}

function finDictee(message) {
  const cible = dictee;
  if (message.type === "horsecran-transcription") {
    direALaPage(cible, { type: "dictee", phase: "transcription", secondes: message.secondes });
    return;
  }
  dictee = null;
  direALaPage(cible, {
    type: "dictee", phase: "fin", texte: message.texte || "", erreur: message.erreur || "",
  });
}

// Les pages

function ouvrirPage(page) {
  if (page === "reglages") {
    chrome.runtime.openOptionsPage();
    return;
  }
  chrome.tabs.create({ url: chrome.runtime.getURL(`pages/${page}.html`) });
}

/** Une commande pour le champ où l'on écrit : celui de l'onglet actif. */
async function versLeChamp(message) {
  const [onglet] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!onglet) return;
  if (dernierChamp && dernierChamp.tabId === onglet.id) {
    chrome.tabs.sendMessage(onglet.id, message, { frameId: dernierChamp.frameId }).catch(() => {});
  } else {
    chrome.tabs.sendMessage(onglet.id, message, { frameId: 0 }).catch(() => {});
  }
}

chrome.runtime.onMessage.addListener((m, sender, repondre) => {
  if (!m || m.cible === "horsecran") return false;
  switch (m.type) {
    case "correcteur":
      envoyer(m.requete || {}).then(repondre);
      return true;
    case "reveil":
      if (sender.tab) {
        dernierChamp = { tabId: sender.tab.id, frameId: sender.frameId || 0 };
        chrome.storage.session.set({ dernierChamp }).catch(() => {});
      }
      etatLu.then(() => {
        if (etat.moteur === "arrete") preparer();
        repondre(etat);
      });
      return true;
    case "connecter":
      // Le popup ou les réglages s'ouvrent : le correcteur se prépare ; après une
      // panne, « Réessayer » le recharge.
      etatLu.then(() => {
        if (etat.moteur === "panne") fermer().then(preparer);
        else if (etat.moteur === "arrete") preparer();
        repondre(etat);
      });
      return true;
    case "etat":
      etatLu.then(() => repondre(etat));
      return true;
    case "dicter":
      if (m.action === "commencer") {
        commencerDictee(sender).then(repondre);
        return true;
      }
      if (m.action === "arreter" || m.action === "annuler") {
        chrome.runtime.sendMessage({ cible: "horsecran", type: m.action }).catch(() => {});
        repondre({ ok: !!dictee });
        return false;
      }
      repondre({ erreur: "action inconnue" });
      return false;
    case "horsecran-etat":
      publierEtat(m.etat);
      return false;
    case "horsecran-repos":
      if (!dictee) fermer();
      return false;
    case "horsecran-progres":
      direALaPage(dictee, { type: "dictee", phase: "ecoute", secondes: m.secondes, niveau: m.niveau });
      return false;
    case "horsecran-transcription":
    case "horsecran-fini":
    case "horsecran-erreur":
      finDictee(m);
      return false;
    case "commande":
      versLeChamp({ type: "commande", nom: m.nom });
      return false;
    case "ouvrir":
      ouvrirPage(m.page);
      return false;
    default:
      return false;
  }
});

// Raccourcis clavier et menu du clic droit

chrome.commands.onCommand.addListener(async (nom) => {
  if (nom === "basculer") {
    const r = await chrome.storage.sync.get("reglages");
    const actuels = C.reglagesComplets(r.reglages);
    await chrome.storage.sync.set({ reglages: { ...actuels, allume: !actuels.allume } });
    return;
  }
  versLeChamp({ type: "commande", nom });
});

const MENUS = [
  { id: "kab-relire", title: "Relire avec Kab-board", contexts: ["selection", "editable"] },
  { id: "kab-dicter", title: "Dicter en kabyle", contexts: ["editable"] },
  { id: "kab-fiche", title: "Asegzawal : « %s »", contexts: ["selection"] },
  { id: "kab-chercher", title: "Du français au kabyle : « %s »", contexts: ["selection"] },
];

chrome.contextMenus.onClicked.addListener((info, onglet) => {
  if (!onglet || onglet.id === undefined) return;
  chrome.tabs.sendMessage(onglet.id, {
    type: "menu", id: info.menuItemId, selection: info.selectionText || "",
  }, { frameId: info.frameId || 0 }).catch(() => {});
});

chrome.runtime.onInstalled.addListener(async (details) => {
  chrome.contextMenus.removeAll(() => {
    for (const menu of MENUS) chrome.contextMenus.create(menu);
  });
  if (details.reason === "install") ouvrirPage("reglages");
  // Les onglets déjà ouverts reçoivent le script de contenu tout de suite : pas
  // besoin de les recharger.
  const manifeste = chrome.runtime.getManifest();
  const scripts = manifeste.content_scripts[0];
  const onglets = await chrome.tabs.query({ url: ["http://*/*", "https://*/*", "file:///*"] });
  for (const onglet of onglets) {
    if (onglet.discarded) continue;
    const cible = { tabId: onglet.id, allFrames: true };
    chrome.scripting.insertCSS({ target: cible, files: scripts.css }).catch(() => {});
    chrome.scripting.executeScript({ target: cible, files: scripts.js }).catch(() => {});
  }
});
