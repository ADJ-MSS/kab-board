// Le correcteur de l'extension : le moteur de l'application Android, chargé une fois, et
// les requêtes auxquelles répondait le service de l'ordinateur (proposer, predire,
// juger, fiche, chercher, motdujour, basculer), avec les mêmes réponses.

import {
  AUCUN, CONTEXTE_MAX, MAX_PROPOSITIONS, casserComme, corrigerMot, etats, gloseCourte,
  jugerMot, longueurMotsAvant, mots, predireSuite,
} from "./clavier.js";
import { Correcteur } from "./correcteur.js";
import { Etiqueteur } from "./etiqueteur.js";
import { GraphieBV } from "./graphie.js";
import { derniers, estLettre, rogner } from "./kotlin.js";
import { ModeleLangue } from "./modele_langue.js";
import { MotDuJour } from "./mot_du_jour.js";
import { normalize } from "./normalisation.js";
import { lignes } from "./ressources.js";

/** Les fichiers du dossier moteur dont le correcteur se sert, le modèle de langue à part. */
export const FICHIERS = [
  "amyag.mots", "lexcat.cat", "lexcat.mots", "lexcat.noms", "lexique.freq", "lexique.mots",
  "lexique.nsrc", "listes.txt", "pool.freq", "pool.frequents", "pool.mots", "pool.nsrc", "pool.sdx",
  "pool.src", "pool.srcnoms", "wordnet.ancrages", "wordnet.formes", "wordnet.gloses", "wordnet.voisins",
];
export const MODELE_LANGUE = "kabyle_3gram.binary";
export const ETIQUETEUR = "pos_kab.crfsuite";
export const TABLE_BV = "table_bv.tsv";

/** Mots relus au plus d'un coup, comme le service de l'ordinateur. */
const RELIRE_MOTS_MAX = 400;
const RESULTATS_MAX = 8;

export const CATEGORIES = {
  adj_fem: "adjectif féminin", adj_masc: "adjectif masculin", adverb: "adverbe",
  ambig: "nom ou adjectif", conj: "conjonction", fem: "nom féminin", fem_pl: "nom féminin pluriel",
  interj: "interjection", locution: "locution", masc: "nom masculin", num: "numéral",
  particle: "particule", prep: "préposition", presentat: "présentatif", pron: "pronom",
  propn: "nom propre",
};

/** La graphie en v au départ, comme sur le téléphone : b seulement si on l'a choisi. */
function mode(requete) {
  return requete.graphie === "b" ? "b" : "v";
}

export class Moteur {
  constructor(c, graphie) {
    this.c = c;
    this.graphie = graphie;
  }

  /**
   * lire(nom) : les octets d'un fichier des ressources (dossier moteur, et
   * table_bv.tsv), en promesse. modules : { KenLM, CRFsuite, optionsKenLM, optionsCRF },
   * les fabriques des modules WebAssembly et leurs options.
   */
  static async charger(lire, modules) {
    const fichiers = new Map();
    await Promise.all(FICHIERS.map(async (nom) => fichiers.set(nom, await lire(nom))));
    const table = await lire(TABLE_BV);
    const tagger = await Etiqueteur.ouvrir(modules.CRFsuite, await lire(ETIQUETEUR), modules.optionsCRF || {});
    const lm = await ModeleLangue.ouvrir(modules.KenLM, await lire(MODELE_LANGUE), modules.optionsKenLM || {});
    const c = new Correcteur((nom) => fichiers.get(nom) ?? null, lm, tagger);
    // La complétion, construite d'avance : la barre ne l'attend jamais.
    void c.completion;
    return new Moteur(c, new GraphieBV(lignes(table)));
  }

  /** La barre du mot en cours : complétion de 1 à 3 lettres, sinon la correction. */
  proposer(contexte, mot, mode) {
    if (!mot) return { nature: "prop", formes: [], mots_avant: 0 };
    const b = corrigerMot(this.c, this.graphie, mot, derniers(contexte, CONTEXTE_MAX), mode);
    return { nature: b.nature, formes: b.formes.slice(0, MAX_PROPOSITIONS), mots_avant: b.motsAvant };
  }

  /** Le mot suivant. */
  predire(contexte, mode) {
    return predireSuite(this.c, this.graphie, derniers(contexte, CONTEXTE_MAX), mode).slice(0, MAX_PROPOSITIONS);
  }

