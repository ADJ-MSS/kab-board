// Le décor des captures : Chrome en français, l'extension chargée dans un profil jetable,
// avec ses ressources et le vrai correcteur, une page d'exemple neutre.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
export const { chromium } = require("playwright");

export const DEPOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
export const EXTENSION = path.join(DEPOT, "chrome", "extension");
export const ID = "bdmaonaapnhmnkcealgfodhmkijkhbgg";
// Google Chrome s'il est là, sinon le Chromium de Playwright.
const CHROME = process.env.CHROME || (fs.existsSync("/usr/bin/google-chrome") ? "/usr/bin/google-chrome" : chromium.executablePath());

export const attendre = (ms) => new Promise((r) => setTimeout(r, ms));
export async function jusqua(f, delai = 15000, pas = 100) {
  const fin = Date.now() + delai;
  let v;
  while (Date.now() < fin) { v = await f(); if (v) return v; await attendre(pas); }
  return v;
}

const PAGE = `<!doctype html><html lang="kab"><head><meta charset="utf-8"><title>Tabrat tamaynut</title>
<link rel="icon" href="data:,">
<style>
*{box-sizing:border-box} body{margin:0;background:#f3f4f6;font:16px/1.5 "Noto Sans","DejaVu Sans",sans-serif;color:#1f2933}
.cadre{max-width:820px;margin:28px auto;background:#fff;border:1px solid #dde1e6;border-radius:10px;padding:22px 26px 26px}
h1{font-size:20px;margin:0 0 16px} label{display:block;font-size:13px;color:#52606d;margin:14px 0 5px}
input,textarea,.ed{width:100%;font:17px/1.55 "Noto Sans","DejaVu Sans",sans-serif;color:#1f2933;border:1px solid #c4cad1;border-radius:7px;padding:9px 11px;background:#fff}
textarea{height:170px;resize:vertical} .ed{min-height:110px}
.pied{display:flex;justify-content:flex-end;margin-top:16px} .envoyer{background:#1d6fb8;color:#fff;border:0;border-radius:7px;padding:9px 18px;font-size:15px}
</style></head><body><div class="cadre">
<h1>Tabrat tamaynut</h1>
<label for="sujet">Asentel</label><input id="sujet" type="text">
<label for="zone">Izen</label><textarea id="zone"></textarea>
<label>Tazmilt</label><div id="ed" class="ed" contenteditable="true"></div>
<label for="mdp">Awal uffir</label><input id="mdp" type="password">
<div class="pied"><button class="envoyer">Azen</button></div>
</div></body></html>`;

