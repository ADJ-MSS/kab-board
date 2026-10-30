// Tous les genres de champs du web : la conversion gh → ɣ et la barre, champ par champ.
import { monter, attendre, correcteurPret } from "./decor.mjs";

const CADRE = `<!doctype html><meta charset="utf-8"><textarea id="t" style="width:300px;height:60px"></textarea>`;
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>Champs</title>
<style>body{font:15px sans-serif;margin:16px} .c{margin:8px 0} textarea,input,[contenteditable]{width:360px;font-size:16px}
[contenteditable]{border:1px solid #999;min-height:24px;padding:4px}</style></head><body>
<div class="c">A <textarea id="A"></textarea></div>
<div class="c">B <input id="B"></div>
<div class="c">C <input id="C" type="search"></div>
<div class="c">D <input id="D" type="text" autocomplete="off"></div>
<div class="c">E <input id="E" type="text" autocomplete="username"></div>
<div class="c">F <input id="F" type="text" autocomplete="name"></div>
<div class="c">G <div id="G" contenteditable="true"></div></div>
<div class="c">H <div id="H" contenteditable="plaintext-only"></div></div>
<div class="c">I <div id="I" role="textbox" contenteditable="true" aria-multiline="true"></div></div>
<div class="c">J <span id="J"></span></div>
<div class="c">K <span id="K"></span></div>
<div class="c">L <span id="L"></span></div>
<div class="c">M <iframe id="M" src="/cadre" style="height:80px"></iframe></div>
<div class="c">N <iframe id="N" src="http://autre.exemple:PORT/cadre" style="height:80px"></iframe></div>
<div class="c">O <iframe id="O" srcdoc='<textarea id="t"></textarea>' style="height:80px"></iframe></div>
<div class="c">P <iframe id="P" style="height:80px"></iframe></div>
<div class="c">Q <span id="Q"></span></div>
<dialog id="R" open style="position:static">R <textarea id="Rt"></textarea></dialog>
<div class="c">S <input id="S" type="email"></div>
<div class="c">T <input id="T" type="url"></div>
<div class="c">U <input id="U" type="tel"></div>
<div class="c">V <textarea id="V" spellcheck="false"></textarea></div>
<div class="c">W <textarea id="W"></textarea></div>
<div class="c">Z <iframe id="Z" style="height:80px"></iframe></div>
<script>
document.getElementById("J").attachShadow({mode:"open"}).innerHTML = '<input id="ji" style="width:300px">';
document.getElementById("K").attachShadow({mode:"open"}).innerHTML = '<div id="ki" contenteditable="true" style="border:1px solid #999;min-height:24px;width:300px"></div>';
window.__fermee = document.getElementById("L").attachShadow({mode:"closed"});
window.__fermee.innerHTML = '<textarea id="li" style="width:300px"></textarea>';
const p = document.getElementById("P").contentDocument; p.open(); p.write('<textarea id="t"></textarea>'); p.close();
setTimeout(() => { const t = document.createElement("textarea"); t.id = "Qt"; document.getElementById("Q").appendChild(t); }, 1500);
// Un éditeur qui garde les touches pour lui, comme certains sites
window.addEventListener("keydown", (e) => { if (e.target.id === "W") e.stopImmediatePropagation(); }, true);
const z = document.getElementById("Z").contentDocument; z.open(); z.write('<body>texte : </body>'); z.close(); z.designMode = "on";
</script></body></html>`;

const pages = { "/cadre": CADRE };
const d = await monter({ pages });
const port = new URL(d.SITE).port;
const page = await d.contexte.newPage();
await page.setViewportSize({ width: 900, height: 2200 });
const url = d.SITE.replace(/\/$/, "") + "/champs";
// la page avec le bon port pour l'iframe d'une autre origine
pages["/champs"] = PAGE.replace("PORT", port);
await page.goto(url);
await attendre(2500);
// réveiller le correcteur
await page.click("#A"); await page.keyboard.type("a");
await correcteurPret(d.sw);
await page.fill("#A", "");

const barreDans = (f) => f.evaluate(() => {
  const h = document.querySelector("kab-board-interface");
  const b = h && h.shadowRoot && h.shadowRoot.querySelector(".barre");
  return b && !b.classList.contains("cache") ? [...b.querySelectorAll(".forme .mot")].map((x) => x.textContent).join(" ") : "";
}).catch(() => "?");

const cas = [
  ["A textarea", () => page.locator("#A"), page, () => page.inputValue("#A")],
  ["B input sans type", () => page.locator("#B"), page, () => page.inputValue("#B")],
  ["C input search", () => page.locator("#C"), page, () => page.inputValue("#C")],
  ["D autocomplete=off", () => page.locator("#D"), page, () => page.inputValue("#D")],
  ["E autocomplete=username", () => page.locator("#E"), page, () => page.inputValue("#E")],
  ["F autocomplete=name", () => page.locator("#F"), page, () => page.inputValue("#F")],
  ["G contenteditable", () => page.locator("#G"), page, () => page.locator("#G").innerText()],
  ["H plaintext-only", () => page.locator("#H"), page, () => page.locator("#H").innerText()],
  ["I role=textbox", () => page.locator("#I"), page, () => page.locator("#I").innerText()],
  ["J ombre ouverte, input", () => page.locator("#ji"), page, () => page.locator("#ji").inputValue()],
  ["K ombre ouverte, éditable", () => page.locator("#ki"), page, () => page.locator("#ki").innerText()],
  ["L ombre fermée", () => page.locator("#L"), page, () => page.evaluate(() => window.__fermee.querySelector("#li").value)],
  ["M iframe même origine", () => page.frameLocator("#M").locator("#t"), () => page.frame({ url: /\/cadre$/ }), () => page.frameLocator("#M").locator("#t").inputValue()],
  ["N iframe autre origine", () => page.frameLocator("#N").locator("#t"), () => page.frames().find((f) => f.url().includes("autre.exemple")), () => page.frameLocator("#N").locator("#t").inputValue()],
  ["O iframe srcdoc", () => page.frameLocator("#O").locator("#t"), () => page.frames().find((f) => f.url() === "about:srcdoc"), () => page.frameLocator("#O").locator("#t").inputValue()],
  ["P iframe about:blank", () => page.frameLocator("#P").locator("#t"), () => page.frames().find((f) => f.url() === "about:blank"), () => page.frameLocator("#P").locator("#t").inputValue()],
  ["Q ajouté après coup", () => page.locator("#Qt"), page, () => page.inputValue("#Qt")],
  ["R dans un dialog", () => page.locator("#Rt"), page, () => page.inputValue("#Rt")],
  ["S email (exclu)", () => page.locator("#S"), page, () => page.inputValue("#S")],
  ["T url", () => page.locator("#T"), page, () => page.inputValue("#T")],
  ["U tel", () => page.locator("#U"), page, () => page.inputValue("#U")],
  ["V spellcheck=false", () => page.locator("#V"), page, () => page.inputValue("#V")],
  ["W touches gardées par la page", () => page.locator("#W"), page, () => page.inputValue("#W")],
  ["Z designMode", () => page.frameLocator("#Z").locator("body"), () => page.frames().find((f, i) => i > 0 && f.url() === "about:blank" && f !== page.frames().find((g) => g.url() === "about:blank")), () => page.frameLocator("#Z").locator("body").innerText()],
];

for (const [nom, loc, cadre, lire] of cas) {
  try {
    const l = loc();
    await l.click({ timeout: 5000 });
    await page.keyboard.press("End");
    await page.keyboard.type(" ruhagh", { delay: 50 });
    await attendre(2500);
    const v = await lire();
    const f = typeof cadre === "function" ? cadre() : cadre;
    const b = f ? await barreDans(f) : "?";
    console.log(`${v.includes("ruhaɣ") ? "ok " : "NON"} conversion · ${b ? "ok " : "NON"} barre   ${nom.padEnd(30)} ${JSON.stringify(v.slice(-12))}  ${b.slice(0, 40)}`);
    await page.keyboard.press("Escape");
  } catch (e) {
    console.log(`ERR ${nom}: ${e.message.split("\n")[0]}`);
  }
}
await d.fermer();