  /**
   * Les soulignés et « Relire » : jugerMot sur chaque mot de texte, et la fusion des
   * possessifs. avant : le texte qui précède, pour le contexte des premiers mots ; un
   * signal qui commence avant texte a un début négatif. connus : les mots de « mon
   * dictionnaire », en minuscules, qui passent.
   */
  juger(texte, avant, mode, nb = 5, connus = new Set()) {
    const signales = [];
    const plein = avant + texte;
    const base = avant.length;
    for (const [n, [debut, mot]] of mots(texte).entries()) {
      if (n >= RELIRE_MOTS_MAX) break;
      if (mot.length < 2 || ![...mot].some((c) => c.length === 1 && estLettre(c)) || connus.has(mot.toLowerCase())) continue;
      const gauche = derniers(rogner(plein.slice(0, base + debut)), CONTEXTE_MAX);
      const j = jugerMot(this.c, this.graphie, gauche, mot, nb, mode);
      if (j.fusion !== null) {
        // Le mot et ceux d'avant, à fondre en un : « tamurt iw » -> « tamurt-iw ».
        const k = longueurMotsAvant(plein.slice(0, base + debut), j.motsAvant);
        if (k > 0) {
          const portee = plein.slice(base + debut - k, base + debut + mot.length);
          if (!connus.has(portee.toLowerCase())) {
            signales.push({ mot: portee, debut: debut - k, fin: debut + mot.length,
              propositions: [casserComme(portee, j.fusion)], soulignement: "faute", fusion: true });
          }
        }
      }
      if (j.soulignement === AUCUN || !j.propositions.length) continue;
      signales.push({ mot, debut, fin: debut + mot.length, propositions: j.propositions,
        soulignement: j.soulignement, fusion: false });
    }
    return signales;
  }

  /** Asegzawal : la glose, la catégorie, la fréquence et les deux états d'un nom. */
  fiche(mot, mode) {
    const res = this.c.res;
    const forme = normalize(mot);
    if (!forme) return { mot: "", glose: "", categorie: "", libre: "", annexion: "" };
    // « aɣrum-a » : la glose et la catégorie sont celles du nom.
    const base = forme.split("-")[0];
    const categorie = res.lexcat(forme) ?? res.lexcat(base);
    const verbe = res.amyag.has(forme) || res.amyag.has(base);
    const e = etats(this.c.postprocess, forme, verbe, categorie);
    const g = (f) => this.graphie.basculer(f, mode);
    return {
      mot: g(forme),
      glose: res.glose(forme) || res.glose(base),
      categorie: categorie !== null ? CATEGORIES[categorie] ?? categorie : verbe ? "forme verbale" : "",
      frequence: res.freq(forme),
      libre: e ? g(e.libre) : "",
      annexion: e ? g(e.annexion) : "",
    };
  }

  /** Du français au kabyle : les formes dont la glose répond le mieux. */
  chercher(requete, mode) {
    return this.c.res.chercherFrancais(requete, RESULTATS_MAX)
      .map((t) => [this.graphie.basculer(t.forme, mode), gloseCourte(t.glose)]);
  }

  /** Le mot du jour, le jour local de maintenant. */
  motDuJour(mode, maintenant = Date.now(), decalage = -new Date(maintenant).getTimezoneOffset() * 60000) {
    const m = MotDuJour.choisir(this.c.res.motsDuJour, MotDuJour.jourLocal(maintenant, decalage));
    return m ? { forme: this.graphie.basculer(m, mode), glose: this.c.res.glose(m) } : { forme: "", glose: "" };
  }

  /** Une requête du script de contenu ou du popup, et sa réponse. */
  traiter(r) {
    const g = mode(r);
    switch (r.quoi) {
      case "proposer":
        return this.proposer(String(r.contexte ?? ""), String(r.mot ?? ""), g);
      case "predire":
        return { formes: this.predire(String(r.contexte ?? ""), g) };
      case "juger": {
        const nb = Math.max(1, Math.min(Number(r.nb) || 5, MAX_PROPOSITIONS));
        return { signales: this.juger(String(r.texte ?? ""), String(r.avant ?? ""), g, nb, new Set(r.connus || [])) };
      }
      case "fiche":
        return this.fiche(String(r.mot ?? "").trim(), g);
      case "chercher":
        return { trouves: this.chercher(String(r.requete ?? "").trim(), g) };
      case "motdujour":
        return this.motDuJour(g);
      case "basculer":
        return { texte: this.graphie.appliquerTexte(String(r.texte ?? ""), g) };
      default:
        return { erreur: "requête inconnue" };
    }
  }
}

