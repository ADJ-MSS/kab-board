// Le micro, morceau par morceau, vers le document hors écran. Rien ne sort :
// process() ne remplit pas sa sortie, le nœud est muet.
class Capteur extends AudioWorkletProcessor {
  process(entrees) {
    const canaux = entrees[0];
    if (canaux && canaux.length) {
      // Mono : la moyenne des canaux, si le micro en donne plusieurs.
      const n = canaux[0].length;
      const morceau = new Float32Array(n);
      for (const canal of canaux) {
        for (let i = 0; i < n; i++) morceau[i] += canal[i] / canaux.length;
      }
      this.port.postMessage(morceau, [morceau.buffer]);
    }
    return true;
  }
}

registerProcessor("capteur", Capteur);
