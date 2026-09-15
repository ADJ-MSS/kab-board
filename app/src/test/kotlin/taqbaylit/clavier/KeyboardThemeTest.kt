package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotSame
import org.junit.Assert.assertSame
import org.junit.Test
import taqbaylit.clavier.KeyboardTheme.Mode

/** La table de décision des thèmes. */
class KeyboardThemeTest {

    private fun r(mode: Mode, sombre: Boolean) = KeyboardTheme.resoudre(mode, sombre)

    @Test
    fun `systeme suit le telephone, clair et sombre non`() {
        assertSame(r(Mode.CLAIR, false), r(Mode.SYSTEME, false))
        assertSame(r(Mode.SOMBRE, false), r(Mode.SYSTEME, true))
        assertSame(r(Mode.CLAIR, false), r(Mode.CLAIR, true))
        assertSame(r(Mode.SOMBRE, false), r(Mode.SOMBRE, true))
    }

    @Test
    fun `contraste eleve et Tamazɣa ignorent le mode du telephone`() {
        assertSame(r(Mode.CONTRASTE, false), r(Mode.CONTRASTE, true))
        assertSame(r(Mode.TAMAZGHA, false), r(Mode.TAMAZGHA, true))
    }

    @Test
    fun `quatre palettes distinctes`() {
        val palettes = listOf(
            r(Mode.CLAIR, false), r(Mode.SOMBRE, false),
            r(Mode.CONTRASTE, false), r(Mode.TAMAZGHA, false))
        for (i in palettes.indices) for (j in palettes.indices) {
            if (i != j) assertNotSame(palettes[i], palettes[j])
        }
    }

    @Test
    fun `les cles se relisent, une cle inconnue retombe sur le systeme`() {
        for (m in Mode.entries) assertEquals(m, Mode.depuisCle(m.cle))
        assertEquals(Mode.entries.size, Mode.entries.map { it.cle }.toSet().size)
        assertEquals(Mode.SYSTEME, Mode.depuisCle("inconnue"))
        assertEquals(Mode.SYSTEME, Mode.depuisCle(null))
    }

    @Test
    fun `seul Tamazɣa change le libelle de l'espace et porte une bande`() {
        assertEquals("ⵣ", r(Mode.TAMAZGHA, false).libelleEspace)
        assertEquals(3, r(Mode.TAMAZGHA, false).bandeIdentite?.size)
        for (m in listOf(Mode.CLAIR, Mode.SOMBRE, Mode.CONTRASTE)) {
            assertEquals(KeyboardTheme.LIBELLE_LANGUE, r(m, false).libelleEspace)
            assertEquals(null, r(m, false).bandeIdentite)
        }
    }
}
