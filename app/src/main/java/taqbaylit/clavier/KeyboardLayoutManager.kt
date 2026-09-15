package taqbaylit.clavier

import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.StateListDrawable
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat

/**
 * Gestionnaire responsable de la création et du stylisme des layouts de clavier
 * Sépare la logique de création des touches du service principal
 */
class KeyboardLayoutManager(private val context: Context) {
    
    companion object {
        private const val BUTTON_HEIGHT_DP = 48
        // Sous cette hauteur les touches deviennent difficiles à viser : mieux vaut
        // alors rogner ailleurs que continuer à réduire.
        private const val BUTTON_MIN_HEIGHT_DP = 32
        // En paysage la fenêtre IME ne reçoit qu'environ 359 dp de haut, contre 891 en portrait sur
        // le même écran.
        private const val BUTTON_HEIGHT_LANDSCAPE_DP = BUTTON_MIN_HEIGHT_DP
        private const val KEYBOARD_ROW_COUNT = 4
        // Padding vertical du bloc de touches, resserré en paysage pour la même raison.
        private const val VERTICAL_PADDING_DP = 8
        private const val VERTICAL_PADDING_LANDSCAPE_DP = 4
        private const val BUTTON_MARGIN_DP = 2
        private const val CORNER_RADIUS_DP = 10f
        // Taille de police d'une lettre, en part de la hauteur de touche.
        private const val KEY_TEXT_HEIGHT_RATIO = 0.62f
        // Les libellés de plusieurs caractères ("123", "ABC", "Taqbaylit") sont contraints par la
        // largeur de la touche, pas par sa hauteur.
        private const val WIDE_LABEL_TEXT_RATIO = 0.28f
        // La signature Taqbaylit de la barre d'espace n'est pas une commande : elle ne s'appuie
        // pas, elle ne se lit qu'une fois.
        private const val SPACE_LABEL_TEXT_RATIO = 0.22f
        // La hauteur ne peut pas commander seule : une touche est plus haute que large, et un
        // glyphe large finit par déborder puis se faire remplacer par une ellipse.
        private const val LABEL_WIDTH_RATIO = 0.90f
        // Padding latéral du bloc de touches, retiré de la largeur d'écran pour
        // savoir ce qui revient réellement à chaque touche.
        private const val KEYBOARD_SIDE_PADDING_DP = 8
        // Aperçus d'appui long dans les coins des touches.
        private const val HINT_TEXT_HEIGHT_RATIO = 0.21f
        private const val TAG = "KeyboardLayoutManager"

        // Délai pour l'appui long sur la barre d'espace (1 seconde)
        private const val SPACE_LONG_PRESS_DELAY = 1000L

        /**
         * Distance que le doigt parcourt sur la barre d'espace pour déplacer le curseur d'un
         * caractère (v14.0.0).
         */
        private const val SPACE_CURSOR_STEP_DP = 10

        /**
         * Nombre de caractères dont le curseur doit se déplacer pour un déplacement de deltaPx du
         * doigt depuis le dernier cran franchi, négatif vers la gauche.
         */
        internal fun cursorStepsFor(deltaPx: Float, stepPx: Float): Int =
            if (stepPx <= 0f) 0 else (deltaPx / stepPx).toInt()

        fun isLandscape(context: Context): Boolean =
            context.resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE

        fun verticalPaddingDp(context: Context): Int =
            if (isLandscape(context)) VERTICAL_PADDING_LANDSCAPE_DP else VERTICAL_PADDING_DP
    }
    
    // État du clavier
    private var isCapitalMode = false
    private var isCapsLock = false
    private var isNumericMode = false // FORCE ALPHABÉTIQUE PAR DÉFAUT
    private var isEmojiMode = false
    private val keyboardButtons = mutableListOf<View>() // Changé de TextView à View pour supporter ImageButton

    // Hauteur que la fenêtre IME peut réellement accorder aux quatre rangées de touches, renseignée
    // par le service avant chaque création de layout.
    private var availableRowsHeightPx = 0

    // Référence optionnelle pour prévisualiser les options d'appui long dans les coins des touches
    // (v8.3.0).
    var accentHandler: AccentHandler? = null
    
    // Handler pour l'appui long personnalisé de la barre d'espace
    private val spaceLongPressHandler = Handler(Looper.getMainLooper())
    private var spaceLongPressRunnable: Runnable? = null
    private var isSpaceLongPressTriggered = false

    // Glissement horizontal sur la barre d'espace (v14.0.0).
    private var spaceCursorAnchorX = 0f
    private var isSpaceCursorMode = false
    
    init {
        // Garantir que le clavier démarre toujours en mode alphabétique
        ensureAlphabeticMode()
    }
    
    // Callbacks pour l'interaction avec les touches
    interface KeyboardInteractionListener {
        fun onKeyPress(key: String)
        fun onLongPress(key: String, button: View) // Changé de TextView à View
        fun onKeyRelease()

        /**
         * Le doigt glisse sur la barre d'espace : déplacer le curseur de steps caractères, négatif
         * vers la gauche (v14.0.0).
         */
        fun onSpaceCursorMove(steps: Int) {}

