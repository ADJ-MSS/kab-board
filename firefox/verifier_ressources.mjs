// Les ressources compressées de l'extension pour Firefox redonnent-elles, décompressées
// par le correcteur lui-même (moteur/compression.js, kab_xz.wasm), les fichiers d'origine,
// octet pour octet ?
//
//   node firefox/verifier_ressources.mjs firefox/extension [chemin…]
//
// Sans chemin, tous ceux de compresses.json.
import crypto from "node:crypto";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [extension, ...chemins] = process.argv.slice(2);
const moteur = path.resolve(extension, "moteur");
const ressources = path.resolve(extension, "ressources");
// Le module d'Emscripten, fait pour le navigateur, attend sous Node ce que donne CommonJS.
globalThis.require = createRequire(import.meta.url);
globalThis.__dirname = moteur;
const { default: KabXz } = await import(pathToFileURL(path.join(moteur, "kab_xz.mjs")).href);
const { restituer } = await import(pathToFileURL(path.join(moteur, "compression.js")).href);
const infos = JSON.parse(fs.readFileSync(path.join(ressources, "compresses.json"), "utf8"));

async function* morceaux(base, parties) {
  for (let k = 1; k <= parties; k++) {
    for await (const c of fs.createReadStream(`${base}.xz.${k}`, { highWaterMark: 1 << 22 })) {
      yield new Uint8Array(c.buffer, c.byteOffset, c.length);
    }
  }
}

let ok = 0;
const liste = chemins.length ? chemins : Object.keys(infos);
for (const chemin of liste) {
  const info = infos[chemin];
  const t = performance.now();
  const octets = await restituer(KabXz, { wasmBinary: fs.readFileSync(path.join(moteur, "kab_xz.wasm")) },
    morceaux(path.join(ressources, chemin), info.parties), info);
  const secondes = (performance.now() - t) / 1000;
  const h = crypto.createHash("sha256").update(octets).digest("hex");
  const identique = h === info.sha256;
  if (identique) ok++;
  console.log(`  ${chemin} : ${identique ? "identique" : "DIFFÉRENT"} (${secondes.toFixed(1)} s)`);
}
process.exit(ok === liste.length ? 0 : 1);
