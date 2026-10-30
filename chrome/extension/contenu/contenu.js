/*
 * Le clavier kabyle dans la page : il suit le champ où l'on écrit.
 *
 * Tout ce que fait le clavier Android de kab-board se fait ici de la même façon
 * (ClavierKabyle.kt, CorrecteurSysteme.kt), avec son correcteur porté en JavaScript
 * (moteur/) : les mêmes propositions, les mêmes soulignés.
 *
 *  - « Écrire comme on parle » : gh → ɣ, dh → ḍ, kh → x, aa → ɛ, ou → u, quand la
 *    lettre tapée forme une paire avec celle qui précède le curseur ; un
 *    effacement juste après défait la conversion. AltGr + g, e, d, h, t, z, s, c,
 *    j, r, en plus.
 *  - La barre des six propositions, recalculée à chaque mouvement du curseur :
 *    complétion de 1 à 3 lettres, puis la correction en contexte et les
 *    candidats ; sans mot en cours, le mot suivant. 1 à 6 ou un clic pour
 *    choisir. Rien n'est corrigé d'office.
 *  - La correction automatique, si on l'allume : le mot que le correcteur ne
 *    connaît pas est corrigé à l'espace, et Retour arrière l'annule.
 *  - Les fautes soulignées pendant qu'on écrit (rouge : un mot inconnu ; bleu : un
 *    mot connu que le contexte écrirait autrement), une carte au clic.
 *  - Les outils : dictée, Asegzawal, du français au kabyle, relire, mot du jour,
 *    les lettres kabyles.
 *
 * La logique (logique.js) et les champs (champs.js) sont à part : ce fichier ne
 * fait que relier la page, le fond et l'interface.
 */
