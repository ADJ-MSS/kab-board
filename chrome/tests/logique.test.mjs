// La logique de l'extension, sans navigateur : node --test chrome/tests
//
// Les cas viennent des vérifications de kab-board (moteur/test_saisie.py) : les
// mêmes règles doivent donner les mêmes résultats dans Chrome.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const L = require("../extension/logique.js");

/** Tape un mot lettre à lettre, comme le fait le script de contenu. */
function taper(mot, translitteration = true) {
  let texte = "";
  let precedente = null;   // la lettre tapée juste avant, si rien n'est venu entre
  for (const c of mot) {
    const conv = translitteration && precedente !== null ? L.convertir(precedente, c) : null;
    if (conv) {
      texte = texte.slice(0, -1) + conv;
      precedente = null;
    } else {
      texte += c;
      precedente = L.estLettre(c) ? c : null;
    }
  }
  return texte;
}

test("les lettres kabyles sur un clavier physique", () => {
  assert.equal(taper("ruhagh"), "ruhaɣ");
  assert.equal(taper("adhar"), "aḍar");
  assert.equal(taper("khedmegh"), "xedmeɣ");
  assert.equal(taper("laada"), "lɛda");
  assert.equal(taper("aourar"), "aurar");
  assert.equal(taper("Ghef"), "Ɣef");
  assert.equal(taper("GH"), "Ɣ");
  assert.equal(taper("ruhagh", false), "ruhagh");
});

test("une lettre convertie ne se reconvertit pas", () => {
  assert.equal(taper("ghh"), "ɣh");
  assert.equal(taper("aaa"), "ɛa");
  assert.equal(taper("ouu"), "uu");
});

test("AltGr", () => {
  assert.equal(L.altgr("g", false), "ɣ");
  assert.equal(L.altgr("G", false), "ɣ");
  assert.equal(L.altgr("e", true), "Ɛ");
  assert.equal(L.altgr("q", false), null);
  for (const [latine, kabyle] of Object.entries(L.ALTGR)) {
    assert.equal(L.altgr(latine, false), kabyle);
  }
});

test("ce qui est une lettre : ClavierKabyle.estCaractereMot", () => {
  assert.equal(L.estLettre("ɣ"), true);
  assert.equal(L.estLettre("Ɣ"), true);
  assert.equal(L.estLettre("Ḍ"), true);
  assert.equal(L.estLettre("-"), true);
  assert.equal(L.estLettre("é"), true, "toute lettre, comme Char.isLetter");
  assert.equal(L.estLettre("ⵣ"), true);
  assert.equal(L.estLettre(" "), false);
  assert.equal(L.estLettre("."), false);
  assert.equal(L.estLettre("'"), false);
  assert.equal(L.estLettre("1"), false);
  assert.equal(L.estLettre(""), false);
  assert.equal(L.estLettre(undefined), false);
});

test("ce qui finit un mot pour la correction automatique", () => {
  for (const c of [" ", "\n", "\u00a0", ".", ",", ";", ":", "!", "?", "…", ")", "»", "\""]) {
    assert.equal(L.finitUnMot(c), true, JSON.stringify(c));
  }
  for (const c of ["a", "ɣ", "-", "1", "'", "(", "«", ""]) assert.equal(L.finitUnMot(c), false, JSON.stringify(c));
});

test("le mot en cours : ClavierKabyle.motAvant", () => {
  assert.deepEqual(L.motEnCours("ruḥeɣ ɣer tamet", 15),
    { mot: "tamet", debut: 10, fin: 15, finApres: 0, gauche: "ruḥeɣ ɣer" });
  assert.equal(L.motEnCours("tamurt-iw", 9).mot, "tamurt-iw");
  assert.equal(L.motEnCours("ruḥeɣ ", 6), null, "après une espace, pas de mot");
  assert.equal(L.motEnCours("azul, ttrugh", 12).mot, "ttrugh");
  assert.equal(L.motEnCours("ttrugh.", 6).mot, "ttrugh");
  assert.equal(L.motEnCours("abrid -", 7).mot, "-", "le tiret compte, comme sur le téléphone");
  assert.equal(L.motEnCours("l'abrid", 7).mot, "abrid", "l'apostrophe coupe");
  assert.equal(L.motEnCours("2abrid", 6).mot, "abrid", "un chiffre aussi");
  // Au milieu d'un mot : le début du mot, et ce qui suit sera remplacé avec lui.
  const milieu = L.motEnCours("tamettut", 4);
  assert.equal(milieu.mot, "tame");
  assert.equal(milieu.finApres, 4);
});

