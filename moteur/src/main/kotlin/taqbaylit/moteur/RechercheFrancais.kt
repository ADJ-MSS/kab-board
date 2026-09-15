package taqbaylit.moteur

import java.text.Normalizer

/** Trouver un mot kabyle à partir d'un mot français, dans les gloses du graphe sémantique. */
object RechercheFrancais {

    /** Une forme trouvée : sa glose, la place du mot cherché, sa fréquence au lexique. */
    data class Trouve(val forme: String, val glose: String, val rang: Int, val frequence: Int)

    /** En dessous de deux lettres, presque toutes les gloses répondraient. */
    const val REQUETE_MIN = 2

    private val SEPARATEURS = charArrayOf(',', ';', '.', '‖', '(', ')', '[', ']', ':', '!', '?')
    private val BLANCS = Regex("\\s+")

    /**
     * Minuscules, sans diacritiques, blancs réduits : « École » et « ecole » se
     * valent, puisqu'on tape souvent le français sans accents sur ce clavier.
     */
    fun plier(texte: String): String {
        val decompose = Normalizer.normalize(texte.lowercase(), Normalizer.Form.NFD)
        val sb = StringBuilder(decompose.length)
        for (c in decompose) {
            if (Character.getType(c) != Character.NON_SPACING_MARK.toInt()) sb.append(c)
        }
        return BLANCS.replace(sb.toString().trim(), " ")
    }

    /** Première occurrence de mot en mot entier dans texte, ou -1. */
    private fun occurrence(texte: String, mot: String): Int {
        var i = texte.indexOf(mot)
        while (i >= 0) {
            val fin = i + mot.length
            val avantLibre = i == 0 || !texte[i - 1].isLetterOrDigit()
            val apresLibre = fin == texte.length || !texte[fin].isLetterOrDigit()
            if (avantLibre && apresLibre) return i
            i = texte.indexOf(mot, i + 1)
        }
        return -1
    }

    /**
     * Place du mot cherché dans une glose, toutes deux déjà pliées ; null si le mot n'y figure pas
     * en mot entier.
     */
    fun rang(glosePliee: String, requetePliee: String): Int? {
        if (requetePliee.length < REQUETE_MIN) return null
        if (occurrence(glosePliee, requetePliee) < 0) return null
        val segments = glosePliee.split(*SEPARATEURS).map { it.trim() }.filter { it.isNotEmpty() }
        val premier = segments.firstOrNull() ?: return 4
        val dansLePremier = occurrence(premier, requetePliee)
        return when {
            premier == requetePliee -> 0
            segments.any { it == requetePliee } -> 1
            dansLePremier == 0 -> 2
            dansLePremier > 0 -> 3
            else -> 4
        }
    }

    /** Le meilleur rang d'abord, puis la forme la plus fréquente, puis l'ordre alphabétique. */
    fun classer(trouves: List<Trouve>, nb: Int): List<Trouve> =
        trouves.sortedWith(compareBy<Trouve>({ it.rang }, { -it.frequence }, { it.forme })).take(nb)
}