/** panne : une copie de l'extension dont le correcteur ne se charge pas (son fil manque). */
export async function monter({ panne = false, audio = "", pages = {} } = {}) {
  const TEMP = fs.mkdtempSync(path.join(os.tmpdir(), "kab-captures-"));
  const PROFIL = path.join(TEMP, "profil");
  fs.mkdirSync(path.join(PROFIL, "Default"), { recursive: true });
  fs.writeFileSync(path.join(PROFIL, "Default", "Preferences"),
    JSON.stringify({ extensions: { ui: { developer_mode: true } }, intl: { accept_languages: "fr-FR,fr" } }));
  let extension = EXTENSION;
  if (panne) {
    extension = path.join(TEMP, "extension");
    fs.cpSync(EXTENSION, extension, { recursive: true, filter: (f) => !/[\\/](ressources|ort)$/.test(f) });
    fs.rmSync(path.join(extension, "moteur", "travailleur.js"));
  } else if (!fs.existsSync(path.join(EXTENSION, "ressources", "moteur", "kabyle_3gram.binary"))) {
    throw new Error("il manque les ressources : chrome/autonome/ressources.sh <kab-board-0.3.apk>");
  }
  const serveur = http.createServer((q, r) => {
    r.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    r.end(pages[q.url.split("?")[0]] ?? PAGE);
  });
  await new Promise((r) => serveur.listen(0, "127.0.0.1", r));
  // Un nom de site fictif, que le popup affiche (« Sur tabrat.exemple »).
  const SITE = `http://tabrat.exemple:${serveur.address().port}/`;

  const port = 9300 + Math.floor(Math.random() * 600);
  const chrome = spawn(CHROME, [
    "--headless=new", "--no-sandbox", "--disable-gpu", `--user-data-dir=${PROFIL}`, "--lang=fr",
    `--remote-debugging-port=${port}`, "--enable-unsafe-extension-debugging", "--no-first-run",
    "--no-default-browser-check", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
    "--disable-background-networking", "--disable-component-update", "--disable-sync", "--no-pings",
    "--disable-features=OptimizationHints,MediaRouter,Translate,HttpsUpgrades,HttpsFirstBalancedModeAutoEnable", "--hide-scrollbars",
    "--host-resolver-rules=MAP tabrat.exemple 127.0.0.1, MAP autre.exemple 127.0.0.1",
    "--window-size=1100,900", ...(audio ? [`--use-file-for-fake-audio-capture=${audio}`] : []), "about:blank"],
    { stdio: "ignore", detached: true, env: { ...process.env, LANG: "fr_FR.UTF-8", LANGUAGE: "fr" } });
  let nav = null;
  for (let i = 0; i < 50 && !nav; i++) {
    await attendre(200);
    nav = await chromium.connectOverCDP(`http://127.0.0.1:${port}`).catch(() => null);
  }
  const cdp = await nav.newBrowserCDPSession();
  const r = await cdp.send("Extensions.loadUnpacked", { path: extension });
  if (r.id !== ID) throw new Error("identifiant : " + JSON.stringify(r));
  const contexte = nav.contexts()[0];
  const sw = contexte.serviceWorkers().find((w) => w.url().includes(ID)) ||
    await contexte.waitForEvent("serviceworker", { predicate: (w) => w.url().includes(ID) });
  await attendre(800);
  const ouvertes = contexte.pages().filter((p) => p.url().startsWith("chrome-extension://"));

  async function fermer() {
    await nav.close().catch(() => {});
    try { process.kill(-chrome.pid, "SIGKILL"); } catch { /* parti */ }
    serveur.close();
    await attendre(500);
    fs.rmSync(TEMP, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  }
  return { nav, contexte, sw, SITE, ouvertes, fermer, port };
}

/** Le vrai popup, celui qu'ouvre le bouton de l'extension : capturé par son propre WebSocket. */
export async function capturerPopup(port, fichier, avant = null) {
  const liste = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const cible = liste.find((t) => t.url.endsWith("popup/popup.html"));
  if (!cible) return false;
  const ws = new WebSocket(cible.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));
  let n = 0;
  const envoyer = (method, params = {}) => new Promise((r) => {
    const id = ++n;
    const ecoute = (e) => { const m = JSON.parse(e.data); if (m.id === id) { ws.removeEventListener("message", ecoute); r(m.result); } };
    ws.addEventListener("message", ecoute);
    ws.send(JSON.stringify({ id, method, params }));
  });
  if (avant) await envoyer("Runtime.evaluate", { expression: avant, awaitPromise: true });
  await attendre(600);
  const m = await envoyer("Page.getLayoutMetrics");
  const l = Math.ceil(m.cssLayoutViewport.clientWidth), h = Math.ceil(m.cssLayoutViewport.clientHeight);
  await envoyer("Emulation.setDeviceMetricsOverride", { width: l, height: h, deviceScaleFactor: 2, mobile: false });
  await attendre(400);
  const { data } = await envoyer("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(fichier, Buffer.from(data, "base64"));
  ws.close();
  return { largeur: l, hauteur: h };
}

/** Ce que montre l'extension dans la page (sa racine d'ombre). */
export const ombre = (p, corps) => p.evaluate((f) => {
  const hote = document.querySelector("kab-board-interface");
  return hote && hote.shadowRoot ? new Function("racine", f)(hote.shadowRoot) : null;
}, corps);
export const barre = (p) => ombre(p, `const b = racine.querySelector(".barre");
  if (!b || b.classList.contains("cache")) return null;
  return { formes: [...b.querySelectorAll(".forme .mot")].map((x) => x.textContent),
           message: (b.querySelector(".message") || {}).textContent || "" };`);
export const barreAvec = (p, f, delai = 10000) => jusqua(() => barre(p).then((b) => b && f(b) ? b : null), delai);
export async function cliquerDans(p, selecteur, texte) {
  const h = await p.evaluateHandle(([s, t]) => [...document.querySelector("kab-board-interface").shadowRoot
    .querySelectorAll(s)].find((x) => x.textContent.includes(t)), [selecteur, texte]);
  const e = h.asElement();
  if (e) await e.click();
  return !!e;
}
export const panneau = (p) => ombre(p, `const x = racine.querySelector(".panneau");
  return x && !x.classList.contains("cache") ? x.innerText : null;`);
export const etat = (sw) => sw.evaluate(() => chrome.storage.session.get("etat").then((r) => r.etat));
export const correcteurPret = (sw) => jusqua(async () => { const e = await etat(sw); return e && e.moteur === "pret"; }, 120000, 300);