test("le contexte : 80 caractères avant le curseur, sans le mot, rognés, 60 au plus", () => {
  // ClavierKabyle.contexteGauche : rien ne s'arrête à la ligne.
  assert.equal(L.etat("azul\nruḥeɣ ɣer tam", 18).gauche, "azul\nruḥeɣ ɣer");
  assert.equal(L.etat("azul, ", 6).gauche, "azul,");
  assert.equal(L.etat("tamurt", 0).gauche, "");
  const long = "abrid ".repeat(20);
  const e = L.etat(long + "tam", long.length + 3);
  assert.equal(e.gauche, long.slice(-(80 - 3)).trim().slice(-60));
  assert.equal(e.gauche.length, 60);
  // Les 80 caractères comptent le mot : un long mot réduit le contexte.
  const avant = "abrid abrid abrid abrid abrid tamurt ";
  const mot = "a".repeat(60);
  assert.equal(L.etat(avant + mot, avant.length + 60).gauche, "abrid abrid tamurt");
});

test("le mot d'avant que rattache un possessif", () => {
  assert.equal(L.longueurMotsAvant("tamurt ", 1), 7);
  assert.equal(L.longueurMotsAvant("ruḥeɣ ɣer tamurt ", 1), 7);
  assert.equal(L.longueurMotsAvant("tamurt  ", 1), 8);
  assert.equal(L.longueurMotsAvant("ruḥeɣ ɣer axxam nneɣ ", 2), "axxam nneɣ ".length);
  assert.equal(L.longueurMotsAvant("tamurt", 1), -1);
  assert.equal(L.longueurMotsAvant("tamurt, ", 1), -1);
  assert.equal(L.longueurMotsAvant("tamurt ", 2), -1);
  assert.equal(L.longueurMotsAvant("", 1), -1);
});

test("les blancs et le rognage de Kotlin", () => {
  for (const c of [" ", "\t", "\n", "\r", "\u00a0", "\u202f", "\u2007", "\u3000", "\u2028", "\x1c"]) {
    assert.equal(L.estBlanc(c), true, JSON.stringify(c));
  }
  for (const c of ["a", "-", ".", "\ufeff", "\u200b", ""]) assert.equal(L.estBlanc(c), false, JSON.stringify(c));
  assert.equal(L.rogner("\u00a0 azul\n\ufeff"), "azul\n\ufeff");
  // takeLast(60) compte en unités UTF-16 : un emoji en vaut deux.
  const emoji = "😀".repeat(40);
  assert.equal(L.gaucheDe(emoji + " "), emoji.slice(-60));
  assert.equal(L.gaucheDe("a😀" + "b".repeat(59)).charCodeAt(0), 0xde00, "la paire coupée, comme sur le téléphone");
});

test("le contexte envoyé avec un morceau suffit à chaque mot", () => {
  // gaucheDe(avantUtile(a) + m) === gaucheDe(a + m), quels que soient a et m.
  const alphabet = ["a", "ɣ", "-", " ", " ", "\n", "\u00a0", ".", ",", "😀", "é", "\t"];
  let graine = 7;
  const hasard = (n) => (graine = (graine * 1103515245 + 12345) % 2147483648) % n;
  const tirer = (n) => Array.from({ length: n }, () => alphabet[hasard(alphabet.length)]).join("");
  const blancs = (n) => Array.from({ length: n }, () => [" ", "\n", "\u00a0"][hasard(3)]).join("");
  for (let k = 0; k < 3000; k++) {
    const avant = tirer(hasard(200)) + (k % 3 === 0 ? blancs(hasard(150)) : "") + (k % 5 === 0 ? tirer(hasard(5)) : "");
    const morceau = (k % 7 === 0 ? blancs(hasard(80)) : "") + tirer(hasard(30));
    const court = L.avantUtile(avant);
    assert.ok(avant.endsWith(court));
    for (let d = 0; d <= morceau.length; d++) {
      assert.equal(L.gaucheDe(court + morceau.slice(0, d)), L.gaucheDe(avant + morceau.slice(0, d)),
        JSON.stringify([avant, morceau.slice(0, d)]));
    }
    // Les mots qu'une correction rattache au premier mot du morceau y sont entiers.
    for (const n of [1, 2]) {
      const k = L.longueurMotsAvant(avant, n);
      const blancs = avant.length - L.rogner("x" + avant).length + 1;
      if (k > 0 && k - blancs <= 60) assert.equal(L.longueurMotsAvant(court, n), k, JSON.stringify([avant, n]));
    }
  }
  assert.equal(L.avantUtile("azul fell-awen.\n\n"), "azul fell-awen.\n\n");
  const long = "  " + "abrid ".repeat(30);
  assert.equal(L.avantUtile(long), long.slice(-66), "au moins 60 unités, depuis le début d'un mot");
});

