/*
 * Ce que partagent le popup et les pages de l'extension : parler au correcteur, lire
 * et changer les réglages, dire l'état, dessiner les interrupteurs et la graphie.
 */
(function () {
  "use strict";
  const C = globalThis.KabCommun;

  const INTERRUPTEURS = [
    ["translitteration", "Écrire comme on parle", "gh → ɣ, dh → ḍ, kh → x, aa → ɛ, ou → u. Un effacement juste après défait la conversion."],
    ["altgr", "AltGr + une lettre", "AltGr + g, e, d, h, t, z, s, c, j, r donnent ɣ ɛ ḍ ḥ ṭ ẓ ṣ č ǧ ṛ."],
    ["barre", "Barre des propositions", "Six propositions sous le mot : la correction en contexte (vert), les candidats (bleu), la complétion (ocre)."],
    ["chiffres", "Choisir avec 1 à 6", "Tant qu'un mot est en cours. En AZERTY : Maj + 1 à 6, ou le pavé numérique."],
    ["prediction", "Proposer le mot suivant", "Quand un mot finit, la barre propose la suite (en ocre)."],
    ["souligner", "Souligner les fautes", "Pendant qu'on écrit ; un clic sur le mot souligné pour le corriger. Le correcteur de Chrome, qui ne connaît pas le kabyle, se tait alors dans le champ."],
    ["autocorrection", "Correction automatique", "À l'espace, corrige les mots que le correcteur ne connaît pas (jamais un mot connu, un nom propre, un sigle). Retour arrière rend le mot tapé."],
  ];

  async function correcteur(requete) {
    try {
      const { graphie } = await lireReglages();
      const r = await chrome.runtime.sendMessage({ type: "correcteur", requete: { graphie, ...requete } });
      return r || { erreur: "Le correcteur ne répond pas.", indisponible: true };
    } catch (erreur) {
      return { erreur: "Le correcteur ne répond pas.", indisponible: true };
    }
  }

  async function lireReglages() {
    const r = await chrome.storage.sync.get("reglages");
    return C.reglagesComplets(r.reglages);
  }

  async function changerReglages(changements) {
    const nouveaux = { ...(await lireReglages()), ...changements };
    await chrome.storage.sync.set({ reglages: nouveaux });
    return nouveaux;
  }

  /** L'état du correcteur, en le réveillant : ouvrir le popup le prépare. */
  async function etat() {
    try {
      return await chrome.runtime.sendMessage({ type: "connecter" });
    } catch (erreur) {
      return null;
    }
  }

  function surEtat(fonction) {
    chrome.storage.onChanged.addListener((changements, zone) => {
      if (zone === "session" && changements.etat) fonction(changements.etat.newValue);
    });
  }

  function surReglages(fonction) {
    chrome.storage.onChanged.addListener((changements, zone) => {
      if (zone === "sync" && changements.reglages) fonction(C.reglagesComplets(changements.reglages.newValue));
    });
  }

  /** { classe, texte } : la pastille de l'état. */
  function decrireEtat(e) {
    if (!e) return { classe: "attente", texte: "…" };
    if (e.moteur === "panne") return { classe: "erreur", texte: "Le correcteur ne se charge pas" };
    if (e.moteur !== "pret") return { classe: "attente", texte: "Le correcteur se prépare…" };
    return { classe: "pret", texte: "Prêt, sur cet ordinateur" };
  }

  function dessinerEtat(element, e) {
    const d = decrireEtat(e);
    element.className = "pastille " + d.classe;
    element.textContent = d.texte;
  }

  /** Les interrupteurs des réglages, rangés dans conteneur. */
  function dessinerInterrupteurs(conteneur, reglages, sansDetail) {
    conteneur.textContent = "";
    for (const [cle, libelle, detail] of INTERRUPTEURS) {
      const ligne = document.createElement("label");
      ligne.className = "interrupteur";
      const coche = document.createElement("input");
      coche.type = "checkbox";
      coche.checked = !!reglages[cle];
      coche.dataset.cle = cle;
      coche.addEventListener("change", () => changerReglages({ [cle]: coche.checked }));
      const textes = document.createElement("span");
      const l = document.createElement("span");
      l.className = "libelle";
      l.textContent = libelle;
      textes.appendChild(l);
      if (!sansDetail) {
        const d = document.createElement("span");
        d.className = "detail";
        d.textContent = detail;
        textes.appendChild(d);
      } else {
        ligne.title = detail;
      }
      ligne.append(coche, textes);
      conteneur.appendChild(ligne);
    }
  }

  function mettreInterrupteurs(conteneur, reglages) {
    for (const coche of conteneur.querySelectorAll("input[data-cle]")) {
      coche.checked = !!reglages[coche.dataset.cle];
    }
  }

  /** Les deux boutons de la graphie ; marquer(g) les remet à jour. */
  function brancherGraphie(conteneur, reglages) {
    const boutons = conteneur.querySelectorAll("button[data-graphie]");
    const marquer = (g) => {
      for (const b of boutons) b.setAttribute("aria-pressed", String(b.dataset.graphie === g));
    };
    marquer(reglages.graphie);
    for (const b of boutons) {
      b.addEventListener("click", () => {
        marquer(b.dataset.graphie);
        changerReglages({ graphie: b.dataset.graphie });
      });
    }
    return marquer;
  }

  globalThis.KabPages = {
    INTERRUPTEURS, correcteur, lireReglages, changerReglages, etat, surEtat, surReglages,
    decrireEtat, dessinerEtat, dessinerInterrupteurs, mettreInterrupteurs, brancherGraphie,
  };
})();
