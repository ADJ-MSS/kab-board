package taqbaylit.moteur

/** Le mot suivant, avant qu'une seule lettre soit tapee. */
class Prediction(private val lm: ModeleLangue, private val candidats: List<String>) {

    val disponible: Boolean get() = candidats.isNotEmpty()

    /** Les nb formes les plus probables apres contexteGauche. */
    fun suivants(contexteGauche: String, nb: Int = 5): List<String> {
        if (candidats.isEmpty()) return emptyList()
        val tokens = Normalisation.tokenize(dernierePhrase(contexteGauche))
        lm.etat().use { entree ->
            lm.etat().use { sortie ->
                lm.debutPhrase(entree)
                for (t in tokens) { lm.baseScore(entree, t, sortie); lm.copier(sortie, entree) }

                // Selection des nb meilleurs, sans trier les 5 000.
                val tete = arrayOfNulls<String>(nb)
                val scores = FloatArray(nb) { Float.NEGATIVE_INFINITY }
                var remplis = 0
                for (mot in candidats) {
                    val score = lm.baseScore(entree, mot, sortie)
                    if (remplis == nb && score <= scores[nb - 1]) continue
                    var i = minOf(remplis, nb - 1)
                    while (i > 0 && score > scores[i - 1]) {
                        scores[i] = scores[i - 1]; tete[i] = tete[i - 1]; i--
                    }
                    scores[i] = score; tete[i] = mot
                    if (remplis < nb) remplis++
                }
                return tete.take(remplis).filterNotNull()
            }
        }
    }

    /** Ce qui suit le dernier point, point d'exclamation ou d'interrogation. */
    private fun dernierePhrase(texte: String): String {
        var coupe = -1
        for (i in texte.indices) if (texte[i] == '.' || texte[i] == '!' || texte[i] == '?') coupe = i
        return if (coupe >= 0) texte.substring(coupe + 1) else texte
    }
}
