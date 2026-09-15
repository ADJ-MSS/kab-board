package taqbaylit.moteur

/** Port de pipeline/v2/decodeur.py : recherche en faisceau sur la phrase. */
object Decodeur {
    const val W_LM = 0.5f          // poids du log10 KenLM
    const val BEAM = 8             // largeur du faisceau
    const val MAX_CAND_BEAM = 6    // candidats par position entrant dans le faisceau

    private class Chemin(val score: Double, val etat: ModeleLangue.Etat, val suite: List<Candidat>)

    /** Un candidat par position, maximise score local + W_LM × log P(KenLM). */
    fun decoder(candsParPos: List<List<Candidat>>, lm: ModeleLangue?,
                wLm: Float = W_LM, beam: Int = BEAM): List<Candidat> {
        if (candsParPos.isEmpty()) return emptyList()

        // Pas de LM : le meilleur score local, la liste est déjà triée
        if (lm == null || wLm <= 0f) return candsParPos.map { it.first() }

        val aLiberer = ArrayList<ModeleLangue.Etat>()
        try {
            val e0 = lm.etat().also { aLiberer.add(it); lm.debutPhrase(it) }
            var faisceau = listOf(Chemin(0.0, e0, emptyList()))

            for (cands in candsParPos) {
                val nouveaux = ArrayList<Chemin>(faisceau.size * cands.size)
                for (ch in faisceau) {
                    for (c in cands) {
                        val sortie = lm.etat().also { aLiberer.add(it) }
                        val lp = lm.baseScore(ch.etat, c.forme, sortie)
                        nouveaux.add(Chemin(ch.score + c.score + wLm * lp,
                                            sortie, ch.suite + c))
                    }
                }
                nouveaux.sortByDescending { it.score }
                faisceau = nouveaux.take(beam)
            }

            var meilleurScore = Double.NEGATIVE_INFINITY
            var meilleur: List<Candidat> = emptyList()
            for (ch in faisceau) {
                val sortie = lm.etat().also { aLiberer.add(it) }
                val total = ch.score + wLm * lm.baseScore(ch.etat, "</s>", sortie)
                if (total > meilleurScore) { meilleurScore = total; meilleur = ch.suite }
            }
            return meilleur
        } finally {
            aLiberer.forEach { it.close() }
        }
    }
}
