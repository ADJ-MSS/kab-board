// L'essai de l'extension dans un vrai navigateur, le même pour Chromium et pour Firefox.
// Les lanceurs préparent le navigateur et l'extension (chrome/tests/essai_navigateur.mjs,
// avec Playwright ; firefox/tests/essai_firefox.mjs, avec Puppeteer), puis ceci tape dans
// une page comme le ferait quelqu'un, et vérifie.
//
// Le lanceur donne n : SITE (la page d'essai), EXTENSION (son dossier), TEMP, VRAI, AUDIO,
// DICTEE, CAPTURES ; url(chemin), une adresse de l'extension ; nouvellePage(), une page
// qui répond comme celles de Playwright ; fond(f, x), f(g, x) évaluée dans le fond de
// l'extension, g étant son objet global ; memoire(), s'il sait la mesurer.
import fs from "node:fs";
import path from "node:path";

let ok = 0;
const rates = [];
export function verifie(intitule, condition, detail) {
  if (condition) {
    ok++;
    console.log("  ok      " + intitule);
  } else {
    rates.push(intitule);
    console.log("  ÉCHEC   " + intitule + (detail === undefined ? "" : "  " + JSON.stringify(detail)));
  }
}
export const bilan = () => ({ ok, rates });
export const attendre = (ms) => new Promise((r) => setTimeout(r, ms));
export async function jusqua(f, delai = 15000, pas = 100) {
  const fin = Date.now() + delai;
  let v;
  while (Date.now() < fin) {
    v = await f();
    if (v) return v;
    await attendre(pas);
  }
  return v;
}

/** La mémoire d'un navigateur sous Linux : la somme des PSS de racine et de ses
 * descendants, qui partage entre eux ce qu'ils ont en commun ; et le plus gros. En Mo. */
export function memoireDe(racine) {
  const parents = new Map();
  for (const pid of fs.readdirSync("/proc").filter((x) => /^\d+$/.test(x))) {
    try {
      const stat = fs.readFileSync(`/proc/${pid}/stat`, "utf8");
      parents.set(pid, stat.slice(stat.lastIndexOf(")") + 2).split(" ")[1]);
    } catch { /* parti entre-temps */ }
  }
  const famille = new Set([String(racine)]);
  for (let encore = true; encore;) {
    encore = false;
    for (const [pid, parent] of parents) {
      if (!famille.has(pid) && famille.has(parent)) {
        famille.add(pid);
        encore = true;
      }
    }
  }
  let total = 0;
  let plus = 0;
  for (const pid of famille) {
    try {
      const ligne = fs.readFileSync(`/proc/${pid}/smaps_rollup`, "utf8").match(/Pss:\s+(\d+)/);
      const ko = ligne ? Number(ligne[1]) : 0;
      total += ko;
      plus = Math.max(plus, ko);
    } catch { /* parti entre-temps */ }
  }
  return { total: Math.round(total / 1024), plus: Math.round(plus / 1024) };
}