/** Le texte après un choix : ce que fait ClavierKabyle.appliquerChoix. */
function choisir(texte, curseur, forme, motsAvant = 0) {
  const c = L.choix(texte, curseur, forme, motsAvant);
  return { texte: texte.slice(0, c.debut) + c.texte + texte.slice(c.fin), curseur: c.curseurApres };
}

test("choisir une proposition", () => {
  const texte = "nekk ttrugh";
  assert.deepEqual(L.choix(texte, 11, "ttruɣ", 0), { debut: 5, fin: 11, texte: "ttruɣ ", curseurApres: 11 });
  // Au milieu d'un mot, le mot entier est remplacé.
  assert.deepEqual(choisir("nekk ttrugh ass", 8, "ttruɣ"), { texte: "nekk ttruɣ ass", curseur: 10 });
  // Sans mot (une prédiction), la forme s'écrit au curseur.
  assert.deepEqual(choisir("azul ", 5, "fell-awen"), { texte: "azul fell-awen ", curseur: 15 });
});

test("la tête rattache le possessif, jamais par-dessus une virgule", () => {
  assert.deepEqual(choisir("deg tamurt iw", 13, "tamurt-iw", 1), { texte: "deg tamurt-iw ", curseur: 14 });
  assert.equal(choisir("deg tamurt, iw", 14, "tamurt-iw", 1).texte, "deg tamurt, tamurt-iw ",
    "seul le mot tapé est remplacé");
  assert.equal(choisir("deg tamurt iw", 13, "is", 0).texte, "deg tamurt is ",
    "un candidat ne remplace que le mot tapé");
  assert.equal(choisir("deg axxam nneɣ", 14, "axxam-nneɣ", 1).texte, "deg axxam-nneɣ ");
});

test("l'espace après le choix : seulement s'il en manque un", () => {
  assert.deepEqual(choisir("ttrugh ass-a", 6, "ttruɣ"), { texte: "ttruɣ ass-a", curseur: 5 },
    "une espace suit déjà : le curseur reste devant, comme sur le téléphone");
  assert.equal(choisir("ttrugh.", 6, "ttruɣ").texte, "ttruɣ .", "devant un point aussi");
  assert.equal(choisir("ttrugh\nazul", 6, "ttruɣ").texte, "ttruɣ\nazul", "un saut de ligne est un blanc");
  assert.equal(choisir("ttrugh", 6, "ttruɣ").texte, "ttruɣ ");
});

test("les chiffres choisissent tant qu'un mot est en cours", () => {
  const enCours = { debut: 0, fin: 3, mot: "abr" };
  const props = ["abrid", "abrik", "abriḍ"];
  assert.equal(L.rangDuChiffre("1", props, "prop", enCours), 0);
  assert.equal(L.rangDuChiffre("3", props, "comp", enCours), 2);
  assert.equal(L.rangDuChiffre("5", props, "prop", enCours), -1);
  assert.equal(L.rangDuChiffre("1", props, "pred", enCours), -1, "pas une prédiction");
  assert.equal(L.rangDuChiffre("1", props, "prop", null), -1, "pas sans mot en cours");
  assert.equal(L.rangDuChiffre("7", props, "prop", enCours), -1);
  assert.equal(L.rangDuChiffre("&", props, "prop", enCours), -1);
});

