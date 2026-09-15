package taqbaylit.clavier

import android.content.Context
import android.util.Log

/** Les emojis récemment employés, en tête du panneau emoji (v15.0.0). */
object EmojiRecents {

    private const val TAG = "EmojiRecents"
    private const val PREFS_NAME = "taqbaylit_emoji"
    private const val KEY_RECENTS = "recents"

    /** Nombre d'emojis conservés. */
    const val CAPACITE = 30

    /** Séparateur des entrées dans la préférence. */
    private const val SEPARATEUR = "\u001F"

    /** Faux dans un champ dont le contenu ne doit rien laisser derrière lui. */
    @Volatile
    private var enregistrementAutorise = true

    fun setEnregistrementAutorise(autorise: Boolean) {
        enregistrementAutorise = autorise
    }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** Les emojis récents, du plus récent au plus ancien. */
    fun lire(context: Context): List<String> {
        val brut = prefs(context).getString(KEY_RECENTS, null) ?: return emptyList()
        return brut.split(SEPARATEUR).filter { it.isNotEmpty() }.take(CAPACITE)
    }

    /** Note l'emploi d'un emoji, sauf dans un champ sensible. */
    fun enregistrer(context: Context, emoji: String) {
        if (!enregistrementAutorise) {
            Log.d(TAG, "Champ sensible: emoji non retenu")
            return
        }
        if (emoji.isEmpty() || emoji.contains(SEPARATEUR)) return

        val misAJour = fusionner(lire(context), emoji)
        prefs(context).edit()
            .putString(KEY_RECENTS, misAJour.joinToString(SEPARATEUR))
            .apply()
    }

    /** Efface la liste. Appelé depuis les réglages du clavier. */
    fun vider(context: Context) {
        prefs(context).edit().remove(KEY_RECENTS).apply()
        Log.d(TAG, "Emojis récents effacés")
    }

    /** La liste mise à jour par l'emploi de emoji. */
    internal fun fusionner(existants: List<String>, emoji: String): List<String> =
        (listOf(emoji) + existants.filter { it != emoji }).take(CAPACITE)
}
