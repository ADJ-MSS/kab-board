package taqbaylit.clavier

import android.view.inputmethod.EditorInfo

/**
 * « Écrire comme on parle » : les graphies du clavier latin ordinaire deviennent les lettres
 * kabyles au moment où on les tape.
 */
object EcritureParlee {

    /** Deux lettres tapées, et la lettre kabyle qui les remplace. */
    val PAIRES: Map<String, String> = linkedMapOf(
        "gh" to "ɣ",
        "dh" to "ḍ",
        "kh" to "x",
        "aa" to "ɛ",
        "ou" to "u",
    )

    /**
     * La lettre qui remplace precedent suivi de tape, ou null si les deux ne forment pas une paire.
     */
    fun convertir(precedent: Char, tape: String): String? {
        if (tape.length != 1) return null
        val cible = PAIRES["${precedent.lowercaseChar()}${tape.lowercase()}"] ?: return null
        return if (precedent.isUpperCase()) cible.uppercase() else cible
    }

    /** Le champ accepte-t-il la conversion ? */
    fun accepte(inputType: Int): Boolean {
        if ((inputType and EditorInfo.TYPE_MASK_CLASS) != EditorInfo.TYPE_CLASS_TEXT) return false
        return when (inputType and EditorInfo.TYPE_MASK_VARIATION) {
            EditorInfo.TYPE_TEXT_VARIATION_EMAIL_ADDRESS,
            EditorInfo.TYPE_TEXT_VARIATION_WEB_EMAIL_ADDRESS,
            EditorInfo.TYPE_TEXT_VARIATION_URI,
            EditorInfo.TYPE_TEXT_VARIATION_PASSWORD,
            EditorInfo.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD,
            EditorInfo.TYPE_TEXT_VARIATION_WEB_PASSWORD -> false
            else -> true
        }
    }
}
