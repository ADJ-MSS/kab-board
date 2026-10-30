// Ce que l'application Android fait autour du moteur, recopié : la barre
// (ClavierKabyle.corrigerMot et predireSuite, Propositions.calculer), la casse
// (ClavierKabyle.casserComme), le jugement d'un mot pour les soulignés et « Relire »
// (CorrecteurSysteme.jugerMot), les états d'un nom pour la fiche (FicheMot.etats).

import { Completion } from "./completion.js";
import { normalize } from "./normalisation.js";
import { Prediction } from "./prediction.js";
import { distincts, estBlanc, estLettre, estMajuscule, estMinuscule, estVide, majusculeChar, rogner, rognerFin } from "./kotlin.js";

export const MAX_PROPOSITIONS = 6;
export const CONTEXTE_MAX = 60;

/** ClavierKabyle.estCaractereMot : une lettre, de n'importe quel alphabet, ou un tiret. */
export function estCaractereMot(c) {
  return estLettre(c) || c === "-";
}

/** ClavierKabyle.casserComme : la casse du mot tapé. Une casse mixte ne se reporte pas. */
export function casserComme(saisi, proposition) {
  if (!saisi || !proposition) return proposition;
  const lettres = [...saisi].filter((c) => c.length === 1 && estLettre(c));
  if (lettres.length >= 2 && lettres.every((c) => estMajuscule(c))) return proposition.toUpperCase();
  let reste = true;
  for (let i = 1; i < saisi.length; i++) if (estLettre(saisi[i]) && !estMinuscule(saisi[i])) reste = false;
  if (estMajuscule(saisi[0]) && reste) return majusculeChar(proposition[0]) + proposition.slice(1);
  return proposition;
}

/** ClavierKabyle.longueurMotsAvant. */
export function longueurMotsAvant(texteAvant, n) {
  let i = texteAvant.length;
  for (let k = 0; k < n; k++) {
    const apresBlancs = i;
    while (i > 0 && estBlanc(texteAvant[i - 1])) i--;
    if (i === apresBlancs) return -1;
    const finMot = i;
    while (i > 0 && estCaractereMot(texteAvant[i - 1])) i--;
    if (i === finMot) return -1;
  }
  return texteAvant.length - i;
}

/** Les lettres et tirets qui finissent un texte. */
function finDeMot(texte) {
  let i = texte.length;
  while (i > 0 && estCaractereMot(texte[i - 1])) i--;
  return texte.slice(i);
}

/**
 * Propositions.calculer : la correction absolue et le top-5 du mot isolé, dans la
 * graphie réglée, et le nombre de mots déjà écrits que la correction remplace aussi.
 */
export function calculer(c, graphie, gauche, mot, mode) {
  const resultat = c.corriger(`${gauche} ${mot}`);
  const t = rogner(resultat.texteCorrige);
  let absolue = t.slice(t.lastIndexOf(" ") + 1);
  let motsAvant = resultat.couvertureFin - 1;
  // Le correcteur fond le possessif avec le mot d'avant même par-dessus une virgule,
  // qu'il ne voit pas : on ne garde alors que le mot en cours.
  if (motsAvant > 0 && longueurMotsAvant(`${gauche} `, motsAvant) < 0) {
    absolue = absolue.slice(absolue.lastIndexOf("-") + 1);
    motsAvant = 0;
  }
  const derniere = resultat.annexions.filter((a) => a.idx === resultat.tokensEntree.length - 1).pop();
  const brutes = c.topCandidats(mot, 5).map((x) => x.forme);
  const absolueG = graphie.basculer(absolue, mode);
  return {
    absolue: absolueG,
    cinq: graphie.appliquer(brutes, mode),
    raison: derniere ? derniere.raison : null,
    motsAvant: estVide(absolue) ? 0 : motsAvant,
  };
}