/** Le parcours : rend les mesures (chargement, barre, dictée, mémoire). */
export async function scenario(n) {
  const { SITE, TEMP, VRAI, AUDIO, DICTEE, CAPTURES } = n;
  const page = await n.nouvellePage();
  await page.goto(SITE);

  const etat = () => n.fond(async (g) => (await g.chrome.storage[g.KabCommun.zoneEtat()].get("etat")).etat);
  const capture = async (nom, p = page) => {
    if (CAPTURES) await p.screenshot({ path: path.join(CAPTURES, nom + ".png") });
  };
  /** Ce que montre l'extension dans la page (sa racine d'ombre) : corps est le texte d'une
   * fonction de racine, évalué tel quel (une page de l'extension refuserait new Function). */
  const ombre = (corps, p = page) => p.evaluate(`(() => {
    const hote = document.querySelector("kab-board-interface");
    return hote && hote.shadowRoot ? ((racine) => { ${corps} })(hote.shadowRoot) : null;
  })()`);
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
  if (!pret) return { mesures: {} };
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
  const nb = await jusqua(() => ombre(`const n = racine.querySelectorAll(".calque .souligne").length; return n >= 3 ? n : null`));
  verifie("les fautes se soulignent dans une zone de texte", nb >= 3, nb);
  // Des mots connus que le contexte écrirait autrement : des doutes, en bleu, comme sur le téléphone.
  const teinte = await ombre(`return decodeURIComponent([...racine.querySelectorAll(".calque .souligne")][0].style.backgroundImage)`);
  verifie("un doute se souligne en bleu", /#0072BB/i.test(teinte || ""), teinte);
  verifie("le correcteur du navigateur s'y tait", await page.getAttribute("#zone", "spellcheck") === "false");
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

  await n.fond(async (g) => {
    const r = await g.chrome.storage.sync.get("reglages");
    await g.chrome.storage.sync.set({ reglages: { ...(r.reglages || {}), autocorrection: true } });
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
  await n.fond(async (g) => {
    const r = await g.chrome.storage.sync.get("reglages");
    await g.chrome.storage.sync.set({ reglages: { ...(r.reglages || {}), autocorrection: false } });
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

  // 8. La dictée : le micro et la transcription, là où tourne le correcteur

  await n.fond((g) => {
    g.chrome.runtime.onMessage.addListener((m) => {
      if (m && m.type === "horsecran-transcription") g.__transcription = { secondes: m.secondes };
    });
  });
  await page.click("#ligne");
  await page.fill("#ligne", "");
  await page.keyboard.type("a", { delay: 30 });
  await barreAvec((x) => x.formes.length > 0);
  const clic = Date.now();
  await cliquerDans(".barre .outil", "🎤");
  const ecoute = await barreAvec((x) => /écoute/.test(x.message), 10000);
  mesures.micro = (Date.now() - clic) / 1000;
  verifie("la dictée écoute", !!ecoute, await barre());
  await capture("7-dictee");
  await attendre(AUDIO ? 6500 : 2500);
  verifie("« Arrêter » répond pendant l'écoute", await cliquerDans(".barre .outil", "Arrêter"));
  const debutDictee = Date.now();
  const fin = await jusqua(() => panneau().then((t) => t && /Dictée/.test(t) ? t : null), 120000);
  mesures.dictee = (Date.now() - debutDictee) / 1000;
  verifie("la dictée va jusqu'au correcteur et revient", !!fin && !/impossible/.test(fin), fin);
  const transcription = await n.fond((g) => g.__transcription);
  verifie("le son arrive au correcteur en 16 kHz, de la durée de l'écoute",
    transcription && transcription.secondes > 1.5 && transcription.secondes < 10, transcription);
  const dit = (await page.inputValue("#ligne")).replace(/^a /, "").trim();
  if (!VRAI) verifie("le texte dicté s'écrit au curseur, jamais corrigé", await page.inputValue("#ligne") === "a azul fell-awen ",
    await page.inputValue("#ligne"));
  else if (DICTEE) verifie(`la voix jouée donne « ${DICTEE} »`, dit === DICTEE, dit);
  else if (AUDIO) verifie(`la voix jouée est transcrite : « ${dit} »`, dit.length > 0, dit);

  // 9. Le popup, la graphie, les réglages, « Écrire et relire »

  const popup = await n.nouvellePage();
  await popup.setViewportSize({ width: 380, height: 760 });
  await popup.goto(n.url("popup/popup.html"));
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
  const graphieB = await jusqua(() => n.fond(async (g) => ((await g.chrome.storage.sync.get("reglages")).reglages || {}).graphie), 3000);
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

  const reglages = await n.nouvellePage();
  await reglages.goto(n.url("pages/reglages.html"));
  await reglages.fill("#nouveau-mot", "tamettut");
  await reglages.click("#ajout button");
  verifie("« mon dictionnaire » : un mot ajouté", !!await jusqua(() => reglages.evaluate(() => document.getElementById("mots").innerText.includes("tamettut")), 5000));
  const fichier = path.join(TEMP, "mes_mots.txt");
  fs.writeFileSync(fichier, "\uFEFFAzul\r\ntamettut\r\nabrid\r\n");
  await reglages.setInputFiles("#fichier", fichier);
  const importe = await jusqua(() => reglages.evaluate(() => document.getElementById("importe").textContent || null), 5000);
  verifie("un fichier s'importe, sans doublon", importe === "2 mots ajoutés.", importe);
  const gardes = await n.fond(async (g) => (await g.chrome.storage.local.get("mesMots")).mesMots);
  verifie("gardés par le navigateur, en minuscules", JSON.stringify(gardes) === JSON.stringify(["abrid", "azul", "tamettut"]), gardes);
  await capture("9-reglages", reglages);
  await reglages.close();
  await page.bringToFront();
  await page.fill("#zone", "");
  await page.click("#zone");
  await page.keyboard.type("Nekk ttwalagh tamettut. ", { delay: 15 });
  const apres = await jusqua(() => ombre(`return racine.querySelectorAll(".calque .souligne").length === 1 ? 1 : null`), 8000);
  verifie("un mot de mon dictionnaire ne se souligne plus", apres === 1, await ombre(`return racine.querySelectorAll(".calque .souligne").length`));

  const ecrire = await n.nouvellePage();
  await ecrire.goto(n.url("pages/ecrire.html"));
  await ecrire.click("#texte");
  await ecrire.keyboard.type("ruhegh ghar", { delay: 40 });
  verifie("« Écrire et relire » : gh → ɣ", (await ecrire.inputValue("#texte")).endsWith("ruheɣ ɣar"), await ecrire.inputValue("#texte"));
  verifie("« Écrire et relire » : la barre", !!await barreAvec((x) => x.formes.length > 0, 8000, ecrire));
  await capture("10-ecrire", ecrire);
  await ecrire.close();

  // 10. Le repos et la panne : le correcteur fermé, puis rouvert au premier mot

  await n.fond((g) => g.fermer());
  verifie("au repos, le correcteur se ferme",
    await n.fond((g) => g.KabPlateforme.ouvert()) === false && (await etat()).moteur === "arrete", await etat());
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
    const travailleur = path.join(n.EXTENSION, "moteur", "travailleur.js");
    fs.renameSync(travailleur, travailleur + ".cache");
    await n.fond((g) => g.fermer());
    const panne = await n.nouvellePage();
    await panne.goto(n.url("pages/reglages.html"));
    verifie("un correcteur qui ne se charge pas : les réglages le disent", !!await jusqua(() => panne.evaluate(() =>
      !document.getElementById("panne").classList.contains("cache")), 8000), await etat());
    verifie("l'icône aussi", await n.fond((g) => g.chrome.action.getBadgeText({})) === "!");
    await capture("11-panne", panne);
    fs.renameSync(travailleur + ".cache", travailleur);
    await panne.click("#reessayer");
    verifie("« Réessayer » recharge le correcteur",
      !!await jusqua(async () => (await etat()).moteur === "pret", 15000, 100), await etat());
    verifie("et la page le dit", !!await jusqua(() => panne.evaluate(() =>
      document.getElementById("panne").classList.contains("cache")), 5000));
    await panne.close();
  }

  // La mémoire : celle du navigateur, avec et sans le correcteur.
  if (VRAI && n.memoire) {
    mesures.avec = n.memoire();
    await n.fond((g) => g.fermer());
    await attendre(2000);
    mesures.sans = n.memoire();
  }
  return { mesures };
}
