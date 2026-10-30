// L'extension pour de vrai : Chromium, l'extension chargée, et le correcteur dans son
// document hors écran.
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
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

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

let ok = 0;
const rates = [];
function verifie(intitule, condition, detail) {
  if (condition) {
    ok++;
    console.log("  ok      " + intitule);
  } else {
    rates.push(intitule);
    console.log("  ÉCHEC   " + intitule + (detail === undefined ? "" : "  " + JSON.stringify(detail)));
  }
}
const attendre = (ms) => new Promise((r) => setTimeout(r, ms));
async function jusqua(f, delai = 15000, pas = 100) {
  const fin = Date.now() + delai;
  let v;
  while (Date.now() < fin) {
    v = await f();
    if (v) return v;
    await attendre(pas);
  }
  return v;
}

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

const PAGE = `<!doctype html><html lang="kab"><head><meta charset="utf-8"><title>Essai</title>
<link rel="icon" href="data:,">
<style>body{font:16px/1.5 sans-serif;margin:24px;max-width:760px}
textarea{width:100%;height:140px;font:17px/1.5 "DejaVu Sans",sans-serif;padding:8px}
input{width:100%;font:17px "DejaVu Sans",sans-serif;padding:6px 8px}
.ed{border:1px solid #999;min-height:100px;padding:8px;font:17px/1.5 "DejaVu Sans",sans-serif}
label{display:block;margin-top:18px;color:#555;font-size:13px}</style></head><body>
<h1>Essai de Kab-board</h1>
<label for="zone">Une zone de texte</label><textarea id="zone"></textarea>
<label for="ligne">Une ligne</label><input id="ligne" type="text">
<label>Un élément modifiable</label><div id="ed" class="ed" contenteditable="true"></div>
<label for="mdp">Un mot de passe</label><input id="mdp" type="password">
<label for="courriel">Un courriel</label><input id="courriel" type="email">
<label for="complete">Une recherche qui complète ce qu'on tape (comme Bing)</label><input id="complete" type="search">
<script>
const complete = document.getElementById("complete");
complete.addEventListener("input", (e) => {
  if (e.inputType !== "insertText" || !complete.value.endsWith("g")) return;
  const n = complete.value.length;
  complete.value += "irc arrco";
  complete.setSelectionRange(n, complete.value.length);
});
</script>
</body></html>`;
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

const page = await contexte.newPage();
await page.setViewportSize({ width: 900, height: 900 });
page.on("pageerror", (e) => console.log("   [page] " + e.message));
await page.goto(SITE);

const etat = () => sw.evaluate(() => chrome.storage.session.get("etat").then((r) => r.etat));
const capture = async (nom, p = page) => {
  if (CAPTURES) await p.screenshot({ path: path.join(CAPTURES, nom + ".png") });
};
/** Ce que montre l'extension dans la page (sa racine d'ombre). */
const ombre = (corps, p = page) => p.evaluate((f) => {
  const hote = document.querySelector("kab-board-interface");
  return hote && hote.shadowRoot ? new Function("racine", f)(hote.shadowRoot) : null;
}, corps);
const barre = (p = page) => ombre(`const b = racine.querySelector(".barre");
  if (!b || b.classList.contains("cache")) return null;
  return { formes: [...b.querySelectorAll(".forme .mot")].map((x) => x.textContent),
           message: (b.querySelector(".message") || {}).textContent || "" };`, p);
const barreAvec = (f, delai = 8000, p = page) => jusqua(() => barre(p).then((b) => b && f(b) ? b : null), delai);
async function cliquerDans(selecteur, texte, p = page) {
  const h = await p.evaluateHandle(([s, t]) => [...document.querySelector("kab-board-interface").shadowRoot
    .querySelectorAll(s)].find((x) => x.textContent.includes(t)), [selecteur, texte]);
  const e = h.asElement();
  if (e) await e.click();
  return !!e;
}
const panneau = (p = page) => ombre(`const x = racine.querySelector(".panneau");
  return x && !x.classList.contains("cache") ? x.innerText : null;`, p);

