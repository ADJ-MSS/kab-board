import { monter, attendre, correcteurPret } from "./decor.mjs";
const SITES = [
  ["DeepL", "https://www.deepl.com/fr/translator"],
  ["Reddit", "https://www.reddit.com/"],
  ["GitHub", "https://github.com/"],
  ["Le Bon Coin", "https://www.leboncoin.fr/"],
  ["Bing", "https://www.bing.com/?setlang=fr"],
];
const d = await monter();
const page = await d.contexte.newPage();
await page.setViewportSize({ width: 1280, height: 900 });
await page.goto(d.SITE.replace("tabrat.exemple", "127.0.0.1")); await page.click("#zone"); await page.keyboard.type("a");
await correcteurPret(d.sw);
const barreDans = (f) => f.evaluate(() => { const h = document.querySelector("kab-board-interface"); const b = h && h.shadowRoot && h.shadowRoot.querySelector(".barre");
  return b && !b.classList.contains("cache") ? [...b.querySelectorAll(".forme .mot")].map((x) => x.textContent).join(" ") : ""; }).catch(() => "?");
for (const [nom, url] of SITES) {
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 25000 });
    await attendre(4000);
    for (const t of ["Tout accepter", "Accepter tout", "Accept all", "Accepter & Fermer", "Accepter", "Reject all", "Tout refuser", "Continuer sans accepter"]) {
      const b = page.locator(`button:has-text("${t}")`).first();
      if (await b.count() && await b.isVisible().catch(() => false)) { await b.click().catch(() => {}); await attendre(1500); break; }
    }
    const cible = await page.evaluate(() => {
      const tous = (r) => [...r.querySelectorAll("*")].flatMap((e) => [e, ...(e.shadowRoot ? tous(e.shadowRoot) : [])]);
      const ok = tous(document).filter((e) => (e.matches("textarea, input[type=search], input[type=text], input:not([type])") || e.isContentEditable && e.getAttribute("contenteditable") !== null)
        && !e.disabled && !e.readOnly).map((e) => ({ e, r: e.getBoundingClientRect() })).filter((x) => x.r.width > 80 && x.r.height > 15 && x.r.top >= 0 && x.r.top < innerHeight);
      ok.sort((a, b) => a.r.top - b.r.top);
      const x = ok[0]; if (!x) return null;
      return { x: x.r.left + Math.min(40, x.r.width / 2), y: x.r.top + x.r.height / 2, quoi: x.e.tagName + (x.e.id ? "#" + x.e.id : "") + " " + (x.e.getAttribute("type") || (x.e.isContentEditable ? "editable" : "")) };
    });
    if (!cible) { console.log(`--- ${nom} : aucun champ visible`); await page.screenshot({ path: `site2-${nom}.png` }); continue; }
    await page.mouse.click(cible.x, cible.y);
    await page.keyboard.type("ruhagh", { delay: 70 });
    await attendre(3000);
    const v = await page.evaluate(() => { let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement;
      return a ? (a.value !== undefined ? a.value : a.innerText) : ""; });
    let b = await barreDans(page);
    if (!b) for (const f of page.frames()) { b = await barreDans(f); if (b && b !== "?") break; }
    console.log(`${/ruhaɣ/.test(v) ? "ok " : "NON"} conversion · ${b && b !== "?" ? "ok " : "NON"} barre   ${nom.padEnd(12)} ${cible.quoi.padEnd(28)} ${JSON.stringify((v || "").slice(-16))}`);
    await page.screenshot({ path: `site2-${nom.replace(/\W+/g, "-")}.png` });
  } catch (e) { console.log(`ERR ${nom}: ${e.message.split("\n")[0].slice(0, 120)}`); }
}
await d.fermer();
