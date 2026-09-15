package taqbaylit.clavier

import android.view.inputmethod.EditorInfo
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class EcritureParleeTest {

    @Test
    fun `les cinq paires deviennent des lettres kabyles`() {
        assertEquals("ɣ", EcritureParlee.convertir('g', "h"))
        assertEquals("ḍ", EcritureParlee.convertir('d', "h"))
        assertEquals("x", EcritureParlee.convertir('k', "h"))
        assertEquals("ɛ", EcritureParlee.convertir('a', "a"))
        assertEquals("u", EcritureParlee.convertir('o', "u"))
    }

    @Test
    fun `th et ch ne sont pas convertis`() {
        assertNull(EcritureParlee.convertir('t', "h"))
        assertNull(EcritureParlee.convertir('c', "h"))
    }

    @Test
    fun `la casse suit la premiere lettre`() {
        assertEquals("Ɣ", EcritureParlee.convertir('G', "h"))
        assertEquals("Ɣ", EcritureParlee.convertir('G', "H"))
        assertEquals("ɣ", EcritureParlee.convertir('g', "H"))
        assertEquals("Ḍ", EcritureParlee.convertir('D', "h"))
        assertEquals("Ɛ", EcritureParlee.convertir('A', "a"))
    }

    @Test
    fun `seule une lettre tapee a la fois compte`() {
        assertNull(EcritureParlee.convertir('g', "hh"))
        assertNull(EcritureParlee.convertir('g', ""))
        assertNull(EcritureParlee.convertir(' ', "h"))
    }

    @Test
    fun `texte ordinaire et message acceptes`() {
        assertTrue(EcritureParlee.accepte(EditorInfo.TYPE_CLASS_TEXT))
        assertTrue(EcritureParlee.accepte(
            EditorInfo.TYPE_CLASS_TEXT or EditorInfo.TYPE_TEXT_VARIATION_SHORT_MESSAGE))
        assertTrue(EcritureParlee.accepte(
            EditorInfo.TYPE_CLASS_TEXT or EditorInfo.TYPE_TEXT_FLAG_MULTI_LINE))
    }

    @Test
    fun `adresse, URL, mot de passe et nombre refuses`() {
        val texte = EditorInfo.TYPE_CLASS_TEXT
        assertFalse(EcritureParlee.accepte(texte or EditorInfo.TYPE_TEXT_VARIATION_EMAIL_ADDRESS))
        assertFalse(EcritureParlee.accepte(texte or EditorInfo.TYPE_TEXT_VARIATION_WEB_EMAIL_ADDRESS))
        assertFalse(EcritureParlee.accepte(texte or EditorInfo.TYPE_TEXT_VARIATION_URI))
        assertFalse(EcritureParlee.accepte(texte or EditorInfo.TYPE_TEXT_VARIATION_PASSWORD))
        assertFalse(EcritureParlee.accepte(texte or EditorInfo.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD))
        assertFalse(EcritureParlee.accepte(texte or EditorInfo.TYPE_TEXT_VARIATION_WEB_PASSWORD))
        assertFalse(EcritureParlee.accepte(EditorInfo.TYPE_CLASS_NUMBER))
        assertFalse(EcritureParlee.accepte(EditorInfo.TYPE_CLASS_PHONE))
    }
}
