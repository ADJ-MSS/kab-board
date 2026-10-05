package taqbaylit.clavier

import taqbaylit.moteur.Correcteur

/** Les six propositions d'un mot : la correction absolue, puis le top-5. */
object Propositions {

    /**
     * La correction absolue et le top-5 du mot isole, en formes normalisees. motsAvant dit
     * combien de mots deja ecrits la correction absolue remplace aussi : 1 quand elle
     * rattache un possessif au nom qui le precede (« tamurt iw » -> « tamurt-iw »).
     * Le top-5, lui, ne remplace jamais que le mot en cours.
     */
    data class Six(val absolue: String, val cinq: List<String>, val raison: String? = null,
                   val motsAvant: Int = 0)

    /** Bloque le fil appelant : a n'appeler que depuis Moteur.avec. */
    fun calculer(c: Correcteur, gauche: String, mot: String,
                 mode: GraphieBV.Mode = GraphieBV.Mode.V): Six {
        // Position 1 : la correction en contexte. Le correcteur rend la phrase
        // entiere, et le dernier mot est celui qu'on juge.
        val resultat = c.corriger("$gauche $mot")
        var absolue = resultat.texteCorrige.trim().substringAfterLast(' ')
        var motsAvant = resultat.couvertureFin - 1
        // Le correcteur fond le possessif avec le mot d'avant meme par-dessus une virgule,
        // qu'il ne voit pas : on ne garde alors que le mot en cours.
        if (motsAvant > 0 && ClavierKabyle.longueurMotsAvant("$gauche ", motsAvant) < 0) {
            absolue = absolue.substringAfterLast('-')
            motsAvant = 0
        }
        val raison = resultat.annexions
            .lastOrNull { it.idx == resultat.tokensEntree.lastIndex }?.raison
        // Positions 2 a 6 : le top-5 du mot isole, qui exclut le mot lui-meme.
        val brutes = c.topCandidats(mot, 5).map { it.forme }
        // La graphie reglee vaut pour les six, pas pour la seule correction.
        return Six(GraphieBV.basculer(absolue, mode),
                   GraphieBV.appliquer(brutes, mode), raison,
                   if (absolue.isBlank()) 0 else motsAvant)
    }
}