test("les couleurs du téléphone", () => {
  assert.equal(L.couleur("prop", 0), L.VERT);
  assert.equal(L.couleur("prop", 3), L.BLEU);
  assert.equal(L.couleur("comp", 0), L.OCRE);
  assert.equal(L.couleur("pred", 2), L.OCRE);
  // Les soulignés de CorrecteurSysteme : rouge la faute, bleu le doute.
  assert.equal(L.couleurSouligne("faute"), L.ROUGE);
  assert.equal(L.couleurSouligne("doute"), L.BLEU);
});

test("la correction automatique ne touche qu'aux mots inconnus", () => {
  const prop = (formes, extra = {}) => ({ nature: "prop", formes, mots_avant: 0, ...extra });
  const vide = new Set();
  assert.equal(L.autocorrection("ttrugh", "nekk ", prop(["ttruɣ", "ttru"]), vide), "ttruɣ");
  assert.equal(L.autocorrection("Ttrugh", "", prop(["Ttruɣ"]), vide), "Ttruɣ", "en début de phrase");
  assert.equal(L.autocorrection("ttrugh", "", prop(["ttruɣ"], { mots_avant: 1 }), vide), null);
  assert.equal(L.autocorrection("tamurt", "", prop(["tmurt", "tamurt"]), vide), null,
    "un mot connu reste : la relecture le soulignera");
  assert.equal(L.autocorrection("iw", "", prop(["iw", "is"]), vide), null);
  assert.equal(L.autocorrection("ttrugh", "", { nature: "comp", formes: ["ttruɣ"] }, vide), null);
  assert.equal(L.autocorrection("ttrugh", "", prop([]), vide), null);
  assert.equal(L.autocorrection("ttrugh", "", null, vide), null);
  assert.equal(L.autocorrection("ttrugh", "", prop(["ttruɣ"]), new Set(["ttrugh"])), null, "gardé");
  assert.equal(L.autocorrection("ONU", "", prop(["unu"]), vide), null, "un sigle");
  assert.equal(L.autocorrection("Massil", "azul a ", prop(["massir"]), vide), null,
    "un nom propre au milieu d'une phrase");
  assert.equal(L.autocorrection("Massil", "Azul. ", prop(["Massir"]), vide), "Massir");
  assert.equal(L.autocorrection("x", "", prop(["d"]), vide), null);
});

test("les morceaux à relire : une phrase chacun", () => {
  const texte = "Azul fell-awen. Amek tellam?\n\nTtrugh ass-a deg tamurt iw.\n123";
  const m = L.morceaux(texte);
  assert.deepEqual(m.map((x) => x.texte), ["Azul fell-awen. ", "Amek tellam?", "Ttrugh ass-a deg tamurt iw."]);
  for (const x of m) assert.equal(texte.slice(x.debut, x.debut + x.texte.length), x.texte);
  const phrase = "Ttrugh ass-a. ";
  const long = phrase.repeat(10);
  const phrases = L.morceaux(long);
  assert.equal(phrases.length, 10);
  assert.equal(phrases.map((x) => x.texte).join(""), long, "rien ne se perd");
  const sansPoint = "abrid ".repeat(20);
  const coupes = L.morceaux(sansPoint, 40);
  assert.equal(coupes.map((x) => x.texte).join(""), sansPoint);
  for (const x of coupes) {
    assert.ok(x.texte.length <= 40);
    assert.ok(x.texte.endsWith(" "), "coupé à une espace : " + JSON.stringify(x.texte));
    assert.equal(sansPoint.slice(x.debut, x.debut + x.texte.length), x.texte);
  }
  const unMot = "a".repeat(100);
  assert.equal(L.morceaux(unMot, 40).map((x) => x.texte).join(""), unMot);
  assert.deepEqual(L.morceaux(""), []);
  assert.deepEqual(L.morceaux("Azul!"), [{ debut: 0, texte: "Azul!" }]);
});