// 1. La frappe, avant même que le correcteur soit prêt

await page.click("#zone");
await page.keyboard.type("ruhagh", { delay: 40 });
verifie("gh → ɣ dans une zone de texte", await page.inputValue("#zone") === "ruhaɣ", await page.inputValue("#zone"));
await page.keyboard.press("Backspace");
verifie("un effacement juste après défait la conversion", await page.inputValue("#zone") === "ruhagh");
for (let i = 0; i < 3; i++) await page.keyboard.press("Backspace");
await page.keyboard.type("egh", { delay: 40 });
verifie("après un effacement, la conversion reprend", await page.inputValue("#zone") === "ruheɣ", await page.inputValue("#zone"));
await page.keyboard.press("Control+z");
verifie("Ctrl+Z défait une conversion", (await page.inputValue("#zone")).endsWith("g"), await page.inputValue("#zone"));

const pret = await jusqua(async () => {
  const e = await etat();
  return e && e.moteur === "pret" ? e : null;
}, VRAI ? 120000 : 15000, 100);
verifie("le correcteur se charge dans le navigateur", !!pret, await etat());
if (!pret) await finir(1);
const mesures = { chargement: pret.secondes };

// 2. La barre des propositions

await page.fill("#zone", "");
await page.click("#zone");
await page.keyboard.type("nekk ttrugh", { delay: 50 });
let b = await barreAvec((x) => x.formes[0] === "ttruɣ");
verifie("la barre propose : ttruɣ en tête", !!b, await barre());
await capture("1-barre");
await page.keyboard.press("1");
verifie("1 choisit, suivi d'une espace", await page.inputValue("#zone") === "nekk ttruɣ ", await page.inputValue("#zone"));
b = await barreAvec((x) => x.formes.length > 0);
verifie("le mot fini, la barre propose la suite", !!b);
await page.keyboard.type("a", { delay: 40 });
b = await barreAvec((x) => x.formes.length && x.formes.every((f) => f.startsWith("a")));
verifie("une lettre : la complétion", !!b, await barre());
await page.keyboard.press("Escape");
verifie("Échap cache la barre", (await barre()) === null);
verifie("Échap n'écrit rien", await page.inputValue("#zone") === "nekk ttruɣ a");

await page.fill("#zone", "");
await page.click("#zone");
await page.keyboard.type("tamourt", { delay: 50 });
verifie("ou → u", await page.inputValue("#zone") === "tamurt", await page.inputValue("#zone"));

await page.click("#complete");
await page.keyboard.type("agh", { delay: 50 });
verifie("gh → ɣ quand la page complète et sélectionne la suite", await page.inputValue("#complete") === "aɣ",
  await page.inputValue("#complete"));
await page.click("#zone");
b = await barreAvec((x) => x.formes.includes("takurt"));
await cliquerDans(".forme", "takurt");
verifie("un clic choisit, et le curseur reste dans le champ",
  await page.inputValue("#zone") === "takurt " && await page.evaluate(() => document.activeElement.id) === "zone",
  await page.inputValue("#zone"));

// 3. Les fautes soulignées, la carte d'un mot

