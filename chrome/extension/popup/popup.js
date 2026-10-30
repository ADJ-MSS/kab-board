/*
 * Le popup : l'état, les interrupteurs, la graphie, les outils.
 * Asegzawal, fr → kab et le mot du jour s'y consultent sans page ; la dictée,
 * la relecture et les lettres agissent dans le champ de l'onglet.
 */
"use strict";

const C = globalThis.KabCommun;
const L = globalThis.KabLogique;
const P = globalThis.KabPages;
const $ = (id) => document.getElementById(id);

let reglages = C.reglagesComplets({});
let etat = null;
let site = "";
let ongletId = null;
let mode = "fiche";
let marquerGraphie = () => {};

function el(nom, attributs, ...enfants) {
  const e = document.createElement(nom);
  for (const [cle, valeur] of Object.entries(attributs || {})) {
    if (cle === "classe") e.className = valeur;
    else if (cle.startsWith("sur")) e.addEventListener(cle.slice(3), valeur);
    else e.setAttribute(cle, valeur);
  }
  for (const enfant of enfants) if (enfant !== null && enfant !== undefined) e.append(enfant);
  return e;
}

function montrerEtat(e) {
  etat = e;
  P.dessinerEtat($("etat"), e);
}

function montrerReglages() {
  $("allume").checked = reglages.allume;
  marquerGraphie(reglages.graphie);
  $("site").checked = !C.siteExclu(reglages, site);
  $("site").disabled = !reglages.allume;
  P.mettreInterrupteurs($("interrupteurs"), reglages);
}

async function copier(texte, bouton) {
  try {
    await navigator.clipboard.writeText(texte);
    const avant = bouton.textContent;
    bouton.textContent = "Copié";
    setTimeout(() => { bouton.textContent = avant; }, 1200);
  } catch (erreur) {
    // le presse-papiers refusé : rien de grave
  }
}

function boutonCopier(texte) {
  const b = el("button", { classe: "lien", title: "Copier" }, "Copier");
  b.addEventListener("click", () => copier(texte, b));
  return b;
}

async function chercher() {
  const requete = $("requete").value.trim();
  const sortie = $("resultats");
  sortie.textContent = "";
  if (!requete) return;
  sortie.append(el("p", { classe: "discret" }, "…"));
  if (mode === "fiche") {
    const r = await P.correcteur({ quoi: "fiche", mot: requete });
    sortie.textContent = "";
    if (r.erreur) return sortie.append(el("p", {}, r.erreur));
    if (!r.mot) return sortie.append(el("p", {}, "Fiche indisponible : le correcteur se charge encore."));
    sortie.append(el("p", {}, el("span", { classe: "grand" }, r.mot), " ", boutonCopier(r.mot)),
      el("p", {}, r.glose || "Pas de glose pour cette forme."));
    if (r.categorie) sortie.append(el("p", { classe: "discret" }, "catégorie : " + r.categorie));
    if (r.libre) sortie.append(el("p", {}, "état libre : ", el("b", {}, r.libre), " ", boutonCopier(r.libre)));
    if (r.annexion) sortie.append(el("p", {}, "état d'annexion : ", el("b", {}, r.annexion), " ", boutonCopier(r.annexion)));
    return;
  }
  const r = await P.correcteur({ quoi: "chercher", requete });
  sortie.textContent = "";
  if (r.erreur) return sortie.append(el("p", {}, r.erreur));
  const trouves = r.trouves || [];
  if (!trouves.length) return sortie.append(el("p", {}, "Aucun résultat."));
  for (const [forme, glose] of trouves) {
    sortie.append(el("div", { classe: "resultat" }, el("span", { classe: "forme" }, forme),
      el("span", { classe: "glose" }, glose), boutonCopier(forme)));
  }
}

function changerMode(nouveau) {
  mode = nouveau;
  for (const b of document.querySelectorAll(".onglets button")) {
    b.setAttribute("aria-selected", String(b.dataset.mode === mode));
  }
  $("requete").placeholder = mode === "fiche" ? "Un mot kabyle (gh → ɣ)" : "Un mot français";
  $("requete").spellcheck = mode !== "fiche";
  $("resultats").textContent = "";
  $("requete").focus();
}

async function motDuJour() {
  const r = await P.correcteur({ quoi: "motdujour" });
  const bloc = $("mot-du-jour");
  bloc.textContent = "";
  if (!r.forme) {
    bloc.classList.add("cache");
    return;
  }
  bloc.classList.remove("cache");
  bloc.append(el("p", { classe: "discret" }, "Mot du jour"),
    el("p", {}, el("span", { classe: "grand" }, r.forme), " ", boutonCopier(r.forme)),
    el("p", {}, r.glose || ""));
}

async function demarrer() {
  const [onglet] = await chrome.tabs.query({ active: true, currentWindow: true });
  ongletId = onglet ? onglet.id : null;
  site = onglet && onglet.url ? C.site(onglet.url) : "";
  const pageOuverte = !!site;
  $("nom-site").textContent = site || "cette page";
  $("ligne-site").classList.toggle("cache", !pageOuverte);
  $("page-interdite").classList.toggle("cache", pageOuverte);
  for (const b of document.querySelectorAll("[data-commande]")) b.disabled = !pageOuverte;

  reglages = await P.lireReglages();
  P.dessinerInterrupteurs($("interrupteurs"), reglages, true);
  marquerGraphie = P.brancherGraphie($("graphie"), reglages);
  montrerReglages();
  P.surReglages((r) => {
    const graphieChangee = r.graphie !== reglages.graphie;
    reglages = r;
    montrerReglages();
    if (graphieChangee && etat && etat.moteur === "pret") {
      motDuJour();
      chercher();
    }
  });

  montrerEtat(await P.etat());
  P.surEtat((e) => {
    const etaitPret = etat && etat.moteur === "pret";
    montrerEtat(e);
    if (!etaitPret && e && e.moteur === "pret") motDuJour();
  });
  if (etat && etat.moteur === "pret") motDuJour();

  $("allume").addEventListener("change", () => P.changerReglages({ allume: $("allume").checked }));
  $("site").addEventListener("change", () => {
    const autres = reglages.sitesExclus.filter((s) => s !== site);
    P.changerReglages({ sitesExclus: $("site").checked ? autres : [...autres, site] });
  });
  for (const b of document.querySelectorAll("[data-commande]")) {
    b.addEventListener("click", async () => {
      await chrome.runtime.sendMessage({ type: "commande", nom: b.dataset.commande });
      window.close();           // le champ retrouve le focus : la dictée y écrira
    });
  }
  for (const b of document.querySelectorAll("[data-page]")) {
    b.addEventListener("click", () => {
      chrome.runtime.sendMessage({ type: "ouvrir", page: b.dataset.page });
      window.close();
    });
  }
  $("reglages").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
    window.close();
  });
  for (const b of document.querySelectorAll(".onglets button")) {
    b.addEventListener("click", () => changerMode(b.dataset.mode));
  }
  L.brancherSaisie($("requete"), () => mode === "fiche" && reglages.translitteration);
  $("formulaire").addEventListener("submit", (e) => {
    e.preventDefault();
    chercher();
  });
}

demarrer();