test("tout corriger d'un coup", () => {
  const texte = "😀 ttrugh deg tamurt iw";
  const signales = [
    { mot: "ttrugh", debut: 3, fin: 9, propositions: ["ttruɣ"] },
    { mot: "tamurt iw", debut: 14, fin: 23, propositions: ["tamurt-iw"] },
  ];
  assert.equal(L.toutCorriger(texte, signales), "😀 ttruɣ deg tamurt-iw");
  const change = [{ mot: "ttrugh", debut: 0, fin: 6, propositions: ["ttruɣ"] }];
  assert.equal(L.toutCorriger("abrid ass", change), "abrid ass", "le texte a changé : on n'y touche pas");
});

test("les champs sensibles", () => {
  assert.equal(L.champSensible("password", ""), true);
  assert.equal(L.champSensible("text", "one-time-code"), true);
  assert.equal(L.champSensible("text", "section-x cc-number"), true);
  assert.equal(L.champSensible("text", "new-password"), true);
  assert.equal(L.champSensible("text", "name"), false);
  assert.equal(L.champSensible("search", ""), false);
  assert.equal(L.typeEcrit("text"), true);
  assert.equal(L.typeEcrit("search"), true);
  assert.equal(L.typeEcrit(undefined), true);
  assert.equal(L.typeEcrit("email"), false);
  assert.equal(L.typeEcrit("url"), false);
  assert.equal(L.typeEcrit("number"), false);
});

test("le rééchantillonnage pour le modèle vocal", () => {
  const taux = 48000;
  const sinus = (f, n) => Float32Array.from({ length: n }, (_, i) => Math.sin(2 * Math.PI * f * i / taux));
  const energie = (x) => Math.sqrt(x.slice(200, -200).reduce((s, v) => s + v * v, 0) / (x.length - 400));
  const voix = L.reechantillonner(sinus(1000, taux), taux, 16000);
  assert.equal(voix.length, 16000);
  assert.ok(Math.abs(energie(voix) - Math.SQRT1_2) < 0.02, "1 kHz passe : " + energie(voix));
  // 1 kHz garde sa fréquence : un passage par zéro toutes les 8 trames.
  let zeros = 0;
  for (let i = 201; i < voix.length - 200; i++) if ((voix[i - 1] < 0) !== (voix[i] < 0)) zeros++;
  assert.ok(Math.abs(zeros - 2 * 1000 * (voix.length - 401) / 16000) <= 2, "zéros : " + zeros);
  const sifflante = L.reechantillonner(sinus(12000, taux), taux, 16000);
  assert.ok(energie(sifflante) < 0.01, "12 kHz ne se replie pas : " + energie(sifflante));
  assert.equal(L.reechantillonner(Float32Array.of(0.1, 0.2), 16000, 16000).length, 2);
  const de441 = L.reechantillonner(sinus(1000, 44100), 44100, 16000);
  assert.equal(de441.length, Math.floor(44100 / (44100 / 16000)));
});

test("les réglages et « mon dictionnaire »", async () => {
  const C = require("../extension/commun.js");
  assert.equal(C.reglagesComplets({}).graphie, "v");
  assert.equal(C.reglagesComplets({ graphie: "b" }).graphie, "b");
  assert.equal(C.reglagesComplets({ graphie: "x", barre: "oui" }).graphie, "v");
  assert.equal(C.reglagesComplets({ barre: "oui" }).barre, true);
  const local = {};
  globalThis.chrome = {
    storage: {
      local: {
        get: async (cle) => (cle in local ? { [cle]: local[cle] } : {}),
        set: async (valeurs) => Object.assign(local, valeurs),
      },
    },
  };
  try {
    assert.deepEqual(await C.mesMots(), []);
    assert.deepEqual(await C.ajouterMots(["Tazmamt"]), { ajoutes: 1, total: 1 });
    assert.deepEqual(await C.ajouterMots(["\uFEFFabrid", "tazmamt", "", "deux mots", " ɣef "]),
      { ajoutes: 2, total: 3 });
    assert.deepEqual(await C.mesMots(), ["abrid", "tazmamt", "ɣef"]);
    assert.deepEqual(await C.ajouterMots(["", "deux mots"]), { erreur: "Un mot, sans espace." });
    assert.deepEqual(await C.oublierMot(" Tazmamt"), { total: 2 });
  } finally {
    delete globalThis.chrome;
  }
});