(function () {
  "use strict";
  const C = globalThis.KabCommun;
  const L = globalThis.KabLogique;
  const K = globalThis.KabChamps;
  const I = globalThis.KabInterface;
  const el = I.el;

  // Une seule instance par document : après une mise à jour de l'extension, la
  // nouvelle relève l'ancienne, qui n'a plus de fond à qui parler.
  const INSTANCE = Math.random().toString(36).slice(2);
  document.dispatchEvent(new CustomEvent("kab-board-releve", { detail: INSTANCE }));

  const ui = new I.Interface();
  K.poserMiroirsDans(ui.miroirs);

  let reglages = C.reglagesComplets({});
  let etat = { moteur: "arrete", erreur: "" };
  const SITE = siteCourant();
  let monte = true;

  let champ = null;            // le champ où l'on écrit en ce moment
  let dernierChamp = null;     // le dernier, pour les outils ouverts depuis le panneau
  let frappe = null;           // { el, pos, lettre } : la lettre tapée juste avant
  let conversion = null;       // { el, pos, avant, apres } : défaite par un effacement
  let autoCorr = null;         // { el, debut, original, forme, sep, pos } : idem
  let finDeMot = null;         // le mot que termine le séparateur en train d'être tapé
  let notreEcriture = 0;       // nos propres remplacements, que les écouteurs ignorent
  let barre = { formes: [], nature: "prop", motsAvant: 0, cle: "" };
  let enVol = null;
  let suivante = null;
  let derniereReponse = null;
  let dictee = null;           // { champ, debut, fin, phase, secondes }
  let messageMontre = "";
  let disposition = null;      // la disposition du clavier physique, pour AltGr

  const gardes = new Set();    // les mots gardés dans cette page
  let mesMots = new Set();     // « mon dictionnaire »
  const cacheRelecture = new Map();
  const CACHE_MAX = 3000;
  let minuterieRelecture = null;
  let relectureEnCours = false;
  let relectureDemandee = false;
  let dessinPrevu = false;
  const correcteurOrthographe = new WeakMap();
  const observateurTaille = new ResizeObserver(() => prevoirDessin());

  // Le fond

  function vivant() {
    try {
      return !!(chrome.runtime && chrome.runtime.id);
    } catch (erreur) {
      return false;
    }
  }

  function envoyerFond(message) {
    return new Promise((resoudre) => {
      if (!vivant()) {
        demonter();
        resoudre(null);
        return;
      }
      try {
        chrome.runtime.sendMessage(message, (reponse) => {
          void chrome.runtime.lastError;
          resoudre(reponse === undefined ? null : reponse);
        });
      } catch (erreur) {
        demonter();
        resoudre(null);
      }
    });
  }

  async function correcteur(requete) {
    const r = await envoyerFond({ type: "correcteur", requete: { graphie: reglages.graphie, ...requete } });
    return r || { erreur: "Le correcteur ne répond pas.", indisponible: true };
  }

  function siteCourant() {
    const ancetres = location.ancestorOrigins;
    if (ancetres && ancetres.length) return C.site(ancetres[ancetres.length - 1]);
    return C.site(location.href);
  }

  function actif() {
    return monte && reglages.allume && !C.siteExclu(reglages, SITE);
  }

  // Les écouteurs, retirés d'un coup quand l'instance est relevée

  const ecouteurs = [];
  function ecouter(cible, type, fonction, options) {
    const f = (e) => {
      if (!vivant()) {
        demonter();
        return;
      }
      try {
        fonction(e);
      } catch (erreur) {
        console.warn("Kab-board :", erreur);
      }
    };
    cible.addEventListener(type, f, options);
    ecouteurs.push([cible, type, f, options]);
  }

  function demonter() {
    if (!monte) return;
    monte = false;
    for (const [cible, type, f, options] of ecouteurs) cible.removeEventListener(type, f, options);
    ecouteurs.length = 0;
    quitterChamp();
    ui.detacher();
    observateurTaille.disconnect();
    try {
      CSS.highlights.delete("kab-board-faute");
      CSS.highlights.delete("kab-board-doute");
      CSS.highlights.delete("kab-board-actuel");
    } catch (erreur) {
      // rien
    }
  }

  // Le champ

  function cibleDe(e) {
    const chemin = e.composedPath ? e.composedPath() : [];
    // Une racine d'ombre fermée ne montre que son hôte : on y descend.
    return K.auFond(chemin[0] || e.target);
  }

  function dansLeChamp(e) {
    if (!champ) return false;
    const cible = cibleDe(e);
    return cible === champ.el || champ.el.contains(cible);
  }

  function entrerChamp(nouveau) {
    if (nouveau === champ) return;
    quitterChamp();
    champ = nouveau;
    dernierChamp = nouveau;
    frappe = conversion = autoCorr = finDeMot = null;
    if (!actif()) return;
    taireCorrecteurDuNavigateur(champ);
    observateurTaille.observe(champ.el);
    envoyerFond({ type: "reveil" }).then((e) => {
      if (e) mettreEtat(e);
    });
    planifierRelecture(150);
    prevoirDessin();
  }

  function quitterChamp() {
    if (!champ) return;
    ui.cacherBarre();
    ui.cacherCarte();
    ui.effacerSoulignes(champ);
    if (champ.genre === "editable") effacerSurlignages();
    observateurTaille.unobserve(champ.el);
    champ = null;
  }

  /** Le correcteur de Chrome ne connaît pas le kabyle : il soulignerait chaque mot.
   * Tant que Kab-board souligne, il se tait dans ce champ ; il revient si l'on
   * éteint Kab-board. */
  function taireCorrecteurDuNavigateur(c) {
    if (!reglages.souligner || correcteurOrthographe.has(c.el)) return;
    correcteurOrthographe.set(c.el, c.el.getAttribute("spellcheck"));
    c.el.setAttribute("spellcheck", "false");
  }

  function rendreCorrecteurDuNavigateur() {
    for (const c of [champ, dernierChamp]) {
      if (!c || !correcteurOrthographe.has(c.el)) continue;
      const avant = correcteurOrthographe.get(c.el);
      if (avant === null) c.el.removeAttribute("spellcheck");
      else c.el.setAttribute("spellcheck", avant);
      correcteurOrthographe.delete(c.el);
    }
  }

  function surFocus(e) {
    const cible = cibleDe(e);
    if (ui.contient(e)) return;
    const nouveau = K.champPour(cible);
    if (nouveau) entrerChamp(nouveau);
    else quitterChamp();
  }

  function surPerteFocus(e) {
    if (!champ || !dansLeChamp(e)) return;
    // Le focus part ailleurs (pas dans nos outils, qui ne le prennent jamais).
    setTimeout(() => {
      if (champ && K.elementActif(document) !== champ.el &&
          !champ.el.contains(K.elementActif(document))) {
        quitterChamp();
      }
    }, 0);
  }

  // Écrire

  function ecrire(c, debut, fin, texte, curseurApres) {
    notreEcriture++;
    try {
      return c.remplacer(debut, fin, texte, curseurApres);
    } finally {
      notreEcriture--;
    }
  }

  function apresChangement(genre) {
    ui.cacherCarte();
    if (genre !== "autocorrection") planifierPropositions();
    prevoirDessin();
    planifierRelecture();
  }

  function surAvantSaisie(e) {
    if (!e.isTrusted || notreEcriture || !dansLeChamp(e) || e.isComposing || !actif()) return;
    if (convertirSurSelection(e)) return;
    const curseur = champ.curseur();
    if (curseur === null) return;
    if (e.inputType === "insertText" && e.data && e.data.length === 1) {
      if (reglages.translitteration && curseur > 0) {
        const texte = champ.texte();
        const avant = texte[curseur - 1];
        const conv = L.convertir(avant, e.data);
        if (conv) {
          e.preventDefault();
          ecrire(champ, curseur - 1, curseur, conv);
          conversion = { el: champ.el, pos: curseur - 1 + conv.length, avant: avant + e.data, apres: conv };
          frappe = { el: champ.el, pos: curseur - 1 + conv.length };
          autoCorr = null;
          apresChangement("lettre");
          return;
        }
      }
      if (L.finitUnMot(e.data)) {
        const texte = champ.texte();
        const etatMot = L.etat(texte, curseur);
        finDeMot = etatMot.mot && etatMot.finApres === 0 ? {
          el: champ.el, mot: etatMot.mot, debut: etatMot.debut, fin: curseur,
          contexte: etatMot.gauche, sep: e.data,
        } : null;
      }
      return;
    }
    if (e.inputType === "deleteContentBackward") {
      const texte = champ.texte();
      if (conversion && conversion.el === champ.el && conversion.pos === curseur &&
          texte.slice(curseur - conversion.apres.length, curseur) === conversion.apres) {
        e.preventDefault();
        const debut = curseur - conversion.apres.length;
        ecrire(champ, debut, curseur, conversion.avant);
        frappe = { el: champ.el, pos: debut + conversion.avant.length };
        conversion = null;
        apresChangement("lettre");
        return;
      }
      if (autoCorr && autoCorr.el === champ.el && autoCorr.pos === curseur &&
          texte.slice(autoCorr.debut, curseur) === autoCorr.forme + autoCorr.sep) {
        e.preventDefault();
        ecrire(champ, autoCorr.debut, curseur, autoCorr.original + autoCorr.sep);
        gardes.add(autoCorr.original.toLowerCase());
        autoCorr = null;
        frappe = null;
        ui.cacherBarre();
        apresChangement("autre");
      }
    }
  }

  /**
   * La lettre tapée remplace une sélection : la suite qu'un site propose dans le champ
   * pendant qu'on tape (Bing, certains moteurs de recherche) est sélectionnée. La paire
   * se forme alors avec la lettre qui précède la sélection.
   */
  function convertirSurSelection(e) {
    if (e.inputType !== "insertText" || !e.data || e.data.length !== 1 || !reglages.translitteration) return false;
    const [debut, fin] = champ.selection();
    if (debut === null || fin === null || fin <= debut || debut === 0) return false;
    const avant = champ.texte()[debut - 1];
    const conv = L.convertir(avant, e.data);
    if (!conv) return false;
    e.preventDefault();
    ecrire(champ, debut - 1, fin, conv);
    conversion = { el: champ.el, pos: debut - 1 + conv.length, avant: avant + e.data, apres: conv };
    frappe = { el: champ.el, pos: debut - 1 + conv.length };
    autoCorr = null;
    apresChangement("lettre");
    return true;
  }

  function surSaisie(e) {
    if (notreEcriture || !dansLeChamp(e)) return;
    if (!actif()) return;
    const curseur = champ.curseur();
    if (e.isTrusted && e.inputType === "insertText" && e.data && e.data.length === 1 && curseur !== null) {
      if (L.estLettre(e.data)) {
        frappe = { el: champ.el, pos: curseur };
        conversion = null;
        autoCorr = null;
        finDeMot = null;
        apresChangement("lettre");
        return;
      }
      frappe = null;
      conversion = null;
      autoCorr = null;
      const fin = finDeMot;
      finDeMot = null;
      apresChangement("separateur");
      if (fin && fin.el === champ.el && fin.fin + fin.sep.length === curseur &&
          reglages.autocorrection && actif()) {
        corrigerDOffice(fin);
      }
      return;
    }
    if (e.isTrusted && e.inputType === "deleteContentBackward" && curseur !== null) {
      const c = champ.texte()[curseur - 1];
      frappe = L.estLettre(c) ? { el: champ.el, pos: curseur } : null;
      conversion = null;
      autoCorr = null;
      finDeMot = null;
      apresChangement("effacement");
      return;
    }
    frappe = conversion = autoCorr = finDeMot = null;
    apresChangement("autre");
  }

  async function chargerDisposition() {
    try {
      if (navigator.keyboard && navigator.keyboard.getLayoutMap) {
        disposition = await navigator.keyboard.getLayoutMap();
      }
    } catch (erreur) {
      disposition = null;       // un cadre, ou un navigateur qui ne la donne pas
    }
  }

  /** La lettre latine de la touche, sans AltGr : « g » pour AltGr + g. */
  function baseDeTouche(e) {
    const selonDisposition = disposition && disposition.get(e.code);
    if (selonDisposition && selonDisposition.length === 1) return selonDisposition;
    const m = /^Key([A-Z])$/.exec(e.code || "");
    return m ? m[1].toLowerCase() : "";
  }

  function surTouche(e) {
    if (!e.isTrusted || !dansLeChamp(e) || e.isComposing) return;
    if (e.key === "Escape") {
      if (dictee && dictee.phase === "ecoute") {
        envoyerFond({ type: "dicter", action: "annuler" });
      } else if (ui.carteVisible) {
        ui.cacherCarte();
        planifierPropositions();
      } else if (ui.barreVisible) {
        ui.cacherBarre();
      } else {
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    if (!actif()) return;
    if (reglages.chiffres && ui.barreVisible && !e.ctrlKey && !e.altKey && !e.metaKey) {
      const curseur = champ.curseur();
      if (curseur !== null) {
        const texte = champ.texte();
        if (barreValable(texte, curseur)) {
          const rang = L.rangDuChiffre(e.key, barre.formes, barre.nature, L.motEnCours(texte, curseur));
          if (rang >= 0) {
            e.preventDefault();
            e.stopPropagation();
            choisir(rang);
            return;
          }
        }
      }
    }
    if (reglages.altgr && e.getModifierState && e.getModifierState("AltGraph") && !e.metaKey) {
      const majuscule = e.shiftKey !== e.getModifierState("CapsLock");
      const lettre = L.altgr(baseDeTouche(e), majuscule);
      if (!lettre) return;
      e.preventDefault();
      e.stopPropagation();
      const [d, f] = champ.selection();
      if (d === null) return;
      ecrire(champ, d, f, lettre);
      frappe = conversion = autoCorr = null;
      apresChangement("lettre");
    }
  }

  // La barre des propositions

  /**
   * Une réponse vaut-elle pour le texte tel qu'il est ? Comme ClavierKabyle.calculer :
   * le même contexte, et le même mot, ou ce mot continué le temps que le correcteur
   * réponde (un chiffre choisit alors ce que l'on voit).
   */
  function valable(demande, actuel) {
    if (actuel.gauche !== demande.gauche) return false;
    return demande.mot === "" ? actuel.mot === "" : actuel.mot.startsWith(demande.mot);
  }

  function barreValable(texte, curseur) {
    return !!barre.formes.length && valable(barre, L.etat(texte, curseur));
  }

  let minuterieBarre = null;

  /** ClavierKabyle.proposer : la frappe suivante remplace celle-ci tant que le calcul
   * n'est pas parti (60 ms). */
  function planifierPropositions() {
    clearTimeout(minuterieBarre);
    minuterieBarre = setTimeout(proposer, 60);
  }

  function proposer() {
    if (!champ || !actif() || !reglages.barre || dictee) {
      if (!dictee) ui.cacherBarre();
      return;
    }
    const curseur = champ.curseur();
    if (curseur === null) {
      ui.cacherBarre();
      return;
    }
    if (etat.moteur === "panne" && messageMontre) {
      ui.cacherBarre();
      return;
    }
    const e = L.etat(champ.texte(), curseur);
    // Aucun mot en cours ni rien avant (gauche est déjà rogné) : ni à corriger, ni à prédire.
    if (!e.mot && !e.gauche) {
      ui.cacherBarre();
      return;
    }
    if (e.mot) demander({ quoi: "proposer", contexte: e.gauche, mot: e.mot }, e);
    else if (reglages.prediction) demander({ quoi: "predire", contexte: e.gauche }, e);
    else ui.cacherBarre();
  }

  /** Un calcul à la fois ; à son retour, il repart sur le dernier état. */
  function demander(requete, e) {
    const demande = { requete, champ, mot: e.mot, gauche: e.gauche };
    if (enVol) {
      suivante = demande;
      return;
    }
    lancer(demande);
  }

  async function lancer(demande) {
    enVol = demande;
    const r = await correcteur(demande.requete);
    enVol = null;
    derniereReponse = { requete: demande.requete, reponse: r };
    if (suivante) {
      const s = suivante;
      suivante = null;
      lancer(s);
    }
    if (demande.champ !== champ || !champ || dictee) return;
    const curseur = champ.curseur();
    if (curseur === null || !valable(demande, L.etat(champ.texte(), curseur))) return;
    // Un clic sur un mot souligné ouvre sa carte, et place le curseur dans le mot : la
    // barre de ce début de mot attendra que la carte se ferme.
    if (ui.carteVisible) return;
    if (r.erreur) {
      // Un correcteur en panne se dit une fois : la frappe (gh → ɣ), elle, continue
      // sans lui. Un correcteur qui se charge, lui, se dit à chaque mot.
      if (!r.indisponible) montrerMessage(r.erreur);
      else if (etat.moteur !== "panne") montrerMessage(messageEtat());
      else if (!messageMontre) {
        messageMontre = "panne";
        montrerMessage(messageEtat());
      } else ui.cacherBarre();
      return;
    }
    const formes = r.formes || [];
    const nature = demande.requete.quoi === "predire" ? "pred" : (r.nature || "prop");
    if (!formes.length) {
      if (etat.moteur !== "pret") montrerMessage(messageEtat());
      else ui.cacherBarre();
      return;
    }
    barre = {
      formes, nature, motsAvant: nature === "prop" ? (r.mots_avant || 0) : 0,
      mot: demande.mot, gauche: demande.gauche,
    };
    ui.montrerBarre({ formes, nature, ancre: champ.rectangleCurseur(curseur), chiffres: reglages.chiffres });
  }

  function messageEtat() {
    if (etat.moteur === "panne") return "Le correcteur ne se charge pas";
    return "Le correcteur se prépare…";
  }

  /** Une ligne à la place des propositions, jusqu'à ce que le curseur bouge. */
  function montrerMessage(message) {
    if (!champ) return;
    const curseur = champ.curseur();
    if (curseur === null) return;
    const e = L.etat(champ.texte(), curseur);
    barre = { formes: [], nature: "prop", motsAvant: 0, mot: e.mot, gauche: e.gauche, message: true };
    ui.montrerBarre({ formes: [], message, ancre: champ.rectangleCurseur(curseur) });
  }

  /** ClavierKabyle.appliquerChoix : seule la tête d'une correction rattache les mots
   * d'avant. */
  function choisir(rang) {
    if (!champ || !barre.formes[rang]) return;
    const forme = barre.formes[rang];
    const curseur = champ.curseur();
    if (curseur === null) return;
    const motsAvant = rang === 0 && barre.nature === "prop" ? barre.motsAvant : 0;
    const c = L.choix(champ.texte(), curseur, forme, motsAvant);
    ecrire(champ, c.debut, c.fin, c.texte, c.curseurApres);
    frappe = conversion = autoCorr = finDeMot = null;
    ui.cacherBarre();
    apresChangement("choix");
  }

  // La correction automatique

  async function corrigerDOffice(fin) {
    const d = derniereReponse;
    let r = d && d.requete.quoi === "proposer" && d.requete.mot === fin.mot &&
      d.requete.contexte === fin.contexte ? d.reponse : null;
    if (!r || r.erreur) r = await correcteur({ quoi: "proposer", contexte: fin.contexte, mot: fin.mot });
    const connus = new Set([...gardes, ...mesMots]);
    const forme = L.autocorrection(fin.mot, fin.contexte, r, connus);
    if (!forme || !champ || champ.el !== fin.el) return;
    // Seulement si rien n'a bougé depuis : le mot, le séparateur, le curseur juste après.
    const curseur = champ.curseur();
    const texte = champ.texte();
    if (curseur !== fin.fin + fin.sep.length || texte.slice(fin.debut, curseur) !== fin.mot + fin.sep) return;
    const pos = fin.debut + forme.length + fin.sep.length;
    if (!ecrire(champ, fin.debut, fin.fin, forme, pos)) return;
    autoCorr = { el: champ.el, debut: fin.debut, original: fin.mot, forme, sep: fin.sep, pos };
    apresChangement("autocorrection");
    montrerMessage(`« ${fin.mot} » → « ${forme} » · Retour arrière pour garder « ${fin.mot} »`);
  }

  // Les soulignés

  function memoriser(texte, signales) {
    if (cacheRelecture.size >= CACHE_MAX) {
      cacheRelecture.delete(cacheRelecture.keys().next().value);
    }
    cacheRelecture.set(texte, signales);
  }

  function planifierRelecture(delai) {
    clearTimeout(minuterieRelecture);
    if (!champ || !reglages.souligner || !actif()) return;
    minuterieRelecture = setTimeout(relireEnFond, delai === undefined ? 700 : delai);
  }

  /** Relit les phrases qui n'ont pas encore été relues, la plus proche du curseur d'abord. */
  async function relireEnFond() {
    if (relectureEnCours) {
      relectureDemandee = true;
      return;
    }
    const c = champ;
    if (!c || !reglages.souligner || !actif()) return;
    if (etat.moteur !== "pret") {
      if (etat.moteur !== "panne") planifierRelecture(1500);
      return;
    }
    relectureEnCours = true;
    try {
      for (let tour = 0; tour < 200 && c === champ && monte; tour++) {
        const texte = c.texte();
        if (texte.length > 200000) break;
        const curseur = c.curseur() ?? 0;
        const manquants = morceauxEnContexte(texte).filter((m) => !cacheRelecture.has(m.cle));
        if (!manquants.length) break;
        manquants.sort((a, b) => distance(a, curseur) - distance(b, curseur));
        const morceau = manquants[0];
        const r = await correcteur({ quoi: "juger", texte: morceau.texte, avant: morceau.avant });
        if (r.erreur) {
          // Le correcteur se recharge : on réessaiera, sans rien retenir.
          if (etat.moteur !== "panne") relectureDemandee = true;
          break;
        }
        memoriser(morceau.cle, r.signales || []);
        prevoirDessin();
      }
    } finally {
      relectureEnCours = false;
    }
    if (relectureDemandee) {
      relectureDemandee = false;
      planifierRelecture(etat.moteur === "pret" ? 0 : 2000);
    }
  }

  /** Les phrases à juger, chacune avec ce qui la précède : le contexte de ses premiers
   * mots est celui qu'a le mot dans tout le texte, comme dans « Relire » d'Android. */
  function morceauxEnContexte(texte) {
    return L.morceaux(texte).map((m) => {
      const avant = L.avantUtile(texte.slice(0, m.debut));
      return { ...m, avant, cle: avant + "\u0001" + m.texte };
    });
  }

  function distance(morceau, curseur) {
    if (curseur < morceau.debut) return morceau.debut - curseur;
    const fin = morceau.debut + morceau.texte.length;
    return curseur > fin ? curseur - fin : 0;
  }

  function soulignesDe(c, texte) {
    const curseur = c.curseur();
    const liste = [];
    for (const m of morceauxEnContexte(texte)) {
      const signales = cacheRelecture.get(m.cle);
      if (!signales) continue;
      for (const s of signales) {
        const debut = m.debut + s.debut;
        const fin = m.debut + s.fin;
        if (texte.slice(debut, fin) !== s.mot) continue;
        const bas = s.mot.toLowerCase();
        if (gardes.has(bas) || mesMots.has(bas)) continue;
        // Le mot que l'on tape n'est pas encore fini : on ne le souligne pas.
        if (curseur === fin && frappe && frappe.el === c.el) continue;
        if (!s.propositions || !s.propositions.length) continue;
        liste.push({ ...s, debut, fin });
      }
    }
    return liste;
  }

  function prevoirDessin() {
    if (dessinPrevu) return;
    dessinPrevu = true;
    requestAnimationFrame(() => {
      dessinPrevu = false;
      dessiner();
    });
  }

  function dessiner() {
    if (!champ || !monte) return;
    if (ui.barreVisible && champ.curseur() !== null) ui.replacerBarre(champ.rectangleCurseur(champ.curseur()));
    if (!reglages.souligner || !actif()) {
      ui.effacerSoulignes(champ);
      effacerSurlignages();
      return;
    }
    const liste = soulignesDe(champ, champ.texte());
    champ.soulignes = liste;
    if (champ.genre === "texte") {
      ui.dessinerSoulignes(champ, liste, champ.actuel || null);
    } else {
      surligner(champ, liste);
    }
  }

  function surligner(c, liste) {
    if (!window.CSS || !CSS.highlights) return;
    const fautes = [];
    const doutes = [];
    const plages = c.plages(liste);
    liste.forEach((s, i) => (s.soulignement === "doute" ? doutes : fautes).push(plages[i]));
    CSS.highlights.set("kab-board-faute", new Highlight(...fautes));
    CSS.highlights.set("kab-board-doute", new Highlight(...doutes));
    if (c.actuel) CSS.highlights.set("kab-board-actuel", new Highlight(...c.plages([c.actuel])));
    else CSS.highlights.delete("kab-board-actuel");
  }

  function effacerSurlignages() {
    if (!window.CSS || !CSS.highlights) return;
    CSS.highlights.delete("kab-board-faute");
    CSS.highlights.delete("kab-board-doute");
    CSS.highlights.delete("kab-board-actuel");
  }

  function souligneSous(c, position) {
    return (c.soulignes || []).find((s) => position >= s.debut && position <= s.fin) || null;
  }

  function surClic(e) {
    if (!e.isTrusted || !dansLeChamp(e) || !actif() || !reglages.souligner) return;
    setTimeout(() => {
      if (!champ) return;
      const curseur = champ.curseur();
      if (curseur === null) return;
      const s = souligneSous(champ, curseur);
      if (!s) {
        ui.cacherCarte();
        return;
      }
      const rects = champ.rectangles([{ debut: s.debut, fin: s.fin }])[0];
      const ancre = rects[rects.length - 1] || champ.rectangleCurseur(curseur);
      ui.cacherBarre();
      ui.montrerCarte({ souligne: s, ancre });
    }, 0);
  }

  /** Comme onUpdateSelection : le curseur a bougé, la barre se recalcule. */
  function surSelection() {
    if (!champ || notreEcriture) return;
    prevoirDessin();
    if (dictee) return;
    const curseur = champ.curseur();
    if (curseur === null) {
      ui.cacherBarre();
      return;
    }
    if (conversion && conversion.pos !== curseur) conversion = null;
    if (barre.message && ui.barreVisible && valable(barre, L.etat(champ.texte(), curseur))) return;
    planifierPropositions();
  }

  function remplacerSouligne(s, forme) {
    const c = champ || dernierChamp;
    if (!c) return;
    if (c.texte().slice(s.debut, s.fin) !== s.mot) {
      ui.cacherCarte();
      return;
    }
    ecrire(c, s.debut, s.fin, forme);
    ui.cacherCarte();
    apresChangement("autre");
  }

  function garder(s) {
    gardes.add(s.mot.toLowerCase());
    ui.cacherCarte();
    prevoirDessin();
  }

  async function ajouterAuDictionnaire(mot) {
    const r = await C.ajouterMots([mot]);
    if (!r.erreur) mesMots.add(mot.toLowerCase());
    return r;
  }

  // La dictée : le micro est écouté par le fond, le texte s'écrit ici

  async function basculerDictee() {
    if (dictee && dictee.phase === "ecoute") {
      envoyerFond({ type: "dicter", action: "arreter" });
      return;
    }
    if (dictee) return;
    const c = champ || dernierChamp;
    if (!c || !c.el.isConnected) {
      outilMessage("Dictée", "Cliquez d'abord dans le champ où écrire, puis dictez.");
      return;
    }
    const [d, f] = c.selection();
    const longueur = c.texte().length;
    dictee = { champ: c, debut: d === null ? longueur : d, fin: f === null ? longueur : f, phase: "ecoute", secondes: 0 };
    montrerDictee();
    const r = await envoyerFond({ type: "dicter", action: "commencer" });
    if (!r || r.erreur) {
      dictee = null;
      ui.cacherBarre();
      const erreur = r && r.erreur === "micro-refuse"
        ? "Chrome doit d'abord pouvoir écouter le micro : autorisez-le dans l'onglet qui vient de s'ouvrir, puis recommencez."
        : (r && r.erreur) || "Le micro ne répond pas.";
      outilMessage("Dictée", erreur);
    }
  }

  function montrerDictee() {
    if (!dictee) return;
    const c = dictee.champ;
    const position = Math.min(dictee.fin, c.texte().length);
    let ancre;
    try {
      ancre = c.rectangleCurseur(position);
    } catch (erreur) {
      ancre = c.el.getBoundingClientRect();
    }
    ui.montrerBarre({
      ancre, ecoute: dictee.phase === "transcription" ? { transcription: true } : { secondes: dictee.secondes },
    });
  }

  function finirDictee(message) {
    const d = dictee;
    dictee = null;
    ui.cacherBarre();
    if (!d) return;
    if (message.erreur) {
      outilMessage("Dictée", message.erreur === "Dictée annulée." ? message.erreur : "Dictée impossible : " + message.erreur);
      return;
    }
    const dit = (message.texte || "").trim();
    if (!dit) {
      outilMessage("Dictée", "Rien entendu. Parlez près du micro, en kabyle, puis arrêtez la dictée.");
      return;
    }
    const c = d.champ;
    if (!c.el.isConnected) {
      outilMessage("Dictée", `« ${dit} » : le champ a disparu, le texte n'a pas été écrit.`);
      return;
    }
    if (K.elementActif(document) !== c.el && !c.el.contains(K.elementActif(document))) {
      c.el.focus({ preventScroll: true });
    }
    const texte = c.texte();
    let [debut, fin] = c.selection();
    if (debut === null) {
      debut = Math.min(d.debut, texte.length);
      fin = Math.min(d.fin, texte.length);
    }
    const avant = texte[debut - 1];
    const apres = texte[fin];
    const insere = (avant && !/\s/u.test(avant) ? " " : "") + dit + (apres && /\s/u.test(apres) ? "" : " ");
    ecrire(c, debut, fin, insere);
    frappe = conversion = autoCorr = null;
    apresChangement("autre");
    const debutDit = debut + (insere.startsWith(" ") ? 1 : 0);
    ui.panneau("Dictée", (corps) => {
      corps.append(el("p", { classe: "grand" }, `« ${dit} »`),
        el("p", { classe: "discret" }, "Écrit tel quel, jamais corrigé d'office : les mots à revoir se soulignent."));
      corps.append(I.sansFocus(el("button", { classe: "bouton" }, "Relire la dictée"),
        () => ouvrirRelecture(c, [debutDit, debutDit + dit.length])));
    });
  }

  // Les outils

  function outilMessage(titre, texte) {
    ui.panneau(titre, (corps) => corps.append(el("p", {}, texte)));
  }

  /** Écrit au curseur du champ où l'on écrivait, même si le panneau a pris le focus. */
  function insererAuCurseur(texte) {
    const c = champ || dernierChamp;
    if (!c || !c.el.isConnected) return false;
    if (K.elementActif(document) !== c.el && !c.el.contains(K.elementActif(document))) {
      c.el.focus({ preventScroll: true });
    }
    let [d, f] = c.selection();
    if (d === null) d = f = c.texte().length;
    const avant = c.texte()[d - 1];
    const ok = ecrire(c, d, f, (avant && L.estLettre(avant) ? " " : "") + texte);
    frappe = conversion = autoCorr = null;
    apresChangement("choix");
    return ok;
  }

  function motSousLeCurseur() {
    const c = champ || dernierChamp;
    if (!c) return "";
    const [d, f] = c.selection();
    const texte = c.texte();
    if (d !== null && f > d) return texte.slice(d, f).trim().split(/\s+/u)[0] || "";
    if (d === null) return "";
    let debut = d;
    let fin = d;
    while (debut > 0 && L.estLettre(texte[debut - 1])) debut--;
    while (fin < texte.length && L.estLettre(texte[fin])) fin++;
    return texte.slice(debut, fin);
  }

  function ligneEtat() {
    let texte;
    if (etat.moteur === "panne") texte = "Le correcteur ne se charge pas : " + etat.erreur;
    else if (etat.moteur === "pret") texte = `Correcteur prêt · graphie ${reglages.graphie}`;
    else texte = "Le correcteur se prépare…";
    return el("p", { classe: "discret" }, texte);
  }

  function boutonOutil(libelle, action) {
    return I.sansFocus(el("button", { classe: "bouton" }, libelle), action);
  }

  function ouvrirOutils() {
    ui.cacherBarre();
    ui.panneau("Kab-board", (corps) => {
      corps.append(ligneEtat());
      const grille = el("div", { style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", marginTop: "6px" } });
      grille.append(
        boutonOutil("🎤 Dicter", () => basculerDictee()),
        boutonOutil("Asegzawal", () => ouvrirFiche(motSousLeCurseur())),
        boutonOutil("fr → kab", () => ouvrirRecherche("")),
        boutonOutil("Relire", () => ouvrirRelecture(champ || dernierChamp)),
        boutonOutil("Mot du jour", () => ouvrirMotDuJour()),
        boutonOutil("ɣ ɛ ḍ ḥ…", () => ouvrirLettres()),
        boutonOutil("Écrire et relire", () => envoyerFond({ type: "ouvrir", page: "ecrire" })),
        boutonOutil("Réglages", () => envoyerFond({ type: "ouvrir", page: "reglages" })));
      corps.append(grille);
    });
  }

  function champDeSaisie(valeur, indication) {
    const champSaisie = el("input", { type: "text", value: valeur || "", placeholder: indication, spellcheck: "false" });
    L.brancherSaisie(champSaisie, () => reglages.translitteration);
    return champSaisie;
  }

  function ouvrirFiche(mot) {
    ui.panneau("Asegzawal", (corps) => {
      const saisie = champDeSaisie(mot, "Un mot kabyle (gh → ɣ)");
      const resultat = el("div");
      const chercher = async () => {
        const m = saisie.value.trim();
        resultat.textContent = "";
        if (!m) return;
        resultat.append(el("p", { classe: "discret" }, "…"));
        const r = await correcteur({ quoi: "fiche", mot: m });
        resultat.textContent = "";
        if (r.erreur) {
          resultat.append(el("p", {}, r.erreur));
          return;
        }
        if (!r.mot) {
          resultat.append(el("p", {}, "Fiche indisponible : le correcteur se charge encore."));
          return;
        }
        resultat.append(el("p", { classe: "grand" }, r.mot),
          el("p", {}, r.glose || "Pas de glose pour cette forme."));
        if (r.categorie) resultat.append(el("p", { classe: "discret" }, "catégorie : " + r.categorie));
        for (const [libelle, forme] of [["état libre", r.libre], ["état d'annexion", r.annexion]]) {
          if (!forme) continue;
          resultat.append(el("div", { classe: "rangee" }, el("span", {}, `${libelle} : `),
            el("b", {}, forme), boutonOutil("Insérer", () => insererAuCurseur(forme))));
        }
      };
      saisie.addEventListener("keydown", (e) => {
        if (e.key === "Enter") chercher();
      });
      corps.append(el("div", { classe: "rangee" }, saisie, boutonOutil("Voir", chercher)), resultat);
      if (mot) chercher();
      else setTimeout(() => saisie.focus(), 0);
    });
  }

  function ouvrirRecherche(requete) {
    ui.panneau("Du français au kabyle", (corps) => {
      const saisie = el("input", { type: "text", value: requete || "", placeholder: "Un mot français", spellcheck: "true" });
      const resultats = el("div");
      const chercher = async () => {
        const q = saisie.value.trim();
        resultats.textContent = "";
        if (q.length < 2) return;
        resultats.append(el("p", { classe: "discret" }, "…"));
        const r = await correcteur({ quoi: "chercher", requete: q });
        resultats.textContent = "";
        const trouves = r.trouves || [];
        if (r.erreur) resultats.append(el("p", {}, r.erreur));
        else if (!trouves.length) resultats.append(el("p", {}, "Aucun résultat."));
        for (const [forme, glose] of trouves) {
          resultats.append(I.sansFocus(el("button", { classe: "resultat", title: "Insérer" },
            el("b", {}, forme), " · ", el("span", { classe: "discret" }, glose.slice(0, 90))),
          () => insererAuCurseur(forme + " ")));
        }
      };
      saisie.addEventListener("keydown", (e) => {
        if (e.key === "Enter") chercher();
      });
      corps.append(el("div", { classe: "rangee" }, saisie, boutonOutil("Chercher", chercher)), resultats);
      if (requete) chercher();
      else setTimeout(() => saisie.focus(), 0);
    });
  }

  async function ouvrirMotDuJour() {
    const corps = ui.panneau("Mot du jour", (c) => c.append(el("p", { classe: "discret" }, "…")));
    const r = await correcteur({ quoi: "motdujour" });
    corps.textContent = "";
    if (!r.forme) {
      corps.append(el("p", {}, r.erreur || "Ressources indisponibles."));
      return;
    }
    corps.append(el("p", { classe: "grand" }, r.forme), el("p", {}, r.glose || ""),
      el("div", { classe: "rangee" }, boutonOutil("Insérer", () => insererAuCurseur(r.forme + " ")),
        boutonOutil("Asegzawal", () => ouvrirFiche(r.forme))));
  }

  function ouvrirLettres() {
    let majuscules = false;
    ui.panneau("Les lettres kabyles", (corps) => {
      const grille = el("div", { classe: "lettres" });
      const dessinerGrille = () => {
        grille.textContent = "";
        for (const lettre of L.KABYLES) {
          const l = majuscules ? lettre.toUpperCase() : lettre;
          grille.append(I.sansFocus(el("button", { title: `Écrire ${l}` }, l), () => insererLettre(l)));
        }
      };
      dessinerGrille();
      const maj = I.sansFocus(el("button", { classe: "bouton" }, "⇧ Majuscules"), () => {
        majuscules = !majuscules;
        maj.textContent = majuscules ? "⇩ Minuscules" : "⇧ Majuscules";
        dessinerGrille();
      });
      corps.append(grille, el("div", { classe: "rangee" }, maj),
        el("p", { classe: "discret" }, "Au clavier : gh → ɣ, dh → ḍ, kh → x, aa → ɛ, ou → u ; AltGr + g, e, d, h, t, z, s, c, j, r."));
    });
  }

  function insererLettre(lettre) {
    const c = champ || dernierChamp;
    if (!c) return;
    let [d, f] = c.selection();
    if (d === null) d = f = c.texte().length;
    ecrire(c, d, f, lettre);
    frappe = conversion = autoCorr = null;
    apresChangement("lettre");
  }

  /** Relit un champ (ou une partie) et liste les mots à revoir, avec leurs propositions. */
  async function ouvrirRelecture(c, plage) {
    if (!c || !c.el.isConnected) {
      outilMessage("Relire", "Cliquez d'abord dans le champ à relire.");
      return;
    }
    if (!plage) {
      const [d, f] = c.selection();
      if (d !== null && f > d) plage = [d, f];
    }
    const corps = ui.panneau(plage ? "Relire la sélection" : "Relire", (x) =>
      x.append(el("p", { classe: "discret" }, "Relecture…")));
    const texte = c.texte();
    const [debut, fin] = plage || [0, texte.length];
    const morceaux = morceauxEnContexte(texte)
      .filter((m) => m.debut + m.texte.length > debut && m.debut < fin);
    const signales = [];
    for (let i = 0; i < morceaux.length; i++) {
      const m = morceaux[i];
      let sig = cacheRelecture.get(m.cle);
      if (!sig) {
        corps.firstChild.textContent = `Relecture… ${i + 1} / ${morceaux.length}`;
        const r = await correcteur({ quoi: "juger", texte: m.texte, avant: m.avant });
        if (r.erreur) {
          corps.textContent = "";
          corps.append(el("p", {}, r.erreur));
          return;
        }
        sig = r.signales || [];
        memoriser(m.cle, sig);
      }
      for (const s of sig) {
        if (gardes.has(s.mot.toLowerCase()) || mesMots.has(s.mot.toLowerCase())) continue;
        const d = m.debut + s.debut;
        if (d < debut || m.debut + s.fin > fin) continue;
        // « Relire » d'Android : quatre propositions au plus.
        signales.push({ ...s, propositions: s.propositions.slice(0, 4), debut: d, fin: m.debut + s.fin });
      }
    }
    prevoirDessin();
    afficherRelecture(corps, c, signales, plage);
  }

  function afficherRelecture(corps, c, signales, plage) {
    corps.textContent = "";
    // Après un remplacement, la plage relue s'allonge ou raccourcit d'autant.
    const longueur = c.texte().length;
    const relancer = () => ouvrirRelecture(c, plage
      ? [plage[0], Math.max(plage[0], plage[1] + c.texte().length - longueur)] : undefined);
    if (!signales.length) {
      corps.append(el("p", {}, "Rien à signaler."));
      return;
    }
    corps.append(el("div", { classe: "rangee" },
      el("span", { style: { flex: "1" } }, signales.length === 1 ? "1 mot à revoir" : `${signales.length} mots à revoir`),
      boutonOutil("Tout corriger", () => {
        for (const s of [...signales].sort((a, b) => b.debut - a.debut)) {
          if (c.texte().slice(s.debut, s.fin) === s.mot) ecrire(c, s.debut, s.fin, s.propositions[0]);
        }
        apresChangement("autre");
        relancer();
      })));
    for (const s of signales) {
      const ligne = el("div", { classe: "signale" });
      const mot = I.sansFocus(el("span", {
        classe: "mot-signale", title: "Montrer dans le texte",
        style: { textDecoration: `underline wavy ${L.couleurSouligne(s.soulignement)}` },
      }, `« ${s.mot} »`), () => {
        if (c.texte().slice(s.debut, s.fin) !== s.mot) return;
        c.actuel = { debut: s.debut, fin: s.fin };
        const rects = c.rectangles([{ debut: s.debut, fin: s.fin }])[0];
        if (rects[0] && (rects[0].top < 0 || rects[0].bottom > window.innerHeight)) {
          c.el.scrollIntoView({ block: "center" });
        }
        prevoirDessin();
      });
      const props = el("div", { classe: "props", style: { display: "flex", flexWrap: "wrap", gap: "4px", margin: "4px 0" } });
      s.propositions.forEach((p, rang) => {
        const couleur = rang === 0 ? L.VERT : L.BLEU;
        props.append(I.sansFocus(el("button", { classe: "prop", style: { borderBottomColor: couleur } }, p), () => {
          if (c.texte().slice(s.debut, s.fin) === s.mot) ecrire(c, s.debut, s.fin, p);
          c.actuel = null;
          apresChangement("autre");
          relancer();
        }));
      });
      const actions = el("div", { classe: "actions" },
        I.sansFocus(el("button", { classe: "lien" }, "Garder"), () => {
          gardes.add(s.mot.toLowerCase());
          relancer();
        }),
        s.mot.includes(" ") ? null : I.sansFocus(el("button", { classe: "lien" }, "Ajouter à mon dictionnaire"), async () => {
          await ajouterAuDictionnaire(s.mot);
          relancer();
        }),
        I.sansFocus(el("button", { classe: "lien" }, "Asegzawal"), () => ouvrirFiche(s.propositions[0])));
      ligne.append(mot, props, actions);
      corps.append(ligne);
    }
  }

  /** Relire un texte que l'on ne peut pas modifier : une sélection dans la page. */
  async function relireLecture(texte) {
    const corps = ui.panneau("Relire la sélection", (x) => x.append(el("p", { classe: "discret" }, "Relecture…")));
    const signales = [];
    for (const m of morceauxEnContexte(texte.slice(0, 20000))) {
      const r = await correcteur({ quoi: "juger", texte: m.texte, avant: m.avant });
      if (r.erreur) {
        corps.textContent = "";
        corps.append(el("p", {}, r.erreur));
        return;
      }
      for (const s of r.signales || []) signales.push({ ...s, debut: m.debut + s.debut, fin: m.debut + s.fin });
    }
    corps.textContent = "";
    if (!signales.length) {
      corps.append(el("p", {}, "Rien à signaler."));
      return;
    }
    for (const s of signales) {
      corps.append(el("div", { classe: "signale" }, el("b", {}, s.mot), " → ",
        s.propositions.slice(0, 4).join(" · ")));
    }
    corps.append(el("div", { classe: "rangee" }, boutonOutil("Copier le texte corrigé", async () => {
      try {
        await navigator.clipboard.writeText(L.toutCorriger(texte, signales));
        corps.append(el("p", { classe: "discret" }, "Copié : collez-le où vous voulez (Ctrl+V)."));
      } catch (erreur) {
        corps.append(el("p", {}, "La page ne laisse pas écrire dans le presse-papiers."));
      }
    })));
  }

  // L'état et les réglages

  function mettreEtat(nouveau) {
    if (!nouveau) return;
    const avant = etat;
    etat = { ...etat, ...nouveau };
    if (avant.moteur !== "pret" && etat.moteur === "pret") {
      planifierRelecture(0);
      if (ui.barreVisible && !barre.formes.length) planifierPropositions();
    }
  }

  async function chargerMesMots() {
    try {
      mesMots = new Set(await C.mesMots());
    } catch (erreur) {
      return;                          // l'extension a été rechargée
    }
    prevoirDessin();
  }

  function mettreReglages(nouveaux) {
    const avant = reglages;
    reglages = C.reglagesComplets(nouveaux);
    if (avant.graphie !== reglages.graphie) {
      cacheRelecture.clear();          // les propositions dépendent de la graphie
      planifierPropositions();
    }
    if (!actif()) {
      ui.cacherBarre();
      ui.cacherCarte();
      if (champ) ui.effacerSoulignes(champ);
      effacerSurlignages();
      rendreCorrecteurDuNavigateur();
      return;
    }
    if (!reglages.souligner) {
      if (champ) ui.effacerSoulignes(champ);
      effacerSurlignages();
      rendreCorrecteurDuNavigateur();
    } else if (champ) {
      taireCorrecteurDuNavigateur(champ);
    }
    if (!reglages.barre) ui.cacherBarre();
    if (champ && (!avant.allume || avant.sitesExclus.length !== reglages.sitesExclus.length)) {
      planifierRelecture(0);
    }
    prevoirDessin();
  }

  chrome.storage.sync.get("reglages").then((r) => mettreReglages(r.reglages)).catch(() => {});
  chrome.storage.session.get("etat").then((r) => mettreEtat(r.etat)).catch(() => {});
  chargerMesMots();
  chrome.storage.onChanged.addListener((changements, zone) => {
    if (!monte) return;
    if (zone === "sync" && changements.reglages) mettreReglages(changements.reglages.newValue);
    if (zone === "session" && changements.etat) mettreEtat(changements.etat.newValue);
    if (zone === "local" && changements.mesMots) chargerMesMots();
  });

  // Les messages du fond : dictée, menu du clic droit, raccourcis, popup

  const COMMANDES = {
    dicter: () => basculerDictee(),
    relire: () => ouvrirRelecture(champ || dernierChamp),
    outils: () => ouvrirOutils(),
    fiche: () => ouvrirFiche(motSousLeCurseur()),
    chercher: () => ouvrirRecherche(""),
    motdujour: () => ouvrirMotDuJour(),
    lettres: () => ouvrirLettres(),
  };

  function pourCeCadre() {
    return !!(champ || (dernierChamp && dernierChamp.el.isConnected));
  }

  chrome.runtime.onMessage.addListener((m) => {
    if (!monte || !m || m.cible) return false;
    if (m.type === "dictee") {
      if (!dictee) return false;
      if (m.phase === "ecoute") {
        dictee.secondes = m.secondes;
        montrerDictee();
      } else if (m.phase === "transcription") {
        dictee.phase = "transcription";
        montrerDictee();
      } else if (m.phase === "fin") {
        finirDictee(m);
      }
      return false;
    }
    if (m.type === "menu") {
      if (m.id === "kab-relire") {
        const c = champ || dernierChamp;
        if (c && (champ || !m.selection)) ouvrirRelecture(c);
        else if (m.selection) relireLecture(m.selection);
      } else if (m.id === "kab-dicter") {
        basculerDictee();
      } else if (m.id === "kab-fiche") {
        ouvrirFiche((m.selection || "").trim().split(/\s+/u)[0] || "");
      } else if (m.id === "kab-chercher") {
        ouvrirRecherche((m.selection || "").trim());
      }
      return false;
    }
    if (m.type === "commande") {
      if (!pourCeCadre() && window !== window.top) return false;
      if (COMMANDES[m.nom]) COMMANDES[m.nom]();
      return false;
    }
    return false;
  });

  // On branche

  ui.actions = {
    choisir: (rang) => choisir(rang),
    fiche: (forme) => ouvrirFiche(forme),
    dicter: () => basculerDictee(),
    outils: () => ouvrirOutils(),
    remplacer: remplacerSouligne,
    garder,
    ajouter: async (s) => {
      ui.cacherCarte();
      await ajouterAuDictionnaire(s.mot);
      prevoirDessin();
    },
    panneauFerme: () => {
      for (const c of [champ, dernierChamp]) if (c && c.actuel) c.actuel = null;
      prevoirDessin();
    },
  };

  ecouter(document, "kab-board-releve", (e) => {
    if (e.detail !== INSTANCE) demonter();
  });
  ecouter(document, "focusin", surFocus, true);
  ecouter(document, "focusout", surPerteFocus, true);
  ecouter(document, "keydown", surTouche, true);
  ecouter(document, "beforeinput", surAvantSaisie, true);
  ecouter(document, "input", surSaisie, true);
  ecouter(document, "mouseup", surClic, true);
  ecouter(document, "selectionchange", surSelection);
  ecouter(window, "scroll", prevoirDessin, { capture: true, passive: true });
  ecouter(window, "resize", prevoirDessin, { passive: true });
  ecouter(window, "focus", chargerDisposition);
  chargerDisposition();

  // Les pages de l'extension qui portent ce script (« Écrire et relire ») ont leurs
  // propres boutons.
  globalThis.KabContenu = { commande: (nom) => COMMANDES[nom] && COMMANDES[nom]() };

  // Le script arrive parfois après le focus (une page déjà ouverte) : on prend le
  // champ actif tel qu'il est.
  const deja = K.champPour(K.elementActif(document));
  if (deja) entrerChamp(deja);
})();
