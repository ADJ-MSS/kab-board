// Les captures du manuel, avec le vrai correcteur.
import fs from "node:fs";
import path from "node:path";
import { monter, capturerPopup, ID, barre, barreAvec, cliquerDans, panneau, ombre, attendre, jusqua, correcteurPret } from "./decor.mjs";

const SORTIE = path.join(path.dirname(new URL(import.meta.url).pathname), "..", "captures");
fs.mkdirSync(SORTIE, { recursive: true });
const journal = (...a) => console.log(...a);

// Les captures passent par le protocole de débogage : Playwright ramènerait l'échelle à 1.
const sessions = new WeakMap();
async function nette(page, largeur, hauteur) {
  const s = await page.context().newCDPSession(page);
  sessions.set(page, { s, largeur, hauteur });
  await s.send("Emulation.setDeviceMetricsOverride", { width: largeur, height: hauteur, deviceScaleFactor: 2, mobile: false });
}
const cap = async (page, nom, options = {}) => {
  const { s, largeur, hauteur } = sessions.get(page);
  let h = hauteur;
  if (options.fullPage) {
    const m = await s.send("Page.getLayoutMetrics");
    h = Math.ceil(m.cssContentSize.height);
    await s.send("Emulation.setDeviceMetricsOverride", { width: largeur, height: h, deviceScaleFactor: 2, mobile: false });
    await attendre(300);
  }
  const { data } = await s.send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(SORTIE, nom + ".png"), Buffer.from(data, "base64"));
  if (h !== hauteur) await s.send("Emulation.setDeviceMetricsOverride", { width: largeur, height: hauteur, deviceScaleFactor: 2, mobile: false });
  journal("  capture", nom);
};
async function taper(page, champ, texte, delai = 45) {
  await page.fill(champ, "");
  await page.click(champ);
  await page.keyboard.type(texte, { delay: delai });
}

// ─── Avec Kab-board installé ───────────────────────────────────────────────────
const d = await monter({ audio: path.join(path.dirname(new URL(import.meta.url).pathname), "voix.wav") });

// La page qui s'ouvre à l'installation
if (d.ouvertes.length) {
  const accueil = d.ouvertes[0];
  journal("page d'accueil :", accueil.url());
}

/** L'encart publicitaire de Chrome, dans sa colonne de gauche, et l'avis d'un navigateur
 * géré (celui d'une machine d'essai) : ils n'ont rien à faire dans le manuel. */
const sansEncart = (p) => p.evaluate(() => {
  const tous = (racine) => [racine, ...[...racine.querySelectorAll("*")].flatMap((e) => e.shadowRoot ? tous(e.shadowRoot) : [])];
  for (const r of tous(document)) for (const e of r.querySelectorAll("*")) {
    if (e.localName === "managed-footnote") e.style.display = "none";
    if (e.children.length < 3 && /agents de codage/i.test(e.textContent || "")) {
      // Le plus grand bloc qui ne contient que l'encart.
      let bloc = e;
      while (bloc.parentElement && (bloc.parentElement.textContent || "").length < 400) bloc = bloc.parentElement;
      bloc.style.visibility = "hidden";
    }
  }
});

// chrome://extensions et les raccourcis
const ext = await d.contexte.newPage();
await nette(ext, 1100, 640);
await ext.goto("chrome://extensions");
await attendre(1500);
await sansEncart(ext);
await cap(ext, "01-extensions");
await ext.goto("chrome://extensions/shortcuts");
await attendre(1500);
await sansEncart(ext);
await cap(ext, "02-raccourcis");
await ext.close();

// La page de l'exemple
const page = await d.contexte.newPage();
await nette(page, 900, 620);
page.on("pageerror", (e) => journal("   [page] " + e.message));
await page.goto(d.SITE);
await page.click("#zone");
await page.keyboard.type("a", { delay: 30 });
const pret = await correcteurPret(d.sw);
journal("correcteur prêt :", !!pret);
for (const p of d.contexte.pages()) if (p.url().startsWith("chrome-extension://") && p !== page) await p.close();

// Écrire comme on parle, et la barre
await taper(page, "#zone", "Azul fell-awen. Iḍelli ruhagh");
await barreAvec(page, (b) => b.formes[0] === "ruḥeɣ");
await attendre(300);
await cap(page, "03-barre-correction");

await taper(page, "#zone", "Azul fell-awen. Tam");
await barreAvec(page, (b) => b.formes.includes("tamurt"));
await attendre(300);
await cap(page, "04-barre-completion");

await taper(page, "#zone", "Azul fell-awen. Tamurt ");
await barreAvec(page, (b) => b.formes.length > 3);
await attendre(300);
await cap(page, "05-barre-prediction");

