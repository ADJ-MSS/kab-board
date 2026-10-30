// Un faux correcteur pour l'essai de l'extension dans le navigateur : essai_navigateur.mjs
// le met à la place de moteur/travailleur.js. Le vrai a besoin de 350 Mo de ressources,
// que la CI n'a pas. Celui-ci donne pour les phrases de l'essai ce que donne le vrai
// (relevé le 30/10/2026) : l'essai passe avec l'un comme avec l'autre.

import { casserComme, mots } from "./clavier.js";

// Les réponses du vrai correcteur, en minuscules ; la casse suit le mot tapé.
const PROPOSITIONS = {
  "ttruɣ": ["ttruɣ", "ttru", "ttuɣ", "ttaruɣ", "ttrun", "truɣ"],
  "tamurt": ["tamurt", "tmurt", "takurt", "tamart", "temurt", "tamunt"],
  "ruheɣ": ["ruḥeɣ", "ruhen", "ruhaɣ", "ṛuheɣ", "ruyeɣ"],
  "aɣrum": ["aɣrum", "uɣrum", "adrum", "aɣṛum", "aɣrud", "arum"],
  "tamettut": ["tameṭṭut", "tmettut", "tamattut", "tameɣtut", "tamettit", "takettut"],
};
// Le jugement de chaque mot : tous connus du correcteur, que le contexte écrirait
// autrement, donc des doutes. « mot d'avant|mot » passe devant le mot seul.
const JUGEMENTS = {
  "ruheɣ": ["ruḥeɣ", "ruhen", "ruhaɣ", "ṛuheɣ", "ruyeɣ"],
  "ruhaɣ": ["ruḥeɣ", "ruheɣ", "rujaɣ", "uhaɣ", "cuhaɣ"],
  "ɣar": ["ɣer", "ar", "gar", "ɣas", "war"],
  "tamettut": ["tmeṭṭut", "tmettut", "tamattut", "tameɣtut", "tamettit"],
  "ttwalaɣ|tamettut": ["tameṭṭut", "tmettut", "tamattut", "tameɣtut", "tamettit"],
  "ttwalaɣ": ["ttwaliɣ", "t-walaɣ", "tt-walaɣ", "twalaɣ", "ttlalaɣ"],
};
const COMPLETIONS = ["almi", "ayen", "armi", "akken", "acku", "aṭas", "aɣ", "aɣrum", "aɣvalu",
  "aɣervaz", "aɣyul", "aɣelluy", "takurt"];
const SUITE = ["fell-as", "ɣef", "ma", "am", "medden", "tettru"];
const GRAPHIE_B = { avrid: "abrid", vava: "baba" };
const FICHES = { aɣrum: { glose: "pain, galette", categorie: "nom masculin", frequence: 8100, libre: "aɣrum", annexion: "uɣrum" } };
const FRANCAIS = { pain: [["aɣrum", "pain, galette"], ["tagella", "aliment à base de farine, pain, nourriture"]] };

function graphie(mot, mode) {
  if (mode === "b") return GRAPHIE_B[mot] || mot;
  const v = Object.keys(GRAPHIE_B).find((k) => GRAPHIE_B[k] === mot);
  return v || mot;
}

function proposer(mot, mode) {
  const bas = mot.toLowerCase();
  if ([...bas].length <= 3) {
    const formes = COMPLETIONS.filter((f) => f.startsWith(bas)).map((f) => casserComme(mot, graphie(f, mode)));
    if (formes.length) return { nature: "comp", formes: formes.slice(0, 6), mots_avant: 0 };
  }
  const formes = PROPOSITIONS[bas] || [bas];
  return { nature: "prop", formes: formes.map((f) => casserComme(mot, graphie(f, mode))).slice(0, 6), mots_avant: 0 };
}

function juger(texte, avant, mode, nb) {
  const signales = [];
  let precedent = (mots(avant).pop() || [0, ""])[1].toLowerCase();
  for (const [debut, mot] of mots(texte)) {
    const bas = mot.toLowerCase();
    const propositions = JUGEMENTS[precedent + "|" + bas] || JUGEMENTS[bas];
    precedent = bas;
    if (!propositions) continue;
    signales.push({
      mot, debut, fin: debut + mot.length, soulignement: "doute", fusion: false,
      propositions: propositions.map((p) => casserComme(mot, graphie(p, mode))).slice(0, nb),
    });
  }
  return signales;
}

function traiter(r) {
  const mode = r.graphie === "b" ? "b" : "v";
  switch (r.quoi) {
    case "proposer":
      return proposer(String(r.mot || ""), mode);
    case "predire":
      return { formes: SUITE };
    case "juger":
      return { signales: juger(String(r.texte || ""), String(r.avant || ""), mode, Math.max(1, Math.min(Number(r.nb) || 5, 6))) };
    case "fiche": {
      const mot = String(r.mot || "").trim();
      return { mot, glose: "", categorie: "", libre: "", annexion: "", ...FICHES[mot.toLowerCase()] };
    }
    case "chercher":
      return { trouves: FRANCAIS[String(r.requete || "").trim().toLowerCase()] || [] };
    case "motdujour":
      return { forme: "temɣer", glose: "vieillesse" };
    case "basculer":
      return { texte: String(r.texte || "").replace(/\p{L}+/gu, (m) => graphie(m, mode)) };
    default:
      return { erreur: "requête inconnue" };
  }
}

postMessage({ etat: "chargement" });
setTimeout(() => postMessage({ etat: "pret", secondes: 0.3 }), 300);

onmessage = (e) => {
  const { id, requete, audio } = e.data;
  // Une seconde au moins de son : « azul fell-awen ».
  const reponse = audio ? { texte: audio.length >= 16000 ? "azul fell-awen" : "" } : traiter(requete);
  postMessage({ id, reponse });
};