        /** Le doigt se lève après un glissement de curseur (v14.0.0). */
        fun onSpaceCursorEnd() {}
    }
    
    private var interactionListener: KeyboardInteractionListener? = null
    
    fun setInteractionListener(listener: KeyboardInteractionListener) {
        this.interactionListener = listener
    }

    /** Déclare la hauteur disponible pour les rangées de touches, marges comprises. */
    fun setAvailableRowsHeight(heightPx: Int) {
        availableRowsHeightPx = heightPx.coerceAtLeast(0)
    }

    /**
     * Hauteur d'une touche : la hauteur nominale tant qu'elle tient, sinon la part
     * de place restante, sans jamais descendre sous le seuil de visée.
     */
    private fun keyHeightPx(): Int {
        val nominal = dpToPx(
            if (isLandscape(context)) BUTTON_HEIGHT_LANDSCAPE_DP else BUTTON_HEIGHT_DP
        )
        if (availableRowsHeightPx <= 0) return nominal
        val verticalMargins = dpToPx(BUTTON_MARGIN_DP) * 2
        val fitted = availableRowsHeightPx / KEYBOARD_ROW_COUNT - verticalMargins
        return fitted.coerceIn(dpToPx(BUTTON_MIN_HEIGHT_DP), nominal)
    }
    
    /** Largeur que la rangée accorde à une touche, marges déduites. */
    private fun keyWidthPx(weight: Float, totalWeight: Float): Int {
        val disponible = context.resources.displayMetrics.widthPixels -
            dpToPx(KEYBOARD_SIDE_PADDING_DP) * 2
        val part = (disponible * weight / totalWeight).toInt()
        return (part - dpToPx(BUTTON_MARGIN_DP) * 2).coerceAtLeast(1)
    }

    /** Les panneaux alphabétique et numérique coexistent dans un même conteneur. */
    private var panelHolder: FrameLayout? = null
    private var alphaPanel: View? = null
    private var numericPanel: View? = null
    private var emojiPanel: View? = null
    // Touches de la rangée de contrôle emoji : suivies à part pour ne pas gonfler
    // keyboardButtons d'une ouverture du panneau à l'autre.
    private val emojiPanelButtons = mutableListOf<View>()

    /**
     * Construit le conteneur du clavier : les panneaux alpha et numérique, prêts tous les deux,
     * seul celui du mode courant visible.
     */
    fun createKeyboardLayout(): View {
        Log.d("KeyboardLayoutManager", "createKeyboardLayout - isNumericMode: $isNumericMode")

        keyboardButtons.clear()
        emojiPanelButtons.clear()

        val holder = FrameLayout(context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        }
        val alpha = buildPanel { createAlphabeticLayout(it) }
        val numeric = buildPanel { createNumericLayout(it) }
        holder.addView(alpha)
        holder.addView(numeric)

        alphaPanel = alpha
        numericPanel = numeric
        panelHolder = holder
        emojiPanel = null
        applyMode()
        return holder
    }