await taper(page, "#zone", "tamurt iw");
await barreAvec(page, (b) => b.formes[0] === "tamurt-iw");
await attendre(300);
await cap(page, "06-barre-possessif");
await cliquerDans(page, ".forme", "tamurt-iw");
await attendre(500);
journal("possessif choisi :", JSON.stringify(await page.inputValue("#zone")));
await cap(page, "07-possessif-choisi");
await page.keyboard.press("Escape");

// Les soulignés et la carte
await page.fill("#zone", "");
await page.click("#zone");
await page.keyboard.type("Ruhegh gher tamettut. Nekk ttwalagh tamdint, tamurt iw tecbeh aṭas. ", { delay: 15 });
await page.keyboard.press("Escape");
const n = await jusqua(() => ombre(page, `const n = racine.querySelectorAll(".calque .souligne").length; return n >= 3 ? n : null`), 20000);
journal("soulignés :", n);
await attendre(800);
await page.keyboard.press("Escape");
await attendre(400);
await cap(page, "08-soulignes");
const point = await ombre(page, `const s = [...racine.querySelectorAll(".calque .souligne")][1].getBoundingClientRect();
  return { x: s.left + s.width / 2, y: s.top - 6 };`);
await page.mouse.click(point.x, point.y);
await jusqua(() => ombre(page, `const c = racine.querySelector(".carte"); return c && !c.classList.contains("cache")`), 5000);
await attendre(500);
await cap(page, "09-carte");
await page.keyboard.press("Escape");

// Un élément modifiable (un éditeur riche)
await page.click("#ed");
await page.keyboard.type("Ass-a nruh ghar lexla, nwala ttyur d iseklan. ", { delay: 20 });
await page.keyboard.press("Escape");
await attendre(4000);
await cap(page, "10-editable");

// Les outils de la barre
await taper(page, "#zone", "Ččiɣ aghrum");
await barreAvec(page, (b) => b.formes.length > 0);
const outils = await page.evaluateHandle(() => [...document.querySelector("kab-board-interface").shadowRoot
  .querySelectorAll(".barre .outil")].pop());
await outils.asElement().click();
await jusqua(() => panneau(page), 4000);
await attendre(400);
await cap(page, "11-outils");
await cliquerDans(page, ".panneau .bouton", "Asegzawal");
await jusqua(() => panneau(page).then((t) => t && /pain/.test(t)), 6000);
await attendre(400);
await cap(page, "12-asegzawal");

async function fermerPanneau() {
  const r = await ombre(page, `const f = racine.querySelector(".panneau:not(.cache) .fermer");
    if (!f) return null; const b = f.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 };`);
  if (r) { await page.mouse.click(r.x, r.y); await attendre(300); }
}
async function outil(nom) {
  await fermerPanneau();
  await attendre(300);
  await page.click("#zone");
  await page.keyboard.press("End");
  // La barre revient dès que la saisie bouge.
  await page.keyboard.type(" ", { delay: 30 });
  await page.keyboard.press("Backspace");
  await barreAvec(page, (b) => b.formes.length > 0, 8000);
  const h = await page.evaluateHandle(() => [...document.querySelector("kab-board-interface").shadowRoot
    .querySelectorAll(".barre .outil")].pop());
  if (h.asElement()) await h.asElement().click();
  await jusqua(() => panneau(page), 4000);
  await cliquerDans(page, ".panneau .bouton", nom);
}

await outil("fr → kab");
await attendre(500);
await page.keyboard.type("pain", { delay: 40 });
await page.keyboard.press("Enter");
await jusqua(() => panneau(page).then((t) => t && /aɣrum/.test(t)), 6000);
await attendre(500);
await cap(page, "13-fr-kab");

await outil("Mot du jour");
await jusqua(() => panneau(page).then((t) => t && !/…$/.test(t.trim())), 6000);
await attendre(600);
await cap(page, "14-mot-du-jour");

await outil("ɣ ɛ ḍ ḥ…");
await attendre(600);
await cap(page, "15-lettres");

// Relire un champ, et tout corriger
await fermerPanneau();
await page.fill("#zone", "");
await page.click("#zone");
await page.keyboard.type("Ruhegh gher tamettut. Nekk ttwalagh tamdint, tamurt iw tecbeh aṭas.", { delay: 10 });
await page.keyboard.press("Escape");
await attendre(1500);
await outil("Relire");
await jusqua(() => panneau(page).then((t) => t && /Tout corriger/.test(t)), 15000);
await attendre(600);
await cap(page, "16-relire");

