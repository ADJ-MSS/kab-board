// L'extension pour Firefox, pour de vrai : Firefox, l'extension installée (comme un module
// temporaire), et le même parcours que pour Chromium (chrome/tests/scenario.mjs).
//
//   node firefox/tests/essai_firefox.mjs           avec le faux correcteur (faux_travailleur.js)
//   node firefox/tests/essai_firefox.mjs --vrai    avec le vrai, et ses ressources : il faut
//                                                  d'abord firefox/construire.sh
//
// Il faut Puppeteer (npm install puppeteer-core) et Firefox 140 ou plus récent :
// FIREFOX=/chemin/vers/firefox, sinon celui du système. firefox/extension doit exister
// (firefox/construire.sh, ou firefox/construire.sh --sans-ressources pour le faux
// correcteur). KAB_ESSAI_CAPTURES=dossier garde des captures d'écran. Firefox n'a pas de
// micro tiré d'un fichier : la dictée entend le son d'essai de Firefox.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { attendre, bilan, jusqua, memoireDe, scenario, verifie } from "../../chrome/tests/scenario.mjs";

const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");

const ICI = path.dirname(fileURLToPath(import.meta.url));
const DEPOT = path.resolve(ICI, "..", "..");
const SOURCE = path.join(DEPOT, "firefox", "extension");
const IDENTIFIANT = "kab-board@adj-mss";
const UUID = "6b616232-626f-4172-6400-66697265666f";   // fixé par les préférences : des adresses stables
const VRAI = process.argv.includes("--vrai");
const CAPTURES = process.env.KAB_ESSAI_CAPTURES || "";
const FIREFOX = process.env.FIREFOX || execFileSync("sh", ["-c", "command -v firefox"]).toString().trim();

if (!fs.existsSync(path.join(SOURCE, "manifest.json"))) {
  console.log("Il manque l'extension pour Firefox : firefox/construire.sh");
  process.exit(2);
}
if (VRAI && !fs.existsSync(path.join(SOURCE, "ressources", "compresses.json"))) {
  console.log("Il manque les ressources de l'extension : firefox/construire.sh, sans --sans-ressources");
  process.exit(2);
}

const TEMP = fs.mkdtempSync(path.join(os.tmpdir(), "kab-essai-firefox-"));
if (CAPTURES) fs.mkdirSync(CAPTURES, { recursive: true });

// Avec le faux correcteur, une copie de l'extension, sans ses ressources, où il prend la
// place du vrai.
let EXTENSION = SOURCE;
if (!VRAI) {
  EXTENSION = path.join(TEMP, "extension");
  fs.cpSync(SOURCE, EXTENSION, { recursive: true, filter: (f) => !/[\\/](ressources|ort)$/.test(f) });
  fs.copyFileSync(path.join(DEPOT, "chrome", "tests", "faux_travailleur.js"),
    path.join(EXTENSION, "moteur", "travailleur.js"));
}

// La même page d'essai que pour Chromium.
const PAGE = fs.readFileSync(path.join(DEPOT, "chrome", "tests", "page_essai.html"), "utf8");
const serveur = http.createServer((_q, r) => {
  r.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  r.end(PAGE);
});
await new Promise((r) => serveur.listen(0, "127.0.0.1", r));
const SITE = `http://127.0.0.1:${serveur.address().port}/`;

const navigateur = await puppeteer.launch({
  browser: "firefox", executablePath: FIREFOX, headless: true,
  // Les pages de l'extension sont fermées à WebDriver sans cet accès.
  args: ["--width=1000", "--height=900", "-remote-allow-system-access"],
  extraPrefsFirefox: {
    "extensions.webextensions.uuids": JSON.stringify({ [IDENTIFIANT]: UUID }),
    "intl.accept_languages": "fr-FR, fr",
    // Le micro : le son d'essai de Firefox, sans rien demander.
    "media.navigator.streams.fake": true,
    "media.navigator.permission.disabled": true,
    // Firefox se tait (mises à jour, télémétrie) et va droit à la page d'essai.
    "network.proxy.type": 0,
    "app.update.enabled": false,
    "datareporting.policy.dataSubmissionEnabled": false,
    "toolkit.telemetry.enabled": false,
  },
});

