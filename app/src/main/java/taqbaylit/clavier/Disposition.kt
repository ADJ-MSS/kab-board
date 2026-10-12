package taqbaylit.clavier

/**
 * Les lettres du clavier. AZERTY et QWERTY servent à écrire en français ou en anglais sans
 * changer de clavier : ni correction kabyle, ni lettres kabyles.
 */
enum class Disposition(val cle: String, val nom: String, val detail: String) {
    KABYLE("kab", "Taqbaylit", ""),
    AZERTY("azerty", "Français", "AZERTY"),
    QWERTY("qwerty", "English", "QWERTY");

    val estKabyle: Boolean get() = this == KABYLE

    /** Les rangées des dispositions latines. La kabyle se construit dans KeyboardLayoutManager. */
    val rangees: List<Array<String>>
        get() = when (this) {
            KABYLE -> emptyList()
            AZERTY -> listOf(
                arrayOf("a", "z", "e", "r", "t", "y", "u", "i", "o", "p"),
                arrayOf("q", "s", "d", "f", "g", "h", "j", "k", "l", "m"),
                arrayOf("⇧", "w", "x", "c", "v", "b", "n", "'", "⌫"),
                arrayOf("123", ",", "-", " ", ".", "⏎")
            )
            QWERTY -> listOf(
                arrayOf("q", "w", "e", "r", "t", "y", "u", "i", "o", "p"),
                arrayOf("a", "s", "d", "f", "g", "h", "j", "k", "l"),
                arrayOf("⇧", "z", "x", "c", "v", "b", "n", "m", "⌫"),
                arrayOf("123", ",", "-", " ", "'", ".", "⏎")
            )
        }

    companion object {
        /** Une valeur absente ou inconnue ramène au kabyle. */
        fun depuisCle(cle: String?): Disposition = values().firstOrNull { it.cle == cle } ?: KABYLE
    }
}
