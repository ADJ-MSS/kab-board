package taqbaylit.clavier

import android.content.Context
import android.graphics.drawable.GradientDrawable
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.PopupWindow
import android.widget.TextView

/**
 * Gestionnaire des accents et caractères spéciaux pour le clavier créole
 * Gère les popups d'accents et la sélection de caractères diacritiques
 */
class AccentHandler(private val context: Context) {
    
    companion object {
        private const val TAG = "AccentHandler"
        private const val LONG_PRESS_DELAY = 500L
        private const val POPUP_ELEVATION_DP = 8f
        private const val ACCENT_BUTTON_SIZE_DP = 48
        private const val ACCENT_BUTTON_MARGIN_DP = 4
    }
    
    // État du mode majuscule
    var isCapitalMode: Boolean = false
    
    // La table qui suit est kabyle et n'a rien gardé de la leur.
    private val accentMap = mapOf(
        "d" to listOf("ḍ"),
        "h" to listOf("ḥ"),
        "t" to listOf("ṭ"),
        "z" to listOf("ẓ"),
        "s" to listOf("ṣ"),
        // ǧ et č sont aussi les affriquees notees dj et tc dans d'autres graphies.
        "g" to listOf("ǧ"),
        "c" to listOf("č"),
        // ṛ n'apparait pas dans les formes verbales mais dans 12 609 formes du vivier : certaines
        // graphies le notent, la normalisation le ramene ensuite sur « r ».
        "r" to listOf("ṛ"),
        // b n'a pas d'appui long. bʷ n'est pas propose, pour la meme raison que gʷ ; ḅ, essaye un
        // temps, non plus.
        "u" to listOf("o", "û", "ù"),
        "a" to listOf("â", "à"),
        "e" to listOf("é", "è", "ê"),
        "i" to listOf("î", "ï"),
        "," to listOf(";", ":", "'"),
        "." to listOf("!", "?", "…")
    )

    // Ordre d'affichage des aperçus en coin, quand il doit différer de l'ordre du popup d'appui
    // long (v8.7.0).
    private val cornerHintOverrides = mapOf(
        "e" to listOf("é", "è"),
        "u" to listOf("o", "û")
    )

    // Tons de peau pour le panneau emoji exhaustif (v10.1.0), chargés depuis emoji_data.json au
    // démarrage du clavier (EmojiData.skinTones).
    private var emojiSkinTones: Map<String, List<String>> = emptyMap()

    fun loadEmojiSkinTones(skinTones: Map<String, List<String>>) {
        emojiSkinTones = skinTones
    }

    // État actuel
    private var currentAccentPopup: PopupWindow? = null
    private val longPressHandler = Handler(Looper.getMainLooper())
    private var longPressRunnable: Runnable? = null
    private var isLongPressTriggered = false
    private var currentBaseCharacter: String? = null
    
    // Callbacks
    interface AccentSelectionListener {
        fun onAccentSelected(accent: String, baseCharacter: String)
        fun onLongPressStarted(baseKey: String)
        fun onLongPressCancelled()
    }
    
    private var accentListener: AccentSelectionListener? = null
    
    fun setAccentSelectionListener(listener: AccentSelectionListener) {
        this.accentListener = listener
    }
    
    /**
     * Vérifie si une touche a des accents disponibles
     */
    fun hasAccents(key: String): Boolean {
        return accentMap.containsKey(key.lowercase()) || emojiSkinTones.containsKey(key)
    }
    
    /**
     * Démarre le timer de pression longue pour une touche
     */
    fun startLongPressTimer(key: String, anchorButton: View) {
        if (!hasAccents(key)) return
        
        cancelLongPress()
        currentBaseCharacter = key  // Stocker le caractère de base
        
        longPressRunnable = Runnable {
            isLongPressTriggered = true
            showAccentPopup(key, anchorButton)
            accentListener?.onLongPressStarted(key)
        }
        
        longPressHandler.postDelayed(longPressRunnable!!, LONG_PRESS_DELAY)
    }
    
    /**
     * Annule la pression longue en cours
     */
    fun cancelLongPress() {
        longPressRunnable?.let {
            longPressHandler.removeCallbacks(it)
            longPressRunnable = null
        }
        
        if (isLongPressTriggered) {
            accentListener?.onLongPressCancelled()
            isLongPressTriggered = false
        }
    }
    
