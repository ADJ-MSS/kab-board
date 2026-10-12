package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DispositionTest {

    @Test
    fun `sans reglage ou avec une valeur inconnue, le clavier reste kabyle`() {
        assertEquals(Disposition.KABYLE, Disposition.depuisCle(null))
        assertEquals(Disposition.KABYLE, Disposition.depuisCle("dvorak"))
    }

    @Test
    fun `chaque disposition se relit depuis sa cle`() {
        for (d in Disposition.values()) assertEquals(d, Disposition.depuisCle(d.cle))
    }

    @Test
    fun `AZERTY et QWERTY commencent par leurs lettres`() {
        assertEquals("azertyuiop", Disposition.AZERTY.rangees[0].joinToString(""))
        assertEquals("qwertyuiop", Disposition.QWERTY.rangees[0].joinToString(""))
        assertEquals("asdfghjkl", Disposition.QWERTY.rangees[1].joinToString(""))
    }

    @Test
    fun `aucune lettre kabyle dans les dispositions latines`() {
        val kabyles = setOf("ɣ", "ɛ", "ḍ", "ḥ", "ṭ", "ẓ", "ṣ", "ǧ", "č", "ṛ")
        for (d in listOf(Disposition.AZERTY, Disposition.QWERTY)) {
            val touches = d.rangees.flatMap { it.toList() }
            assertTrue(d.name, touches.none { it in kabyles })
            // la dictee est kabyle : elle reste sur la disposition kabyle
            assertFalse(d.name, "MICRO" in touches)
            for (indispensable in listOf("⇧", "⌫", "⏎", " ", "123"))
                assertTrue("$indispensable manque en ${d.name}", indispensable in touches)
        }
    }
}
