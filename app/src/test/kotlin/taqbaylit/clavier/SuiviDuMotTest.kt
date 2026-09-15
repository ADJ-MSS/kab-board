package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Test

/** Le mot suivi, reconstitue depuis le texte. */
class SuiviDuMotTest {

    @Test
    fun `le mot courant est la suite de lettres precedant le curseur`() {
        assertEquals("ruhagh", ClavierKabyle.motAvant("ruhagh", false))
        assertEquals("taddart", ClavierKabyle.motAvant("ruhagh ɣer taddart", false))
    }

    @Test
    fun `un curseur pose apres un separateur ne designe aucun mot`() {
        assertEquals("", ClavierKabyle.motAvant("azul ", false))
        assertEquals("", ClavierKabyle.motAvant("azul.", false))
        assertEquals("", ClavierKabyle.motAvant("", false))
    }

    @Test
    fun `le curseur au milieu d'un mot ne retient que ce qui precede`() {
        assertEquals("ruh", ClavierKabyle.motAvant("ad ruh", false))
    }

    /** Le trait d'union lie les clitiques a leur support. */
    @Test
    fun `le trait d'union kabyle fait partie du mot`() {
        assertEquals("tawilayt-a", ClavierKabyle.motAvant("ɣer tawilayt-a", false))
        assertEquals("yusa-d", ClavierKabyle.motAvant("yusa-d", false))
        assertEquals("fell-awen", ClavierKabyle.motAvant("azul fell-awen", false))
    }

    @Test
    fun `les lettres propres au kabyle font partie du mot`() {
        assertEquals("ẓẓay", ClavierKabyle.motAvant("aḥeḥḥuḥ ẓẓay", false))
        assertEquals("aɣrum", ClavierKabyle.motAvant("yečča aɣrum", false))
        assertEquals("ɛeddan", ClavierKabyle.motAvant("ɛeddan", false))
    }

    @Test
    fun `une majuscule ne coupe pas le mot`() {
        assertEquals("Ameqqran", ClavierKabyle.motAvant("Ameqqran", false))
        assertEquals("Ɣef", ClavierKabyle.motAvant("Ɣef", false))
    }

    /**
     * Une selection active ne designe aucun mot en cours : la remplacer par une
     * proposition effacerait un texte que l'utilisateur a designe expressement.
     */
    @Test
    fun `une selection active ne designe aucun mot`() {
        assertEquals("", ClavierKabyle.motAvant("ruhagh", true))
    }

    @Test
    fun `la fin du mot apres le curseur est mesuree`() {
        // « ruh|agh » : les trois lettres qui suivent doivent partir avec
        assertEquals(3, ClavierKabyle.finApres("agh"))
        assertEquals(3, ClavierKabyle.finApres("agh ɣer taddart"))
        assertEquals(0, ClavierKabyle.finApres(" ɣer"))
        assertEquals(0, ClavierKabyle.finApres(""))
        assertEquals(0, ClavierKabyle.finApres(", tam"))
    }

    @Test
    fun `la fin du mot compte aussi le trait d'union`() {
        assertEquals(2, ClavierKabyle.finApres("-a suivant"))
    }

    @Test
    fun `un chiffre n'appartient pas a un mot`() {
        assertFalse(ClavierKabyle.estCaractereMot('7'))
        assertEquals("", ClavierKabyle.motAvant("2024", false))
    }

    @Test
    fun `les lettres kabyles sont bien des lettres`() {
        for (c in "aɣɛḥẓṭḍṣčǧṛ") assertTrue("« $c » devrait etre une lettre", ClavierKabyle.estCaractereMot(c))
    }
}

/**
 * La casse rendue aux propositions, et les cas que leurs tests couvrent et que
 * les miens ne couvraient pas.
 */
class CasseEtCasLimitesTest {

    @Test
    fun `une proposition suit la minuscule du mot tape`() {
        assertEquals("ruḥeɣ", ClavierKabyle.casserComme("ruhagh", "ruḥeɣ"))
    }

    @Test
    fun `une capitale initiale se reporte sur la proposition`() {
        // Debut de phrase : « Ruhagh » corrige doit rester capitalise
        assertEquals("Ruḥeɣ", ClavierKabyle.casserComme("Ruhagh", "ruḥeɣ"))
        assertEquals("Taddart", ClavierKabyle.casserComme("Taddart", "taddart"))
    }

    @Test
    fun `un mot entierement en capitales le reste`() {
        assertEquals("RUḤEƔ", ClavierKabyle.casserComme("RUHAGH", "ruḥeɣ"))
    }

    /**
     * Le seuil de deux lettres : avec une seule, la majuscule que pose la
     * touche shift mettrait toute la proposition en capitales.
     */
    @Test
    fun `une seule lettre majuscule ne met pas tout en capitales`() {
        assertEquals("Ruḥeɣ", ClavierKabyle.casserComme("R", "ruḥeɣ"))
    }

    /**
     * Leur troisieme cas n'est pas repris : une capitale en milieu de mot n'a pas de sens en
     * kabyle.
     */
    @Test
    fun `une casse mixte n'est pas reportee`() {
        assertEquals("taddart", ClavierKabyle.casserComme("taDda", "taddart"))
    }

    @Test
    fun `un mot vide ou une proposition vide ne font pas tomber`() {
        assertEquals("ruḥeɣ", ClavierKabyle.casserComme("", "ruḥeɣ"))
        assertEquals("", ClavierKabyle.casserComme("Ruhagh", ""))
    }

    @Test
    fun `le trait d'union ne casse pas le report de capitale`() {
        assertEquals("Tawilayt-a", ClavierKabyle.casserComme("Tawilayt-a", "tawilayt-a"))
    }

    // ---- cas que leurs tests couvrent et pas les miens

    @Test
    fun `un emoji avant le curseur ne fait pas partie du mot`() {
        assertEquals("", ClavierKabyle.motAvant("azul 🥭", false))
    }

    @Test
    fun `un numero de telephone n'est pas un champ sensible`() {
        // TYPE_NUMBER_VARIATION_PASSWORD et TYPE_TEXT_VARIATION_VISIBLE_PASSWORD partagent la meme
        // valeur.
        assertEquals(false, ClavierKabyle.estSensible(
            android.text.InputType.TYPE_CLASS_PHONE, 0))
    }

    @Test
    fun `un champ e-mail ou nom propre n'est pas sensible`() {
        assertEquals(false, ClavierKabyle.estSensible(
            android.text.InputType.TYPE_CLASS_TEXT or
            android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS, 0))
        assertEquals(false, ClavierKabyle.estSensible(
            android.text.InputType.TYPE_CLASS_TEXT or
            android.text.InputType.TYPE_TEXT_VARIATION_PERSON_NAME, 0))
    }

    @Test
    fun `effacer l'espace apres un mot valide redonne ce mot comme prefixe`() {
        assertEquals("", ClavierKabyle.motAvant("azul ", false))
        assertEquals("azul", ClavierKabyle.motAvant("azul", false))
    }
}