async function finir(code) {
  await navigateur.close().catch(() => {});
  serveur.close();
  try {
    fs.rmSync(TEMP, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  } catch (e) {
    console.log(`(${TEMP} reste : ${e.code})`);
  }
  process.exit(code);
}

const id = await navigateur.installExtension(EXTENSION).catch((e) => ({ erreur: e.message }));
verifie("l'extension s'installe, avec son identifiant", id === IDENTIFIANT, id);
if (id !== IDENTIFIANT) await finir(1);
const url = (chemin) => `moz-extension://${UUID}/${chemin}`;

/**
 * Va à une page de l'extension. Firefox ne dit pas à WebDriver quand elle a fini de se
 * charger : on y va sans attendre cet événement, puis on attend qu'elle soit là.
 */
async function allerA(page, u) {
  page.goto(u, { timeout: 0 }).catch(() => {});
  const la = await jusqua(() => page.evaluate(() => `${location.href}|${document.readyState}`)
    .then((x) => x === `${u}|complete`, () => false), 15000, 100);
  if (!la) throw new Error(`la page ne s'ouvre pas : ${u}`);
}

// Le fond : joint par runtime.getBackgroundPage(), depuis une page de l'extension ouverte
// tout du long.
const fondPage = await navigateur.newPage();
await allerA(fondPage, url("pages/micro.html"));
const fond = (f, x) => fondPage.evaluate(`(async () => {
  const g = await chrome.runtime.getBackgroundPage();
  return await (${f})(g, ${JSON.stringify(x ?? null)});
})()`);
verifie("le fond démarre", await fond((g) => typeof g.publierEtat === "function").catch((e) => e.message) === true);

/** Une page de Puppeteer, qui répond comme celles de Playwright (ce dont se sert le parcours). */
function commePlaywright(p) {
  return {
    goto: (u) => (u.startsWith("moz-extension:") ? allerA(p, u) : p.goto(u)),
    url: () => p.url(),
    close: () => p.close(),
    // WebDriver ne sait pas mettre au premier plan une page de l'extension.
    bringToFront: () => p.bringToFront().catch(() => {}),
    setViewportSize: ({ width, height }) => p.setViewport({ width, height }),
    screenshot: (o) => p.screenshot(o),
    evaluate: (f, x) => p.evaluate(f, x),
    evaluateHandle: (f, x) => p.evaluateHandle(f, x),
    click: (s) => p.click(s),
    mouse: p.mouse,
    on: (type, f) => p.on(type, f),
    getAttribute: (s, a) => p.$eval(s, (e, a) => e.getAttribute(a), a),
    inputValue: (s) => p.$eval(s, (e) => e.value),
    fill: (s, v) => p.$eval(s, (e, v) => {
      e.focus();
      e.value = v;
      e.dispatchEvent(new Event("input", { bubbles: true }));
    }, v),
    // WebDriver ne sait pas non plus y choisir un fichier : la page le reçoit tel quel.
    setInputFiles: (s, f) => p.$eval(s, (e, nom, base64) => {
      const octets = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
      const choix = new DataTransfer();
      choix.items.add(new File([octets], nom, { type: "text/plain" }));
      e.files = choix.files;
      e.dispatchEvent(new Event("change", { bubbles: true }));
    }, path.basename(f), fs.readFileSync(f).toString("base64")),
    keyboard: {
      type: (texte, o) => p.keyboard.type(texte, o),
      // « Control+z » : les touches tenues, puis la dernière.
      async press(touches) {
        const t = touches.split("+");
        for (const m of t.slice(0, -1)) await p.keyboard.down(m);
        await p.keyboard.press(t[t.length - 1]);
        for (const m of t.slice(0, -1).reverse()) await p.keyboard.up(m);
      },
    },
  };
}

const n = {
  SITE, EXTENSION, TEMP, VRAI, AUDIO: "", DICTEE: "", CAPTURES,
  url,
  async nouvellePage() {
    const p = commePlaywright(await navigateur.newPage());
    await p.setViewportSize({ width: 900, height: 900 });
    p.on("pageerror", (e) => console.log("   [page] " + e.message));
    return p;
  },
  fond,
  memoire: process.platform === "linux" ? () => memoireDe(navigateur.process().pid) : null,
};
const { mesures } = await scenario(n);

console.log(`\nLe micro de la dictée ouvert en ${mesures.micro.toFixed(1)} s.`);

if (VRAI && mesures.barre) {
  console.log(`Le correcteur chargé en ${mesures.chargement.toFixed(1)} s ; la barre répond en ` +
    `${mesures.barre.mediane.toFixed(1)} ms (médiane), ${mesures.barre.p95.toFixed(1)} ms (95 %) ; ` +
    `la dictée transcrite en ${mesures.dictee.toFixed(1)} s.`);
  if (mesures.avec) {
    console.log(`Mémoire de Firefox (PSS) : ${mesures.avec.total} Mo avec le correcteur, ` +
      `${mesures.sans.total} Mo sans ; le plus gros processus : ${mesures.avec.plus} Mo.`);
  }
}
const { ok, rates } = bilan();
console.log(`\n${ok} vérifications passées, ${rates.length} échec(s)` + (VRAI ? " (vrai correcteur)" : " (faux correcteur)"));
await attendre(100);
await finir(rates.length ? 1 : 0);
