package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Test

/** Combien d'unites UTF-16 un retour arriere doit emporter. */
class RetourArriereTest {

    private fun n(t: String) = ClavierKabyle.longueurRetourArriere(t)

    @Test
    fun `une lettre latine occupe une unite`() {
        assertEquals(1, n("azul"))
        assertEquals(1, n("a"))
    }

    @Test
    fun `une lettre kabyle occupe une unite`() {
        // ɣ ɛ ḥ ẓ sont tous dans le plan de base
        for (mot in listOf("ruḥeɣ", "aɣrum", "ẓẓay", "ɛeddan", "yečča"))
            assertEquals("« ${mot.last()} » devrait tenir en une unite", 1, n(mot))
    }

    @Test
    fun `un texte vide ne fait pas tomber`() {
        assertEquals(1, n(""))
    }

    @Test
    fun `un emoji hors plan de base occupe deux unites`() {
        assertEquals(2, n("azul 🌟"))
        assertEquals(2, n("🌟"))
    }

    @Test
    fun `un emoji a ton de peau part entier`() {
        // Emoji de base + modificateur = deux points de code, quatre unites.
        assertEquals(4, n("👍🏿"))
        assertEquals(4, n("azul 👍🏻"))
    }

    @Test
    fun `un modificateur seul en tete de texte ne deborde pas`() {
        assertEquals(2, n("🏿"))
    }

    @Test
    fun `le trait d'union et l'espace comptent pour un`() {
        assertEquals(1, n("yusa-"))
        assertEquals(1, n("azul "))
    }
}