// La dictée
await fermerPanneau();
await taper(page, "#sujet", "a");
await barreAvec(page, (b) => b.formes.length > 0);
await page.fill("#sujet", "");
await page.keyboard.type("Azul! ", { delay: 30 });
await barreAvec(page, (b) => b.formes.length > 0);
await cliquerDans(page, ".barre .outil", "🎤");
const ecoute = await barreAvec(page, (b) => /écoute/.test(b.message), 8000);
journal("dictée :", JSON.stringify(ecoute));
await attendre(2200);
await cap(page, "17-dictee");
await attendre(3600);
await cliquerDans(page, ".barre .outil", "Arrêter");
await jusqua(async () => (await page.inputValue("#sujet")).length > 8 || /Dictée/.test(await panneau(page) || ""), 60000);
await attendre(800);
journal("dicté :", JSON.stringify(await page.inputValue("#sujet")), JSON.stringify(await panneau(page)));
await cap(page, "18-dictee-finie");

// Un mot de passe : rien
await fermerPanneau();
await taper(page, "#mdp", "ghaghagh");
await attendre(800);
journal("mot de passe :", JSON.stringify(await page.inputValue("#mdp")), JSON.stringify(await barre(page)));

// Le popup, ouvert au-dessus du site comme par son bouton
async function popupReel(nom, avant = null) {
  await page.bringToFront();
  await d.sw.evaluate(() => chrome.action.openPopup());
  await attendre(1500);
  const r = await capturerPopup(d.port, path.join(SORTIE, nom + ".png"), avant);
  journal("  capture", nom, JSON.stringify(r));
}
await page.click("#zone");
await popupReel("19-popup");
await popupReel("20-popup-reglages", `(async () => { document.querySelector("details").open = true;
  await new Promise((r) => setTimeout(r, 300)); document.scrollingElement.scrollTop = 1e6; return true; })()`);
await popupReel("21-popup-asegzawal", `(async () => { document.querySelector("#requete").value = "aɣrum";
  document.querySelector("#formulaire").requestSubmit(); await new Promise((r) => setTimeout(r, 2000)); return true; })()`);

// Les réglages
const reglages = await d.contexte.newPage();
await nette(reglages, 860, 900);
await reglages.goto(`chrome-extension://${ID}/pages/reglages.html`);
await attendre(1500);
await cap(reglages, "22-reglages", { fullPage: true });
await reglages.close();

// Écrire et relire
const ecrire = await d.contexte.newPage();
await nette(ecrire, 900, 620);
await ecrire.goto(`chrome-extension://${ID}/pages/ecrire.html`);
await attendre(1000);
await ecrire.click("textarea");
await ecrire.keyboard.type("Azul fell-awen! Ass-a ruhegh ghar temdint, ttwalagh tamettut", { delay: 30 });
await barreAvec(ecrire, (b) => b.formes.length > 0);
await attendre(800);
await cap(ecrire, "23-ecrire-relire");
await ecrire.close();

// L'autorisation du micro
const micro = await d.contexte.newPage();
await nette(micro, 760, 420);
await micro.goto(`chrome-extension://${ID}/pages/micro.html`);
await attendre(1500);
await cap(micro, "24-micro");
await micro.close();

// La graphie b, choisie dans le popup
const p2 = await d.contexte.newPage();
await p2.goto(`chrome-extension://${ID}/popup/popup.html`);
await attendre(1200);
await p2.click('#graphie button[data-graphie="b"]');
await attendre(1500);
await p2.close();
await page.bringToFront();
await taper(page, "#zone", "Azul fell-awen. Tamurt ");
await barreAvec(page, (b) => b.formes.length > 3);
await attendre(300);
journal("graphie b :", JSON.stringify(await barre(page)));
await cap(page, "25-graphie-b");

journal("pages ouvertes :", d.contexte.pages().map((p) => p.url()));
await d.fermer();

// ─── Un correcteur qui ne se charge pas ───────────────────────────────────────
const s = await monter({ panne: true });
const reglagesPanne = s.ouvertes.find((p) => p.url().includes("reglages.html")) || await s.contexte.newPage();
if (!reglagesPanne.url().includes("reglages.html")) await reglagesPanne.goto(`chrome-extension://${ID}/pages/reglages.html`);
await nette(reglagesPanne, 860, 900);
await jusqua(() => reglagesPanne.evaluate(() => !document.getElementById("panne").classList.contains("cache")), 15000);
await attendre(800);
await cap(reglagesPanne, "26-panne-reglages");
const q = await s.contexte.newPage();
await nette(q, 900, 620);
await q.goto(s.SITE);
await q.click("#zone");
await q.keyboard.type("ruhagh", { delay: 40 });
await attendre(3000);
journal("en panne :", JSON.stringify(await q.inputValue("#zone")), JSON.stringify(await barre(q)));
await cap(q, "27-panne-site");
await q.bringToFront();
await s.sw.evaluate(() => chrome.action.openPopup());
await attendre(2500);
journal("  capture 28-panne-popup", JSON.stringify(
  await capturerPopup(s.port, path.join(SORTIE, "28-panne-popup.png"))));
await s.fermer();
journal("fini");