    /**
     * Vérifie si une pression longue est en cours
     */
    fun isLongPressActive(): Boolean {
        return isLongPressTriggered
    }
    
    /**
     * Affiche la popup d'accents pour une touche de base
     */
    fun showAccentPopup(baseKey: String, anchorButton: View) {
        val accents = accentMap[baseKey.lowercase()] ?: emojiSkinTones[baseKey] ?: return
        
        // Fermer la popup existante si elle existe
        dismissAccentPopup()
        
        try {
            // Créer le layout de la popup
            val popupLayout = createAccentPopupLayout(accents, baseKey)
            
            // Créer la popup window
            currentAccentPopup = PopupWindow(
                popupLayout,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                false  // non focusable, sinon la fenêtre de saisie se ferme
            ).apply {
                // Style de la popup
                setBackgroundDrawable(createPopupBackground())
                elevation = dpToPx(POPUP_ELEVATION_DP).toFloat()
                
                // Configuration pour IME
                isTouchable = true  // la popup reçoit les touchers
                isOutsideTouchable = true  // un toucher à l'extérieur la ferme
                
                // Animation d'entrée/sortie
                animationStyle = android.R.style.Animation_Dialog
                
                // Affichage au-dessus de la touche
                showAsDropDown(
                    anchorButton,
                    calculatePopupX(anchorButton, popupLayout),
                    -anchorButton.height - dpToPx(50)
                )
            }
            
            Log.d(TAG, "Popup d'accents affichée pour '$baseKey' avec ${accents.size} options")
            
        } catch (e: Exception) {
            Log.e(TAG, "Erreur lors de l'affichage de la popup: ${e.message}", e)
        }
    }
    
    /**
     * Ferme la popup d'accents actuelle
     */
    fun dismissAccentPopup() {
        currentAccentPopup?.let { popup ->
            try {
                if (popup.isShowing) {
                    popup.dismiss()
                } else {
                    // Popup déjà fermé
                }
            } catch (e: Exception) {
                Log.w(TAG, "Erreur lors de la fermeture de la popup: ${e.message}")
            }
        }
        currentAccentPopup = null
        isLongPressTriggered = false
    }
    
