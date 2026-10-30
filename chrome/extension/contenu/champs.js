/*
 * Les champs où l'on écrit, vus comme une seule chaîne de texte : lire ce qui
 * précède le curseur, remplacer un morceau, savoir où il est à l'écran.
 *
 * Deux sortes de champs :
 *  - <textarea> et <input> : leur valeur est le texte ;
 *  - un élément modifiable (contenteditable : Gmail, Facebook, WhatsApp Web…) :
 *    le texte de ses nœuds, une ligne par bloc ou <br>.
 *
 * Toute écriture passe par document.execCommand("insertText") : c'est ce que
 * fait la frappe elle-même, si bien que l'éditeur de la page (React, Lexical,
 * ProseMirror…) suit, et que Ctrl+Z défait le changement. setRangeText, ou la
 * modification directe du DOM, ne servent qu'en dernier recours.
 */
(function () {
  "use strict";
  const L = globalThis.KabLogique;

  const BLOCS = new Set(["ADDRESS", "ARTICLE", "ASIDE", "BLOCKQUOTE", "DD", "DIV", "DL", "DT",
    "FIELDSET", "FIGCAPTION", "FIGURE", "FOOTER", "FORM", "H1", "H2", "H3", "H4", "H5", "H6",
    "HEADER", "HR", "LI", "MAIN", "NAV", "OL", "P", "PRE", "SECTION", "TABLE", "TD", "TH", "TR",
    "UL"]);
  const IGNORES = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "TITLE"]);
  // Des éditeurs de code : on n'y écrit pas du kabyle.
  const EDITEURS_DE_CODE = ".cm-editor, .CodeMirror, .monaco-editor, .ace_editor";

  const STYLES_MIROIR = ["direction", "fontFamily", "fontSize", "fontStyle", "fontVariant",
    "fontWeight", "fontStretch", "fontFeatureSettings", "fontKerning", "fontVariantLigatures",
    "fontVariantNumeric", "lineHeight", "letterSpacing", "wordSpacing", "textAlign",
    "textTransform", "textIndent", "tabSize", "wordBreak", "overflowWrap", "hyphens",
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "textRendering"];

  let documentMiroir = null;      // où poser les miroirs : notre racine d'ombre
  let jamaisMotDePasse = new WeakSet();

  function poserMiroirsDans(racine) {
    documentMiroir = racine;
  }

  /** La racine d'ombre d'un élément, même fermée : une extension y a accès. */
  function racineOmbre(el) {
    if (el.shadowRoot) return el.shadowRoot;
    try {
      return chrome.dom && chrome.dom.openOrClosedShadowRoot ? chrome.dom.openOrClosedShadowRoot(el) : null;
    } catch (erreur) {
      return null;
    }
  }

  /** L'élément qui a le focus sous el, à travers les racines d'ombre, fermées comprises. */
  function auFond(el) {
    for (let r = el && racineOmbre(el); r && r.activeElement; r = racineOmbre(el)) el = r.activeElement;
    return el;
  }

  /** L'élément actif, à travers les racines d'ombre. */
  function elementActif(doc) {
    return auFond((doc || document).activeElement);
  }

  function selectionDe(el) {
    const racine = el.getRootNode();
    if (racine && racine !== document && typeof racine.getSelection === "function") {
      return racine.getSelection();
    }
    return (el.ownerDocument || document).getSelection();
  }

  /** L'hôte d'édition d'un élément modifiable : le plus haut ancêtre modifiable. */
  function hoteEdition(el) {
    let hote = el;
    while (hote.parentElement && hote.parentElement.isContentEditable) hote = hote.parentElement;
    return hote;
  }

  /** Le champ où l'on peut écrire du kabyle, ou null (mot de passe, code, lecture seule…). */
  function champPour(cible) {
    if (!cible || cible.nodeType !== 1) return null;
    if (cible.closest && cible.closest("[data-kab-board]")) return null;
    if (cible instanceof HTMLTextAreaElement) {
      if (cible.readOnly || cible.disabled) return null;
      if (cible.closest(EDITEURS_DE_CODE)) return null;
      if (L.champSensible("", cible.autocomplete)) return null;
      return obtenir(cible, ChampTexte);
    }
    if (cible instanceof HTMLInputElement) {
      if (cible.type === "password") jamaisMotDePasse.add(cible);
      // Un mot de passe rendu visible reste un mot de passe.
      if (jamaisMotDePasse.has(cible)) return null;
      if (!L.typeEcrit(cible.type) || L.champSensible(cible.type, cible.autocomplete)) return null;
      if (cible.readOnly || cible.disabled) return null;
      return obtenir(cible, ChampTexte);
    }
    if (cible.isContentEditable) {
      const hote = hoteEdition(cible);
      if (hote.closest(EDITEURS_DE_CODE)) return null;
      if (hote.getAttribute("aria-hidden") === "true") return null;
      return obtenir(hote, ChampEditable);
    }
    return null;
  }

  const champs = new WeakMap();
  function obtenir(el, Genre) {
    let champ = champs.get(el);
    if (!champ || !(champ instanceof Genre)) {
      champ = new Genre(el);
      champs.set(el, champ);
    }
    return champ;
  }

  function insererTexte(doc, texte) {
    try {
      return texte ? doc.execCommand("insertText", false, texte) : doc.execCommand("delete", false);
    } catch (erreur) {
      return false;
    }
  }

  // <textarea> et <input>

  class ChampTexte {
    constructor(el) {
      this.el = el;
      this.genre = "texte";
      this.miroir = null;
    }

    get ligneUnique() {
      return this.el instanceof HTMLInputElement;
    }

    texte() {
      return this.el.value;
    }

    curseur() {
      const { selectionStart: d, selectionEnd: f } = this.el;
      return d === f && d !== null ? d : null;
    }

    selection() {
      return [this.el.selectionStart, this.el.selectionEnd];
    }

    placerCurseur(position) {
      this.el.setSelectionRange(position, position);
    }

    remplacer(debut, fin, texte, curseurApres) {
      const el = this.el;
      const avant = el.value;
      const attendu = avant.slice(0, debut) + texte + avant.slice(fin);
      if (el.ownerDocument.activeElement !== el) el.focus({ preventScroll: true });
      el.setSelectionRange(debut, fin);
      const fait = insererTexte(el.ownerDocument, texte);
      if (!fait || el.value !== attendu) {
        if (el.value === avant) {
          el.setRangeText(texte, debut, fin, "end");
          el.dispatchEvent(new InputEvent("input", {
            bubbles: true, inputType: "insertReplacementText", data: texte,
          }));
        }
      }
      const position = curseurApres === undefined ? debut + texte.length : curseurApres;
      if (el.value === attendu) el.setSelectionRange(position, position);
      return el.value === attendu;
    }

    /** Le miroir : un double invisible du champ, mêmes polices, mêmes marges, pour
     * savoir où tombe chaque caractère. */
    _miroir() {
      if (!this.miroir) {
        this.miroir = document.createElement("div");
        this.miroir.className = "kab-miroir";
        (documentMiroir || document.documentElement).appendChild(this.miroir);
      }
      const m = this.miroir;
      const s = getComputedStyle(this.el);
      for (const p of STYLES_MIROIR) m.style[p] = s[p];
      m.style.position = "absolute";
      m.style.visibility = "hidden";
      m.style.top = "0";
      m.style.left = "-99999px";
      m.style.boxSizing = "border-box";
      m.style.border = "0";
      m.style.margin = "0";
      m.style.overflow = "hidden";
      if (this.ligneUnique) {
        m.style.whiteSpace = "pre";
        m.style.width = "auto";
        m.style.height = "auto";
      } else {
        m.style.whiteSpace = "pre-wrap";
        m.style.width = this.el.clientWidth + "px";
        m.style.height = "auto";
      }
      return m;
    }

    /** Les rectangles, à l'écran, de chaque plage [debut, fin), en une passe. */
    rectangles(plages) {
      const el = this.el;
      const texte = el.value;
      const m = this._miroir();
      m.textContent = "";
      const tries = plages.map((p, i) => ({ ...p, i })).sort((a, b) => a.debut - b.debut);
      const spans = new Array(plages.length);
      let position = 0;
      for (const p of tries) {
        if (p.debut < position) continue;
        m.appendChild(document.createTextNode(texte.slice(position, p.debut)));
        const span = document.createElement("span");
        span.textContent = texte.slice(p.debut, p.fin) || "​";
        m.appendChild(span);
        spans[p.i] = span;
        position = p.fin;
      }
      m.appendChild(document.createTextNode(texte.slice(position) + "​"));
      const boite = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      const repere = m.getBoundingClientRect();
      // Un <input> centre sa ligne dans sa hauteur.
      let decalageY = 0;
      if (this.ligneUnique) {
        const haut = parseFloat(s.paddingTop) || 0;
        const bas = parseFloat(s.paddingBottom) || 0;
        const ligne = m.getBoundingClientRect().height - haut - bas;
        decalageY = Math.max(0, (el.clientHeight - haut - bas - ligne) / 2);
      }
      const x0 = boite.left + el.clientLeft - el.scrollLeft;
      const y0 = boite.top + el.clientTop - el.scrollTop + decalageY;
      return spans.map((span) => {
        if (!span) return [];
        return Array.from(span.getClientRects()).map((r) => new DOMRect(
          x0 + r.left - repere.left, y0 + r.top - repere.top, r.width, r.height));
      });
    }

    rectangleCurseur(position) {
      const [rects] = this.rectangles([{ debut: position, fin: position }]);
      const r = rects && rects[0];
      return r ? new DOMRect(r.left, r.top, 0, r.height) : this.el.getBoundingClientRect();
    }

    /** La partie visible du champ, où l'on peut dessiner. */
    zoneVisible() {
      const boite = this.el.getBoundingClientRect();
      return new DOMRect(boite.left + this.el.clientLeft, boite.top + this.el.clientTop,
        this.el.clientWidth, this.el.clientHeight);
    }

    oublier() {
      if (this.miroir) this.miroir.remove();
      this.miroir = null;
    }
  }

  // Les éléments modifiables

  /** Le texte d'un hôte d'édition, et de quoi passer d'une position à un nœud. */
  class Modele {
    constructor(hote) {
      this.hote = hote;
      this.morceaux = [];        // { noeud, debut, fin } pour chaque nœud texte
      this.debuts = new Map();   // nœud -> position où il commence
      this.fins = new Map();     // nœud -> position où il finit
      this.texte = "";
      const parties = [];
      let longueur = 0;
      const ajouter = (t) => {
        parties.push(t);
        longueur += t.length;
      };
      const finitParLigne = () => longueur === 0 || parties[parties.length - 1].endsWith("\n");
      const parcourir = (noeud) => {
        this.debuts.set(noeud, longueur);
        if (noeud.nodeType === 3) {
          const t = noeud.data.replace(/ /g, " ");
          this.morceaux.push({ noeud, debut: longueur, fin: longueur + t.length });
          ajouter(t);
        } else if (noeud.nodeType === 1) {
          const nom = noeud.nodeName;
          if (IGNORES.has(nom)) {
            // rien
          } else if (nom === "BR") {
            ajouter("\n");
          } else if (noeud !== hote && noeud.getAttribute("contenteditable") === "false") {
            ajouter("￼");            // une mention, une image : un objet, pas du texte
          } else {
            const bloc = noeud !== hote && BLOCS.has(nom);
            if (bloc && !finitParLigne()) ajouter("\n");
            for (const enfant of noeud.childNodes) parcourir(enfant);
            if (bloc && !finitParLigne()) ajouter("\n");
          }
        }
        this.fins.set(noeud, longueur);
      };
      parcourir(hote);
      this.texte = parties.join("");
    }

    /** La position, dans le texte, d'un point du DOM. null s'il est ailleurs. */
    position(noeud, decalage) {
      if (noeud.nodeType === 3) {
        const debut = this.debuts.get(noeud);
        if (debut === undefined) return null;
        return debut + Math.min(decalage, noeud.data.length);
      }
      if (!this.debuts.has(noeud)) return null;
      const enfant = noeud.childNodes[decalage];
      if (enfant && this.debuts.has(enfant)) return this.debuts.get(enfant);
      return this.fins.get(noeud);
    }

    /** Le point du DOM d'une position du texte : dans un nœud texte si possible. */
    point(position) {
      let precedent = null;
      for (const m of this.morceaux) {
        if (position <= m.fin) {
          if (position >= m.debut) return { noeud: m.noeud, decalage: position - m.debut };
          // Dans un saut de ligne ou un objet : la fin du texte d'avant.
          return precedent ? { noeud: precedent.noeud, decalage: precedent.noeud.data.length }
            : { noeud: m.noeud, decalage: 0 };
        }
        precedent = m;
      }
      if (precedent) return { noeud: precedent.noeud, decalage: precedent.noeud.data.length };
      return { noeud: this.hote, decalage: this.hote.childNodes.length };
    }

    plage(debut, fin) {
      const range = document.createRange();
      const a = this.point(debut);
      const b = fin === debut ? a : this.point(fin);
      range.setStart(a.noeud, a.decalage);
      range.setEnd(b.noeud, b.decalage);
      return range;
    }
  }

  class ChampEditable {
    constructor(el) {
      this.el = el;
      this.genre = "editable";
      this._modele = null;
      // Le texte se relit quand le DOM a bougé, et seulement alors : la page peut
      // le changer à tout moment, nous aussi.
      this.observateur = new MutationObserver(() => {
        this._modele = null;
      });
      this.observateur.observe(el, { childList: true, characterData: true, subtree: true });
    }

    modele() {
      if (this.observateur.takeRecords().length) this._modele = null;
      if (!this._modele) this._modele = new Modele(this.el);
      return this._modele;
    }

    texte() {
      return this.modele().texte;
    }

    _bornes() {
      const sel = selectionDe(this.el);
      if (!sel || sel.rangeCount === 0) return null;
      const r = sel.getRangeAt(0);
      if (!this.el.contains(r.startContainer) || !this.el.contains(r.endContainer)) return null;
      const m = this.modele();
      const d = m.position(r.startContainer, r.startOffset);
      const f = r.collapsed ? d : m.position(r.endContainer, r.endOffset);
      if (d === null || f === null) return null;
      return [d, f];
    }

    curseur() {
      const b = this._bornes();
      return b && b[0] === b[1] ? b[0] : null;
    }

    selection() {
      return this._bornes() || [null, null];
    }

    placerCurseur(position) {
      const sel = selectionDe(this.el);
      const range = this.modele().plage(position, position);
      sel.removeAllRanges();
      sel.addRange(range);
    }

    remplacer(debut, fin, texte, curseurApres) {
      const el = this.el;
      const avant = this.texte();
      const attendu = avant.slice(0, debut) + texte + avant.slice(fin);
      if (!el.contains(elementActif(el.ownerDocument)) && elementActif(el.ownerDocument) !== el) {
        el.focus({ preventScroll: true });
      }
      const sel = selectionDe(el);
      const range = this.modele().plage(debut, fin);
      sel.removeAllRanges();
      sel.addRange(range);
      const fait = insererTexte(el.ownerDocument, texte);
      if (!fait && this.texte() === avant) {
        // Dernier recours : le DOM lui-même, puis un « input » pour l'éditeur.
        range.deleteContents();
        if (texte) range.insertNode(document.createTextNode(texte));
        el.dispatchEvent(new InputEvent("input", {
          bubbles: true, inputType: "insertReplacementText", data: texte,
        }));
      }
      const reussi = this.texte() === attendu;
      if (reussi && curseurApres !== undefined && curseurApres !== debut + texte.length) {
        this.placerCurseur(curseurApres);
      }
      return reussi;
    }

    rectangles(plages) {
      const m = this.modele();
      return plages.map((p) => Array.from(m.plage(p.debut, p.fin).getClientRects()));
    }

    rectangleCurseur(position) {
      const m = this.modele();
      const range = m.plage(position, position);
      let r = range.getClientRects()[0];
      if (!r && position > 0) {
        const avant = m.plage(position - 1, position).getClientRects();
        const dernier = avant[avant.length - 1];
        if (dernier) r = new DOMRect(dernier.right, dernier.top, 0, dernier.height);
      }
      if (!r) {
        const b = this.el.getBoundingClientRect();
        const s = getComputedStyle(this.el);
        const ligne = parseFloat(s.lineHeight) || parseFloat(s.fontSize) * 1.3 || 18;
        r = new DOMRect(b.left + (parseFloat(s.paddingLeft) || 0), b.top + (parseFloat(s.paddingTop) || 0), 0, ligne);
      }
      return r;
    }

    plages(liste) {
      const m = this.modele();
      return liste.map((p) => m.plage(p.debut, p.fin));
    }

    zoneVisible() {
      return this.el.getBoundingClientRect();
    }

    oublier() {
      this.observateur.disconnect();
    }
  }

  globalThis.KabChamps = {
    champPour, elementActif, auFond, selectionDe, poserMiroirsDans, ChampTexte, ChampEditable, Modele,
  };
})();
