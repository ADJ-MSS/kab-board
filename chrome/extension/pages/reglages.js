/*
 * La page des réglages : l'état du correcteur, les interrupteurs, la graphie, « mon
 * dictionnaire », les sites exclus et les raccourcis.
 */
"use strict";

const C = globalThis.KabCommun;
const L = globalThis.KabLogique;
const P = globalThis.KabPages;
const $ = (id) => document.getElementById(id);

let reglages = C.reglagesComplets({});
let mots = [];
let marquerGraphie = () => {};

function ligne(texte, libelleBouton, action) {
  const li = document.createElement("li");
  const s = document.createElement("span");
  s.textContent = texte;
  const b = document.createElement("button");
  b.className = "bouton";
  b.textContent = libelleBouton;
  b.addEventListener("click", action);
  li.append(s, b);
  return li;
}

function montrerEtat(e) {
  P.dessinerEtat($("etat"), e);
  const panne = !!e && e.moteur === "panne";
  $("panne").classList.toggle("cache", !panne);
  $("erreur-moteur").textContent = panne ? e.erreur : "";
}

function montrerReglages() {
  $("allume").checked = reglages.allume;
  marquerGraphie(reglages.graphie);
  P.mettreInterrupteurs($("interrupteurs"), reglages);
  const sites = $("sites");
  sites.textContent = "";
  for (const s of reglages.sitesExclus) {
    sites.append(ligne(s, "Retirer", () => P.changerReglages({
      sitesExclus: reglages.sitesExclus.filter((x) => x !== s),
    })));
  }
  $("aucun-site").classList.toggle("cache", reglages.sitesExclus.length > 0);
}

async function chargerMots() {
  mots = await C.mesMots();
  montrerMots();
}

function montrerMots() {
  const filtre = $("filtre").value.trim().toLowerCase();
  const liste = $("mots");
  liste.textContent = "";
  const vus = mots.filter((m) => !filtre || m.includes(filtre));
  for (const m of vus.slice(0, 500)) {
    liste.append(ligne(m, "Retirer", () => C.oublierMot(m)));
  }
  $("total").textContent = mots.length === 1 ? "1 mot" : `${mots.length} mots`;
}

/** Un fichier texte, un mot par ligne : celui de Kab-board pour Windows, ou un export. */
async function importer(fichier) {
  const texte = await fichier.text();
  const r = await C.ajouterMots(texte.replace(/^\uFEFF/, "").split(/\r?\n/));
  $("importe").textContent = r.erreur ? "Aucun mot dans ce fichier."
    : r.ajoutes === 1 ? "1 mot ajouté." : `${r.ajoutes} mots ajoutés.`;
}

function exporter() {
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(new Blob([mots.join("\n") + "\n"], { type: "text/plain" }));
  lien.download = "mes_mots.txt";
  lien.click();
  setTimeout(() => URL.revokeObjectURL(lien.href), 1000);
}

async function demarrer() {
  reglages = await P.lireReglages();
  P.dessinerInterrupteurs($("interrupteurs"), reglages, false);
  marquerGraphie = P.brancherGraphie($("graphie"), reglages);
  montrerReglages();
  P.surReglages((r) => {
    reglages = r;
    montrerReglages();
  });
  montrerEtat(await P.etat());
  P.surEtat(montrerEtat);

  $("allume").addEventListener("change", () => P.changerReglages({ allume: $("allume").checked }));
  $("reessayer").addEventListener("click", async () => montrerEtat(await P.etat()));
  $("changer-raccourcis").addEventListener("click", () => chrome.tabs.create({ url: "chrome://extensions/shortcuts" }));
  L.brancherSaisie($("nouveau-mot"), () => reglages.translitteration);
  L.brancherSaisie($("filtre"), () => reglages.translitteration);
  $("ajout").addEventListener("submit", async (e) => {
    e.preventDefault();
    const mot = $("nouveau-mot").value.trim();
    if (!mot) return;
    const r = await C.ajouterMots([mot]);
    if (r.erreur) {
      $("total").textContent = r.erreur;
      return;
    }
    $("nouveau-mot").value = "";
  });
  $("filtre").addEventListener("input", montrerMots);
  $("importer").addEventListener("click", () => $("fichier").click());
  $("fichier").addEventListener("change", () => {
    if ($("fichier").files[0]) importer($("fichier").files[0]);
    $("fichier").value = "";
  });
  $("exporter").addEventListener("click", exporter);
  chrome.storage.onChanged.addListener((changements, zone) => {
    if (zone === "local" && changements.mesMots) chargerMots();
  });
  chargerMots();
  $("ajout-site").addEventListener("submit", (e) => {
    e.preventDefault();
    const saisi = $("nouveau-site").value.trim().toLowerCase();
    const nom = C.site(saisi.includes("://") ? saisi : "https://" + saisi);
    if (!nom || reglages.sitesExclus.includes(nom)) return;
    $("nouveau-site").value = "";
    P.changerReglages({ sitesExclus: [...reglages.sitesExclus, nom] });
  });
}

demarrer();
