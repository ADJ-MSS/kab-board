/*
 * Ce que l'extension montre dans la page : la barre des propositions, la carte
 * d'un mot souligné, le panneau des outils, les soulignés d'un <textarea>.
 *
 * Tout vit dans une racine d'ombre : la page ne voit pas nos styles, ni nous les
 * siens, et nos boutons n'obéissent qu'aux vrais clics. Rien ne prend jamais le focus : un clic sur une proposition
 * laisse le curseur dans le champ, comme la barre de Windows.
 */
(function () {
  "use strict";
  const L = globalThis.KabLogique;

  const STYLE = `
    :host { all: initial; }
    * { box-sizing: border-box; }
    .boite {
      --fond: #ffffff; --texte: #1e1e1e; --discret: #6b7280; --bord: #c8c8c8;
      --survol: #eef4fa; --rouge: #c62828; --ombre: 0 4px 16px rgba(0,0,0,.18);
      font: 14px/1.35 "Segoe UI", "Noto Sans", system-ui, -apple-system, sans-serif;
      color: var(--texte);
    }
    @media (prefers-color-scheme: dark) {
      .boite { --fond: #24272b; --texte: #eceff1; --discret: #a0a7b0; --bord: #4a4f55;
        --survol: #2f3b47; --rouge: #ef5350; --ombre: 0 4px 16px rgba(0,0,0,.5); }
    }
    .flottant { position: fixed; z-index: 2147483647; background: var(--fond);
      border: 1px solid var(--bord); border-radius: 8px; box-shadow: var(--ombre); }
    .cache { display: none !important; }

    .barre { display: flex; align-items: stretch; padding: 3px; gap: 2px; max-width: calc(100vw - 16px);
      user-select: none; }
    .forme { display: flex; flex-direction: column; justify-content: center; padding: 2px 6px 0;
      border-radius: 5px; cursor: pointer; min-width: 28px; }
    .forme:hover { background: var(--survol); }
    .forme .ligne { display: flex; align-items: baseline; gap: 3px; white-space: nowrap; }
    .forme .chiffre { font-size: 10px; color: var(--discret); }
    .forme .mot { font-size: 15px; }
    .forme .trait { height: 3px; border-radius: 2px; margin-top: 2px; }
    .separe { width: 1px; background: var(--bord); margin: 3px 2px; }
    .outil { display: flex; align-items: center; justify-content: center; min-width: 30px;
      padding: 0 6px; border-radius: 5px; cursor: pointer; color: var(--discret); font-size: 15px; }
    .outil:hover { background: var(--survol); color: var(--texte); }
    .message { display: flex; align-items: center; padding: 4px 8px; color: var(--discret);
      white-space: nowrap; }
    .ecoute { color: var(--rouge); font-weight: 600; }

    .carte { padding: 8px; min-width: 200px; max-width: 320px; }
    .carte .titre { color: var(--discret); font-size: 12px; margin: 0 2px 4px; }
    .carte .props { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
    .prop { border: 1px solid var(--bord); border-bottom-width: 3px; border-radius: 6px;
      padding: 2px 8px; cursor: pointer; background: var(--fond); color: var(--texte);
      font: inherit; font-size: 15px; }
    .prop:hover { background: var(--survol); }
    .actions { display: flex; flex-wrap: wrap; gap: 4px; }
    .lien { background: none; border: 0; color: #0072bb; cursor: pointer; padding: 2px 4px;
      font: inherit; font-size: 13px; border-radius: 4px; }
    .lien:hover { background: var(--survol); }
    @media (prefers-color-scheme: dark) { .lien { color: #64b5f6; } }

    .panneau { right: 16px; bottom: 16px; width: 340px; max-width: calc(100vw - 32px);
      max-height: min(70vh, 560px); display: flex; flex-direction: column; overflow: hidden; }
    .panneau .tete { display: flex; align-items: center; gap: 8px; padding: 8px 10px;
      border-bottom: 1px solid var(--bord); }
    .panneau .tete img { width: 18px; height: 18px; border-radius: 4px; }
    .panneau .tete .nom { flex: 1; font-weight: 600; }
    .panneau .fermer { background: none; border: 0; color: var(--discret); cursor: pointer;
      font-size: 16px; padding: 0 4px; }
    .panneau .corps { padding: 8px 10px 10px; overflow: auto; }
    .panneau p { margin: 4px 0; }
    .panneau .discret { color: var(--discret); font-size: 12px; }
    .panneau .grand { font-size: 18px; font-weight: 600; }
    .panneau input[type=text] { width: 100%; font: inherit; font-size: 15px; padding: 5px 8px;
      border: 1px solid var(--bord); border-radius: 6px; background: var(--fond); color: var(--texte); }
    .panneau .rangee { display: flex; gap: 6px; align-items: center; margin: 6px 0; }
    .panneau .bouton { border: 1px solid var(--bord); background: var(--fond); color: var(--texte);
      border-radius: 6px; padding: 4px 10px; cursor: pointer; font: inherit; }
    .panneau .bouton:hover { background: var(--survol); }
    .panneau .resultat { display: block; width: 100%; text-align: left; border: 0; border-radius: 6px;
      background: none; color: var(--texte); padding: 5px 6px; cursor: pointer; font: inherit; }
    .panneau .resultat:hover { background: var(--survol); }
    .panneau .resultat b { font-size: 15px; }
    .signale { border-top: 1px solid var(--bord); padding: 6px 0; }
    .signale:first-child { border-top: 0; }
    .signale .mot-signale { font-weight: 600; cursor: pointer; }
    .lettres { display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; }
    .lettres button { font: inherit; font-size: 20px; padding: 6px 0; border: 1px solid var(--bord);
      border-radius: 6px; background: var(--fond); color: var(--texte); cursor: pointer; }
    .lettres button:hover { background: var(--survol); }

    .calque { position: fixed; z-index: 2147483646; pointer-events: none; overflow: hidden; }
    .calque .souligne { position: absolute; height: 4px; background-repeat: repeat-x;
      background-size: 6px 4px; }
    .calque .actuel { position: absolute; background: rgba(0, 114, 187, .16); border-radius: 2px; }
    .kab-miroir { position: absolute; visibility: hidden; }
  `;

  // L'icône, dans le fichier même : une page ne peut pas charger les fichiers de l'extension.
  const LOGO = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAEcUlEQVR42sWXX4hUVRzHP79z7+yd/zM747jrOKtTm9liWJZSRhRGKgURJGUalRBB0ZNkED3kS/TSU0JG9NRLBBHUgxQRVAQuUrFkKjLL6rqurmy67s7Mujsz957Tw73KStbemV3owIXL797z+/7+ne/5/QAU/koCB4HTgAuYZX7cQPfBAIsF2KwEjrWrVMCIdGTMsQATgBTwe/ChCehODAn5rw4wTICZsoB3gD1AC4gAQshVyEYRZdNsuWE3CWAFWKXAGEYArx3PLeV7ncgo8+nu1SZp251EwgNGFFAOiiGUE5YCT4OxYf+WNM/nkuxb34eFtBE7JMAs2wsrcbGlxAdfl+/ipf4iu/vjeElFb5egEDxjkMDFsCrtdsC1gV2PpTjQXWb2ZBSvNktlcp5DI+O00IiAaQOdsN5LAL7pNoeDz5aJSRQxmk8q0zz6zRkmq/O+56adLPjLDgNuDJRX2Wwopxge1ZQc+OD8Ob67dplyTxepaJQ/z1WJWELLay8NKowBAJvWxag2oiQjwvsVHzweEw4/uYKY56tJxRVPPJjGLNi3LCkAiESEiG3xw1CNI8f/QiE8fo/D1p4UlfFZAK7WPFYmDduKhdC1oMKcF4DJqSY9Oc1n319BNw0aw/Y1URoT0LQ0SvmcPDbT5I3e1dzrpAIAWZoBnvbDOXhiHtw6Pd0W2viygbUJrmYitDyN1oZkDHLZJI2qsC2TvSmFS05BowVf/TLD/hcSbC5lsCJCv23RnNM4tuKBvhSf719HdSaK1jDRaoZmJNMOD5R6FYce7sM7m2H9mnlSSvPjGYeHcknyrwivfniR/JjFl5NjVD1vUYDQRKQNKAXjlzQvHjnHno3dbCwVEMfBHTb8erlGfdClMl7l1KWZG4xklisCC1lOIRTzDj8/sxKZivL64DSTsw2Oz9bxXO9GbvVypeA6eMJRvLV3FTtmCninHbq21OnNa079FKPXiTCzq8GBw+cZGp3G097yEZExsCKr2H5/FtV0+GJ0isPTo8TzDeYtm2GmaWQaDPQ49OQSvF26g9ud2E3HuKMauL45GhV2bsozONzk66NnfGEc3nMt5scUB06cZW0hwptHVyAxuMuKsy9X5N2JEZT4t2RHEVDK937vlgxZL8tU3cVSgiWKpAh0WUjGgpYwfKHJax9fJB6vkUhAPOS19J8GGOMruTsbYa6uWFtK4mmDZzQehhbaD6HyjRXgj+E6/UWXodq1pRsg4ofu5FyDWMZl/EI9YDYBDdlUhKGWpuVplPgdUTpiU6m7fDt7JTi+ix+yf+92g5a7WLDNhr6EAYxSviydFPPRUwWTj3cZBGMpMYB5eUe36U+n2+kR22i/5dbvwT1knnskbTbfmbxJttgTii9EfCpeGE1jfNl1in76vjS1OcVvlTqWCDrcdaw7assXRsG2xewcyJitxUQ7nt9oyy0gB2wLZjcrdF8dRGRgdYKJaZcTk9ewFGE9dwMOOrTk0Uz5RyXsjPiP0WxJw+mtCrKT4fR/Hc//Bs/bim402qicAAAAAElFTkSuQmCC";

  function vague(couleur) {
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='6' height='4'><path d='M0 3 Q1.5 0 3 3 T6 3' fill='none' stroke='${couleur}' stroke-width='1.2'/></svg>`;
    return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
  }

  /** Un élément, ses attributs, ses enfants : de quoi écrire l'interface sans innerHTML. */
  function el(nom, attributs, ...enfants) {
    const e = document.createElement(nom);
    for (const [cle, valeur] of Object.entries(attributs || {})) {
      if (valeur === undefined || valeur === null || valeur === false) continue;
      if (cle === "classe") e.className = valeur;
      else if (cle === "style" && typeof valeur === "object") Object.assign(e.style, valeur);
      else if (cle.startsWith("sur")) e.addEventListener(cle.slice(3), valeur);
      else e.setAttribute(cle, valeur === true ? "" : valeur);
    }
    for (const enfant of enfants.flat()) {
      if (enfant === null || enfant === undefined || enfant === false) continue;
      e.appendChild(typeof enfant === "string" ? document.createTextNode(enfant) : enfant);
    }
    return e;
  }

  /** Un clic qui ne prend pas le focus : le curseur reste dans le champ. Seul un vrai
   * clic compte : un script de la page ne peut pas, par exemple, lancer la dictée. */
  function sansFocus(element, action) {
    element.addEventListener("mousedown", (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
    element.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.isTrusted) action(e);
    });
    return element;
  }

  function placer(boite, ancre, ecart) {
    const largeur = boite.offsetWidth;
    const hauteur = boite.offsetHeight;
    const vw = document.documentElement.clientWidth || window.innerWidth;
    const vh = document.documentElement.clientHeight || window.innerHeight;
    let x = Math.min(Math.max(ancre.left - 8, 8), vw - largeur - 8);
    let y = ancre.bottom + (ecart || 6);
    if (y + hauteur > vh - 4) y = ancre.top - hauteur - (ecart || 6);
    y = Math.min(Math.max(y, 4), vh - hauteur - 4);
    boite.style.left = Math.round(Math.max(x, 4)) + "px";
    boite.style.top = Math.round(y) + "px";
  }

  class Interface {
    constructor() {
      this.hote = document.createElement("kab-board-interface");
      this.hote.setAttribute("data-kab-board", "");
      this.hote.style.cssText = "all: initial; position: fixed; top: 0; left: 0; width: 0; height: 0; z-index: 2147483647;";
      this.racine = this.hote.attachShadow({ mode: "open" });
      this.racine.appendChild(el("style", {}, STYLE));
      this.boite = el("div", { classe: "boite" });
      this.racine.appendChild(this.boite);
      this.barre = el("div", { classe: "flottant barre cache", role: "listbox", "aria-label": "Propositions de Kab-board" });
      this.carte = el("div", { classe: "flottant carte cache" });
      this.panneauEl = el("div", { classe: "flottant panneau cache", role: "dialog" });
      this.calques = el("div");
      this.miroirs = el("div");
      this.boite.append(this.calques, this.barre, this.carte, this.panneauEl, this.miroirs);
      this.actions = {};           // ce que le script de contenu branche
      this.ancreBarre = null;
      this.ancreCarte = null;
      this.calquesParChamp = new Map();
      this.attache = false;
    }

    attacher() {
      if (!this.attache || !this.hote.isConnected) {
        (document.documentElement || document.body).appendChild(this.hote);
        this.attache = true;
      }
    }

    detacher() {
      this.hote.remove();
      this.attache = false;
    }

    contient(evenement) {
      return evenement.composedPath().includes(this.hote);
    }

    // La barre

    /**
     * formes, nature : les propositions ; ancre : le rectangle du curseur.
     * message : une ligne d'état à la place (ou en plus) des propositions.
     * ecoute : la dictée en cours ({ secondes } ou { transcription: true }).
     */
    montrerBarre({ formes, nature, ancre, chiffres, message, ecoute }) {
      this.attacher();
      const b = this.barre;
      if (ecoute) {
        const texte = ecoute.transcription ? "Transcription…"
          : `● J'écoute… ${Math.floor(ecoute.secondes || 0)} s`;
        const mode = ecoute.transcription ? "transcription" : "ecoute";
        // Pendant l'écoute, seul le compteur change : la barre n'est pas refaite,
        // sinon « Arrêter » disparaîtrait sous le clic.
        if (this.modeBarre === mode && this.messageEcoute && !b.classList.contains("cache")) {
          this.messageEcoute.textContent = texte;
          return;
        }
        b.textContent = "";
        this.messageEcoute = el("div", { classe: "message ecoute" }, texte);
        b.appendChild(this.messageEcoute);
        if (!ecoute.transcription) {
          b.appendChild(sansFocus(el("div", { classe: "outil", title: "Arrêter la dictée" }, "■ Arrêter"),
            () => this.actions.dicter && this.actions.dicter()));
        }
        this.modeBarre = mode;
      } else {
        b.textContent = "";
        this.modeBarre = "propositions";
        this.messageEcoute = null;
        (formes || []).forEach((forme, rang) => {
          const caseForme = el("div", { classe: "forme", role: "option", title: "Clic droit : Asegzawal" },
            el("div", { classe: "ligne" },
              chiffres ? el("span", { classe: "chiffre" }, String(rang + 1)) : null,
              el("span", { classe: "mot" }, forme)),
            el("div", { classe: "trait", style: { background: L.couleur(nature, rang) } }));
          sansFocus(caseForme, () => this.actions.choisir && this.actions.choisir(rang, forme));
          caseForme.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.isTrusted && this.actions.fiche) this.actions.fiche(forme);
          });
          b.appendChild(caseForme);
        });
        if (message) b.appendChild(el("div", { classe: "message" }, message));
        if ((formes && formes.length) || message) b.appendChild(el("div", { classe: "separe" }));
        b.appendChild(sansFocus(el("div", { classe: "outil", title: "Dicter en kabyle (Alt+Maj+D)" }, "🎤"),
          () => this.actions.dicter && this.actions.dicter()));
        b.appendChild(sansFocus(el("div", { classe: "outil", title: "Les outils de Kab-board" },
          el("img", { src: LOGO, alt: "Outils", style: { width: "18px", height: "18px", borderRadius: "4px" } })),
          () => this.actions.outils && this.actions.outils()));
      }
      b.classList.remove("cache");
      this.ancreBarre = ancre;
      placer(b, ancre);
    }

    cacherBarre() {
      this.barre.classList.add("cache");
      this.ancreBarre = null;
    }

    get barreVisible() {
      return !this.barre.classList.contains("cache");
    }

    replacerBarre(ancre) {
      if (!this.barreVisible || !ancre) return;
      this.ancreBarre = ancre;
      placer(this.barre, ancre);
    }

    // La carte d'un mot souligné

    montrerCarte({ souligne, ancre }) {
      this.attacher();
      const c = this.carte;
      c.textContent = "";
      c.appendChild(el("div", { classe: "titre" },
        souligne.fusion ? `« ${souligne.mot} » : en un seul mot ?`
          : souligne.soulignement === "doute" ? `« ${souligne.mot} » : dans ce contexte, plutôt…`
            : `« ${souligne.mot} »`));
      const props = el("div", { classe: "props" });
      souligne.propositions.forEach((p, rang) => {
        const couleur = rang === 0 ? L.VERT : L.BLEU;
        const bouton = el("button", { classe: "prop", style: { borderBottomColor: couleur }, title: "Clic droit : Asegzawal" }, p);
        sansFocus(bouton, () => this.actions.remplacer && this.actions.remplacer(souligne, p));
        bouton.addEventListener("contextmenu", (e) => {
          e.preventDefault();
          if (e.isTrusted && this.actions.fiche) this.actions.fiche(p);
        });
        props.appendChild(bouton);
      });
      c.appendChild(props);
      const actions = el("div", { classe: "actions" });
      actions.appendChild(sansFocus(el("button", { classe: "lien" }, "Garder mon mot"),
        () => this.actions.garder && this.actions.garder(souligne)));
      if (!souligne.mot.includes(" ")) {
        actions.appendChild(sansFocus(el("button", { classe: "lien" }, "Ajouter à mon dictionnaire"),
          () => this.actions.ajouter && this.actions.ajouter(souligne)));
      }
      actions.appendChild(sansFocus(el("button", { classe: "lien" }, "Asegzawal"),
        () => this.actions.fiche && this.actions.fiche(souligne.propositions[0] || souligne.mot)));
      c.appendChild(actions);
      c.classList.remove("cache");
      this.ancreCarte = ancre;
      placer(c, ancre, 4);
    }

    cacherCarte() {
      this.carte.classList.add("cache");
      this.ancreCarte = null;
    }

    get carteVisible() {
      return !this.carte.classList.contains("cache");
    }

    // Le panneau des outils

    /** Ouvre le panneau : remplir(corps) y met ce qu'il faut. */
    panneau(titre, remplir) {
      this.attacher();
      const p = this.panneauEl;
      p.textContent = "";
      const logo = el("img", { src: LOGO, alt: "" });
      const fermer = el("button", { classe: "fermer", title: "Fermer", "aria-label": "Fermer" }, "✕");
      sansFocus(fermer, () => this.fermerPanneau());
      p.appendChild(el("div", { classe: "tete" }, logo, el("div", { classe: "nom" }, titre), fermer));
      const corps = el("div", { classe: "corps" });
      p.appendChild(corps);
      p.classList.remove("cache");
      if (remplir) remplir(corps);
      return corps;
    }

    fermerPanneau() {
      this.panneauEl.classList.add("cache");
      this.panneauEl.textContent = "";
      if (this.actions.panneauFerme) this.actions.panneauFerme();
    }

    get panneauVisible() {
      return !this.panneauEl.classList.contains("cache");
    }

    // Les soulignés d'un <textarea> ou d'un <input> : un calque posé dessus

    dessinerSoulignes(champ, soulignes, actuel) {
      this.attacher();
      let calque = this.calquesParChamp.get(champ);
      if (!calque) {
        calque = el("div", { classe: "calque" });
        this.calques.appendChild(calque);
        this.calquesParChamp.set(champ, calque);
      }
      calque.textContent = "";
      if (!soulignes.length && !actuel) {
        calque.classList.add("cache");
        return;
      }
      const zone = champ.zoneVisible();
      Object.assign(calque.style, {
        left: zone.left + "px", top: zone.top + "px", width: zone.width + "px", height: zone.height + "px",
      });
      calque.classList.remove("cache");
      const plages = soulignes.map((s) => ({ debut: s.debut, fin: s.fin }));
      if (actuel) plages.push({ debut: actuel.debut, fin: actuel.fin });
      const rectangles = champ.rectangles(plages);
      soulignes.forEach((s, i) => {
        const fond = vague(L.couleurSouligne(s.soulignement));
        for (const r of rectangles[i]) {
          if (r.width <= 0) continue;
          calque.appendChild(el("div", {
            classe: "souligne",
            style: {
              left: (r.left - zone.left) + "px", top: (r.bottom - zone.top - 3) + "px",
              width: r.width + "px", backgroundImage: fond,
            },
          }));
        }
      });
      if (actuel) {
        for (const r of rectangles[rectangles.length - 1]) {
          calque.appendChild(el("div", {
            classe: "actuel",
            style: { left: (r.left - zone.left) + "px", top: (r.top - zone.top) + "px", width: r.width + "px", height: r.height + "px" },
          }));
        }
      }
    }

    effacerSoulignes(champ) {
      const calque = this.calquesParChamp.get(champ);
      if (calque) {
        calque.remove();
        this.calquesParChamp.delete(champ);
      }
    }
  }

  globalThis.KabInterface = { Interface, el, sansFocus };
})();
