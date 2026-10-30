// Ce que le moteur Kotlin tient de la bibliothèque standard, à l'identique : les blancs,
// les lettres, la casse d'un caractère, les tris stables, String.hashCode. Les chaînes
// se comparent comme en Kotlin, unité UTF-16 par unité UTF-16.

const BLANC = /^[\t\n\v\f\r\x1c-\x1f\p{Zs}\p{Zl}\p{Zp}]$/u;
const LETTRE = /^\p{L}$/u;
const LETTRE_OU_CHIFFRE = /^[\p{L}\p{Nd}]$/u;

/** Char.isWhitespace. */
export function estBlanc(c) {
  return BLANC.test(c);
}

/** Char.isLetter. */
export function estLettre(c) {
  return LETTRE.test(c);
}

/** Char.isLetterOrDigit. */
export function estLettreOuChiffre(c) {
  return LETTRE_OU_CHIFFRE.test(c);
}

/** String.trim(). */
export function rogner(s) {
  let d = 0;
  let f = s.length;
  while (d < f && estBlanc(s[d])) d++;
  while (f > d && estBlanc(s[f - 1])) f--;
  return s.slice(d, f);
}

/** String.trimEnd(). */
export function rognerFin(s) {
  let f = s.length;
  while (f > 0 && estBlanc(s[f - 1])) f--;
  return s.slice(0, f);
}

/** String.isBlank(). */
export function estVide(s) {
  for (const c of s) if (!estBlanc(c)) return false;
  return true;
}

/** String.takeLast(n), en unités UTF-16. */
export function derniers(s, n) {
  return n >= s.length ? s : s.slice(s.length - n);
}

/** Char.uppercaseChar() : un caractère pour un caractère. */
export function majusculeChar(c) {
  const m = c.toUpperCase();
  return m.length === 1 ? m : c;
}

/** Char.lowercaseChar(). */
export function minusculeChar(c) {
  const m = c.toLowerCase();
  return m.length === 1 ? m : c;
}

/** Char.isUpperCase() : une majuscule, au sens de Character.isUpperCase. */
export function estMajuscule(c) {
  return /^\p{Uppercase}$/u.test(c);
}

/** Char.isLowerCase(). */
export function estMinuscule(c) {
  return /^\p{Lowercase}$/u.test(c);
}

/** String.hashCode() de Java. */
export function hashCode(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) | 0;
  return h;
}

/** Double.compare : -0.0 avant 0.0, NaN après tout. */
export function comparerDouble(a, b) {
  if (a < b) return -1;
  if (a > b) return 1;
  if (a === b) {
    if (a !== 0) return 0;
    const na = Object.is(a, -0);
    const nb = Object.is(b, -0);
    return na === nb ? 0 : na ? -1 : 1;
  }
  const naA = Number.isNaN(a);
  const naB = Number.isNaN(b);
  return naA === naB ? 0 : naA ? 1 : -1;
}

/** compareTo de deux chaînes. */
export function comparerChaines(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** sortedByDescending, stable, sur une clé numérique. */
export function trierDecroissant(liste, cle) {
  return liste.slice().sort((x, y) => comparerDouble(cle(y), cle(x)));
}

/** distinct(), dans l'ordre. */
export function distincts(liste) {
  return [...new Set(liste)];
}

/** Math.floorMod. */
export function floorMod(a, n) {
  return ((a % n) + n) % n;
}

// Math.log10 tel que le calcule le téléphone : bionic, la libm d'Android, le tient de
// FreeBSD (e_log10.c, réécrit en 2013), comme musl. Celui de V8 (et de StrictMath) est
// le fdlibm d'origine, qui en diffère au dernier bit pour un argument sur cinquante
// environ. Recopié de musl (src/math/log10.c), opération par opération.
const IVLN10HI = 4.34294481878168880939e-01;
const IVLN10LO = 2.50829467116452752298e-11;
const LOG10_2HI = 3.01029995663611771306e-01;
const LOG10_2LO = 3.69423907715893078616e-13;
const LG1 = 6.666666666666735130e-01;
const LG2 = 3.999999999940941908e-01;
const LG3 = 2.857142874366239149e-01;
const LG4 = 2.222219843214978396e-01;
const LG5 = 1.818357216161805012e-01;
const LG6 = 1.531383769920937332e-01;
const LG7 = 1.479819860511658591e-01;
const MOT = new Float64Array(1);
const MOITIES = new Uint32Array(MOT.buffer);   // [bas, haut], petit-boutiste

export function log10(x) {
  MOT[0] = x;
  let hx = MOITIES[1];
  let k = 0;
  if (hx < 0x00100000 || hx >>> 31) {
    if (MOITIES[0] === 0 && (hx & 0x7fffffff) === 0) return -1 / (x * x);
    if (hx >>> 31) return (x - x) / 0.0;
    // sous-normal : on le remonte
    k -= 54;
    x *= 18014398509481984;   // 2^54
    MOT[0] = x;
    hx = MOITIES[1];
  } else if (hx >= 0x7ff00000) {
    return x;
  } else if (hx === 0x3ff00000 && MOITIES[0] === 0) {
    return 0;
  }

  // ramène x dans [sqrt(2)/2, sqrt(2)]
  hx = (hx + (0x3ff00000 - 0x3fe6a09e)) >>> 0;
  k += (hx >>> 20) - 0x3ff;
  hx = ((hx & 0x000fffff) + 0x3fe6a09e) >>> 0;
  MOITIES[1] = hx;
  x = MOT[0];

  const f = x - 1.0;
  const hfsq = 0.5 * f * f;
  const s = f / (2.0 + f);
  const z = s * s;
  let w = z * z;
  const t1 = w * (LG2 + w * (LG4 + w * LG6));
  const t2 = z * (LG1 + w * (LG3 + w * (LG5 + w * LG7)));
  const R = t2 + t1;

  let hi = f - hfsq;
  MOT[0] = hi;
  MOITIES[0] = 0;
  hi = MOT[0];
  const lo = f - hi - hfsq + s * (hfsq + R);

  let valHi = hi * IVLN10HI;
  const dk = k;
  const y = dk * LOG10_2HI;
  let valLo = dk * LOG10_2LO + (lo + hi) * IVLN10LO + lo * IVLN10HI;

  w = y + valHi;
  valLo += (y - w) + valHi;
  valHi = w;
  return valLo + valHi;
}
