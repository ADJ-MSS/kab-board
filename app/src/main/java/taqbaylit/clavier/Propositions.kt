package taqbaylit.clavier

import taqbaylit.moteur.Correcteur

/** Les six propositions d'un mot : la correction absolue, puis le top-5. */
object Propositions {

    /** La correction absolue et le top-5 du mot isole, en formes normalisees. */
    data class Six(val absolue: String, val cinq: List<String>, val raison: String? = null)

    /** Bloque le fil appelant : a n'appeler que depuis Moteur.avec. */
    fun calculer(c: Correcteur, gauche: String, mot: String): Six {
        // Position 1 : la correction en contexte. Le correcteur rend la phrase
        // entiere, et le dernier mot est celui qu'on juge.
        val resultat = c.corriger("$gauche $mot")
        val absolue = resultat.texteCorrige.trim().substringAfterLast(' ')
        val raison = resultat.annexions
            .lastOrNull { it.idx == resultat.tokensEntree.lastIndex }?.raison
        // Positions 2 a 6 : le top-5 du mot isole, qui exclut le mot lui-meme.
        val cinq = c.topCandidats(mot, 5).map { it.forme }
        return Six(absolue, cinq, raison)
    }
}
