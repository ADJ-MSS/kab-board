package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import taqbaylit.moteur.Completion

/** De 1 a 3 lettres, la barre complete ; ensuite, ou faute de completion, elle corrige. */
class CompletionTest {

    // Volontairement en desordre : la completion doit trier elle-meme.
    private val c = Completion(
        listOf("tamurt", "tameṭṭut", "tamdint", "taqbaylit", "axxam", "aɣrum", "tamettant"),
        listOf(900, 1200, 300, 800, 2000, 700, 60))

    private val toutFiable: (String) -> Boolean = { true }
    private val rienFiable: (String) -> Boolean = { false }

    @Test
    fun `les mots qui commencent ainsi, les plus frequents d'abord`() {
        assertEquals(listOf("tameṭṭut", "tamurt", "tamdint", "tamettant"), c.candidats("tam"))
        assertEquals(listOf("tameṭṭut", "tamettant"), c.candidats("tame"))
        assertEquals(listOf("axxam", "aɣrum"), c.candidats("a"))
    }

    @Test
    fun `rien ne commence ainsi`() {
        assertEquals(emptyList<String>(), c.candidats("tma"))
        assertEquals(emptyList<String>(), c.candidats(""))
    }

    @Test
    fun `sans modele de langue, la frequence decide`() {
        assertEquals(listOf("tameṭṭut", "tamurt"), c.completer("", "tam", 2, null))
    }

    @Test
    fun `jusqu'a trois lettres la barre complete`() {
        assertEquals(listOf("tameṭṭut", "tamurt", "tamdint", "tamettant"),
            c.barre("", "tam", 6, null, rienFiable))
    }

    @Test
    fun `au-dela de trois lettres, plus de completion`() {
        assertNull(c.barre("", "tame", 6, null, rienFiable))
    }

    @Test
    fun `faute dans les premieres lettres, on corrige`() {
        assertNull(c.barre("", "tma", 6, null, rienFiable))
    }

    @Test
    fun `un mot court sur reste en tete`() {
        val barre = c.barre("", "tam", 3, null, toutFiable)
        assertEquals(listOf("tam", "tameṭṭut", "tamurt"), barre)
    }

    @Test
    fun `les seuils sont ceux de la mesure`() {
        assertEquals(3, Completion.SEUIL)
        assertEquals(4, Completion.LONGUEUR_MIN)
    }
}
