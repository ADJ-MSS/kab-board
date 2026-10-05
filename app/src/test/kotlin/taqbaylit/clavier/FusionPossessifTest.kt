package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Test
import taqbaylit.moteur.Normalisation

/** « tamurt iw » -> « tamurt-iw » : la proposition remplace aussi le mot d'avant. */
class FusionPossessifTest {

    private fun n(texteAvant: String, mots: Int = 1) = ClavierKabyle.longueurMotsAvant(texteAvant, mots)

    @Test
    fun `le mot d'avant et l'espace qui le suit`() {
        // Le texte qui precede « iw » dans « tamurt iw »
        assertEquals("tamurt ".length, n("tamurt "))
        assertEquals("tamurt ".length, n("ruḥeɣ ɣer tamurt "))
    }

    @Test
    fun `plusieurs blancs sont emportes avec le mot`() {
        assertEquals("tamurt  ".length, n("tamurt  "))
    }

    @Test
    fun `deux mots d'avant`() {
        assertEquals("axxam nneɣ ".length, n("ruḥeɣ ɣer axxam nneɣ ", 2))
    }

    @Test
    fun `sans blanc, rien n'est a fondre`() {
        assertEquals(-1, n("tamurt"))
    }

    @Test
    fun `une ponctuation interdit la fusion`() {
        assertEquals(-1, n("tamurt, "))
        assertEquals(-1, n(". "))
    }

    @Test
    fun `pas assez de mots`() {
        assertEquals(-1, n(""))
        assertEquals(-1, n("tamurt ", 2))
    }

    @Test
    fun `le moteur dit combien de jetons recouvre chaque forme`() {
        assertEquals(listOf("tamurt-iw" to 2),
            Normalisation.rejoindrePossessifsPortees(listOf("tamurt", "iw")))
        assertEquals(listOf("ruḥeɣ" to 1, "ɣer" to 1, "axxam-nneɣ" to 2),
            Normalisation.rejoindrePossessifsPortees(listOf("ruḥeɣ", "ɣer", "axxam", "nneɣ")))
        assertEquals(listOf("iw" to 1), Normalisation.rejoindrePossessifsPortees(listOf("iw")))
        // L'ancienne fonction rend toujours la meme chose.
        assertEquals(listOf("tamurt-iw", "telha"),
            Normalisation.rejoindrePossessifs(listOf("tamurt", "iw", "telha")))
    }
}
