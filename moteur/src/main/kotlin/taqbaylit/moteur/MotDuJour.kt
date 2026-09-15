package taqbaylit.moteur

/** Un mot courant et sa glose, qui change chaque jour. */
object MotDuJour {

    /** Longueur maximale d'une glose retenue. */
    const val GLOSE_MAX = 80

    private const val MS_PAR_JOUR = 86_400_000L

    /**
     * Les candidats, dans un ordre fixe mais sans rapport avec la fréquence : sans
     * ce mélange, les premiers jours ne montreraient que des mots-outils.
     */
    fun candidats(frequents: List<String>, glose: (String) -> String): List<String> =
        frequents
            .distinct()
            .filter { val g = glose(it); g.isNotBlank() && g.length <= GLOSE_MAX }
            .sortedWith(compareBy({ it.hashCode() }, { it }))

    /** Le mot du jour [jour], compté en jours depuis l'origine. */
    fun choisir(candidats: List<String>, jour: Long): String? =
        if (candidats.isEmpty()) null
        else candidats[Math.floorMod(jour, candidats.size.toLong()).toInt()]

    /**
     * Le numéro du jour local, sans java.time : l'application descend jusqu'à
     * l'API 24, où java.time n'existe pas sans désucrage.
     */
    fun jourLocal(maintenantMs: Long, decalageMs: Int): Long =
        Math.floorDiv(maintenantMs + decalageMs, MS_PAR_JOUR)
}
