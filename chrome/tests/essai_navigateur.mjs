// L'extension pour de vrai : Chromium, l'extension chargée, et le correcteur dans son
// document hors écran. Le parcours lui-même est dans scenario.mjs, le même pour Firefox
// (firefox/tests/essai_firefox.mjs).
//
//   node chrome/tests/essai_navigateur.mjs           avec le faux correcteur (faux_travailleur.js)
//   node chrome/tests/essai_navigateur.mjs --vrai    avec le vrai : il lui faut ses ressources
//                                                    (chrome/autonome/ressources.sh) ; mesure
//                                                    aussi le temps de chargement et la mémoire
//
// Il faut Playwright (npm install playwright, puis npx playwright install chromium),
// ou un Chrome donné par CHROME=/chemin/vers/chrome. Linux ou macOS.
// KAB_ESSAI_CAPTURES=dossier garde des captures d'écran ; KAB_ESSAI_AUDIO=fichier.wav
// sert de micro à la dictée, et KAB_ESSAI_DICTEE=texte est ce qu'elle doit en tirer.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { attendre, bilan, memoireDe, scenario, verifie } from "./scenario.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const ICI = path.dirname(fileURLToPath(import.meta.url));
const DEPOT = path.resolve(ICI, "..", "..");
const SOURCE = path.join(DEPOT, "chrome", "extension");
const ID = "bdmaonaapnhmnkcealgfodhmkijkhbgg";      // fixé par la clé du manifeste
const VRAI = process.argv.includes("--vrai");
const CAPTURES = process.env.KAB_ESSAI_CAPTURES || "";
const AUDIO = process.env.KAB_ESSAI_AUDIO || "";
const DICTEE = process.env.KAB_ESSAI_DICTEE || "";

// Le décor : un dossier jetable, la page d'essai, l'extension.

const TEMP = fs.mkdtempSync(path.join(os.tmpdir(), "kab-essai-chrome-"));
const PROFIL = path.join(TEMP, "profil");
fs.mkdirSync(PROFIL, { recursive: true });
if (CAPTURES) fs.mkdirSync(CAPTURES, { recursive: true });

// Avec le faux correcteur, une copie de l'extension, sans ses ressources, où il prend la
// place du vrai.
let EXTENSION = SOURCE;
if (VRAI) {
  if (!fs.existsSync(path.join(SOURCE, "ressources", "moteur", "kabyle_3gram.binary"))) {
    console.log("Il manque les ressources de l'extension : chrome/autonome/ressources.sh <kab-board-0.3.apk>");
    process.exit(2);
  }
} else {
  EXTENSION = path.join(TEMP, "extension");
  fs.cpSync(SOURCE, EXTENSION, {
    recursive: true, filter: (f) => !/[\\/](ressources|ort)$/.test(f),
  });
  fs.copyFileSync(path.join(ICI, "faux_travailleur.js"), path.join(EXTENSION, "moteur", "travailleur.js"));
}

const PAGE = fs.readFileSync(path.join(ICI, "page_essai.html"), "utf8");
const serveur = http.createServer((_q, r) => {
  r.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  r.end(PAGE);
});
await new Promise((r) => serveur.listen(0, "127.0.0.1", r));
const SITE = `http://127.0.0.1:${serveur.address().port}/`;

let navigateur = null;

// Chrome. --load-extension n'est plus accepté : l'extension se charge par le
// protocole de débogage, comme le fait « Charger l'extension non empaquetée ».
const executable = process.env.CHROME || chromium.executablePath();
const port = 9300 + Math.floor(Math.random() * 600);
const GROUPE = process.platform !== "win32";
const chrome = spawn(executable, [
  "--headless=new", "--no-sandbox", "--disable-gpu", `--user-data-dir=${PROFIL}`,
  `--remote-debugging-port=${port}`, "--enable-unsafe-extension-debugging", "--no-first-run",
  "--no-default-browser-check", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
  // Chrome lui-même se tait (mises à jour, services de Google) : l'essai ne doit
  // voir partir aucune connexion, l'extension n'en ouvre aucune.
  "--disable-background-networking", "--disable-component-update", "--disable-sync", "--no-pings",
  "--disable-domain-reliability", "--disable-features=OptimizationHints,MediaRouter,Translate",
  "--window-size=900,900", ...(AUDIO ? [`--use-file-for-fake-audio-capture=${AUDIO}%noloop`] : []), "about:blank",
], { stdio: ["ignore", "ignore", "ignore"], detached: GROUPE });

