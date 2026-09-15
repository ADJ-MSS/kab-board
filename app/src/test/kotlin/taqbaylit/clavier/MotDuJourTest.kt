package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import taqbaylit.moteur.MotDuJour

class MotDuJourTest {

    private val gloses = mapOf(
        "axxam" to "maison, famille",
        "aɣrum" to "pain, galette",
        "aman" to "eau",
        "d" to "",
        "long" to "x".repeat(MotDuJour.GLOSE_MAX + 1)
    )

    @Test
    fun `candidats sans glose ou a glose trop longue ecartes`() {
        val c = MotDuJour.candidats(listOf("axxam", "d", "aɣrum", "long", "aman", "axxam")) {
            gloses[it] ?: ""
        }
        assertEquals(setOf("axxam", "aɣrum", "aman"), c.toSet())
        assertEquals(3, c.size)
    }

    @Test
    fun `ordre fixe, independant de l'ordre d'entree`() {
        val a = MotDuJour.candidats(listOf("axxam", "aɣrum", "aman")) { gloses[it] ?: "" }
        val b = MotDuJour.candidats(listOf("aman", "axxam", "aɣrum")) { gloses[it] ?: "" }
        assertEquals(a, b)
    }

    @Test
    fun `choisir tourne sur les candidats, jours negatifs compris`() {
        val c = listOf("a", "b", "c")
        assertEquals("a", MotDuJour.choisir(c, 0))
        assertEquals("b", MotDuJour.choisir(c, 4))
        assertEquals("c", MotDuJour.choisir(c, -1))
        assertNull(MotDuJour.choisir(emptyList(), 12))
    }

    @Test
    fun `le jour local suit le decalage horaire`() {
        val jourMs = 86_400_000L
        assertEquals(0L, MotDuJour.jourLocal(0, 0))
        assertEquals(1L, MotDuJour.jourLocal(jourMs - 1, 1))
        assertEquals(-1L, MotDuJour.jourLocal(0, -1))
        assertTrue(MotDuJour.jourLocal(jourMs * 20_000, 7_200_000) == 20_000L)
    }
}
