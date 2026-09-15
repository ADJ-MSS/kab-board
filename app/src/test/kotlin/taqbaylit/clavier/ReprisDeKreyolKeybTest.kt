package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotSame
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

/** Le code repris de KreyolKeyb, verifie chez nous. */
class ReprisDeKreyolKeybTest {

    // ---- glissement du curseur sur la barre d'espace

    /** Dix dp a densite 3, le cas courant. */
    private val pas = 30f

    @Test
    fun `un deplacement inferieur a un cran ne bouge pas le curseur`() {
        assertEquals(0, KeyboardLayoutManager.cursorStepsFor(0f, pas))
        assertEquals(0, KeyboardLayoutManager.cursorStepsFor(29f, pas))
        assertEquals(0, KeyboardLayoutManager.cursorStepsFor(-29f, pas))
    }

    @Test
    fun `le geste est symetrique a gauche et a droite`() {
        // Avec un arrondi vers le bas, -31 px donnerait -2 crans la ou +31 en
        // donne 1, et un aller-retour du doigt decalerait le curseur.
        for (px in listOf(31f, 45f, 59f, 60f, 91f, 300f))
            assertEquals(
                -KeyboardLayoutManager.cursorStepsFor(px, pas),
                KeyboardLayoutManager.cursorStepsFor(-px, pas))
    }

    @Test
    fun `un balayage de tout l'ecran couvre une ligne de texte`() {
        assertEquals(36, KeyboardLayoutManager.cursorStepsFor(1080f, pas))
    }

    @Test
    fun `un pas nul ne provoque pas de division par zero`() {
        assertEquals(0, KeyboardLayoutManager.cursorStepsFor(100f, 0f))
    }

    // ---- emojis recents

    @Test
    fun `reemployer un emoji le remonte sans le dupliquer`() {
        val apres = EmojiRecents.fusionner(listOf("🥭", "🎺", "🌺"), "🌺")
        assertEquals(listOf("🌺", "🥭", "🎺"), apres)
        assertEquals(apres.size, apres.toSet().size)
    }

    @Test
    fun `la liste ne depasse jamais la page visible du panneau`() {
        var liste = emptyList<String>()
        for (i in 1..50) liste = EmojiRecents.fusionner(liste, "e$i")
        assertEquals(EmojiRecents.CAPACITE, liste.size)
    }

    @Test
    fun `un emoji a ton de peau est une entree distincte de sa variante neutre`() {
        assertEquals(listOf("👍🏻", "👍🏿"), EmojiRecents.fusionner(listOf("👍🏿"), "👍🏻"))
    }

    // ---- theme

    @Test
    fun `un choix explicite l'emporte sur le mode nuit du telephone`() {
        val clair = KeyboardTheme.Mode.CLAIR
        val sombre = KeyboardTheme.Mode.SOMBRE
        assertSame(
            KeyboardTheme.resoudre(clair, systemeEnSombre = false),
            KeyboardTheme.resoudre(clair, systemeEnSombre = true))
        assertSame(
            KeyboardTheme.resoudre(sombre, systemeEnSombre = true),
            KeyboardTheme.resoudre(sombre, systemeEnSombre = false))
    }

    @Test
    fun `le mode systeme suit le telephone`() {
        assertSame(
            KeyboardTheme.resoudre(KeyboardTheme.Mode.SOMBRE, systemeEnSombre = false),
            KeyboardTheme.resoudre(KeyboardTheme.Mode.SYSTEME, systemeEnSombre = true))
        assertNotSame(
            KeyboardTheme.resoudre(KeyboardTheme.Mode.CLAIR, systemeEnSombre = false),
            KeyboardTheme.resoudre(KeyboardTheme.Mode.SOMBRE, systemeEnSombre = false))
    }

    @Test
    fun `une preference absente ou inconnue retombe sur le suivi du telephone`() {
        val systeme = KeyboardTheme.Mode.SYSTEME
        assertEquals(systeme, KeyboardTheme.Mode.depuisCle(null))
        assertEquals(systeme, KeyboardTheme.Mode.depuisCle(""))
        assertEquals(systeme, KeyboardTheme.Mode.depuisCle("auto"))
    }

    @Test
    fun `chaque mode se relit depuis la cle qu'il enregistre`() {
        KeyboardTheme.Mode.entries.forEach {
            assertEquals(it, KeyboardTheme.Mode.depuisCle(it.cle))
        }
        val modes = KeyboardTheme.Mode.entries
        assertEquals(modes.size, modes.map { it.cle }.distinct().size)
        assertTrue(modes.all { it.cle.isNotBlank() })
    }
}
