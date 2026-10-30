/*
 * « Écrire et relire » : une page pour écrire en kabyle avec tout Kab-board, la
 * relire et la copier, là où une page ne laisse pas faire (Google Docs, une page
 * de Chrome). Le script de contenu y est chargé tel quel.
 */
"use strict";

const P = globalThis.KabPages;
const $ = (id) => document.getElementById(id);
const zone = $("texte");
let minuterie = null;

function compter() {
  const mots = zone.value.trim() ? zone.value.trim().split(/\s+/u).length : 0;
  $("compte").textContent = mots === 1 ? "1 mot" : `${mots} mots`;
}

function garder() {
  clearTimeout(minuterie);
  minuterie = setTimeout(() => chrome.storage.local.set({ brouillon: zone.value }), 400);
}

/** Un bouton qui agit sans ôter le curseur de la zone de texte. */
function sansFocus(bouton, action) {
  bouton.addEventListener("mousedown", (e) => e.preventDefault());
  bouton.addEventListener("click", action);
}

async function demarrer() {
  const r = await chrome.storage.local.get("brouillon");
  if (typeof r.brouillon === "string") zone.value = r.brouillon;
  compter();
  zone.focus();
  zone.setSelectionRange(zone.value.length, zone.value.length);
  zone.addEventListener("input", () => {
    compter();
    garder();
  });
  for (const b of document.querySelectorAll("[data-commande]")) {
    sansFocus(b, () => {
      if (document.activeElement !== zone) zone.focus();
      globalThis.KabContenu.commande(b.dataset.commande);
    });
  }
  sansFocus($("copier"), async () => {
    await navigator.clipboard.writeText(zone.value);
    $("copier").textContent = "Copié";
    setTimeout(() => { $("copier").textContent = "Copier le texte"; }, 1200);
  });
  sansFocus($("effacer"), () => {
    if (!zone.value || !confirm("Effacer tout le texte ?")) return;
    zone.select();
    document.execCommand("delete");      // Ctrl+Z le rend
  });
  P.dessinerEtat($("etat"), await P.etat());
  P.surEtat((e) => P.dessinerEtat($("etat"), e));
}

demarrer();
