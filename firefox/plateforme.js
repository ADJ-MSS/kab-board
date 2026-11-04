/*
 * Où tourne le correcteur, sous Firefox : dans la page de fond elle-même. Firefox n'a pas
 * de document hors écran, mais son fond est une page, qui peut lancer un fil de calcul.
 *
 * Cette page, Firefox l'endort après 30 s sans événement. Tant que le correcteur sert,
 * jusqu'à vingt minutes après la dernière requête, une écriture dans
 * chrome.storage.session toutes les 20 s la tient éveillée. Après, le correcteur
 * s'arrête et la page peut s'endormir, comme le document hors écran se ferme sous Chrome.
 *
 * La dictée s'enregistre dans une petite fenêtre de l'extension (horsecran/dictee.html) :
 * la page de fond n'a pas d'écran où Firefox demanderait le micro.
 */
(function (racine) {
  "use strict";

  const REPOS_MS = 20 * 60 * 1000;
  const VEILLE_MS = 20 * 1000;
  const DICTEE = "horsecran/dictee.html";

  let travailleur = null;
  let etatMoteur = null;
  let prochainId = 1;
  const attente = new Map();
  let derniere = 0;
  let veille = null;
  let annoncer = () => {};
  let fenetre = null;            // { id, prete } : la fenêtre de la dictée

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

  function ouvert() {
    return Promise.resolve(travailleur !== null);
  }

  function ouvrir() {
    if (travailleur) return Promise.resolve();
    derniere = Date.now();
    etatMoteur = { moteur: "chargement", erreur: "" };
    travailleur = new Worker("moteur/travailleur.js", { type: "module" });
    travailleur.onmessage = (e) => {
      const m = e.data;
      if (m.etat) {
        if (m.etat === "pret") etatMoteur = { moteur: "pret", erreur: "", secondes: m.secondes, journal: m.journal };
        else if (m.etat === "panne") etatMoteur = { moteur: "panne", erreur: m.erreur, conseil: m.conseil, journal: m.journal };
        else etatMoteur = { moteur: "chargement", erreur: "", journal: [] };
        annoncer({ type: "horsecran-etat", etat: etatMoteur });
        return;
      }
      const resoudre = attente.get(m.id);
      attente.delete(m.id);
      if (resoudre) resoudre(m.reponse);
    };
    // Le fil ne démarre même pas (un module introuvable) : rien ne répondra.
    travailleur.onerror = async (e) => {
      const lieu = e.filename ? ` (${e.filename.replace(/^.*\/\/[^/]+\//, "")}${e.lineno ? `:${e.lineno}` : ""})` : "";
      const manque = await moduleEnCause(new URL("moteur/travailleur.js", location.href).href);
      const erreur = manque ? `Fichier manquant : ${manque.replace(/^.*\/\/[^/]+\//, "")}`
        : `Le programme du correcteur ne démarre pas : ${e.message || "un de ses fichiers ne se lit pas"}${lieu}`;
      etatMoteur = {
        moteur: "panne", erreur, journal: [erreur, `navigateur : ${navigator.userAgent}`],
        conseil: "Un fichier de l'extension manque ou est abîmé : retéléchargez-la, puis installez-la de nouveau.",
      };
      annoncer({ type: "horsecran-etat", etat: etatMoteur });
      for (const resoudre of attente.values()) resoudre({ erreur });
      attente.clear();
    };
    clearInterval(veille);
    veille = setInterval(() => {
      if (!attente.size && !fenetre && Date.now() - derniere > REPOS_MS) {
        annoncer({ type: "horsecran-repos" });
        return;
      }
      chrome.storage.session.set({ veille: Date.now() }).catch(() => {});
    }, VEILLE_MS);
    return Promise.resolve();
  }

  function fermer() {
    if (travailleur) travailleur.terminate();
    travailleur = null;
    etatMoteur = null;
    clearInterval(veille);
    veille = null;
    for (const resoudre of attente.values()) resoudre({ erreur: "Le correcteur s'est arrêté.", indisponible: true });
    attente.clear();
    return Promise.resolve();
  }

  function etat() {
    return Promise.resolve(etatMoteur);
  }

  /** Une requête au fil du correcteur ; la dictée passe aussi par là : { audio, graphie }. */
  function demander(message) {
    if (!travailleur) return Promise.reject(new Error("le correcteur est fermé"));
    derniere = Date.now();
    return new Promise((resoudre) => {
      const id = prochainId++;
      attente.set(id, resoudre);
      travailleur.postMessage({ ...message, id }, message.audio ? [message.audio.buffer] : []);
    });
  }

  function requete(requete) {
    return demander({ requete });
  }

  function fermerFenetre() {
    if (!fenetre) return;
    const { id } = fenetre;
    fenetre = null;
    if (id !== undefined) chrome.windows.remove(id).catch(() => {});
  }

  /** Le micro : commencer (dureeMax, graphie) ouvre la fenêtre de la dictée ; arreter, annuler. */
  async function micro(type, options) {
    if (type !== "commencer") return chrome.runtime.sendMessage({ cible: "horsecran", type });
    let prete;
    fenetre = { prete: new Promise((r) => { prete = r; }) };
    fenetre.signaler = prete;
    const f = await chrome.windows.create({
      url: chrome.runtime.getURL(DICTEE), type: "popup", width: 420, height: 240,
    });
    if (fenetre) fenetre.id = f.id;
    await Promise.race([fenetre.prete, new Promise((r) => setTimeout(r, 10000))]);
    const r = await chrome.runtime.sendMessage({ cible: "horsecran", type: "commencer", ...options })
      .catch(() => null);
    if (!r || r.erreur) fermerFenetre();
    return r;
  }

  chrome.runtime.onMessage.addListener((m, _expediteur, repondre) => {
    if (!m || m.cible) return false;
    if (m.type === "dictee-prete") {
      if (fenetre) fenetre.signaler();
      return false;
    }
    if (m.type === "dictee-transcrire") {
      demander({ audio: Float32Array.from(m.audio), graphie: m.graphie })
        .then(repondre, (erreur) => repondre({ erreur: String(erreur && erreur.message || erreur) }));
      return true;
    }
    if (m.type === "horsecran-fini" || m.type === "horsecran-erreur") fermerFenetre();
    return false;
  });

  // La fenêtre fermée en pleine dictée : c'est une dictée annulée.
  chrome.windows.onRemoved.addListener((id) => {
    if (!fenetre || fenetre.id !== id) return;
    fenetre = null;
    annoncer({ type: "horsecran-erreur", erreur: "Dictée annulée." });
  });

  function ecouter(fonction) {
    annoncer = fonction;
  }

  racine.KabPlateforme = { ouvert, ouvrir, fermer, etat, requete, micro, ecouter };
})(globalThis);
