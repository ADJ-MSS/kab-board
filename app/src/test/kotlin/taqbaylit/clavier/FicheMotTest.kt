package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import taqbaylit.moteur.Postprocess
import java.io.File

/** Les états d'un nom dans la fiche, et la raison qui les accompagne. */
class FicheMotTest {

    private val post = Postprocess(File("src/main/assets/moteur"), null)

    @Test
    fun `un nom a l'etat libre donne son etat d'annexion`() {
        assertEquals(FicheMot.Etats("aɣrum", "uɣrum"), FicheMot.etats(post, "aɣrum", false, "masc"))
        assertEquals(FicheMot.Etats("tamurt", "tmurt"), FicheMot.etats(post, "tamurt", false, "fem"))
    }

    @Test
    fun `un nom a l'etat d'annexion retrouve son etat libre`() {
        assertEquals(FicheMot.Etats("aɣrum", "uɣrum"), FicheMot.etats(post, "uɣrum", false, null))
    }

    @Test
    fun `ni verbe ni categorie non nominale`() {
        assertNull(FicheMot.etats(post, "ini", true, null))
        assertNull(FicheMot.etats(post, "ɣer", false, "prep"))
    }

    @Test
    fun `la raison d'une correction d'etat est rendue avec son index`() {
        val (corrigee, retenues) = post.appliquerChakerValideLm(listOf("ɣer", "tamurt"), null, null)
        assertEquals(listOf("ɣer", "tmurt"), corrigee)
        assertEquals(1, retenues.size)
        assertEquals(Postprocess.Proposition(1, "tamurt", "tmurt", "après préposition 'ɣer'"), retenues[0])
    }

    @Test
    fun `glose courte, premier segment coupe`() {
        assertEquals("pain, galette", FicheMot.gloseCourte("pain, galette ; nourriture"))
        assertEquals("abcd…", FicheMot.gloseCourte("abcdefgh", max = 5))
    }
}
