package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RelectureTest {

    private val phrase = "Ruhagh ɣer a tamurt 12"

    @Test
    fun `mots a relire avec leur debut, lettres seules et nombres exclus`() {
        val choix = Relecture.aRelire(phrase)
        assertEquals(listOf(0 to "Ruhagh", 7 to "ɣer", 13 to "tamurt"), choix.mots)
        assertFalse(choix.tronque)
    }

    @Test
    fun `au-dela du maximum, la liste est tronquee et le dit`() {
        val choix = Relecture.aRelire(phrase, max = 2)
        assertEquals(listOf(0 to "Ruhagh", 7 to "ɣer"), choix.mots)
        assertTrue(choix.tronque)
    }

    @Test
    fun `restreinte a une plage`() {
        assertEquals(listOf(7 to "ɣer", 13 to "tamurt"), Relecture.aRelire(phrase, 7 until 20).mots)
        // Un mot à cheval sur le bord de la plage n'est pas relu.
        assertEquals(listOf(7 to "ɣer"), Relecture.aRelire(phrase, 5 until 15).mots)
    }

    @Test
    fun `le curseur suit le remplacement`() {
        // « Ruhagh » (6) remplacé par « Ruḥeɣ » (5).
        assertEquals(19, Relecture.curseurApres(20, 0, 6, 5))
        assertEquals(5, Relecture.curseurApres(3, 0, 6, 5))
        assertEquals(0, Relecture.curseurApres(0, 0, 6, 5))
        assertEquals(4, Relecture.curseurApres(4, 7, 3, 5))
    }

    @Test
    fun `la dictee est retrouvee juste avant le curseur`() {
        assertEquals(5 until 12, Relecture.plageDictee("azul fell-ak", 12, "fell-ak"))
        assertNull(Relecture.plageDictee("azul fell-ak", 12, "fell-ik"))
        assertNull(Relecture.plageDictee("azul", 4, "azul fell-ak"))
        assertNull(Relecture.plageDictee("azul", 4, ""))
    }
}
