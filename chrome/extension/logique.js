/*
 * La frappe kabyle, sans rien du navigateur : ce qui décide est ici, et se teste
 * sous Node (chrome/tests/logique.test.mjs).
 *
 * Les règles sont celles du clavier Android de kab-board (ClavierKabyle.kt,
 * EcritureParlee.kt), à la lettre : le mot sous le curseur et son contexte, les
 * cinq digrammes d'« écrire comme on parle », le choix d'une proposition et
 * l'espace qui la suit, le possessif rattaché (« tamurt iw » → « tamurt-iw »)
 * jamais par-dessus une virgule. S'y ajoutent ce que permet un clavier physique :
 * AltGr + la lettre latine, et les chiffres qui choisissent. Rien n'est corrigé
 * d'office, sauf si l'on allume la correction automatique : elle ne touche alors
 * qu'aux mots que le correcteur ne connaît pas.
 *
 * Toutes les positions sont celles d'une chaîne JavaScript (unités UTF-16) ;
 * le pont convertit celles du correcteur.
 */
(function (racine, fabrique) {
  if (typeof module === "object" && module.exports) {
    module.exports = fabrique();
  } else {
    racine.KabLogique = fabrique();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // « Écrire comme on parle », les cinq conversions du clavier Android.
  const DIGRAMMES = { gh: "ɣ", dh: "ḍ", kh: "x", aa: "ɛ", ou: "u" };

  // Accès direct, pour qui connaît son clavier : AltGr + la lettre latine.
  const ALTGR = {
    g: "ɣ", e: "ɛ", d: "ḍ", h: "ḥ", t: "ṭ", z: "ẓ",
    s: "ṣ", c: "č", j: "ǧ", r: "ṛ",
  };

  const KABYLES = ["ɣ", "ɛ", "ḍ", "ḥ", "ṭ", "ẓ", "ṣ", "č", "ǧ", "ṛ"];

  const NB_PROPOSITIONS = 6;
  const CONTEXTE_MAX = 60;      // ce que voit le correcteur, comme la barre d'Android
  const REGARD = 64;            // ClavierKabyle.REGARD : où l'on cherche le mot autour du curseur
  const AVANT = 80;             // ClavierKabyle.contexteGauche : ce qu'on lit avant le curseur
  const RELIRE_MORCEAU = 600;   // caractères au plus par relecture : une phrase, d'ordinaire

  // Les trois natures, comme sur le téléphone : vert pour la correction en
  // contexte, bleu pour un candidat, ocre pour une prédiction ou une complétion.
  const VERT = "#00843F";
  const BLEU = "#0072BB";
  const OCRE = "#A86A00";

  const UNE_LETTRE = /\p{L}/u;
  // Char.isWhitespace de Kotlin : un peu plus que \s (les blancs de contrôle), un peu
  // moins (pas U+FEFF).
  const BLANC = /^[\t\n\v\f\r\x1c-\x1f\p{Zs}\p{Zl}\p{Zp}]$/u;

  function estBlanc(c) {
    return BLANC.test(c);
  }

  /** String.trim() de Kotlin. */
  function rogner(texte) {
    let debut = 0;
    let fin = texte.length;
    while (debut < fin && estBlanc(texte[debut])) debut++;
    while (fin > debut && estBlanc(texte[fin - 1])) fin--;
    return texte.slice(debut, fin);
  }

  /** Le contexte d'un mot, ce qui le précède rogné, ses 60 dernières unités : comme
   * contexteGauche et CorrecteurSysteme, emoji compris. */
  function gaucheDe(texteAvant) {
    return rogner(texteAvant).slice(-CONTEXTE_MAX);
  }

  /**
   * Ce qu'il faut envoyer du texte qui précède un morceau pour que le service, qui
   * prend le contexte de chaque mot dans avant + morceau, trouve exactement celui
   * qu'il aurait pris dans tout le texte (les 60 dernières unités, rognées), et les
   * mots qu'une correction rattache (« tamurt » de « tamurt iw », coupés par la fin
   * du morceau d'avant) : au moins 60 unités avant les blancs de la fin, depuis le
   * début d'un mot. C'est aussi ce qui distingue deux morceaux en cache.
   */
  function avantUtile(avant) {
    let fin = avant.length;
    while (fin > 0 && estBlanc(avant[fin - 1])) fin--;
    let debut = 0;
    while (debut < fin && estBlanc(avant[debut])) debut++;
    let i = Math.max(debut, fin - CONTEXTE_MAX);
    while (i > debut && estBlanc(avant[i])) i--;
    while (i > debut && estLettre(avant[i]) && estLettre(avant[i - 1])) i--;
    if (i > debut && /[\udc00-\udfff]/.test(avant[i])) i--;
    return avant.slice(i);
  }

  /** ClavierKabyle.estCaractereMot : une lettre, de n'importe quel alphabet, ou un tiret. */
  function estLettre(c) {
    return typeof c === "string" && c.length > 0 && (UNE_LETTRE.test(c) || c === "-");
  }

  function estMajuscule(c) {
    return c !== c.toLowerCase() && c === c.toUpperCase();
  }

  /** Ce qui finit un mot pour la correction automatique : un blanc ou une
   * ponctuation. Pas un chiffre, ni une apostrophe. */
  function finitUnMot(c) {
    return /^[\s.,;:!?…)\]»"”]$/u.test(c);
  }

  /** La lettre que donnent deux lettres tapées l'une après l'autre, ou null. */
  function convertir(precedente, lettre) {
    const remplace = DIGRAMMES[(precedente + lettre).toLowerCase()];
    if (!remplace) return null;
    return estMajuscule(precedente[0]) ? remplace.toUpperCase() : remplace;
  }

  /** AltGr + une lettre latine : la lettre kabyle, ou null. */
  function altgr(base, majuscule) {
    const lettre = ALTGR[(base || "").toLowerCase()];
    if (!lettre) return null;
    return majuscule ? lettre.toUpperCase() : lettre;
  }

  /**
   * Le mot sous le curseur et son contexte, comme ClavierKabyle : le mot (motCourant,
   * les lettres juste avant le curseur, même au milieu d'un mot), ce qui le suit
   * (finApres), et le contexte du correcteur (contexteGauche : les 80 caractères
   * avant le curseur, sans le mot, rognés, les 60 derniers).
   */
  function etat(texte, curseur) {
    const regard = texte.slice(Math.max(0, curseur - REGARD), curseur);
    let i = regard.length;
    while (i > 0 && estLettre(regard[i - 1])) i--;
    const mot = regard.slice(i);
    const apres = texte.slice(curseur, curseur + REGARD);
    let finApres = 0;
    while (finApres < apres.length && estLettre(apres[finApres])) finApres++;
    const avant = texte.slice(Math.max(0, curseur - AVANT), curseur);
    const gauche = gaucheDe(avant.slice(0, avant.length - mot.length));
    return { mot, debut: curseur - mot.length, fin: curseur, finApres, gauche };
  }

  /** Le mot en cours, ou null s'il n'y en a pas. */
  function motEnCours(texte, curseur) {
    const e = etat(texte, curseur);
    return e.mot ? e : null;
  }

  /**
   * Longueur des n mots qui terminent texteAvant, blancs qui les suivent compris :
   * ce qu'il faut effacer en plus du mot en cours quand une proposition le
   * rattache aux mots précédents. -1 si ces mots ne sont pas là, ou pas séparés
   * par de simples blancs. Même règle que saisie.longueur_mots_avant.
   */
  function longueurMotsAvant(texteAvant, n) {
    let i = texteAvant.length;
    for (let k = 0; k < n; k++) {
      const apresBlancs = i;
      while (i > 0 && estBlanc(texteAvant[i - 1])) i--;
      if (i === apresBlancs) return -1;
      const finMot = i;
      while (i > 0 && (UNE_LETTRE.test(texteAvant[i - 1]) || texteAvant[i - 1] === "-")) i--;
      if (i === finMot) return -1;
    }
    return texteAvant.length - i;
  }

  /**
   * Ce que fait le choix d'une proposition, comme ClavierKabyle.appliquerChoix :
   * remplacer [debut, fin) par texte, le curseur après. La forme remplace le mot
   * sous le curseur, lettres d'après comprises ; motsAvant, le nombre de mots
   * d'avant que la tête rattache (« tamurt iw » → « tamurt-iw »), jamais par-dessus
   * une virgule. Une prédiction s'insère au curseur. Une espace suit, sauf si un
   * blanc vient déjà après.
   */
  function choix(texte, curseur, forme, motsAvant) {
    const e = etat(texte, curseur);
    const avant = texte.slice(Math.max(0, curseur - REGARD), curseur);
    const enPlus = motsAvant > 0
      ? Math.max(0, longueurMotsAvant(avant.slice(0, avant.length - e.mot.length), motsAvant)) : 0;
    const apres = texte.slice(curseur, curseur + REGARD);
    let debut = curseur;
    let fin = curseur;
    if (e.mot || enPlus > 0) {
      debut = curseur - e.mot.length - enPlus;
      fin = curseur + e.finApres;
    }
    const suite = apres.slice(e.finApres);
    const insere = forme + (suite === "" || !estBlanc(suite[0]) ? " " : "");
    return { debut, fin, texte: insere, curseurApres: debut + insere.length };
  }

  /** Le chiffre tapé choisit-il une proposition ? Son rang, ou -1. */
  function rangDuChiffre(touche, propositions, nature, enCours) {
    if (!/^[1-6]$/.test(touche) || !enCours) return -1;
    if (nature !== "prop" && nature !== "comp") return -1;
    const rang = Number(touche) - 1;
    return rang < propositions.length ? rang : -1;
  }

  function couleur(nature, rang) {
    if (nature === "pred" || nature === "comp") return OCRE;
    return rang === 0 ? VERT : BLEU;
  }

  /** La couleur d'un souligné : rouge pour une faute (un mot inconnu), bleu pour un
   * doute (un mot connu que le contexte écrirait autrement), comme sous Android. */
  const ROUGE = "#D32F2F";
  function couleurSouligne(soulignement) {
    return soulignement === "doute" ? BLEU : ROUGE;
  }

  function debutDePhrase(contexte) {
    const avant = contexte.replace(/\s+$/u, "");
    return avant === "" || /[.!?…:;«"“]$/u.test(avant);
  }

  /**
   * La correction automatique, quand on l'a allumée : la forme qui remplace le mot
   * qui vient de finir, ou null. Prudente : seulement une correction en contexte
   * (pas une complétion), seulement si le mot tapé n'est pas lui-même un mot que
   * le correcteur connaît (il figurerait parmi ses candidats), jamais un sigle,
   * un nom propre au milieu d'une phrase, un mot de « mon dictionnaire » ou un mot
   * que l'on a déjà gardé.
   */
  function autocorrection(mot, contexte, reponse, gardes) {
    if (!reponse || reponse.nature !== "prop" || reponse.mots_avant) return null;
    const formes = reponse.formes || [];
    const tete = formes[0];
    if (!tete || mot.length < 2 || !UNE_LETTRE.test(mot)) return null;
    const bas = mot.toLowerCase();
    if (gardes && gardes.has(bas)) return null;
    if (formes.some((f) => f.toLowerCase() === bas)) return null;
    if (mot.length > 1 && mot === mot.toUpperCase() && bas !== mot) return null;
    if (estMajuscule(mot[0]) && !debutDePhrase(contexte)) return null;
    if (/\s/.test(tete)) return null;
    return tete;
  }

  /**
   * Le texte d'un champ, en morceaux à relire : une phrase chacun, et une phrase
   * trop longue coupée à une espace. Le correcteur relit chacun avec le contexte
   * qu'il contient ; une phrase qui n'a pas changé ne se relit pas, si bien que
   * l'on ne relit, en écrivant, que la phrase où l'on écrit.
   */
  function morceaux(texte, taille) {
    const max = taille || RELIRE_MORCEAU;
    const sortie = [];
    const pousser = (debut, morceau) => {
      if (UNE_LETTRE.test(morceau)) sortie.push({ debut, texte: morceau });
    };
    let debutLigne = 0;
    for (const ligne of texte.split("\n")) {
      const fins = /[.!?…]+[\s\u00a0]+/gu;
      let debutPhrase = 0;
      let m;
      const phrases = [];
      while ((m = fins.exec(ligne)) !== null) {
        phrases.push([debutPhrase, m.index + m[0].length]);
        debutPhrase = m.index + m[0].length;
      }
      if (debutPhrase < ligne.length) phrases.push([debutPhrase, ligne.length]);
      for (const [d, f] of phrases) {
        let reste = d;
        while (f - reste > max) {
          let coupe = ligne.lastIndexOf(" ", reste + max) + 1;
          if (coupe <= reste) coupe = reste + max;
          pousser(debutLigne + reste, ligne.slice(reste, coupe));
          reste = coupe;
        }
        pousser(debutLigne + reste, ligne.slice(reste, f));
      }
      debutLigne += ligne.length + 1;
    }
    return sortie;
  }

  /**
   * Remplace chaque mot signalé par sa première proposition : le « tout
   * corriger » de la relecture. Les signalés sont triés et ne se chevauchent pas.
   */
  function toutCorriger(texte, signales) {
    let sortie = texte;
    for (const s of [...signales].sort((a, b) => b.debut - a.debut)) {
      if (!s.propositions || !s.propositions.length) continue;
      if (sortie.slice(s.debut, s.fin) !== s.mot) continue;
      sortie = sortie.slice(0, s.debut) + s.propositions[0] + sortie.slice(s.fin);
    }
    return sortie;
  }

  /**
   * Ramène un enregistrement au taux du modèle vocal (16 kHz) : un filtre
   * passe-bas à sinus cardinal fenêtré (Blackman) puis l'interpolation. Sans
   * filtre, le haut du spectre (les sifflantes, le souffle) se replierait sur la
   * voix.
   */
  function reechantillonner(donnees, tauxSource, tauxCible) {
    if (tauxSource === tauxCible) return Float32Array.from(donnees);
    const rapport = tauxSource / tauxCible;
    const n = Math.floor(donnees.length / rapport);
    const sortie = new Float32Array(n);
    const coupure = 0.45 / Math.max(rapport, 1);   // en fraction du taux source
    const demi = Math.ceil(16 * Math.max(rapport, 1));
    // Le noyau, calculé une fois sur une grille fine : trente secondes à 48 kHz
    // se filtrent en une fraction de seconde.
    const finesse = 256;
    const noyau = new Float32Array(2 * demi * finesse + 1);
    for (let k = 0; k < noyau.length; k++) {
      const t = k / finesse - demi;
      const x = 2 * coupure * t;
      const sinc = x === 0 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x);
      noyau[k] = sinc * (0.42 + 0.5 * Math.cos(Math.PI * t / demi) +
        0.08 * Math.cos(2 * Math.PI * t / demi));
    }
    for (let i = 0; i < n; i++) {
      const centre = i * rapport;
      const premier = Math.max(0, Math.ceil(centre - demi));
      const dernier = Math.min(donnees.length - 1, Math.floor(centre + demi));
      let somme = 0;
      let poids = 0;
      for (let j = premier; j <= dernier; j++) {
        const h = noyau[Math.round((j - centre + demi) * finesse)];
        somme += donnees[j] * h;
        poids += h;
      }
      sortie[i] = poids ? somme / poids : 0;
    }
    return sortie;
  }

  /**
   * Un champ où l'on ne propose rien et n'écoute rien : un mot de passe (même
   * rendu visible), un code à usage unique, une carte bancaire. Comme
   * ChampSensible sur Android.
   */
  function champSensible(type, autocomplete) {
    const t = (type || "").toLowerCase();
    if (t === "password") return true;
    const jetons = (autocomplete || "").toLowerCase().split(/\s+/);
    return jetons.some((j) => j === "current-password" || j === "new-password" ||
      j === "one-time-code" || j.startsWith("cc-"));
  }

  /** Les champs <input> où l'on écrit des phrases. */
  function typeEcrit(type) {
    const t = (type || "text").toLowerCase();
    return t === "text" || t === "search" || t === "";
  }

  /**
   * « Écrire comme on parle » dans un champ de nos propres pages (la recherche
   * d'Asegzawal, du français au kabyle) : le script de contenu ne s'y applique
   * pas. Mêmes règles : deux lettres tapées l'une après l'autre, et un effacement
   * juste après défait la conversion.
   */
  function brancherSaisie(champ, actif) {
    let precedente = null;
    let conversion = null;
    champ.addEventListener("beforeinput", (e) => {
      if (e.isComposing) return;
      const d = champ.selectionStart;
      if (d === null || d !== champ.selectionEnd) return;
      if (e.inputType === "insertText" && e.data && e.data.length === 1) {
        if ((!actif || actif()) && precedente && precedente.pos === d &&
            champ.value[d - 1] === precedente.lettre) {
          const conv = convertir(precedente.lettre, e.data);
          if (conv) {
            e.preventDefault();
            champ.setRangeText(conv, d - 1, d, "end");
            conversion = { pos: d - 1 + conv.length, avant: precedente.lettre + e.data, apres: conv };
            precedente = null;
            champ.dispatchEvent(new Event("input", { bubbles: true }));
          }
        }
      } else if (e.inputType === "deleteContentBackward" && conversion && d === conversion.pos &&
          champ.value.slice(d - conversion.apres.length, d) === conversion.apres) {
        e.preventDefault();
        champ.setRangeText(conversion.avant, d - conversion.apres.length, d, "end");
        precedente = { pos: champ.selectionStart, lettre: conversion.avant.slice(-1) };
        conversion = null;
        champ.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
    champ.addEventListener("input", (e) => {
      if (!e.isTrusted) return;
      if (e.inputType === "insertText" && e.data && e.data.length === 1 && estLettre(e.data)) {
        precedente = { pos: champ.selectionStart, lettre: e.data };
      } else {
        precedente = null;
      }
      conversion = null;
    });
  }

  return {
    DIGRAMMES, ALTGR, KABYLES, NB_PROPOSITIONS, CONTEXTE_MAX, RELIRE_MORCEAU, AVANT,
    VERT, BLEU, OCRE, ROUGE,
    estLettre, estBlanc, rogner, gaucheDe, avantUtile, finitUnMot, convertir, altgr, etat,
    motEnCours, longueurMotsAvant,
    choix, rangDuChiffre, couleur, couleurSouligne, autocorrection, morceaux, toutCorriger,
    reechantillonner, champSensible, typeEcrit, brancherSaisie,
  };
});
