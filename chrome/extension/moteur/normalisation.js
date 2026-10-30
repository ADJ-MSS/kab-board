// Normalisation.kt : la forme normale d'un mot, les jetons d'une phrase, les clitiques.

import { majusculeChar, minusculeChar, rogner } from "./kotlin.js";

// L'ordre compte : chaque remplacement voit le résultat du précédent.
const NORM_TABLE = [
  ["gh", "ɣ"], ["aa", "ɛ"], ["ou", "u"], ["dh", "ḍ"],
  ["th", "t"], ["kh", "x"], ["ch", "c"],
];

// Géminées d'abord, sinon le remplacement est partiel.
const LABIALISEES = [
  ["ggʷ", "ww"], ["bbʷ", "ww"], ["ppʷ", "ww"],
  ["gʷ", "g"], ["bʷ", "b"], ["pʷ", "p"],
];

// TOKEN_RE, [a-zàâæçéèêëîïôœùûüÿɣɛḍṭxṛṣẓčšžɣḥǧ'\-]+ sans casse, comme Java avec
// CASE_INSENSITIVE et UNICODE_CASE : un caractère va s'il est de la classe, ou si la
// minuscule de sa majuscule en est.
const CLASSE = new Set("àâæçéèêëîïôœùûüÿɣɛḍṭxṛṣẓčšžɣḥǧ'-");
function dansLaClasse(c) {
  return (c >= "a" && c <= "z") || CLASSE.has(c);
}
function caractereDeJeton(c) {
  if (dansLaClasse(c)) return true;
  const m = majusculeChar(c);
  return (m >= "a" && m <= "z") || dansLaClasse(minusculeChar(m));
}

export const PARTICULES = new Set(["n", "d", "i", "g", "s", "w"]);
const UN_CHAR_GARDES = new Set([...PARTICULES, "ɣ"]);

export const POSSESSIFS = new Set(["iw", "ik", "im", "is", "nneɣ", "nwen", "nkent", "nsen", "nsent"]);

export const CLITIQUES_SUFF = new Set([...POSSESSIFS,
  "d",
  "yas", "yasen", "yasent",
  "yi",
  "ak", "am",
  "nni", "ni"]);

export const PREFIXES_DIRECTIONNELS = new Set(["d", "as", "aɣ", "iyi", "ak", "am", "ay"]);

export function normalize(t) {
  let s = rogner(t.toLowerCase()).normalize("NFC");
  for (const [k, v] of LABIALISEES) s = s.replaceAll(k, v);
  for (const [k, v] of NORM_TABLE) s = s.replaceAll(k, v);
  return s;
}

export function tokenize(t) {
  const s = normalize(t);
  const jetons = [];
  let i = 0;
  while (i < s.length) {
    if (!caractereDeJeton(s[i])) { i++; continue; }
    const debut = i;
    while (i < s.length && caractereDeJeton(s[i])) i++;
    const j = s.slice(debut, i);
    if (j.length >= 2 || UN_CHAR_GARDES.has(j)) jetons.push(j);
  }
  return jetons;
}

/** [préfixe, base, suffixe], tiret compris. */
export function detacherClitique(tok) {
  const pos = tok.lastIndexOf("-");
  if (pos > 1) {
    const base = tok.slice(0, pos);
    const suf = tok.slice(pos + 1);
    if (CLITIQUES_SUFF.has(suf)) return ["", base, "-" + suf];
  }
  if (tok.split("-").length === 2) {
    const i = tok.indexOf("-");
    const pref = tok.slice(0, i);
    const base = tok.slice(i + 1);
    if (PREFIXES_DIRECTIONNELS.has(pref) && base.length >= 2) return [pref + "-", base, ""];
  }
  return ["", tok, ""];
}

export function rejoindrePossessifs(tokens) {
  return rejoindrePossessifsPortees(tokens).map((p) => p[0]);
}

/** Les mêmes formes, chacune avec le nombre de jetons d'entrée qu'elle recouvre. */
export function rejoindrePossessifsPortees(tokens) {
  const out = [];
  tokens.forEach((tok, i) => {
    if (i > 0 && POSSESSIFS.has(tok) && out.length) {
      const [forme, n] = out[out.length - 1];
      out[out.length - 1] = [`${forme}-${tok}`, n + 1];
    } else out.push([tok, 1]);
  });
  return out;
}
