package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import taqbaylit.moteur.RechercheFrancais
import taqbaylit.moteur.RechercheFrancais.Trouve

class RechercheFrancaisTest {

    @Test
    fun `plier retire casse, accents et blancs en trop`() {
        assertEquals("ecole maison", RechercheFrancais.plier("  École   Maison "))
        assertEquals("pain", RechercheFrancais.plier("PAIN"))
    }

    @Test
    fun `rang selon la place du mot dans la glose`() {
        assertEquals(0, RechercheFrancais.rang("pain, galette", "pain"))
        assertEquals(1, RechercheFrancais.rang("galette ; pain", "pain"))
        assertEquals(2, RechercheFrancais.rang("aller en voyage", "aller"))
        assertEquals(3, RechercheFrancais.rang("le fait d'aller", "aller"))
        assertEquals(4, RechercheFrancais.rang("voir, aller rendre visite", "aller"))
    }

    @Test
    fun `un mot contenu dans un autre ne compte pas`() {
        assertNull(RechercheFrancais.rang("paindemie", "pain"))
        assertNull(RechercheFrancais.rang("copain", "pain"))
    }

    @Test
    fun `une frontiere de mot kabyle n'est pas coupee`() {
        // ɣ est une lettre : « ɣpain » n'est pas le mot « pain ».
        assertNull(RechercheFrancais.rang("ɣpain", "pain"))
    }

    @Test
    fun `requete trop courte`() {
        assertNull(RechercheFrancais.rang("a, b", "a"))
    }

    @Test
    fun `classer par rang, puis frequence, puis ordre alphabetique`() {
        val trouves = listOf(
            Trouve("ẓer", "voir, aller rendre visite", 4, 90_000),
            Trouve("ruḥ", "aller, partir", 0, 20_000),
            Trouve("glu", "aller, accompagner", 0, 30_000),
            Trouve("ddu", "aller, marcher", 0, 30_000)
        )
        val classes = RechercheFrancais.classer(trouves, 3).map { it.forme }
        assertEquals(listOf("ddu", "glu", "ruḥ"), classes)
    }
}
