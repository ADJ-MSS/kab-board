/*
 * Ce que partagent le fond, les pages et le script de contenu : les réglages de
 * l'extension (chrome.storage.sync) et « mon dictionnaire » (chrome.storage.local).
 */
(function (racine, fabrique) {
  if (typeof module === "object" && module.exports) {
    module.exports = fabrique();
  } else {
    racine.KabCommun = fabrique();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const REGLAGES_DEFAUT = Object.freeze({
    allume: true,             // le clavier kabyle, dans toutes les pages
    graphie: "v",             // avrid ; b : abrid. Celle des propositions et de la dictée
    translitteration: true,   // gh → ɣ, dh → ḍ, kh → x, aa → ɛ, ou → u
    altgr: true,              // AltGr + g, e, d, h, t, z, s, c, j, r
    barre: true,              // les six propositions sous le mot
    chiffres: true,           // 1 à 6 choisissent une proposition
    prediction: true,         // le mot suivant, quand un mot finit
    souligner: true,          // les fautes soulignées pendant qu'on écrit
    autocorrection: false,    // corriger d'office les mots inconnus (Retour arrière annule)
    sitesExclus: [],          // les sites où l'extension se tait
  });

  /** Les réglages lus, complétés, et sans valeur d'un mauvais type. */
  function reglagesComplets(lus) {
    const sortie = {};
    for (const [cle, defaut] of Object.entries(REGLAGES_DEFAUT)) {
      const valeur = lus ? lus[cle] : undefined;
      if (Array.isArray(defaut)) {
        sortie[cle] = Array.isArray(valeur) ? valeur.filter((x) => typeof x === "string") : [];
      } else if (cle === "graphie") {
        sortie[cle] = valeur === "b" ? "b" : "v";
      } else {
        sortie[cle] = typeof valeur === typeof defaut ? valeur : defaut;
      }
    }
    return sortie;
  }

  /** Le site d'une adresse, tel qu'on l'exclut : sans « www. ». */
  function site(adresse) {
    try {
      const u = new URL(adresse);
      if (u.protocol !== "http:" && u.protocol !== "https:" && u.protocol !== "file:") return "";
      return u.protocol === "file:" ? "fichiers locaux" : u.hostname.replace(/^www\./, "");
    } catch (e) {
      return "";
    }
  }

  function siteExclu(reglages, nom) {
    return !!nom && reglages.sitesExclus.some((s) => nom === s || nom.endsWith("." + s));
  }

  /** « Mon dictionnaire » : les mots que l'on ne souligne jamais, en minuscules. */
  async function mesMots() {
    const r = await chrome.storage.local.get("mesMots");
    return Array.isArray(r.mesMots) ? r.mesMots.filter((m) => typeof m === "string") : [];
  }

  /** Ajoute une liste de mots : { ajoutes, total }, ou { erreur }. */
  async function ajouterMots(liste) {
    const nouveaux = liste.map((m) => String(m).trim().toLowerCase()).filter((m) => m && !/\s/u.test(m));
    if (!nouveaux.length) return { erreur: "Un mot, sans espace." };
    const mots = new Set(await mesMots());
    const avant = mots.size;
    for (const m of nouveaux) mots.add(m);
    if (mots.size !== avant) await chrome.storage.local.set({ mesMots: [...mots].sort() });
    return { ajoutes: mots.size - avant, total: mots.size };
  }

  async function oublierMot(mot) {
    const bas = String(mot).trim().toLowerCase();
    const mots = (await mesMots()).filter((m) => m !== bas);
    await chrome.storage.local.set({ mesMots: mots });
    return { total: mots.length };
  }

  return { REGLAGES_DEFAUT, reglagesComplets, site, siteExclu, mesMots, ajouterMots, oublierMot };
});
