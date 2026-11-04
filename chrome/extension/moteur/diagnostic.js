// Ce qui dit pourquoi le correcteur ne se charge pas : un journal du chargement, étape par
// étape, et la cause en clair, avec ce qu'il faut faire. Le journal se lit et se copie dans
// les réglages de l'extension.

const debut = performance.now();
export const journal = [];

export function noter(texte) {
  journal.push(`[${((performance.now() - debut) / 1000).toFixed(2).padStart(6)} s] ${texte}`);
}

export const mo = (n) => (n < 1e6 ? `${Math.max(1, Math.round(n / 1e3))} Ko`
  : `${(n / 1e6).toFixed(1).replace(".", ",")} Mo`);

/** Une erreur dont on connaît la cause : memoire, manquant, incomplet, illisible, wasm. */
export function erreur(cause, message, fichier = "") {
  return Object.assign(new Error(message), { kab: cause, fichier });
}

const MEMOIRE = /out of memory|\boom\b|allocation failed|cannot enlarge memory|could not allocate|memory\.grow|maximum memory|insufficient memory/i;

const REINSTALLER = "L'extension est incomplète ou abîmée : retéléchargez l'archive, " +
  "décompressez-la entièrement (sans l'ouvrir seulement), puis, dans la page des extensions, " +
  "supprimez kab-board et chargez de nouveau le dossier.";

/** La cause d'une erreur du chargement : { erreur, conseil }. */
export function expliquer(e) {
  const message = String(e && e.message || e);
  const nom = e && e.name || "";
  const cause = e && e.kab || (MEMOIRE.test(message) ? "memoire"
    : /^(CompileError|LinkError)$/.test(nom) ? "wasm" : "");
  switch (cause) {
    case "memoire":
      return {
        erreur: "Mémoire insuffisante : " + message,
        conseil: "Le correcteur a besoin d'environ 750 Mo de mémoire libre. Fermez des onglets " +
          "et d'autres programmes (ou redémarrez l'ordinateur), puis cliquez sur Réessayer.",
      };
    case "manquant":
      return { erreur: "Fichier manquant : " + message, conseil: REINSTALLER };
    case "incomplet":
      return { erreur: "Fichier incomplet : " + message, conseil: REINSTALLER };
    case "illisible":
      return { erreur: "Fichier abîmé : " + message, conseil: REINSTALLER };
    case "wasm":
      return {
        erreur: e && e.kab ? message : `WebAssembly refusé par le navigateur : ${message}`,
        conseil: "Le correcteur tourne en WebAssembly. Mettez le navigateur à jour. Dans Edge, " +
          "la « sécurité renforcée » (Paramètres › Confidentialité, recherche et services) peut " +
          "le bloquer : désactivez-la, ou passez-la en mode équilibré. Sur un ordinateur géré " +
          "(entreprise, école), une règle de l'administrateur peut aussi l'interdire.",
      };
    default:
      return {
        erreur: "Erreur inattendue : " + message,
        conseil: "Cliquez sur Réessayer. Si l'erreur revient, copiez le journal ci-dessous et " +
          "envoyez-le avec le nom de l'ordinateur et du navigateur.",
      };
  }
}

/** Ce que le navigateur dit de l'appareil, en tête du journal. */
export function noterAppareil() {
  const n = globalThis.navigator || {};
  noter(`navigateur : ${n.userAgent || "?"}`);
  if (n.deviceMemory) noter(`mémoire de l'appareil, selon le navigateur : environ ${n.deviceMemory} Go`);
  if (n.hardwareConcurrency) noter(`processeurs : ${n.hardwareConcurrency}`);
  const wasm = typeof WebAssembly === "object";
  noter(`WebAssembly : ${wasm ? "oui" : "non"}${wasm ? `, exceptions : ${typeof WebAssembly.Tag === "function" ? "oui" : "non"}` : ""}`);
  if (!wasm) throw erreur("wasm", "WebAssembly est désactivé dans ce navigateur.");
}
