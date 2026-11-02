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
        if (m.etat === "pret") etatMoteur = { moteur: "pret", erreur: "", secondes: m.secondes };
        else if (m.etat === "panne") etatMoteur = { moteur: "panne", erreur: m.erreur };
        else etatMoteur = { moteur: "chargement", erreur: "" };
        annoncer({ type: "horsecran-etat", etat: etatMoteur });
        return;
      }
      const resoudre = attente.get(m.id);
      attente.delete(m.id);
      if (resoudre) resoudre(m.reponse);
    };
    // Le fil ne démarre même pas (un module introuvable) : rien ne répondra.
    travailleur.onerror = (e) => {
      const erreur = e.message || "le correcteur ne se charge pas";
      etatMoteur = { moteur: "panne", erreur };
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