await page.fill("#zone", "");
await page.click("#zone");
await page.keyboard.type("Ruhegh gher tamettut. Nekk ttwalagh tamdint. ", { delay: 15 });
const n = await jusqua(() => ombre(`const n = racine.querySelectorAll(".calque .souligne").length; return n >= 3 ? n : null`));
verifie("les fautes se soulignent dans une zone de texte", n >= 3, n);
// Des mots connus que le contexte écrirait autrement : des doutes, en bleu, comme sur le téléphone.
const teinte = await ombre(`return decodeURIComponent([...racine.querySelectorAll(".calque .souligne")][0].style.backgroundImage)`);
verifie("un doute se souligne en bleu", /#0072BB/i.test(teinte || ""), teinte);
verifie("le correcteur de Chrome s'y tait", await page.getAttribute("#zone", "spellcheck") === "false");
await capture("2-soulignes");
const point = await ombre(`const s = [...racine.querySelectorAll(".calque .souligne")][1].getBoundingClientRect();
  return { x: s.left + s.width / 2, y: s.top - 6 };`);
await page.mouse.click(point.x, point.y);
const carte = await jusqua(() => ombre(`const c = racine.querySelector(".carte");
  return c && !c.classList.contains("cache") ? [...c.querySelectorAll(".prop")].map((x) => x.textContent) : null`), 4000);
verifie("un clic sur le mot souligné ouvre sa carte", carte && carte[0] === "tmeṭṭut", carte);
await attendre(400);
verifie("la carte ouverte, la barre attend", (await barre()) === null, await barre());
await capture("3-carte");
await cliquerDans(".carte .prop", "tmeṭṭut");
verifie("la carte remplace le mot", (await page.inputValue("#zone")).includes("ɣer tmeṭṭut."), await page.inputValue("#zone"));

// 4. Une ligne, un élément modifiable

await page.click("#ligne");
await page.keyboard.type("ghef ", { delay: 40 });
verifie("gh → ɣ dans une ligne", await page.inputValue("#ligne") === "ɣef ", await page.inputValue("#ligne"));

await page.click("#ed");
await page.keyboard.type("Ruhagh ghar tamettut. Aghrum", { delay: 30 });
const ed = () => page.evaluate(() => document.querySelector("#ed").innerText.replace(/ /g, " "));
verifie("gh → ɣ dans un élément modifiable", (await ed()).startsWith("Ruhaɣ ɣar tamettut. Aɣrum"), await ed());
b = await barreAvec((x) => x.formes[0] === "Aɣrum" && x.formes[1] === "Uɣrum");
verifie("la barre y propose, à la casse du mot", !!b, await barre());
await page.keyboard.press("2");
verifie("2 choisit dans un élément modifiable", (await ed()).trimEnd().endsWith("Uɣrum"), await ed());
const surlignes = await jusqua(() => page.evaluate(() => {
  const h = CSS.highlights.get("kab-board-doute");
  const mots = h ? [...h].map((r) => r.toString()) : [];
  return mots.length >= 3 ? mots : null;
}));
verifie("les fautes s'y soulignent, sans toucher au DOM", surlignes && surlignes.includes("tamettut"), surlignes);
await capture("4-editable");

// 5. Là où l'on n'écrit pas de kabyle

await page.click("#mdp");
await page.keyboard.type("ghar", { delay: 30 });
verifie("un mot de passe reste intact", await page.inputValue("#mdp") === "ghar");
await page.click("#courriel");
await page.keyboard.type("ghar", { delay: 30 });
verifie("un courriel reste intact", await page.inputValue("#courriel") === "ghar");

// 6. La correction automatique, allumée

await sw.evaluate(async () => {
  const r = await chrome.storage.sync.get("reglages");
  await chrome.storage.sync.set({ reglages: { ...(r.reglages || {}), autocorrection: true } });
});
await attendre(300);
await page.fill("#zone", "");
await page.click("#zone");
await page.keyboard.type("nekk ruhegh ", { delay: 50 });
const corrige = await jusqua(async () => (await page.inputValue("#zone")) === "nekk ruḥeɣ ", 5000);
verifie("à l'espace, un mot inconnu est corrigé", !!corrige, await page.inputValue("#zone"));
await capture("5-autocorrection");
await page.keyboard.press("Backspace");
verifie("Retour arrière rend le mot tapé", await page.inputValue("#zone") === "nekk ruheɣ ", await page.inputValue("#zone"));
await page.keyboard.type("ruhegh ", { delay: 50 });
await attendre(700);
verifie("puis le laisse tel quel", await page.inputValue("#zone") === "nekk ruheɣ ruheɣ ", await page.inputValue("#zone"));
await page.keyboard.type("tamurt ", { delay: 50 });
await attendre(700);
verifie("un mot connu n'est jamais corrigé d'office", (await page.inputValue("#zone")).endsWith(" tamurt "));
await sw.evaluate(async () => {
  const r = await chrome.storage.sync.get("reglages");
  await chrome.storage.sync.set({ reglages: { ...(r.reglages || {}), autocorrection: false } });
});

// 7. Les outils de la barre

await page.keyboard.type("aghrum", { delay: 30 });
await barreAvec((x) => x.formes[0] === "aɣrum");
await attendre(300);
const outils = await page.evaluateHandle(() => [...document.querySelector("kab-board-interface").shadowRoot
  .querySelectorAll(".barre .outil")].pop());
await outils.asElement().click();
verifie("le bouton des outils ouvre le panneau", ((await jusqua(() => panneau(), 3000)) || "").includes("Asegzawal"));
await cliquerDans(".panneau .bouton", "Asegzawal");
const fiche = await jusqua(() => panneau().then((t) => t && t.includes("pain") ? t : null), 5000);
verifie("Asegzawal : la fiche du mot sous le curseur", !!fiche, await panneau());
await capture("6-asegzawal");

// 8. La dictée : le micro et la transcription dans le document hors écran

await sw.evaluate(() => {
  chrome.runtime.onMessage.addListener((m) => {
    if (m && m.type === "horsecran-transcription") globalThis.__transcription = m;
  });
});
await page.click("#ligne");
await page.fill("#ligne", "");
await page.keyboard.type("a", { delay: 30 });
await barreAvec((x) => x.formes.length > 0);
await cliquerDans(".barre .outil", "🎤");
const ecoute = await barreAvec((x) => /écoute/.test(x.message), 6000);
verifie("la dictée écoute", !!ecoute, await barre());
await capture("7-dictee");
await attendre(AUDIO ? 6500 : 2500);
verifie("« Arrêter » répond pendant l'écoute", await cliquerDans(".barre .outil", "Arrêter"));
const debutDictee = Date.now();
const fin = await jusqua(() => panneau().then((t) => t && /Dictée/.test(t) ? t : null), 120000);
mesures.dictee = (Date.now() - debutDictee) / 1000;
verifie("la dictée va jusqu'au correcteur et revient", !!fin && !/impossible/.test(fin), fin);
const transcription = await sw.evaluate(() => globalThis.__transcription);
verifie("le son arrive au correcteur en 16 kHz, de la durée de l'écoute",
  transcription && transcription.secondes > 1.5 && transcription.secondes < 10, transcription);
const dit = (await page.inputValue("#ligne")).replace(/^a /, "").trim();
if (!VRAI) verifie("le texte dicté s'écrit au curseur, jamais corrigé", await page.inputValue("#ligne") === "a azul fell-awen ",
  await page.inputValue("#ligne"));
else if (DICTEE) verifie(`la voix jouée donne « ${DICTEE} »`, dit === DICTEE, dit);
else if (AUDIO) verifie(`la voix jouée est transcrite : « ${dit} »`, dit.length > 0, dit);

// 9. Le popup, la graphie, les réglages, « Écrire et relire »

const popup = await contexte.newPage();
await popup.setViewportSize({ width: 380, height: 760 });
await popup.goto(`chrome-extension://${ID}/popup/popup.html`);
await jusqua(() => popup.evaluate(() => document.getElementById("etat").className.includes("pret")), 8000);
verifie("le popup dit le correcteur prêt", await popup.evaluate(() => document.getElementById("etat").textContent).then((t) => /Prêt/.test(t)));
await popup.fill("#requete", "");
await popup.click("#requete");
await popup.keyboard.type("aghrum", { delay: 30 });
verifie("« écrire comme on parle » dans le popup", await popup.inputValue("#requete") === "aɣrum", await popup.inputValue("#requete"));
await popup.keyboard.press("Enter");
const fichePopup = await jusqua(() => popup.evaluate(() => {
  const t = document.getElementById("resultats").innerText;
  return t.includes("pain") ? t : null;
}), 5000);
verifie("Asegzawal dans le popup, avec les deux états", !!fichePopup && fichePopup.includes("uɣrum"), fichePopup);
await capture("8-popup", popup);
// Le temps de réponse de la barre, vu d'une page de l'extension : la requête passe par
// le fond, le document hors écran et le fil du correcteur.
mesures.barre = await popup.evaluate(async () => {
  const mots = ["ttruɣ", "tamurt", "ruheɣ", "aɣrum", "tamettut", "ass", "deg", "tazmamt", "azekka", "yella"];
  const durees = [];
  for (let i = 0; i < 100; i++) {
    const t = performance.now();
    await chrome.runtime.sendMessage({ type: "correcteur", requete: { quoi: "proposer", contexte: "nekk", mot: mots[i % 10] + "x".repeat(i % 3) } });
    durees.push(performance.now() - t);
  }
  durees.sort((a, b) => a - b);
  return { mediane: durees[50], p95: durees[95] };
});
await popup.click('button[data-graphie="b"]');
const graphieB = await jusqua(() => sw.evaluate(() => chrome.storage.sync.get("reglages").then((r) => r.reglages && r.reglages.graphie)), 3000);
verifie("la graphie b, choisie dans le popup, est gardée", graphieB === "b", graphieB);
await page.bringToFront();
await page.fill("#zone", "");
await page.click("#zone");
await page.keyboard.type("avrid", { delay: 40 });
b = await barreAvec((x) => x.formes[0] === "abrid", 5000);
verifie("et vaut pour la barre : avrid → abrid", !!b, await barre());
await popup.bringToFront();
await popup.click('button[data-graphie="v"]');
await popup.close();

const reglages = await contexte.newPage();
await reglages.goto(`chrome-extension://${ID}/pages/reglages.html`);
await reglages.fill("#nouveau-mot", "tamettut");
await reglages.click("#ajout button");
verifie("« mon dictionnaire » : un mot ajouté", !!await jusqua(() => reglages.evaluate(() => document.getElementById("mots").innerText.includes("tamettut")), 5000));
const fichier = path.join(TEMP, "mes_mots.txt");
fs.writeFileSync(fichier, "﻿Azul\r\ntamettut\r\nabrid\r\n");
await reglages.setInputFiles("#fichier", fichier);
const importe = await jusqua(() => reglages.evaluate(() => document.getElementById("importe").textContent || null), 5000);
verifie("un fichier s'importe, sans doublon", importe === "2 mots ajoutés.", importe);
const gardes = await sw.evaluate(() => chrome.storage.local.get("mesMots").then((r) => r.mesMots));
verifie("gardés dans Chrome, en minuscules", JSON.stringify(gardes) === JSON.stringify(["abrid", "azul", "tamettut"]), gardes);
await capture("9-reglages", reglages);
await reglages.close();
await page.bringToFront();
await page.fill("#zone", "");
await page.click("#zone");
await page.keyboard.type("Nekk ttwalagh tamettut. ", { delay: 15 });
const apres = await jusqua(() => ombre(`return racine.querySelectorAll(".calque .souligne").length === 1 ? 1 : null`), 8000);
verifie("un mot de mon dictionnaire ne se souligne plus", apres === 1, await ombre(`return racine.querySelectorAll(".calque .souligne").length`));

const ecrire = await contexte.newPage();
await ecrire.goto(`chrome-extension://${ID}/pages/ecrire.html`);
await ecrire.click("#texte");
await ecrire.keyboard.type("ruhegh ghar", { delay: 40 });
verifie("« Écrire et relire » : gh → ɣ", (await ecrire.inputValue("#texte")).endsWith("ruheɣ ɣar"), await ecrire.inputValue("#texte"));
verifie("« Écrire et relire » : la barre", !!await barreAvec((x) => x.formes.length > 0, 8000, ecrire));
await capture("10-ecrire", ecrire);
await ecrire.close();

// 10. Le repos et la panne : le document hors écran fermé, puis rouvert au premier mot

await sw.evaluate(() => fermer());
verifie("au repos, le document hors écran se ferme",
  await sw.evaluate(() => horsEcranOuvert()) === false && (await etat()).moteur === "arrete", await etat());
await page.bringToFront();
await page.click("#ligne");
await page.fill("#ligne", "");
await page.keyboard.type("ghef aghrum", { delay: 30 });
verifie("sans le correcteur, gh → ɣ marche encore", await page.inputValue("#ligne") === "ɣef aɣrum", await page.inputValue("#ligne"));
const repris = await jusqua(async () => (await etat()).moteur === "pret", VRAI ? 120000 : 15000, 100);
verifie("au premier champ, le correcteur se recharge", !!repris, await etat());
await page.keyboard.type("x", { delay: 30 });
await page.keyboard.press("Backspace");
// Après « ɣef », l'état d'annexion : uɣrum.
verifie("et la barre revient", !!await barreAvec((x) => x.formes.includes("uɣrum"), 8000), await barre());

// Le correcteur qui ne se charge pas (ici, son fil introuvable) : la copie de l'extension
// seulement.
if (!VRAI) {
  const travailleur = path.join(EXTENSION, "moteur", "travailleur.js");
  fs.renameSync(travailleur, travailleur + ".cache");
  await sw.evaluate(() => fermer());
  const panne = await contexte.newPage();
  await panne.goto(`chrome-extension://${ID}/pages/reglages.html`);
  verifie("un correcteur qui ne se charge pas : les réglages le disent", !!await jusqua(() => panne.evaluate(() =>
    !document.getElementById("panne").classList.contains("cache")), 8000), await etat());
  verifie("l'icône aussi", await sw.evaluate(() => chrome.action.getBadgeText({})) === "!");
  await capture("11-panne", panne);
  fs.renameSync(travailleur + ".cache", travailleur);
  await panne.click("#reessayer");
  verifie("« Réessayer » recharge le correcteur",
    !!await jusqua(async () => (await etat()).moteur === "pret", 15000, 100), await etat());
  verifie("et la page le dit", !!await jusqua(() => panne.evaluate(() =>
    document.getElementById("panne").classList.contains("cache")), 5000));
  await panne.close();
}

// La mémoire : celle des processus de Chromium, avec et sans le correcteur. La PSS
// partage entre eux ce qu'ils ont en commun : leur somme est ce qu'occupe Chromium.
if (VRAI && process.platform === "linux") {
  const memoire = () => {
    const pids = execFileSync("pgrep", ["-g", String(chrome.pid)]).toString().trim().split("\n");
    let total = 0;
    let plus = 0;
    for (const pid of pids) {
      try {
        const ligne = fs.readFileSync(`/proc/${pid}/smaps_rollup`, "utf8").match(/Pss:\s+(\d+)/);
        const ko = ligne ? Number(ligne[1]) : 0;
        total += ko;
        plus = Math.max(plus, ko);
      } catch { /* parti entre-temps */ }
    }
    return { total: Math.round(total / 1024), plus: Math.round(plus / 1024) };
  };
  mesures.avec = memoire();
  await sw.evaluate(() => fermer());
  await attendre(2000);
  mesures.sans = memoire();
}

if (VRAI) {
  console.log(`\nLe correcteur chargé en ${mesures.chargement.toFixed(1)} s ; la barre répond en ` +
    `${mesures.barre.mediane.toFixed(1)} ms (médiane), ${mesures.barre.p95.toFixed(1)} ms (95 %) ; ` +
    `la dictée transcrite en ${mesures.dictee.toFixed(1)} s.`);
  if (mesures.avec) {
    console.log(`Mémoire de Chromium (PSS) : ${mesures.avec.total} Mo avec le correcteur, ` +
      `${mesures.sans.total} Mo sans ; le plus gros processus : ${mesures.avec.plus} Mo.`);
  }
}
console.log(`\n${ok} vérifications passées, ${rates.length} échec(s)` + (VRAI ? " (vrai correcteur)" : " (faux correcteur)"));
await finir(rates.length ? 1 : 0);
