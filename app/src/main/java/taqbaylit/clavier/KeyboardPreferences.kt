package taqbaylit.clavier

import android.content.Context

/**
 * Réglages de comportement du clavier, partagés entre l'écran de l'application (ActiviteReglages)
 * et le service de saisie (ClavierKabyle).
 */
object KeyboardPreferences {

    private const val PREFS_NAME = "taqbaylit_clavier"
    private const val KEY_HAPTIC_ENABLED = "haptic_enabled"
    private const val KEY_SOUND_ENABLED = "sound_enabled"
    private const val KEY_THEME_MODE = "theme_mode"

    /** La vibration est active par défaut, comme sur les autres claviers. */
    private const val DEFAULT_ENABLED = true

    /** Le son, lui, est coupé par défaut. */
    private const val DEFAULT_SON = false

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun hapticEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_HAPTIC_ENABLED, DEFAULT_ENABLED)

    fun soundEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_SOUND_ENABLED, DEFAULT_SON)

    fun setHapticEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_HAPTIC_ENABLED, enabled).apply()
        KeyFeedback.refresh(context)
    }

    fun setSoundEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_SOUND_ENABLED, enabled).apply()
        KeyFeedback.refresh(context)
    }

    /** Thème du clavier. Par défaut il suit le téléphone. */
    fun themeMode(context: Context): KeyboardTheme.Mode =
        KeyboardTheme.Mode.depuisCle(prefs(context).getString(KEY_THEME_MODE, null))

    fun setThemeMode(context: Context, mode: KeyboardTheme.Mode) {
        prefs(context).edit().putString(KEY_THEME_MODE, mode.cle).apply()
        KeyboardTheme.refresh(context)
    }

    private const val KEY_ECRIRE_COMME_ON_PARLE = "ecrire_comme_on_parle"
    private const val KEY_TRAITS_FORMES = "traits_formes"
    private const val KEY_GRAPHIE = "graphie_bv"

    /** Graphie b ou v : un reglage, qui vaut pour les six propositions. */
    fun graphie(context: Context): GraphieBV.Mode =
        graphieDepuis(prefs(context).getString(KEY_GRAPHIE, null))

    /**
     * La graphie en v au depart : c'est celle que les scripteurs emploient.
     * Le b ne s'applique que s'il a ete choisi, et une valeur abimee ne fait rien.
     */
    internal fun graphieDepuis(valeur: String?): GraphieBV.Mode =
        if (valeur == "b") GraphieBV.Mode.B else GraphieBV.Mode.V

    fun setGraphie(context: Context, mode: GraphieBV.Mode) {
        prefs(context).edit()
            .putString(KEY_GRAPHIE, if (mode == GraphieBV.Mode.V) "v" else "b").apply()
    }

    /** « Écrire comme on parle » (EcritureParlee). */
    fun ecrireCommeOnParle(context: Context): Boolean =
        prefs(context).getBoolean(KEY_ECRIRE_COMME_ON_PARLE, false)

    fun setEcrireCommeOnParle(context: Context, actif: Boolean) {
        prefs(context).edit().putBoolean(KEY_ECRIRE_COMME_ON_PARLE, actif).apply()
    }

    /** Traits de nature lisibles sans la couleur : plein, tirets, pointillés. */
    fun traitsFormes(context: Context): Boolean =
        prefs(context).getBoolean(KEY_TRAITS_FORMES, false)

    fun setTraitsFormes(context: Context, actif: Boolean) {
        prefs(context).edit().putBoolean(KEY_TRAITS_FORMES, actif).apply()
    }
}
