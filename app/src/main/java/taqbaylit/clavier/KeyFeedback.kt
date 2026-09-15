package taqbaylit.clavier

import android.content.Context
import android.media.AudioManager
import android.os.Build
import android.util.Log
import android.view.HapticFeedbackConstants
import android.view.View

/** Retour de frappe du clavier : vibration et son, au même endroit. */
object KeyFeedback {

    private const val TAG = "KeyFeedback"

    /** Volume des sons de frappe, sur l'échelle linéaire de playSoundEffect. */
    private const val SOUND_VOLUME = 0.4f

    // Conservé entre les frappes : le service de son se cherche une fois, pas à chaque touche.
    private var audioManager: AudioManager? = null

    // Réglages en cache : ce code est sur le chemin de chaque appui de touche, il ne doit pas
    // relire les préférences à chaque frappe.
    private var hapticEnabled: Boolean? = null
    private var soundEnabled: Boolean? = null

    /**
     * Relit les réglages. Appelé par le service à chaque prise de focus et par l'écran de réglages
     * après un changement, pour qu'un choix s'applique dès le retour dans un champ de saisie.
     */
    fun refresh(context: Context) {
        hapticEnabled = KeyboardPreferences.hapticEnabled(context)
        soundEnabled = KeyboardPreferences.soundEnabled(context)
    }

    /** Retour complet d'une frappe : vibration puis son. */
    fun onKeyPress(view: View, key: String? = null) {
        val context = view.context
        if (hapticEnabled ?: KeyboardPreferences.hapticEnabled(context).also { hapticEnabled = it }) {
            vibrate(view)
        }
        if (soundEnabled ?: KeyboardPreferences.soundEnabled(context).also { soundEnabled = it }) {
            playSound(context, key)
        }
    }

    /**
     * Retour d'un cran de déplacement du curseur, quand le doigt glisse sur la barre d'espace
     * (v14.0.0) : vibration seule, et jamais de son.
     */
    fun onCursorStep(view: View) {
        val context = view.context
        if (hapticEnabled ?: KeyboardPreferences.hapticEnabled(context).also { hapticEnabled = it }) {
            vibrate(view, HapticFeedbackConstants.CLOCK_TICK)
        }
    }

    private fun vibrate(view: View, effect: Int = HapticFeedbackConstants.KEYBOARD_TAP) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                // FLAG_IGNORE_GLOBAL_SETTING. L'échappatoire est ici le réglage de l'application,
                // pas celui du système.
                view.performHapticFeedback(
                    effect,
                    HapticFeedbackConstants.FLAG_IGNORE_GLOBAL_SETTING
                )
            }
        } catch (e: Exception) {
            Log.d(TAG, "Feedback haptique non disponible: ${e.message}")
        }
    }

    private fun playSound(context: Context, key: String?) {
        try {
            val manager = audioManager ?: (context.applicationContext
                .getSystemService(Context.AUDIO_SERVICE) as? AudioManager)
                ?.also { audioManager = it }
            // La variante à volume explicite est celle des claviers.
            manager?.playSoundEffect(effetPour(key), SOUND_VOLUME)
        } catch (e: Exception) {
            Log.d(TAG, "Son de frappe non disponible: ${e.message}")
        }
    }

    /** Le son de frappe d'Android correspondant à la touche. */
    private fun effetPour(key: String?): Int = when (key) {
        " " -> AudioManager.FX_KEYPRESS_SPACEBAR
        "⌫" -> AudioManager.FX_KEYPRESS_DELETE
        "⏎" -> AudioManager.FX_KEYPRESS_RETURN
        else -> AudioManager.FX_KEYPRESS_STANDARD
    }
}
