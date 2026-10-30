// Phonologie.kt : la distance kabyle pondérée et le code sonore.

import { majusculeChar } from "./kotlin.js";

const VOYELLES = new Set(["a", "e", "i", "o", "u"]);

const PAIRES = [
  // Diacritiques : la faute numéro un, sur un clavier sans ces lettres
  ["t", "ṭ", 0.25], ["d", "ḍ", 0.25], ["s", "ṣ", 0.25],
  ["z", "ẓ", 0.25], ["r", "ṛ", 0.25], ["h", "ḥ", 0.25],
  ["c", "č", 0.30], ["g", "ǧ", 0.35], ["s", "š", 0.35],
  ["c", "š", 0.40], ["z", "ž", 0.35],
  // Gutturales et vélaires proches
  ["x", "ɣ", 0.50], ["h", "ɛ", 0.60], ["ḥ", "ɛ", 0.60],
  ["q", "ɣ", 0.60], ["k", "g", 0.50], ["g", "q", 0.50],
  ["k", "q", 0.50],
  // Sourde, voisée
  ["t", "d", 0.60], ["s", "z", 0.60], ["f", "b", 0.65],
  // Semi-voyelles
  ["i", "y", 0.30], ["u", "w", 0.30],
  // Voyelles, schwa instable en kabyle
  ["a", "e", 0.35], ["e", "i", 0.40], ["e", "u", 0.45],
  ["a", "i", 0.50], ["a", "u", 0.55], ["i", "u", 0.50],
  ["o", "u", 0.30],
];

const CONF = new Map();
for (const [a, b, v] of PAIRES) {
  CONF.set(a + b, v);
  CONF.set(b + a, v);
}

const COUT_TRANSPOSITION = 0.60;

function coutSub(a, b) {
  if (a === b) return 0.0;
  const c = CONF.get(a + b);
  if (c !== undefined) return c;
  if (VOYELLES.has(a) && VOYELLES.has(b)) return 0.50;
  return 1.0;
}

function coutIndel(ch, geminee) {
  if (geminee) return 0.25;          // tt, t : gémination instable
  if (ch === "e") return 0.30;       // schwa épenthétique
  if (VOYELLES.has(ch)) return 0.55;
  return 1.0;
}

const TABLE = new Map();
for (const [lettres, code] of [["pb", "1"], ["tṭ", "2"], ["dḍ", "3"], ["kgq", "4"], ["f", "5"],
  ["sṣš", "6"], ["zẓǧčcj", "7"], ["xγhḥɛ", "8"], ["lṛr", "9"], ["mn", "0"]]) {
  for (const c of lettres) TABLE.set(c, code);
}

const REPETE = /(.)\1+/gu;

export const Phonologie = {
  /** Damerau-Levenshtein pondérée par les confusions kabyles. */
  distanceKabyle(sa, sb) {
    if (sa === sb) return 0.0;
    const a = sa;
    const b = sb;
    const la = a.length;
    const lb = b.length;
    if (la === 0 || lb === 0) return Math.max(la, lb);

    const d = Array.from({ length: la + 1 }, () => new Float64Array(lb + 1));
    for (let i = 1; i <= la; i++) {
      const gem = (i >= 2 && a[i - 2] === a[i - 1]) || (i < la && a[i] === a[i - 1]);
      d[i][0] = d[i - 1][0] + coutIndel(a[i - 1], gem);
    }
    for (let j = 1; j <= lb; j++) {
      const gem = (j >= 2 && b[j - 2] === b[j - 1]) || (j < lb && b[j] === b[j - 1]);
      d[0][j] = d[0][j - 1] + coutIndel(b[j - 1], gem);
    }
    for (let i = 1; i <= la; i++) {
      const ca = a[i - 1];
      const gemA = (i >= 2 && a[i - 2] === ca) || (i < la && a[i] === ca);
      for (let j = 1; j <= lb; j++) {
        const cb = b[j - 1];
        const gemB = (j >= 2 && b[j - 2] === cb) || (j < lb && b[j] === cb);
        let cout = Math.min(
          d[i - 1][j] + coutIndel(ca, gemA),
          d[i][j - 1] + coutIndel(cb, gemB),
          d[i - 1][j - 1] + coutSub(ca, cb));
        if (i > 1 && j > 1 && ca === b[j - 2] && a[i - 2] === cb && ca !== cb) {
          cout = Math.min(cout, d[i - 2][j - 2] + COUT_TRANSPOSITION);
        }
        d[i][j] = cout;
      }
    }
    return d[la][lb];
  },

  /** Code sonore kabyle, table Izemrane (URNOP 2016). */
  soundexKabyle(motIn, longueur = 5) {
    if (!motIn) return "";
    let mot = motIn.toLowerCase();
    // Alignés sur NORM_TABLE, sinon le code dépend de si le mot est normalisé
    mot = mot.replaceAll("gh", "γ").replaceAll("ɣ", "γ")
      .replaceAll("kh", "x").replaceAll("ch", "c").replaceAll("dj", "ǧ");
    mot = mot.replace(REPETE, "$1");

    let sb = majusculeChar(mot[0]);
    let precedent = " ";
    for (let k = 1; k < mot.length; k++) {
      const c = mot[k];
      if ("aeiouwy".includes(c)) { precedent = " "; continue; }
      const code = TABLE.get(c) ?? " ";
      if (code !== " " && code !== precedent) sb += code;
      precedent = code;
    }
    while (sb.length < longueur) sb += "0";
    return sb.slice(0, longueur);
  },
};