async function finir(code) {
  if (navigateur) await navigateur.close().catch(() => {});
  if (chrome.exitCode === null) {
    const parti = new Promise((r) => chrome.once("exit", r));
    chrome.kill();
    await Promise.race([parti, attendre(5000)]);
  }
  // Ses processus fils (rendu, rapports d'erreur) écrivent encore dans le profil
  // quand le principal est parti : tout le groupe s'en va.
  if (GROUPE) {
    try { process.kill(-chrome.pid, "SIGKILL"); } catch { /* déjà parti */ }
    await attendre(300);
  }
  serveur.close();
  try {
    fs.rmSync(TEMP, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  } catch (e) {
    console.log(`(${TEMP} reste : ${e.code})`);
  }
  process.exit(code);
}

for (let i = 0; i < 50 && !navigateur; i++) {
  await attendre(200);
  navigateur = await chromium.connectOverCDP(`http://127.0.0.1:${port}`).catch(() => null);
}
if (!navigateur) {
  console.log("Chrome ne démarre pas : " + executable);
  await finir(2);
}
const cdp = await navigateur.newBrowserCDPSession();
const chargee = await cdp.send("Extensions.loadUnpacked", { path: EXTENSION }).catch((e) => ({ erreur: e.message }));
verifie("l'extension se charge, avec l'identifiant fixé par sa clé", chargee.id === ID, chargee);
if (chargee.id !== ID) await finir(1);
const contexte = navigateur.contexts()[0];
const sw = contexte.serviceWorkers().find((w) => w.url().includes(ID)) ||
  await contexte.waitForEvent("serviceworker", { predicate: (w) => w.url().includes(ID) });
verifie("le fond démarre", sw.url() === `chrome-extension://${ID}/fond.js`, sw.url());
await attendre(500);
for (const p of contexte.pages()) if (p.url().startsWith("chrome-extension://")) await p.close();

const n = {
  SITE, EXTENSION, TEMP, VRAI, AUDIO, DICTEE, CAPTURES,
  url: (chemin) => `chrome-extension://${ID}/${chemin}`,
  async nouvellePage() {
    const p = await contexte.newPage();
    await p.setViewportSize({ width: 900, height: 900 });
    p.on("pageerror", (e) => console.log("   [page] " + e.message));
    return p;
  },
  fond: (f, x) => sw.evaluate(`(${f})(globalThis, ${JSON.stringify(x ?? null)})`),
  memoire: process.platform === "linux" ? () => memoireDe(chrome.pid) : null,
};
const { mesures } = await scenario(n);

console.log(`\nLe micro de la dictée ouvert en ${mesures.micro.toFixed(1)} s.`);

if (VRAI && mesures.barre) {
  console.log(`Le correcteur chargé en ${mesures.chargement.toFixed(1)} s ; la barre répond en ` +
    `${mesures.barre.mediane.toFixed(1)} ms (médiane), ${mesures.barre.p95.toFixed(1)} ms (95 %) ; ` +
    `la dictée transcrite en ${mesures.dictee.toFixed(1)} s.`);
  if (mesures.avec) {
    console.log(`Mémoire de Chromium (PSS) : ${mesures.avec.total} Mo avec le correcteur, ` +
      `${mesures.sans.total} Mo sans ; le plus gros processus : ${mesures.avec.plus} Mo.`);
  }
}
const { ok, rates } = bilan();
console.log(`\n${ok} vérifications passées, ${rates.length} échec(s)` + (VRAI ? " (vrai correcteur)" : " (faux correcteur)"));
await finir(rates.length ? 1 : 0);