    /**
     * Crée le layout de la popup d'accents
     */
    private fun createAccentPopupLayout(accents: List<String>, baseKey: String): LinearLayout {
        return LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(
                dpToPx(8), dpToPx(8),
                dpToPx(8), dpToPx(8)
            )
            
            // Ajouter d'abord la touche de base
            addView(createAccentButton(baseKey, isBase = true))
            
            // Ajouter les variantes d'accents
            accents.forEach { accent ->
                addView(createAccentButton(accent, isBase = false))
            }
        }
    }
    
    /**
     * Crée un bouton d'accent individuel
     */
    private fun createAccentButton(accent: String, isBase: Boolean): Button {
        return Button(context).apply {
            // Appliquer la majuscule si le mode est actif
            text = if (isCapitalMode) accent.uppercase() else accent
            textSize = 18f
            setTextColor(
                KeyboardTheme.palette().let { if (isBase) it.popupBaseEncre else it.popupAccentEncre }
            )
            
            // Taille et style
            layoutParams = LinearLayout.LayoutParams(
                dpToPx(ACCENT_BUTTON_SIZE_DP),
                dpToPx(ACCENT_BUTTON_SIZE_DP)
            ).apply {
                setMargins(
                    dpToPx(ACCENT_BUTTON_MARGIN_DP), 0,
                    dpToPx(ACCENT_BUTTON_MARGIN_DP), 0
                )
            }
            
            // Style visuel
            background = createAccentButtonBackground(isBase)
            
            // Événement de clic Le son de frappe vient de KeyFeedback, avec l'effet du clavier et
            // non le clic d'interface que performClick() ajouterait sinon par-dessus.
            isSoundEffectsEnabled = false

            setOnClickListener { bouton ->
                // v10.11.6 : ces touches écrivent un caractère, elles doivent se sentir et
                // s'entendre comme celles du clavier.
                KeyFeedback.onKeyPress(bouton)
                handleAccentSelection(accent)
            }
            
            // Animation tactile légère
            setOnTouchListener { view, event ->
                when (event.action) {
                    android.view.MotionEvent.ACTION_DOWN -> {
                        view.animate().scaleX(0.9f).scaleY(0.9f).setDuration(50).start()
                        false
                    }
                    android.view.MotionEvent.ACTION_UP,
                    android.view.MotionEvent.ACTION_CANCEL -> {
                        view.animate().scaleX(1.0f).scaleY(1.0f).setDuration(50).start()
                        false
                    }
                    else -> false
                }
            }
        }
    }
    
    /**
     * Gère la sélection d'un accent
     */
    private fun handleAccentSelection(accent: String) {
        val baseChar = currentBaseCharacter ?: ""
        // Appliquer la majuscule si le mode est actif
        val finalAccent = if (isCapitalMode) accent.uppercase() else accent
        accentListener?.onAccentSelected(finalAccent, baseChar)
        dismissAccentPopup()
        currentBaseCharacter = null  // Nettoyer après usage
        
        Log.d(TAG, "Accent sélectionné: '$finalAccent' pour base: '$baseChar'")
    }
    
    /**
     * Crée l'arrière-plan de la popup
     */
    private fun createPopupBackground(): GradientDrawable {
        val p = KeyboardTheme.palette()
        return GradientDrawable().apply {
            cornerRadius = dpToPx(12).toFloat()
            setColor(p.popupFond)
            setStroke(dpToPx(1), p.popupBordure)
        }
    }

    /** Crée l'arrière-plan d'un bouton d'accent. */
    private fun createAccentButtonBackground(isBase: Boolean): GradientDrawable {
        val p = KeyboardTheme.palette()
        return GradientDrawable().apply {
            cornerRadius = dpToPx(8).toFloat()
            if (isBase) {
                // Bouton de base (caractère original) - style atténué
                setColor(p.popupBaseFond)
                setStroke(dpToPx(1), p.popupBaseBordure)
            } else {
                // Boutons d'accents - style actif
                setColor(p.popupAccentFond)
                setStroke(dpToPx(1), p.popupAccentBordure)
            }
        }
    }

    /**
     * Calcule la position X de la popup pour qu'elle soit centrée
     */
    private fun calculatePopupX(anchorButton: View, popupLayout: LinearLayout): Int {
        // Mesurer la largeur approximative de la popup
        val buttonWidth = dpToPx(ACCENT_BUTTON_SIZE_DP + ACCENT_BUTTON_MARGIN_DP * 2)
        
        // Récupérer la clé de base depuis le tag (ImageButton) ou le texte (Button)
        val baseKey = when (anchorButton) {
            is Button -> anchorButton.text.toString().lowercase()
            is android.widget.ImageButton -> (anchorButton.tag as? String)?.lowercase() ?: ""
            else -> ""
        }
        
        val accentCount = accentMap[baseKey]?.size ?: 0
        val totalButtons = accentCount + 1 // +1 pour la touche de base
        val popupWidth = totalButtons * buttonWidth + dpToPx(16) // +padding
        
        // Centrer par rapport au bouton ancre
        val anchorWidth = anchorButton.width
        return (anchorWidth - popupWidth) / 2
    }
    
    /**
     * Obtient tous les accents disponibles pour une touche
     */
    fun getAccentsForKey(key: String): List<String> {
        return accentMap[key.lowercase()] ?: emojiSkinTones[key] ?: emptyList()
    }

    /**
     * Obtient les accents à afficher en aperçu dans les coins de la touche, dans l'ordre haut-droit
     * puis bas-droit (peut différer de l'ordre du popup d'appui long, voir cornerHintOverrides)
     */
    fun getCornerHintsForKey(key: String): List<String> {
        return cornerHintOverrides[key.lowercase()] ?: getAccentsForKey(key)
    }

    /**
     * Ajoute un nouvel accent à une touche existante
     */
    fun addAccentToKey(baseKey: String, accent: String) {
        val key = baseKey.lowercase()
        val currentAccents = accentMap[key]?.toMutableList() ?: mutableListOf()
        
        if (accent !in currentAccents) {
            currentAccents.add(accent)
            // Note: Pour une implémentation complète, il faudrait mettre à jour accentMap
            // qui est actuellement immutable
        }
    }
    
    /**
     * Nettoie les ressources
     */
    fun cleanup() {
        dismissAccentPopup()
        cancelLongPress()
        accentListener = null
    }
    
    // Méthodes utilitaires
    
    private fun dpToPx(dp: Int): Int {
        return (dp * context.resources.displayMetrics.density).toInt()
    }
    
    private fun dpToPx(dp: Float): Int {
        return (dp * context.resources.displayMetrics.density).toInt()
    }
}