    /** Enveloppe une série de rangées dans le conteneur vertical à padding du clavier. */
    private fun buildPanel(remplir: (LinearLayout) -> Unit): LinearLayout {
        val verticalPaddingPx = dpToPx(verticalPaddingDp(context))
        val panel = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(
                dpToPx(KEYBOARD_SIDE_PADDING_DP), verticalPaddingPx,
                dpToPx(KEYBOARD_SIDE_PADDING_DP), verticalPaddingPx
            )
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            )
        }
        remplir(panel)
        return panel
    }

    /** Affiche le panneau du mode courant, masque les autres. */
    fun applyMode() {
        val holder = panelHolder ?: return
        if (isEmojiMode) rebuildEmojiPanel(holder) else dropEmojiPanel(holder)
        val alphaVisible = !isNumericMode && !isEmojiMode
        alphaPanel?.visibility = if (alphaVisible) View.VISIBLE else View.INVISIBLE
        numericPanel?.visibility = if (isNumericMode && !isEmojiMode) View.VISIBLE else View.INVISIBLE
        emojiPanel?.visibility = if (isEmojiMode) View.VISIBLE else View.GONE
    }

    private fun rebuildEmojiPanel(holder: FrameLayout) {
        dropEmojiPanel(holder)
        val avant = keyboardButtons.size
        val panel = buildPanel { createEmojiLayout(it) }
        emojiPanelButtons.addAll(keyboardButtons.subList(avant, keyboardButtons.size))
        emojiPanel = panel
        holder.addView(panel)
    }

    private fun dropEmojiPanel(holder: FrameLayout) {
        emojiPanel?.let { holder.removeView(it) }
        emojiPanel = null
        if (emojiPanelButtons.isNotEmpty()) {
            keyboardButtons.removeAll(emojiPanelButtons.toSet())
            emojiPanelButtons.clear()
        }
    }
    
    /**
     * Crée le layout alphabétique (AZERTY créole)
     */
    private fun createAlphabeticLayout(mainLayout: LinearLayout) {
        // Disposition kabyle. La structure, les poids de touche et le raisonnement sont ceux de
        // KreyolKeyb ; seules les lettres changent, et le choix est mesure sur les 1 823 217
        // lettres des formes verbales, qui portent l'orthographe de reference.
        val row1 = arrayOf("a", "z", "e", "r", "t", "y", "u", "i", "ɣ", "p")
        val row2 = arrayOf("q", "s", "d", "f", "g", "h", "j", "k", "l", "m")
        // « ɛ » (1,477 %) occupe l'emplacement de l'apostrophe.
        val row3 = arrayOf("⇧", "w", "x", "c", "v", "b", "n", "ɛ", "⌫")
        // ḍ (1,680 %) et ḥ (1,482 %) sont les deux emphatiques les plus frequentes, devant ɣ
        // lui-meme.
        val row4 = arrayOf("123", ",", "ḍ", "-", " ", "ḥ", ".", "MICRO", "⏎")

        mainLayout.addView(createKeyboardRow(row1))
        mainLayout.addView(createKeyboardRow(row2))
        mainLayout.addView(createKeyboardRow(row3))
        mainLayout.addView(createKeyboardRow(row4))
    }
    
    /**
     * Crée le layout numérique
     */
    private fun createNumericLayout(mainLayout: LinearLayout) {
        val row1 = arrayOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")
        val row2 = arrayOf("-", "/", ":", ";", "(", ")", "€", "&", "@", "\"")
        // v10.12.15 : "#" ajouté. C'est la seule page de symboles du clavier (il n'y a pas de
        // seconde page comme le "=\<" de Gboard), donc son absence signifiait qu'aucun hashtag ne
        // pouvait être écrit sans changer de clavier.
        val row3 = arrayOf("=", ".", ",", "?", "!", "'", "+", "*", "#", "⌫")
        val row4 = arrayOf("ABC", "EMOJI", " ", "⏎")

        mainLayout.addView(createKeyboardRow(row1))
        mainLayout.addView(createKeyboardRow(row2))
        mainLayout.addView(createKeyboardRow(row3))
        mainLayout.addView(createKeyboardRow(row4))
    }

    /** Crée le layout emoji. Accessible depuis le clavier alphabétique et depuis le mode 123. */
    private fun createEmojiLayout(mainLayout: LinearLayout) {
        val controlRow = arrayOf("ABC", "⌫", " ", "⏎")

        val picker = EmojiPickerView(context, accentHandler).apply {
            onEmojiSelected = { emoji ->
                // Noté ici et non dans la vue : le panneau reste une vue, et
                // EmojiRecents écarte de lui-même les champs sensibles.
                EmojiRecents.enregistrer(context, emoji)
                interactionListener?.onKeyPress(emoji)
            }
        }

        mainLayout.addView(picker)
        mainLayout.addView(createKeyboardRow(controlRow))
    }
    
    /**
     * Crée une rangée de touches
     */
    private fun createKeyboardRow(keys: Array<String>): LinearLayout {
        val rowLayout = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            // Un LinearLayout horizontal aligne par défaut ses enfants sur la ligne de base de leur
            // texte.
            isBaselineAligned = false
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, dpToPx(2), 0, dpToPx(2))
            }
        }
        
        val totalWeight = calculateRowWeight(keys)
        
        for (key in keys) {
            // createKeyButton() alimente déjà keyboardButtons avec la touche interactive brute
            // (avant l'éventuel enrobage des indices de coin) ; un second ajout ici dupliquait
            // chaque touche dans la liste.
            val button = createKeyButton(key, totalWeight)
            rowLayout.addView(button)
        }
        
        return rowLayout
    }
    
    /**
     * Crée un bouton de touche individuel (Button ou ImageButton selon le type)
     */
    private fun createKeyButton(key: String, totalWeight: Float): View {
        // Déterminer si on utilise une icône Material Design
        val useIcon = key in listOf("⌫", "⏎", "⇧", "EMOJI", "MICRO")
        
        val button: View = if (useIcon) {
            // Créer un ImageButton pour les touches avec icônes
            android.widget.ImageButton(context).apply {
                // Définir l'icône selon la touche
                setImageResource(when (key) {
                    "⌫" -> R.drawable.ic_backspace
                    "⏎" -> R.drawable.ic_keyboard_return
                    "EMOJI" -> R.drawable.ic_emoji
                    "MICRO" -> R.drawable.ic_micro
                    "⇧" -> if (isCapsLock) R.drawable.ic_shift_caps
                           else if (isCapitalMode) R.drawable.ic_shift_on
                           else R.drawable.ic_shift_off
                    else -> R.drawable.ic_backspace // Fallback
                })
                
                // Teinte provisoire : styliserTouche() pose ensuite l'encre du thème.
                setColorFilter(Color.WHITE)
                
                // Padding de l'icône, différent selon la touche et proportionnel à la hauteur de
                // touche.
                val iconPaddingRatio = when (key) {
                    // Entrée : 8 dp jusqu'en 10.12.8.
                    "⏎" -> 4f / BUTTON_HEIGHT_DP
                    "⌫" -> 10f / BUTTON_HEIGHT_DP // Padding moyen pour Backspace
                    // Emoji : même retrait que la corbeille, dont le tracé remplit son cadre dans
                    // une proportion voisine — le visage en occupe 83 % de la hauteur, la corbeille
                    // 75 %.
                    "EMOJI" -> 10f / BUTTON_HEIGHT_DP
                    // Micro : le retrait de l'entrée, pour la même raison qu'elle.
                    "MICRO" -> 4f / BUTTON_HEIGHT_DP
                    // Shift. Deux causes cumulées.
                    else -> 6f / BUTTON_HEIGHT_DP
                }
                val iconPadding = (keyHeightPx() * iconPaddingRatio).toInt()
                setPadding(iconPadding, iconPadding, iconPadding, iconPadding)
                scaleType = android.widget.ImageView.ScaleType.FIT_CENTER
                adjustViewBounds = true
                
                // Description pour accessibilité Lues par TalkBack : elles doivent suivre la langue
                // de l'appareil comme le reste de l'interface, et non rester figees en francais.
                contentDescription = when (key) {
                    "⌫" -> context.getString(R.string.touche_effacer)
                    "⏎" -> context.getString(R.string.touche_entree)
                    "⇧" -> context.getString(R.string.touche_majuscule)
                    "EMOJI" -> context.getString(R.string.touche_emoji)
                    "MICRO" -> context.getString(R.string.touche_micro)
                    else -> key
                }
                
                // Stocker la clé dans le tag pour identification
                tag = key
                
                // Calcul du poids selon le type de touche
                val weight = getKeyWeight(key)
                layoutParams = LinearLayout.LayoutParams(
                    0,
                    keyHeightPx(),
                    weight
                ).apply {
                    setMargins(
                        dpToPx(BUTTON_MARGIN_DP), 0, 
                        dpToPx(BUTTON_MARGIN_DP), 0
                    )
                }
            }
        } else {
            // Créer un Button classique pour les autres touches
            Button(context).apply {
                text = getDisplayText(key)
                // La touche brute est mémorisée ici, comme sur les ImageButton.
                tag = key
                // TalkBack lisait « Taqbaylit » sur l'espace : il continue de le
                // lire quand le thème y pose un signe à la place du nom.
                if (key == " " && text.toString() != KeyboardTheme.LIBELLE_LANGUE)
                    contentDescription = KeyboardTheme.LIBELLE_LANGUE
                // « 123 » et « ABC » ne tiennent pas en pleine taille dans la largeur d'une touche
                // en portrait.
                maxLines = 1
                // Le thème AppCompat d'une activité impose textAllCaps=true aux Button.
                isAllCaps = false
                // Button a une élévation/StateListAnimator implicite qui le fait dessiner
                // par-dessus ses voisins ajoutés après lui dans un FrameLayout, quel que soit
                // l'ordre d'ajout (constaté en testant les indices d'appui long v8.3.0.
                elevation = 0f
                stateListAnimator = null
                // Taille de police dérivée de la hauteur de touche, en pixels.
                val labelRatio = when (key) {
                    // Un libellé d'un seul signe (ⵣ, thème Tamazɣa) prend la
                    // taille d'une lettre : réduit comme un mot, il serait un point.
                    " " -> if (libelleEspace().length == 1) KEY_TEXT_HEIGHT_RATIO
                           else SPACE_LABEL_TEXT_RATIO
                    "123", "ABC" -> WIDE_LABEL_TEXT_RATIO
                    else -> KEY_TEXT_HEIGHT_RATIO
                }
                val taillePx = minOf(
                    keyHeightPx() * labelRatio,
                    keyWidthPx(getKeyWeight(key), totalWeight) * LABEL_WIDTH_RATIO
                )
                setTextSize(TypedValue.COMPLEX_UNIT_PX, taillePx)
                // Même raison que pour les puces de suggestion.
                includeFontPadding = false
                // Graisse normale. Les touches sont déjà séparées par leur fond et leur ombre : la
                // lettre n'a pas besoin d'être épaissie pour se viser.
                setTypeface(typeface, Typeface.NORMAL)
                // Le style Button par défaut apporte 30 px de padding sur chaque bord, hérités de
                // son fond d'origine.
                setPadding(0, 0, 0, 0)
                minHeight = 0
                minWidth = 0
                
                // Calcul du poids selon le type de touche
                val weight = getKeyWeight(key)
                layoutParams = LinearLayout.LayoutParams(
                    0,
                    keyHeightPx(),
                    weight
                ).apply {
                    setMargins(
                        dpToPx(BUTTON_MARGIN_DP), 0, 
                        dpToPx(BUTTON_MARGIN_DP), 0
                    )
                }
            }
        }
        
        // Fond, encre et ombre
        styliserTouche(button, key)
        
        // Ajouter le bouton à la liste de suivi
        keyboardButtons.add(button)
        
        // Configuration des événements tactiles
        setupButtonInteractions(button, key)

        // Aperçu des options d'appui long dans les coins de la touche (v8.3.0)
        val hints = accentHandler?.takeIf { it.hasAccents(key) }?.getCornerHintsForKey(key)
        if (!hints.isNullOrEmpty()) {
            return wrapWithLongPressHints(button, hints, key)
        }

        // Indice visuel : l'appui long sur la barre d'espace change de clavier système (voir
        // setupSpaceLongPress).
        if (key == " " && accentHandler != null) {
            return wrapWithSpaceGlobeHint(button)
        }

        return button
    }

    /**
     * Superpose un petit globe dans le coin de la barre d'espace, pour rendre découvrable l'appui
     * long sans ajouter de touche dédiée qui réduirait la largeur des touches déjà denses de la
     * rangée du bas.
     */
    private fun wrapWithSpaceGlobeHint(inner: View): FrameLayout {
        val outerParams = inner.layoutParams
        inner.layoutParams = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        )
        // Le côté de l'ancien glyphe, dont la hauteur valait la taille de police.
        val cote = (keyHeightPx() * HINT_TEXT_HEIGHT_RATIO * 1.2f).toInt()
        val hint = android.widget.ImageView(context).apply {
            setImageResource(R.drawable.ic_globe)
            // L'encre du nom de la langue : l'indice et la signature parlent de
            // la même chose, la langue du clavier.
            setColorFilter(KeyboardTheme.palette().encreEspace)
            scaleType = android.widget.ImageView.ScaleType.FIT_CENTER
            isClickable = false
            isFocusable = false
            // Décoratif : la touche porte déjà son nom pour TalkBack.
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            layoutParams = FrameLayout.LayoutParams(cote, cote, Gravity.TOP or Gravity.END).apply {
                // L'espace est une pilule : à 4 dp du bord droit, l'indice sortait de la courbe de
                // son extrémité.
                setMargins(0, dpToPx(4), keyHeightPx() / 4, 0)
            }
        }
        return FrameLayout(context).apply {
            layoutParams = outerParams
            addView(inner)
            addView(hint)
        }
    }

    /**
     * Enveloppe une touche dans un FrameLayout pour superposer, en haut et en bas du côté droit, un
     * aperçu des deux premières options d'appui long.
     */
    private fun wrapWithLongPressHints(inner: View, hints: List<String>, key: String): FrameLayout {
        val outerParams = inner.layoutParams
        inner.layoutParams = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        )

        val hintColor = hintColorFor(key)

        return FrameLayout(context).apply {
            layoutParams = outerParams
            addView(inner)
            addView(createHintLabel(hints[0], Gravity.TOP or Gravity.END, hintColor))
            if (hints.size > 1) {
                addView(createHintLabel(hints[1], Gravity.BOTTOM or Gravity.END, hintColor))
            }
        }
    }

    /**
     * Couleur d'un indice de coin : celle des deux encres, sombre ou blanche, qui contraste le plus
     * avec le fond de la touche.
     */
    private fun hintColorFor(key: String): Int {
        val fond = keyBackgroundColors(key).let { melangerCouleurs(it.first(), it.last()) }
        val sombre = Color.parseColor("#333333")
        val encre = if (contraste(sombre, fond) >= contraste(Color.WHITE, fond)) sombre else Color.WHITE
        // Un fond blanc laisse une marge de contraste telle que l'indice peut rester discret ; sur
        // un fond coloré cette marge est déjà consommée, et à cette taille de glyphe
        // l'anti-crénelage en mange encore une part.
        val alpha = if (contraste(encre, fond) > 8f) 0x99 else 0xFF
        return Color.argb(alpha, Color.red(encre), Color.green(encre), Color.blue(encre))
    }

    /** Moyenne de deux couleurs, pour juger un dégradé sur sa teinte médiane. */
    private fun melangerCouleurs(a: Int, b: Int): Int = Color.rgb(
        (Color.red(a) + Color.red(b)) / 2,
        (Color.green(a) + Color.green(b)) / 2,
        (Color.blue(a) + Color.blue(b)) / 2
    )

    /** Rapport de contraste WCAG entre deux couleurs opaques, de 1 à 21. */
    private fun contraste(a: Int, b: Int): Float {
        val la = luminanceRelative(a)
        val lb = luminanceRelative(b)
        return (maxOf(la, lb) + 0.05f) / (minOf(la, lb) + 0.05f)
    }

    private fun luminanceRelative(couleur: Int): Float {
        fun canal(v: Int): Float {
            val c = v / 255f
            return if (c <= 0.03928f) c / 12.92f else Math.pow(((c + 0.055f) / 1.055f).toDouble(), 2.4).toFloat()
        }
        return 0.2126f * canal(Color.red(couleur)) +
               0.7152f * canal(Color.green(couleur)) +
               0.0722f * canal(Color.blue(couleur))
    }

    private fun createHintLabel(hintText: String, gravity: Int, textColor: Int): TextView {
        return TextView(context).apply {
            text = hintText
            setTextSize(TypedValue.COMPLEX_UNIT_PX, keyHeightPx() * HINT_TEXT_HEIGHT_RATIO)
            setTextColor(textColor)
            isClickable = false
            isFocusable = false
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                gravity
            ).apply {
                setMargins(0, dpToPx(2), dpToPx(3), dpToPx(2))
            }
        }
    }
    
    /** Dégradé de fond d'une touche, du haut vers le bas. */
    private fun keyBackgroundColors(key: String): IntArray = keyBackground(key).couleurs()

    /** Fond d'une touche, dans la palette du thème en cours. */
    private fun keyBackground(key: String): KeyboardTheme.Degrade {
        val p = KeyboardTheme.palette()
        return when (key) {
            "⇧" -> when {
                isCapsLock -> p.toucheCaps
                isCapitalMode -> p.toucheMaj
                else -> p.touche
            }
            "⏎", "123", "ABC", "EMOJI", "MICRO", " " -> p.toucheFonction
            else -> p.touche
        }
    }

    /** La touche est-elle sans surface ? */
    private fun estNue(key: String): Boolean = when (key) {
        "⇧" -> !isCapsLock && !isCapitalMode
        "⏎", "123", "ABC", "EMOJI", "MICRO", " " -> false
        else -> true
    }

    /** Encre d'une touche. */
    private fun keyForeground(key: String): Int {
        val p = KeyboardTheme.palette()
        return when {
            // Le nom de la langue sur l'espace : lisible de près, sans revendiquer le regard
            // pendant la frappe.
            key == " " -> p.encreEspace
            estNue(key) -> p.encre
            else -> p.encreFonction
        }
    }

    /** Fond, encre et état d'appui d'une touche, dans la palette du thème en cours. */
    private fun styliserTouche(view: View, key: String) {
        val p = KeyboardTheme.palette()
        // L'espace est une pilule, comme chez Gboard : c'est la seule touche assez
        // longue pour que la différence se voie.
        val rayon = if (key == " ") keyHeightPx() / 2f
                    else dpToPx(CORNER_RADIUS_DP.toInt()).toFloat()

        // Contraste élevé : une touche nue prend un contour, sans quoi rien ne dessine son étendue
        // sur le fond noir.
        val contour = p.contourTouche.takeIf { Color.alpha(it) != 0 && estNue(key) }

        fun forme(couleurs: IntArray) = GradientDrawable().apply {
            cornerRadius = rayon
            setColors(couleurs)
            orientation = GradientDrawable.Orientation.TOP_BOTTOM
            if (contour != null) setStroke(maxOf(1, dpToPx(1)), contour)
        }

        // Une touche sans surface n'a rien pour dire qu'on l'a touchée : le voile d'appui lui en
        // prête une le temps du contact.
        view.background = StateListDrawable().apply {
            addState(intArrayOf(android.R.attr.state_pressed),
                     forme(intArrayOf(p.enfoncee, p.enfoncee)))
            addState(intArrayOf(), forme(keyBackgroundColors(key)))
        }

        if (view is Button) view.setTextColor(keyForeground(key))

        // Icônes (shift, retour arrière, entrée) : la même encre que les libellés.
        if (view is android.widget.ImageButton) {
            view.setColorFilter(keyForeground(key))
        }
    }
    
    /**
     * Configure les interactions tactiles pour un bouton
     */
    private fun setupButtonInteractions(button: View, key: String) {
        // Le son de frappe est joué explicitement par KeyFeedback, avec l'effet propre à la touche.
        button.isSoundEffectsEnabled = false

        // Appui long personnalisé pour la barre d'espace (1 seconde)
        if (key == " ") {
            // Pas de setOnClickListener ici : setupSpaceLongPress() gère déjà le clic court via son
            // OnTouchListener.
            button.setOnLongClickListener(null) // Désactiver le listener par défaut
            setupSpaceLongPress(button, key)
        } else {
            button.setOnClickListener {
                interactionListener?.onKeyPress(key)
            }
            button.setOnLongClickListener {
                interactionListener?.onLongPress(key, button)
                true
            }
            // Animation tactile pour les touches autres que la barre d'espace
            addTouchAnimation(button, key)
        }
    }
    
    /** Gestes de la barre d'espace. */
    private fun setupSpaceLongPress(button: View, key: String) {
        val slopPx = android.view.ViewConfiguration.get(context).scaledTouchSlop
        val stepPx = dpToPx(SPACE_CURSOR_STEP_DP).toFloat()

        button.setOnTouchListener { view, event ->
            when (event.action) {
                android.view.MotionEvent.ACTION_DOWN -> {
                    isSpaceLongPressTriggered = false
                    isSpaceCursorMode = false
                    spaceCursorAnchorX = event.x
                    
                    // Animation d'appui (100ms)
                    view.animate()
                        .scaleX(0.95f)
                        .scaleY(0.95f)
                        .setDuration(100)
                        .start()
                    
                    KeyFeedback.onKeyPress(view, key)
                    
                    // Démarrer le timer de 1 seconde pour l'appui long
                    spaceLongPressRunnable = Runnable {
                        isSpaceLongPressTriggered = true
                        Log.d(TAG, "⏱️ Appui long 1s détecté sur barre d'espace")
                        interactionListener?.onLongPress(key, button)
                    }
                    spaceLongPressHandler.postDelayed(spaceLongPressRunnable!!, SPACE_LONG_PRESS_DELAY)
                    
                    false
                }
                android.view.MotionEvent.ACTION_MOVE -> {
                    if (!isSpaceCursorMode) {
                        // Le seuil est celui du système (scaledTouchSlop) et non une valeur maison.
                        if (kotlin.math.abs(event.x - spaceCursorAnchorX) > slopPx) {
                            isSpaceCursorMode = true
                            spaceLongPressRunnable?.let { spaceLongPressHandler.removeCallbacks(it) }
                            // L'ancre repart du point courant : sans cela le curseur
                            // sauterait du seuil déjà parcouru dès le premier cran.
                            spaceCursorAnchorX = event.x
                            releaseKeyScale(view)
                            Log.d(TAG, "↔️ Glissement du curseur engagé sur la barre d'espace")
                        }
                    } else {
                        val steps = cursorStepsFor(event.x - spaceCursorAnchorX, stepPx)
                        if (steps != 0) {
                            spaceCursorAnchorX += steps * stepPx
                            KeyFeedback.onCursorStep(view)
                            interactionListener?.onSpaceCursorMove(steps)
                        }
                    }
                    false
                }
                android.view.MotionEvent.ACTION_UP -> {
                    // Annuler le timer si relâché avant 1 seconde
                    spaceLongPressRunnable?.let { spaceLongPressHandler.removeCallbacks(it) }
                    
                    releaseKeyScale(view)
                    
                    interactionListener?.onKeyRelease()
                    
                    when {
                        // Un glissement n'écrit rien : il a déplacé le curseur
                        isSpaceCursorMode -> {
                            isSpaceCursorMode = false
                            interactionListener?.onSpaceCursorEnd()
                        }
                        // Si relâché rapidement (pas d'appui long), c'est un clic normal
                        !isSpaceLongPressTriggered -> interactionListener?.onKeyPress(key)
                    }
                    
                    false
                }
                android.view.MotionEvent.ACTION_CANCEL -> {
                    // Annuler le timer en cas d'annulation
                    spaceLongPressRunnable?.let { spaceLongPressHandler.removeCallbacks(it) }
                    
                    releaseKeyScale(view)
                    
                    interactionListener?.onKeyRelease()
                    if (isSpaceCursorMode) {
                        isSpaceCursorMode = false
                        interactionListener?.onSpaceCursorEnd()
                    }
                    false
                }
                else -> false
            }
        }
    }

    /** Animation de relâchement (120 ms), commune aux fins de geste de l'espace. */
    private fun releaseKeyScale(view: View) {
        view.animate()
            .scaleX(1.0f)
            .scaleY(1.0f)
            .setDuration(120)
            .start()
    }
    
    /** Animation d'appui, vibration et son de frappe sur un bouton de touche. */
    private fun addTouchAnimation(view: View, key: String) {
        view.setOnTouchListener { v, event ->
            when (event.action) {
                android.view.MotionEvent.ACTION_DOWN -> {
                    // Animation d'appui (100ms comme l'original)
                    v.animate()
                        .scaleX(0.95f)
                        .scaleY(0.95f)
                        .setDuration(100)
                        .start()
                    
                    KeyFeedback.onKeyPress(v, key)
                    
                    false
                }
                android.view.MotionEvent.ACTION_UP, 
                android.view.MotionEvent.ACTION_CANCEL -> {
                    // Animation de relâchement (120ms comme l'original)
                    v.animate()
                        .scaleX(1.0f)
                        .scaleY(1.0f)
                        .setDuration(120)
                        .start()
                    
                    interactionListener?.onKeyRelease()
                    false
                }
                else -> false
            }
        }
    }
    
    /**
     * Met à jour l'affichage du clavier selon l'état actuel
     */
    
    /**
     * Met à jour les états internes du clavier
     */
    fun updateKeyboardStates(isNumeric: Boolean, isEmoji: Boolean, isCapital: Boolean, isCapsLock: Boolean) {
        this.isNumericMode = isNumeric
        this.isEmojiMode = isEmoji
        this.isCapitalMode = isCapital
        this.isCapsLock = isCapsLock
    }

    /** Repeint les touches selon l'etat courant. */
    fun updateKeyboardDisplay() {
        
        
        keyboardButtons.forEach { button ->
            val key = getKeyFromButton(button)
            
            // Mise à jour du style pour la touche Shift
            if (key == "⇧") {
                
                // Si c'est un ImageButton, mettre à jour l'icône
                if (button is android.widget.ImageButton) {
                    val newIcon = if (isCapsLock) R.drawable.ic_shift_caps
                                  else if (isCapitalMode) R.drawable.ic_shift_on
                                  else R.drawable.ic_shift_off
                    button.setImageResource(newIcon)
                    // Le fond doit suivre l'état au même titre que l'icône.
                    styliserTouche(button, key)
                } else if (button is Button) {
                    // Si c'est un Button classique, mettre à jour le texte
                    button.text = getDisplayText(key)
                    styliserTouche(button, key)
                }
            } else if (button is Button) {
                // Pour les autres touches, mettre à jour le texte normalement
                button.text = getDisplayText(key)
            }
        }
    }
    
    /**
     * Commute entre les modes majuscule/minuscule
     */
    fun toggleCapsMode(): Boolean {
        when {
            !isCapitalMode && !isCapsLock -> {
                isCapitalMode = true
                isCapsLock = false
            }
            isCapitalMode && !isCapsLock -> {
                isCapitalMode = true
                isCapsLock = true
            }
            else -> {
                isCapitalMode = false
                isCapsLock = false
            }
        }
        // ❌ SUPPRIMÉ: updateKeyboardDisplay() - déjà appelé par InputProcessor
        return isCapitalMode
    }
    
    /** Commute entre mode alphabétique et numérique. */
    fun switchKeyboardMode(): Boolean {
        if (isEmojiMode) {
            isEmojiMode = false
            isNumericMode = false
        } else {
            isNumericMode = !isNumericMode
        }
        return isNumericMode
    }
    
    /**
     * Retourne l'état actuel du mode numérique sans le modifier
     */
    fun isNumericMode(): Boolean {
        return isNumericMode
    }

    /**
     * Retourne l'état actuel du mode emoji sans le modifier
     */
    fun isEmojiMode(): Boolean {
        return isEmojiMode
    }

    /**
     * Active le layout emoji (accessible depuis le mode 123)
     */
    fun switchToEmojiMode() {
        isEmojiMode = true
        isNumericMode = false
        Log.d("KeyboardLayoutManager", "Mode emoji activé")
    }

    /**
     * Force le mode alphabétique (pour l'initialisation)
     */
    fun switchKeyboardModeToAlphabetic() {
        isNumericMode = false
        isEmojiMode = false
        Log.d("KeyboardLayoutManager", "Mode forcé à alphabétique")
    }

    /**
     * Garantit que le clavier démarre en mode alphabétique
     */
    private fun ensureAlphabeticMode() {
        isNumericMode = false
        isEmojiMode = false
        isCapitalMode = false
        isCapsLock = false
        Log.d("KeyboardLayoutManager", "Initialisation : mode alphabétique")
    }
    
    /**
     * Force publiquement le retour au mode alphabétique
     */
    fun forceAlphabeticMode() {
        ensureAlphabeticMode()
        Log.d("KeyboardLayoutManager", "Retour forcé au mode alphabétique")
    }
    
    /**
     * Nettoie les ressources
     */
    fun cleanup() {
        keyboardButtons.forEach { button ->
            cleanupView(button)
        }
        keyboardButtons.clear()
        emojiPanelButtons.clear()
        panelHolder = null
        alphaPanel = null
        numericPanel = null
        emojiPanel = null
        interactionListener = null
    }
    
    // Méthodes utilitaires privées
    
    /** Dernier libellé d'espace demandé, et celui qui a été retenu. */
    private var libelleVerifie: Pair<String, String>? = null

    /** Le libellé de l'espace que le thème demande, s'il se dessine. */
    private fun libelleEspace(): String {
        val demande = KeyboardTheme.palette().libelleEspace
        if (demande == KeyboardTheme.LIBELLE_LANGUE) return demande
        libelleVerifie?.let { (d, retenu) -> if (d == demande) return retenu }
        val dessinable = runCatching { android.graphics.Paint().hasGlyph(demande) }
            .getOrDefault(false)
        val retenu = if (dessinable) demande else KeyboardTheme.LIBELLE_LANGUE
        libelleVerifie = demande to retenu
        return retenu
    }

    private fun getDisplayText(key: String): String {
        return when (key) {
            " " -> libelleEspace()
            "⇧" -> "⇧"
            "⌫" -> "⌫"
            "⏎" -> "⏎"
            "123" -> if (isNumericMode) "ABC" else "123"
            // Les rangées des modes 123 et EMOJI déclarent littéralement "ABC" pour le retour à
            // l'alphabétique ; sans cette branche elle tombait dans le else et s'affichait "abc",
            // en basculant en "ABC" au gré du shift, un état qui ne la concerne pas.
            "ABC" -> "ABC"
            // Touches kabyles dediees : la majuscule s'applique, mais pas le
            // lowercase() du cas general, qui n'aurait rien a faire sur elles.
            "ḍ", "ḥ", "ɣ", "ɛ" -> if (isCapitalMode) key.uppercase() else key
            else -> if (isCapitalMode) key.uppercase() else key.lowercase()
        }
    }
    
    private fun getKeyWeight(key: String): Float {
        return when (key) {
            " " -> 4.0f      // Barre d'espace plus large
            // v10.11.4 : 1,5 → 1,25 pour financer l'apostrophe ajoutée en rangée 3 sans rétrécir
            // les lettres sous la largeur des rangées 1 et 2.
            "⇧", "⌫" -> 1.25f
            else -> 1.0f     // Touches normales
        }
    }
    
    private fun calculateRowWeight(keys: Array<String>): Float {
        return keys.sumOf { getKeyWeight(it).toDouble() }.toFloat()
    }
    
    /** Touche brute portée par une vue. */
    private fun getKeyFromButton(button: View): String {
        (button.tag as? String)?.let { return it }
        return when (button) {
            is Button -> button.text.toString().lowercase()
            else -> ""
        }
    }
    
    private fun dpToPx(dp: Int): Int {
        return (dp * context.resources.displayMetrics.density).toInt()
    }
    
    private fun cleanupView(view: View) {
        view.setOnClickListener(null)
        view.setOnLongClickListener(null)
        view.setOnTouchListener(null)
        view.background = null
        
        // Nettoyer les animations en cours
        view.animate().cancel()
        view.clearAnimation()
        
        // Nettoyer les références du parent
        (view.parent as? ViewGroup)?.removeView(view)
    }
}
