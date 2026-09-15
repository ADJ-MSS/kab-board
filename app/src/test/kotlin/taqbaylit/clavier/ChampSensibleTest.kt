package taqbaylit.clavier

import android.view.inputmethod.EditorInfo
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Ce qui ne doit jamais etre ni propose ni retenu. */
class ChampSensibleTest {

    private fun sensible(type: Int, options: Int = 0) =
        ClavierKabyle.estSensible(type, options)

    @Test
    fun `un champ de texte ordinaire n'est pas sensible`() {
        assertFalse(sensible(EditorInfo.TYPE_CLASS_TEXT))
        assertFalse(sensible(EditorInfo.TYPE_CLASS_TEXT or
            EditorInfo.TYPE_TEXT_VARIATION_LONG_MESSAGE))
    }

    @Test
    fun `un mot de passe masque est sensible`() {
        assertTrue(sensible(EditorInfo.TYPE_CLASS_TEXT or
            EditorInfo.TYPE_TEXT_VARIATION_PASSWORD))
    }

    /** Visible ne veut pas dire public : le mot de passe reste un mot de passe. */
    @Test
    fun `un mot de passe visible est sensible`() {
        assertTrue(sensible(EditorInfo.TYPE_CLASS_TEXT or
            EditorInfo.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD))
    }

    @Test
    fun `un mot de passe web est sensible`() {
        assertTrue(sensible(EditorInfo.TYPE_CLASS_TEXT or
            EditorInfo.TYPE_TEXT_VARIATION_WEB_PASSWORD))
    }

    /** Un code PIN est numerique : la classe change, la regle doit suivre. */
    @Test
    fun `un mot de passe numerique est sensible`() {
        assertTrue(sensible(EditorInfo.TYPE_CLASS_NUMBER or
            EditorInfo.TYPE_NUMBER_VARIATION_PASSWORD))
    }

    @Test
    fun `un champ numerique ordinaire n'est pas sensible`() {
        assertFalse(sensible(EditorInfo.TYPE_CLASS_NUMBER))
    }

    /**
     * L'application peut demander qu'un champ ne nourrisse aucun apprentissage, sans etre un mot de
     * passe : messagerie chiffree, champ medical, recherche privee.
     */
    @Test
    fun `un champ declare sans apprentissage est sensible`() {
        assertTrue(sensible(EditorInfo.TYPE_CLASS_TEXT,
            EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING))
    }

    @Test
    fun `le drapeau sans apprentissage compte meme melange a d'autres`() {
        assertTrue(sensible(EditorInfo.TYPE_CLASS_TEXT,
            EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING or EditorInfo.IME_ACTION_SEND))
    }

    @Test
    fun `un autre drapeau seul ne rend pas le champ sensible`() {
        assertFalse(sensible(EditorInfo.TYPE_CLASS_TEXT, EditorInfo.IME_ACTION_SEND))
    }
}