/** ClavierKabyle.corrigerMot, la complétion prête : de 1 à 3 lettres elle répond, sinon la correction. */
export function corrigerMot(c, graphie, mot, gauche, mode) {
  const tape = normalize(mot);
  const completes = c.completion.barre(gauche, tape, MAX_PROPOSITIONS, c.modeleLangue, Completion.motDeDictionnaire(c.res));
  if (completes) {
    return {
      nature: "comp",
      formes: distincts(graphie.appliquer(completes, mode).map((f) => casserComme(mot, f))),
      motsAvant: 0,
      raison: null,
    };
  }
  const six = calculer(c, graphie, gauche, mot, mode);
  // Rattachée au mot d'avant, la tête en prend la casse.
  const modeleTete = six.motsAvant > 0 ? finDeMot(rognerFin(gauche)) : mot;
  const formes = distincts([casserComme(modeleTete, six.absolue), ...six.cinq.map((f) => casserComme(mot, f))])
    .filter((f) => !estVide(f));
  return { nature: "prop", formes, motsAvant: six.motsAvant, raison: estVide(six.absolue) ? null : six.raison };
}

/** ClavierKabyle.predireSuite : le mot suivant, quand il n'y a plus de mot en cours. */
export function predireSuite(c, graphie, gauche, mode) {
  const lm = c.modeleLangue;
  if (!lm) return [];
  return graphie.appliquer(new Prediction(lm, c.res.frequents).suivants(gauche, MAX_PROPOSITIONS), mode);
}

export const AUCUN = "aucun";
export const DOUTE = "doute";
export const FAUTE = "faute";

/** CorrecteurSysteme.verdict : souligner ce mot, et comment. */
export function verdict(mot, absolue, cinq, connu) {
  const forme = normalize(mot);
  if (absolue === forme) return AUCUN;
  // Une forme connue n'est jamais une faute ; si le contexte n'a rien pu lire, il n'y
  // a rien à départager non plus.
  if (connu) return estVide(absolue) ? AUCUN : DOUTE;
  const propositions = [absolue, ...cinq].filter((p) => !estVide(p) && p !== forme);
  return propositions.length ? FAUTE : AUCUN;
}

/** CorrecteurSysteme.mots : les mots d'un texte, avec leur début. */
export function mots(texte) {
  const trouves = [];
  let i = 0;
  while (i < texte.length) {
    if (!estCaractereMot(texte[i])) { i++; continue; }
    const debut = i;
    while (i < texte.length && estCaractereMot(texte[i])) i++;
    trouves.push([debut, texte.slice(debut, i)]);
  }
  return trouves;
}

/** CorrecteurSysteme.jugerMot : le jugement d'un mot et ses propositions. */
export function jugerMot(c, graphie, gauche, mot, nb, mode) {
  const forme = normalize(mot);
  // « Connu » au sens du pipeline lui-même, et selon ses deux niveaux : la forme de
  // confiance et la forme construite sur une racine fiable.
  const connu = c.res.fiable(forme) || c.res.valideParAffixe(forme);
  const six = calculer(c, graphie, gauche, mot, mode);
  // Une correction qui fond le mot avec le précédent ne vaut pas pour le mot seul.
  const fusion = six.motsAvant > 0 ? six.absolue : null;
  const absolue = fusion !== null ? "" : six.absolue;
  const s = verdict(mot, absolue, six.cinq, connu);
  const propositions = s === AUCUN ? [] : distincts([absolue, ...six.cinq]
    .filter((p) => !estVide(p) && p !== forme)
    .map((p) => casserComme(mot, p))).slice(0, nb);
  return { soulignement: s, propositions, fusion, motsAvant: six.motsAvant };
}

/** Les catégories du lexique que Postprocess traite en noms. */
const NOMINALES = new Set(["masc", "fem", "fem_pl", "adj_masc", "adj_fem", "ambig"]);

/** FicheMot.etats : les deux états d'un nom, ou null si la forme n'en a pas. */
export function etats(post, forme, estVerbe, categorie) {
  if (estVerbe) return null;
  if (categorie !== null && !NOMINALES.has(categorie)) return null;
  let [estNom, etat] = post.identifierNomEtat(forme);
  if (categorie !== null) {
    estNom = true;
    if (etat === "invariable") etat = "libre";
  }
  if (!estNom || etat === null || etat === "invariable") return null;
  const libre = etat === "libre" ? forme : post.versLibre(forme);
  const annexion = etat === "annexion" ? forme : post.versAnnexion(forme);
  return libre === annexion ? null : { libre, annexion };
}

/** FicheMot.gloseCourte : le premier segment d'une glose, coupé à max caractères. */
export function gloseCourte(glose, max = 48) {
  const premier = rogner(glose.split(/[;‖]/)[0]);
  return premier.length <= max ? premier : rognerFin(premier.slice(0, max - 1)) + "…";
}
