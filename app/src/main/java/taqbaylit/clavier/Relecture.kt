package taqbaylit.clavier

/** Les calculs de l'outil « Relire », sans vue ni Android. */
object Relecture {

    /**
     * Mots relus au plus. VERSIONS.md donne ~517 ms par mot pour une correction sur l'appareil de
     * test, mesure d'une construction antérieure que rien n'a relancée depuis.
     */
    const val MOTS_MAX = 40

    /** Longueur de texte demandée au champ. */
    const val CARACTERES_MAX = 4000

    data class Choix(val mots: List<Pair<Int, String>>, val tronque: Boolean)

    /** Les mots à relire dans texte, avec leur début, restreints à plage quand elle est donnée. */
    fun aRelire(texte: String, plage: IntRange? = null, max: Int = MOTS_MAX): Choix {
        val tous = CorrecteurSysteme.mots(texte).filter { (debut, mot) ->
            mot.length >= 2 && mot.any { it.isLetter() } &&
                (plage == null || (debut >= plage.first && debut + mot.length <= plage.last + 1))
        }
        return Choix(tous.take(max), tous.size > max)
    }

    /**
     * Où remettre le curseur après avoir remplacé longueur unités à partir de debut par nouvelle
     * unités.
     */
    fun curseurApres(curseur: Int, debut: Int, longueur: Int, nouvelle: Int): Int = when {
        curseur >= debut + longueur -> curseur + nouvelle - longueur
        curseur > debut -> debut + nouvelle
        else -> curseur
    }

    /**
     * La plage du texte dicté, s'il se trouve encore juste avant le curseur ;
     * null sinon, et la relecture porte alors sur tout le texte.
     */
    fun plageDictee(texte: String, curseur: Int, dicte: String): IntRange? {
        val debut = curseur - dicte.length
        if (dicte.isEmpty() || debut < 0 || curseur > texte.length) return null
        return if (texte.regionMatches(debut, dicte, 0, dicte.length)) debut until curseur else null
    }
}
