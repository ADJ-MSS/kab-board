package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import taqbaylit.clavier.TraitDeNature.Motif

class TraitDeNatureTest {

    @Test
    fun `plein, un seul segment`() {
        assertEquals(listOf(0f to 40f), TraitDeNature.segments(40f, Motif.PLEIN, 2f))
    }

    @Test
    fun `tirets de quatre epaisseurs, blancs de deux`() {
        assertEquals(listOf(0f to 8f, 12f to 20f), TraitDeNature.segments(20f, Motif.TIRETS, 2f))
    }

    @Test
    fun `points d'une epaisseur, blancs d'une et demie`() {
        assertEquals(
            listOf(0f to 2f, 5f to 7f, 10f to 12f, 15f to 17f),
            TraitDeNature.segments(20f, Motif.POINTS, 2f))
    }

    @Test
    fun `les trois motifs se distinguent par le nombre de segments`() {
        val plein = TraitDeNature.segments(64f, Motif.PLEIN, 2f).size
        val tirets = TraitDeNature.segments(64f, Motif.TIRETS, 2f).size
        val points = TraitDeNature.segments(64f, Motif.POINTS, 2f).size
        assertTrue(plein < tirets && tirets < points)
    }

    @Test
    fun `aucun segment ne sort de la largeur`() {
        for (motif in Motif.entries) {
            for ((debut, fin) in TraitDeNature.segments(37f, motif, 3f)) {
                assertTrue(debut >= 0f && fin <= 37f && debut < fin)
            }
        }
    }

    @Test
    fun `largeur nulle, rien a tracer`() {
        for (motif in Motif.entries) assertTrue(TraitDeNature.segments(0f, motif, 2f).isEmpty())
    }
}
