package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Test
import taqbaylit.clavier.CorrecteurSysteme.Soulignement.AUCUN
import taqbaylit.clavier.CorrecteurSysteme.Soulignement.DOUTE
import taqbaylit.clavier.CorrecteurSysteme.Soulignement.FAUTE

/** Quand souligner un mot, et comment. */
class CorrecteurSystemeTest {

    private fun v(mot: String, absolue: String, cinq: List<String> = emptyList(), connu: Boolean = false) =
        CorrecteurSysteme.verdict(mot, absolue, cinq, connu)

    @Test
    fun `le mot que le correcteur ecrirait lui-meme n'est pas souligne`() {
        assertEquals(AUCUN, v("ruḥeɣ", "ruḥeɣ", listOf("ruheɣ"), connu = true))
    }

    @Test
    fun `la casse et la graphie ascii ne font pas une difference`() {
        assertEquals(AUCUN, v("Ruḥeɣ", "ruḥeɣ", connu = true))
        assertEquals(AUCUN, v("gher", "ɣer", connu = true))
    }

    @Test
    fun `une forme connue que le contexte remplace est un doute`() {
        assertEquals(DOUTE, v("ruheɣ", "ruḥeɣ", listOf("ruḥeɣ", "ruḥeɣ"), connu = true))
    }

    @Test
    fun `une forme inconnue que le correcteur remplace est une faute`() {
        assertEquals(FAUTE, v("ruhagh", "ruḥeɣ", listOf("ruḥeɣ", "ruheɣ")))
    }

    /** Un nom propre, un mot francais : le correcteur entier le laisse tel quel. */
    @Test
    fun `une forme inconnue que le correcteur garde n'est pas soulignee`() {
        assertEquals(AUCUN, v("bonjour", "bonjur", listOf("bunjur")))
    }

    /** Le cas qui protege le francais : rien a proposer, on se tait. */
    @Test
    fun `un mot inconnu sans aucune proposition n'est pas souligne`() {
        assertEquals(AUCUN, v("xyzw", "", emptyList()))
    }

    @Test
    fun `une forme connue n'est jamais une faute`() {
        assertEquals(DOUTE, v("ruheɣ", "ruḥeɣ", emptyList(), connu = true))
        assertEquals(AUCUN, v("ruheɣ", "", listOf("ruḥeɣ"), connu = true))
    }
}

/** Le decoupage d'une phrase envoyee par le systeme. */
class DecoupageDuCorrecteurSystemeTest {

    @Test
    fun `chaque mot a sa position`() {
        assertEquals(listOf(0 to "ruḥeɣ", 6 to "ɣer", 10 to "taddart"),
            CorrecteurSysteme.mots("ruḥeɣ ɣer taddart"))
    }

    @Test
    fun `le trait d'union garde les clitiques avec leur mot`() {
        assertEquals(listOf(0 to "yusa-d", 7 to "ass-a"), CorrecteurSysteme.mots("yusa-d ass-a."))
    }

    @Test
    fun `la ponctuation et les chiffres separent les mots`() {
        assertEquals(listOf(0 to "azul", 6 to "fell-ak"), CorrecteurSysteme.mots("azul, fell-ak 123!"))
    }
}

/** La casse rendue par le correcteur systeme. */
class CasseDuCorrecteurSystemeTest {

    @Test
    fun `une correction suit la capitale du mot souligne`() {
        assertEquals("Ruḥeɣ", ClavierKabyle.casserComme("Ruhagh", "ruḥeɣ"))
    }

    @Test
    fun `un mot tout en capitales garde ses capitales`() {
        assertEquals("RUḤEƔ", ClavierKabyle.casserComme("RUHAGH", "ruḥeɣ"))
    }

    @Test
    fun `un mot en minuscules reste en minuscules`() {
        assertEquals("ruḥeɣ", ClavierKabyle.casserComme("ruhagh", "ruḥeɣ"))
    }
}
