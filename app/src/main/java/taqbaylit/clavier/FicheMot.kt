package taqbaylit.clavier

import taqbaylit.moteur.Postprocess

/** Ce que la fiche d'un mot (l'outil Asegzawal) dit de sa grammaire. */
object FicheMot {

    /** Les catégories du lexique que Postprocess traite en noms. */
    private val NOMINALES = setOf("masc", "fem", "fem_pl", "adj_masc", "adj_fem", "ambig")

    /** Longueur d'une glose dans une liste de résultats, au-delà de quoi elle est coupée. */
    const val GLOSE_COURTE = 48

    data class Etats(val libre: String, val annexion: String)

    /** Les deux états d'un nom, ou null si la forme n'en a pas. */
    fun etats(post: Postprocess, forme: String, estVerbe: Boolean, categorie: String?): Etats? {
        if (estVerbe) return null
        if (categorie != null && categorie !in NOMINALES) return null
        var (estNom, etat, _) = post.identifierNomEtat(forme)
        if (categorie != null) {
            estNom = true
            if (etat == "invariable") etat = "libre"
        }
        if (!estNom || etat == null || etat == "invariable") return null
        val libre = if (etat == "libre") forme else post.versLibre(forme)
        val annexion = if (etat == "annexion") forme else post.versAnnexion(forme)
        return if (libre == annexion) null else Etats(libre, annexion)
    }

    /**
     * Le début d'une glose, pour une ligne de résultat : son premier segment,
     * coupé à [max] caractères.
     */
    fun gloseCourte(glose: String, max: Int = GLOSE_COURTE): String {
        val premier = glose.split(';', '‖').first().trim()
        return if (premier.length <= max) premier else premier.take(max - 1).trimEnd() + "…"
    }
}
