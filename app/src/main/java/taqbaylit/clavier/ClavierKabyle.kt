package taqbaylit.clavier

import android.app.ActivityManager
import android.content.Context
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.LayerDrawable
import android.graphics.drawable.Drawable
import android.graphics.Color
import android.graphics.Typeface
import android.inputmethodservice.InputMethodService
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.TypedValue
import android.view.KeyEvent
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputConnection
import android.view.inputmethod.InputMethodManager
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import taqbaylit.moteur.Prediction

/**
 * Le clavier. La couche visuelle — disposition, theme, appuis longs, retour de frappe, barre de
 * suggestions en cuvette — vient de KreyolKeyb (MIT, Potomitan), reprise telle quelle.
 */
class ClavierKabyle : InputMethodService(),
    KeyboardLayoutManager.KeyboardInteractionListener,
    AccentHandler.AccentSelectionListener,
    Outils.Hote {

    companion object {
        private const val TAG = "Taqbaylit"

        /** Caracteres lus autour du curseur pour reconstituer le mot. */
        private const val REGARD = 64

        /** Frappe rapide : on laisse passer la rafale avant de calculer. */
        private const val ATTENTE_MS = 60L

        /** Temps laisse aux evenements de curseur en vol avant de recalculer. */
        private const val DELAI_SYNC_MS = 120L

        /** Cadence de rafraichissement du message de preparation. */
        private const val ATTENTE_ANNONCE_MS = 400L

        /** Des la premiere lettre, et non la deuxieme. */
        private const val LONGUEUR_MIN = 1

        private const val MAX_PROPOSITIONS = 6
        private const val BARRE_HAUTEUR_DP = 44
        private const val BARRE_HAUTEUR_PAYSAGE_DP = 38
        // 0 : la barre est a plat et va d'un bord a l'autre, comme chez Gboard.
        // Le plateau creuse de KreyolKeyb l'encastrait de 8 dp de chaque cote.
        private const val BARRE_MARGE_DP = 0
        private const val PUCE_ECART_DP = 12
        private const val PUCE_PAD_V_DP = 6
        private const val PUCE_LARGEUR_MIN_DP = 88
        private const val RANGEE_PAD_EXT_DP = 4
        private const val TEXTE_SP = 18f
        /** Trait de nature sous une proposition : retrait lateral, et hauteur au-dessus du bas. */
        private const val TRAIT_RETRAIT_DP = 12
        private const val TRAIT_HAUT_DP = 3
        /** Bouton des outils, à gauche de la barre. */
        private const val OUTILS_LARGEUR_DP = 40
        /** Bande d'identité du thème Tamazɣa, prise sur la hauteur de la barre. */
        private const val BANDE_DP = 3

        /**
         * Ce qui appartient a un mot. La frappe et la reconstitution autour du curseur doivent
         * partager cette definition, sinon le mot suivi divergerait du texte reel.
         */
        fun estCaractereMot(c: Char) = c.isLetter() || c == '-'

        /** Mot en cours, deduit du texte qui precede le curseur. */
        fun motAvant(texteAvant: String, selection: Boolean): String =
            if (selection) "" else texteAvant.takeLastWhile(::estCaractereMot)

        /** Unites UTF-16 a effacer pour retirer un seul glyphe. */
        fun longueurRetourArriere(texteAvant: String): Int {
            if (texteAvant.isEmpty()) return 1
            val fin = texteAvant.length
            val dernier = texteAvant.codePointBefore(fin)
            val taille = Character.charCount(dernier)
            val estTonDePeau = dernier in 0x1F3FB..0x1F3FF
            val avantDernier = fin - taille
            if (estTonDePeau && avantDernier > 0)
                return taille + Character.charCount(texteAvant.codePointBefore(avantDernier))
            return taille
        }

        /** Rend a une proposition la casse du mot que l'utilisateur a tape. */
        fun casserComme(saisi: String, proposition: String): String {
            if (saisi.isEmpty() || proposition.isEmpty()) return proposition
            val lettres = saisi.filter { it.isLetter() }
            if (lettres.length >= 2 && lettres.all { it.isUpperCase() })
                return proposition.uppercase()
            if (saisi[0].isUpperCase() &&
                saisi.drop(1).all { !it.isLetter() || it.isLowerCase() })
                return proposition.replaceFirstChar { it.uppercase() }
            // Leur troisieme cas, le report caractere par caractere d'une casse mixte (« kaBr » ->
            // « kaBrit »), n'est pas repris.
            return proposition
        }

        /** Fin du mot situee apres le curseur, quand on edite par le milieu. */
        fun finApres(texteApres: String): Int =
            texteApres.takeWhile(::estCaractereMot).length

        /**
         * Champ dont rien ne doit etre retenu : mot de passe, visible ou masque, texte ou
         * numerique, et champ que l'application declare non memorisable.
         */
        fun estSensible(inputType: Int, imeOptions: Int): Boolean {
            val classe = inputType and EditorInfo.TYPE_MASK_CLASS
            val variation = inputType and EditorInfo.TYPE_MASK_VARIATION
            val motDePasse =
                (classe == EditorInfo.TYPE_CLASS_TEXT && (
                    variation == EditorInfo.TYPE_TEXT_VARIATION_PASSWORD ||
                    variation == EditorInfo.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD ||
                    variation == EditorInfo.TYPE_TEXT_VARIATION_WEB_PASSWORD)) ||
                (classe == EditorInfo.TYPE_CLASS_NUMBER &&
                    variation == EditorInfo.TYPE_NUMBER_VARIATION_PASSWORD)
            val sansApprentissage =
                (imeOptions and EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING) != 0
            return motDePasse || sansApprentissage
        }
    }

    private lateinit var clavier: KeyboardLayoutManager
    private lateinit var accents: AccentHandler

    private var barre: LinearLayout? = null
    private var boutonOutils: ImageView? = null

    /** Les outils ouverts depuis la gauche de la barre. */
    private val outils = Outils(this)

    /** Le dernier texte dicté, tant qu'une puce propose de le relire. */
    private var dicteeARelire: String? = null

    /** La raison d'état de la correction en tête de barre, pour sa fiche. */
    private var raisonDeTete: String? = null

    /**
     * La dernière conversion d'« écrire comme on parle », qu'un effacement
     * immédiat défait. [curseur] : où le curseur s'est posé juste après elle.
     */
    private class Conversion(val lettre: String, val tape: String) { var curseur = -1 }
    private var derniereConversion: Conversion? = null

    /** Dictee : capture et modele, tous deux ouverts a la demande. */
    private val ecouteur by lazy { Ecouteur(this) }
    @Volatile private var transcripteur: Transcripteur? = null
    private var dicteeEnCours: Job? = null
    private var paletteDeLaVue: KeyboardTheme.Palette? = null

    /**
     * Portee sur le fil principal, calcul deporte par withContext : tout ce qui
     * touche une vue est sur le bon fil par construction.
     */
    override val portee = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var travailEnCours: Job? = null

    /** Champ sensible : on ne propose rien et on n'enregistre rien. */
    override var champSensible = false
        private set

    // L'etat du clavier vit ici, et le gestionnaire en recoit une copie.
    private var numerique = false
    private var emoji = false
    private var majuscule = false
    private var verrouMaj = false

    /** Rappel qui rafraichit le message de preparation tant qu'il est affiche. */
    private var attenteEnCours: Runnable? = null

    /** Un glissement sur la barre d'espace est en cours : on ne recalcule pas. */
    private var glissement = false
    private val poigneeSync = Handler(Looper.getMainLooper())
    private var syncEnAttente: Runnable? = null

    // ===== CYCLE DE VIE =====

    override fun onCreate() {
        super.onCreate()
        journaliserSysteme()

        accents = AccentHandler(this).apply { setAccentSelectionListener(this@ClavierKabyle) }
        clavier = KeyboardLayoutManager(this).apply {
            accentHandler = accents
            setInteractionListener(this@ClavierKabyle)
        }
        // Le jeu d'emojis n'est pas charge ici : EmojiPickerView le fait a sa construction et
        // alimente lui-meme AccentHandler en tons de peau.

        // Le chargement des 30 Mio de ressources ne doit pas bloquer l'affichage :
        // le clavier s'ouvre tout de suite, les propositions arrivent apres.
        portee.launch {
            // Si le moteur ne charge pas, on tape sans propositions. Le clavier
            // ne doit jamais disparaitre sous les doigts.
            withContext(Dispatchers.IO) { Moteur.obtenir(this@ClavierKabyle) }
            proposer()
        }
    }

    /**
     * Le tas alloue a un IME decide de tout : le moteur tient 57 Mio de donnees vives, ce qui
     * approche la classe memoire ordinaire d'un appareil d'entree de gamme.
     */
    private fun journaliserSysteme() {
        runCatching {
            val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val info = ActivityManager.MemoryInfo()
            am.getMemoryInfo(info)
            Log.i(TAG, "appareil ${android.os.Build.MODEL} Android ${android.os.Build.VERSION.SDK_INT}")
            Log.i(TAG, "tas ordinaire ${am.memoryClass} Mio, tas large ${am.largeMemoryClass} Mio, " +
                "RAM libre ${info.availMem / 1048576} Mio, faible RAM ${am.isLowRamDevice}")
        }
    }

    override fun onCreateInputView(): View {
        // Les drapeaux d'ici suivent ceux du gestionnaire, sans quoi ils divergent.
        numerique = false; emoji = false; majuscule = false; verrouMaj = false
        clavier.forceAlphabeticMode()
        KeyFeedback.refresh(this)
        KeyboardTheme.refresh(this)
        paletteDeLaVue = KeyboardTheme.palette()

        val racine = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(KeyboardTheme.palette().fondClavier)
        }
        racine.addView(construireBarre())
        // Le panneau des outils, entre la barre et les touches.
        val panneau = FrameLayout(this).apply {
            visibility = View.GONE
            setBackgroundColor(KeyboardTheme.palette().fondClavier)
        }
        racine.addView(panneau, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0))
        // Conteneur distinct de la racine : c'est lui qui portera le decalage
        // du bas, et la barre de propositions ne doit pas le subir.
        val conteneur = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        clavier.setAvailableRowsHeight(hauteurDisponible())
        conteneur.addView(clavier.createKeyboardLayout())
        racine.addView(conteneur)
        val rangee = barre
        val bouton = boutonOutils
        if (rangee != null && bouton != null) outils.attacher(rangee, bouton, panneau, conteneur)
        racine.post { ajusterALaBarreDeNavigation(racine, conteneur) }
        return racine
    }

    /** La barre de propositions. */
    private fun construireBarre(): View {
        val hauteurPx = dpToPx(if (estPaysage()) BARRE_HAUTEUR_PAYSAGE_DP else BARRE_HAUTEUR_DP)
        val rangee = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            // Filets verticaux entre deux propositions. Le message d'attente,
            // seul enfant de la rangée quand il s'affiche, n'en reçoit aucun.
            showDividers = LinearLayout.SHOW_DIVIDER_MIDDLE
            dividerDrawable = GradientDrawable().apply {
                setColor(KeyboardTheme.palette().separateur)
                setSize(dpToPx(1), 0)
            }
            dividerPadding = dpToPx(10)
        }
        barre = rangee
        val defilement = HorizontalScrollView(this).apply {
            isHorizontalScrollBarEnabled = false
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, 1f)
            setPadding(dpToPx(4), dpToPx(RANGEE_PAD_EXT_DP), dpToPx(8), dpToPx(2))
            addView(rangee, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.MATCH_PARENT))
        }
        // Le bouton des outils : un chevron quand la barre propose, une croix quand les outils sont
        // ouverts.
        val bouton = ImageView(this).apply {
            setImageResource(R.drawable.ic_outils)
            setColorFilter(KeyboardTheme.palette().encre)
            scaleType = ImageView.ScaleType.CENTER_INSIDE
            contentDescription = getString(R.string.outils_ouvrir)
            background = Outils.fondAppui(Color.TRANSPARENT, dpToPx(18).toFloat())
            isSoundEffectsEnabled = false
            setOnClickListener { v -> KeyFeedback.onKeyPress(v); outils.basculer() }
            layoutParams = LinearLayout.LayoutParams(
                dpToPx(OUTILS_LARGEUR_DP), LinearLayout.LayoutParams.MATCH_PARENT)
        }
        boutonOutils = bouton
        val ligne = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(bouton)
            addView(defilement)
        }
        val bande = KeyboardTheme.palette().bandeIdentite
        val bandePx = hauteurBande()
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                // Encastrement lateral seulement : la hauteur consommee doit
                // rester celle que le budget vertical prevoit.
                marginStart = dpToPx(BARRE_MARGE_DP)
                marginEnd = dpToPx(BARRE_MARGE_DP)
            }
            background = KeyboardTheme.cuvetteSuggestions(this@ClavierKabyle)
            // La bande prend sa hauteur sur celle de la barre, et non en plus :
            // le budget vertical des touches reste le même dans tous les thèmes.
            if (!bande.isNullOrEmpty() && bandePx > 0) {
                addView(bandeIdentite(bande), LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, bandePx))
            }
            addView(ligne, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, hauteurPx - bandePx))
        }
    }

    /** Les couleurs de la bande d'identité, en parts égales. */
    private fun bandeIdentite(couleurs: List<Int>): View = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        for (c in couleurs) {
            addView(View(this@ClavierKabyle).apply { setBackgroundColor(c) },
                LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, 1f))
        }
    }

    private fun hauteurBande(): Int =
        if (KeyboardTheme.palette().bandeIdentite.isNullOrEmpty()) 0 else dpToPx(BANDE_DP)

    /**
     * Decale le bas du clavier de ce que la barre de navigation lui masque reellement, mesure une
     * fois la mise en page faite.
     */
    private fun ajusterALaBarreDeNavigation(racine: View, conteneur: View) {
        runCatching {
            val insets = window?.window?.decorView?.rootWindowInsets ?: return
            val barrePx = if (android.os.Build.VERSION.SDK_INT >= 30) {
                insets.getInsets(android.view.WindowInsets.Type.navigationBars()).bottom
            } else {
                @Suppress("DEPRECATION")
                insets.systemWindowInsetBottom
            }
            val hauteurEcranPx = if (android.os.Build.VERSION.SDK_INT >= 30) {
                (getSystemService(Context.WINDOW_SERVICE) as android.view.WindowManager)
                    .maximumWindowMetrics.bounds.height()
            } else {
                resources.displayMetrics.heightPixels
            }
            val position = IntArray(2)
            racine.getLocationOnScreen(position)
            val basDuClavier = position[1] + racine.height
            val recouvrement = basDuClavier - (hauteurEcranPx - barrePx)
            val marge = if (recouvrement > 0) recouvrement else 0
            if (conteneur.paddingBottom != marge) conteneur.setPadding(0, 0, 0, marge)
            Log.d(TAG, "barre de navigation ${barrePx}px, recouvrement ${recouvrement}px")
        }
    }

    /** Ce qui reste aux rangees de touches une fois la barre payee. */
    private fun hauteurDisponible(): Int {
        val idBarreEtat = resources.getIdentifier("status_bar_height", "dimen", "android")
        val barreEtatPx = if (idBarreEtat > 0) resources.getDimensionPixelSize(idBarreEtat)
                          else dpToPx(24)
        val fenetrePx = dpToPx(resources.configuration.screenHeightDp) - barreEtatPx
        val barrePx = dpToPx(if (estPaysage()) BARRE_HAUTEUR_PAYSAGE_DP else BARRE_HAUTEUR_DP)
        val padPx = dpToPx(KeyboardLayoutManager.verticalPaddingDp(this)) * 2
        val dispo = fenetrePx - barrePx - padPx - dpToPx(4)
        Log.d(TAG, "fenetre ${fenetrePx}px, barre ${barrePx}px, padding ${padPx}px -> ${dispo}px")
        return dispo
    }

    /**
     * Le mode plein ecran remplace le champ de l'application par un champ extrait gere par le
     * clavier.
     */
    override fun onEvaluateFullscreenMode() = false
    override fun onEvaluateInputViewShown() = true
    override fun isExtractViewShown() = false

    /** Attention au cycle de vie : le systeme appelle onStartInput AVANT onCreateInputView. */
    override fun onStartInput(info: EditorInfo?, restarting: Boolean) {
        super.onStartInput(info, restarting)
        champSensible = estSensible(info)
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        KeyFeedback.refresh(this)
        KeyboardTheme.refresh(this)
        // Meme raison que pour les propositions : un mot de passe ne doit pas laisser d'emoji
        // derriere lui.
        EmojiRecents.setEnregistrementAutorise(!champSensible)
        // La vue est gardee en cache par InputMethodService.
        if (paletteDeLaVue !== KeyboardTheme.palette()) setInputView(onCreateInputView())
        // Un nouveau champ repart des lettres, en minuscules.
        if (!restarting) {
            numerique = false; emoji = false; majuscule = false; verrouMaj = false
            clavier.forceAlphabeticMode()
            clavier.updateKeyboardDisplay()
            clavier.applyMode()
        }
        proposer()
    }

    override fun onFinishInput() {
        super.onFinishInput()
        travailEnCours?.cancel()
        // Un glissement encore marque a l'arrivee dans le champ suivant y ferait sauter les
        // premieres propositions, le temps que la resynchronisation differee retombe.
        syncEnAttente?.let { poigneeSync.removeCallbacks(it) }
        syncEnAttente = null
        glissement = false
        arreterAttente()
        accents.dismissAccentPopup()
        // Un outil ouvert dans un champ ne suit pas l'utilisateur dans le suivant.
        outils.fermer(rendre = false)
        dicteeARelire = null
        derniereConversion = null
        afficher(emptyList())
    }

    /**
     * Seul endroit ou l'on apprend que le texte a bouge sans passer par nos touches : tap dans le
     * texte, selection, correction faite par l'application elle-meme.
     */
    override fun onUpdateSelection(
        oldSelStart: Int, oldSelEnd: Int,
        newSelStart: Int, newSelEnd: Int,
        candidatesStart: Int, candidatesEnd: Int
    ) {
        super.onUpdateSelection(
            oldSelStart, oldSelEnd, newSelStart, newSelEnd, candidatesStart, candidatesEnd)
        // Une conversion ne se défait que si le curseur n'a pas bougé depuis :
        // le premier signal après elle donne sa place, tout écart l'oublie.
        derniereConversion?.let { c ->
            if (c.curseur < 0) c.curseur = newSelEnd
            else if (newSelStart != c.curseur || newSelEnd != c.curseur) derniereConversion = null
        }
        // Pendant un glissement, chaque caractere franchi passe par ici. On
        // laisse filer et on ne recalcule qu'une fois le doigt arrete.
        if (glissement) { planifierSync(); return }
        proposer()
    }

    override fun onDestroy() {
        travailEnCours?.cancel()
        dicteeEnCours?.cancel()
        ecouteur.arreter()
        transcripteur?.close()
        syncEnAttente?.let { poigneeSync.removeCallbacks(it) }
        arreterAttente()
        portee.cancel()
        accents.cleanup()
        clavier.cleanup()
        // Le moteur n'est pas ferme ici : il est partage avec le correcteur
        // systeme, qui peut travailler alors que le clavier est parti.
        outils.detacher()
        barre = null
        boutonOutils = null
        super.onDestroy()
    }

    // ===== TOUCHES =====

    override fun onKeyPress(key: String) {
        val texte = if (majuscule || verrouMaj) key.uppercase() else key
        // Les outils d'abord : pendant la recherche française, les lettres vont
        // à la requête et non au champ.
        if (outils.intercepter(key, texte)) {
            if (majuscule && !verrouMaj && key.length == 1 && key[0].isLetter()) {
                majuscule = false; appliquerEtats()
            }
            return
        }
        if (key != "⌫") derniereConversion = null
        if (key != "⇧" && key != "123" && key != "ABC") dicteeARelire = null
        when (key) {
            "⌫" -> effacer()
            "⏎" -> entree()
            " " -> valider(" ")
            "⇧" -> basculerMaj()
            "123", "ABC" -> basculerNumerique()
            "EMOJI" -> basculerEmoji()
            "MICRO" -> basculerDictee()
            else -> ecrire(texte)
        }
    }

    /** Trois etats en cycle : minuscule, majuscule ponctuelle, verrouillage. */
    private fun basculerMaj() {
        when {
            !majuscule && !verrouMaj -> { majuscule = true; verrouMaj = false }
            majuscule && !verrouMaj -> { majuscule = true; verrouMaj = true }
            else -> { majuscule = false; verrouMaj = false }
        }
        appliquerEtats()
    }

    /** Depuis le panneau emoji, « ABC » ramene aux lettres et non aux chiffres. */
    private fun basculerNumerique() {
        if (emoji) { emoji = false; numerique = false } else numerique = !numerique
        appliquerEtats()
    }

    private fun basculerEmoji() {
        emoji = true
        numerique = false
        appliquerEtats()
    }

    // ===== DICTEE =====

    /** Un appui lance l'ecoute, le suivant l'arrete. */
    private fun basculerDictee() {
        if (ecouteur.actif) { ecouteur.arreter(); return }
        if (!ecouteur.permissionAccordee()) {
            afficherMessage(getString(R.string.micro_reglages))
            ecouteur.demanderPermission()
            return
        }
        dicteeEnCours?.cancel()
        dicteeEnCours = portee.launch {
            travailEnCours?.cancel()
            afficherMessage(getString(R.string.micro_ecoute))
            val echantillons = withContext(Dispatchers.IO) { ecouteur.enregistrer() }
            if (echantillons == null) { afficherMessage(getString(R.string.micro_rien)); return@launch }

            afficherMessage(getString(R.string.micro_transcription))
            val t0 = System.currentTimeMillis()
            val texte = withContext(Dispatchers.Default) {
                val t = transcripteur ?: Transcripteur.ouvrir(this@ClavierKabyle)
                    ?.also { transcripteur = it }
                t?.let { runCatching { it.transcrire(echantillons) }.getOrNull() }
            }
            Log.i(TAG, "dictee : %.1f s d'audio, %d ms, « %s »".format(
                echantillons.size.toFloat() / Transcripteur.TAUX,
                System.currentTimeMillis() - t0, texte ?: ""))

            if (texte.isNullOrBlank()) { afficherMessage(getString(R.string.micro_rien)); return@launch }
            ecrireDictee(texte)
            proposer()
        }
    }

    /** Insere le texte dicte, en le separant de ce qui precede. */
    private fun ecrireDictee(texte: String) {
        val ic = currentInputConnection ?: return
        val avant = ic.getTextBeforeCursor(1, 0)?.toString() ?: ""
        val separateur = if (avant.isEmpty() || avant.last().isWhitespace()) "" else " "
        // Avant l'écriture : les propositions qu'elle déclenche montrent déjà la
        // puce « Relire la dictée ».
        dicteeARelire = texte
        ic.commitText("$separateur$texte", 1)
    }

    /** Un mot dans la barre, qui n'est pas une proposition et ne se touche pas. */
    private fun afficherMessage(texte: String) {
        val rangee = barre ?: return
        if (outils.mode != Outils.Mode.PROPOSITIONS) return
        rangee.removeAllViews()
        rangee.addView(TextView(this).apply {
            this.text = texte
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setTextColor(KeyboardTheme.palette().encreEtiquette)
            includeFontPadding = false
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dpToPx(14), 0, dpToPx(14), 0)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.MATCH_PARENT)
        })
    }

    /** Pose l'etat sur le clavier, puis le fait se redessiner. */
    private fun appliquerEtats() {
        val changeDePanneau = clavier.isNumericMode() != numerique || clavier.isEmojiMode() != emoji
        clavier.updateKeyboardStates(numerique, emoji, majuscule, verrouMaj)
        accents.isCapitalMode = majuscule || verrouMaj
        clavier.updateKeyboardDisplay()
        if (changeDePanneau) clavier.applyMode()
    }

    override fun onLongPress(key: String, button: View) {
        when (key) {
            "⌫" -> effacerMot()
            " " -> (getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager)
                ?.showInputMethodPicker()
            // showAccentPopup directement, et non startLongPressTimer.
            else -> if (accents.hasAccents(key)) accents.showAccentPopup(key, button)
        }
    }

    override fun onKeyRelease() { accents.cancelLongPress() }

    /** Glissement du doigt sur la barre d'espace : le curseur suit. */
    override fun onSpaceCursorMove(steps: Int) {
        if (steps == 0) return
        glissement = true
        val touche = if (steps > 0) KeyEvent.KEYCODE_DPAD_RIGHT else KeyEvent.KEYCODE_DPAD_LEFT
        repeat(kotlin.math.abs(steps)) { sendDownUpKeyEvents(touche) }
    }

    /** Le doigt se leve : une seule resynchronisation, sur la position d'arrivee. */
    override fun onSpaceCursorEnd() { planifierSync() }

    private fun planifierSync() {
        syncEnAttente?.let { poigneeSync.removeCallbacks(it) }
        val r = Runnable { glissement = false; proposer() }
        syncEnAttente = r
        poigneeSync.postDelayed(r, DELAI_SYNC_MS)
    }

    override fun onAccentSelected(accent: String, baseCharacter: String) {
        if (accent.all { it.isLetter() }) {
            val texte = if (majuscule || verrouMaj) accent.uppercase() else accent
            if (outils.intercepter(accent, texte)) return
            derniereConversion = null
            dicteeARelire = null
            ecrire(texte)
        } else {
            // Un ton de peau choisi par appui long est un emoji utilise : il a
            // sa place dans les recents, au meme titre qu'un emoji de la grille.
            currentInputConnection?.commitText(accent, 1)
            EmojiRecents.enregistrer(this, accent)
            travailEnCours?.cancel()
            afficher(emptyList())
        }
    }

    override fun onLongPressStarted(baseKey: String) {}
    override fun onLongPressCancelled() {}

    // ===== SAISIE =====

    /** Le mot en cours est relu dans l'editeur, jamais tenu dans un tampon. */
    override fun motCourant(): String {
        val ic = currentInputConnection ?: return ""
        val avant = ic.getTextBeforeCursor(REGARD, 0)?.toString() ?: return ""
        val selection = ic.getSelectedText(0)?.isNotEmpty() == true
        return motAvant(avant, selection)
    }

    private fun ecrire(texte: String) {
        val ic = currentInputConnection
        if (!ecrireCommeOnParle(ic, texte)) ic?.commitText(texte, 1)
        // La majuscule ponctuelle retombe apres la lettre qu'elle a servie ;
        // le verrouillage, lui, tient jusqu'au prochain appui sur ⇧.
        if (majuscule && !verrouMaj) { majuscule = false; appliquerEtats() }
        proposer()
    }

    private fun effacer() {
        val ic = currentInputConnection ?: return
        if (defaireConversion(ic)) { proposer(); return }
        if (ic.getSelectedText(0)?.isNotEmpty() == true) { ic.commitText("", 1); proposer(); return }
        val avant = ic.getTextBeforeCursor(4, 0)?.toString() ?: ""
        ic.deleteSurroundingText(longueurRetourArriere(avant), 0)
        proposer()
    }

    /** Appui long sur le retour arriere : le mot entier part. */
    private fun effacerMot() {
        val ic = currentInputConnection ?: return
        val avant = ic.getTextBeforeCursor(REGARD, 0)?.toString() ?: return
        if (avant.isEmpty()) return
        // Les espaces qui traînent d'abord, puis le mot qu'ils suivaient : un
        // appui long après « azul  » doit emporter « azul », pas les blancs seuls.
        val sansBlancs = avant.trimEnd()
        val mot = sansBlancs.takeLastWhile(::estCaractereMot)
        val n = (avant.length - sansBlancs.length) + if (mot.isEmpty()) 1 else mot.length
        ic.deleteSurroundingText(n, 0)
        proposer()
    }

    /** La touche Entree fait ce que le champ attend d'elle. */
    private fun entree() {
        val ic = currentInputConnection ?: return
        val info = currentInputEditorInfo
        val options = info?.imeOptions ?: 0
        val action = options and EditorInfo.IME_MASK_ACTION
        val refuseLAction = (options and EditorInfo.IME_FLAG_NO_ENTER_ACTION) != 0
        val multiligne = ((info?.inputType ?: 0) and
            android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE) != 0

        travailEnCours?.cancel()
        afficher(emptyList())

        if (refuseLAction || (multiligne && action == EditorInfo.IME_ACTION_UNSPECIFIED)) {
            ic.commitText("\n", 1)
            return
        }
        when (action) {
            EditorInfo.IME_ACTION_SEND,
            EditorInfo.IME_ACTION_SEARCH,
            EditorInfo.IME_ACTION_GO,
            EditorInfo.IME_ACTION_NEXT,
            EditorInfo.IME_ACTION_PREVIOUS,
            EditorInfo.IME_ACTION_DONE -> ic.performEditorAction(action)
            else -> ic.commitText("\n", 1)
        }
    }

    private fun valider(separateur: String) {
        currentInputConnection?.commitText(separateur, 1)
        travailEnCours?.cancel()
        afficher(emptyList())
    }

    /** Remplace le mot en cours par la forme choisie. */
    private fun appliquerChoix(forme: String) {
        val ic = currentInputConnection ?: return
        val mot = motCourant()
        // Rien a noter quand il n'y avait pas de mot : accepter une prediction n'est pas corriger
        // une graphie, et cela n'a pas sa place dans les contributions.
        val apres = ic.getTextAfterCursor(REGARD, 0)?.toString() ?: ""
        val fin = finApres(apres)
        if (mot.isNotEmpty()) ic.deleteSurroundingText(mot.length, fin)
        // L'espace n'est ajoute que s'il en manque un.
        val suite = apres.drop(fin)
        val espace = if (suite.isEmpty() || !suite[0].isWhitespace()) " " else ""
        ic.commitText("$forme$espace", 1)
        if (mot.isNotEmpty()) Journal.noter(this, mot, forme, champSensible)
        travailEnCours?.cancel()
        // Choisi depuis une fiche : elle a servi.
        outils.fermerPanneau()
        dicteeARelire = null
        afficher(emptyList())
    }

    /**
     * Un champ de mot de passe, ou marque sans apprentissage personnalise, ne
     * doit ni recevoir de propositions ni alimenter le journal.
     */
    private fun estSensible(info: EditorInfo?): Boolean =
        if (info == null) true else estSensible(info.inputType, info.imeOptions)

    // ===== PROPOSITIONS =====

    private fun proposer() {
        travailEnCours?.cancel()
        val mot = motCourant()
        if (champSensible) { afficher(emptyList()); return }
        // Tant que le moteur n'est pas la, la barre dit ou il en est.
        if (!Moteur.dejaPret()) { annoncerPreparation(); return }
        arreterAttente()
        val gauche = contexteGauche(mot)
        // Aucun mot en cours : ce n'est plus au correcteur de parler.
        if (mot.length < LONGUEUR_MIN) { predire(gauche); return }
        travailEnCours = portee.launch {
            // La frappe suivante annule celle-ci : rien n'est calcule pour un
            // prefixe que l'utilisateur a deja quitte.
            delay(ATTENTE_MS)
            val t0 = System.currentTimeMillis()
            val resultat = withContext(Dispatchers.Default) {
                Moteur.avec(this@ClavierKabyle) { m ->
                    // Position 1 : la correction en contexte, qui voit la phrase.
                    val six = Propositions.calculer(m, gauche, mot)
                    val formes = (listOf(six.absolue) + six.cinq)
                        .map { casserComme(mot, it) }
                        .distinct()
                        .filter { it.isNotBlank() }
                    // La raison d'état ne vaut que pour la correction en contexte.
                    formes to six.raison?.takeIf { six.absolue.isNotBlank() }
                }
            }
            val liste = resultat?.first ?: emptyList()
            raisonDeTete = resultat?.second
            Log.i(TAG, "« $mot » -> $liste en ${System.currentTimeMillis() - t0} ms")
            afficher(liste)
        }
    }

    /** Le mot suivant, quand il n'y a plus de mot en cours. */
    private fun predire(gauche: String) {
        raisonDeTete = null
        if (gauche.isBlank()) { afficher(emptyList()); return }
        travailEnCours = portee.launch {
            delay(ATTENTE_MS)
            val t0 = System.currentTimeMillis()
            val liste = withContext(Dispatchers.Default) {
                Moteur.avec(this@ClavierKabyle) { c ->
                    val lm = c.modeleLangue ?: return@avec emptyList()
                    Prediction(lm, c.res.frequents).suivants(gauche, MAX_PROPOSITIONS)
                } ?: emptyList()
            }
            Log.i(TAG, "prediction apres « $gauche » : $liste " +
                "en ${System.currentTimeMillis() - t0} ms")
            afficher(liste, prediction = true)
        }
    }

    /** Affiche l'etat de la preparation, et se rappelle jusqu'a ce qu'elle aboutisse. */
    private fun annoncerPreparation() {
        val rangee = barre ?: return
        // Les outils tiennent la barre : fermés, ils la rendent par proposer().
        if (outils.mode != Outils.Mode.PROPOSITIONS) return
        val texte = when (Moteur.etat) {
            Moteur.Etat.DEPOT ->
                getString(R.string.attente_depot, Moteur.avancement)
            Moteur.Etat.CONSTRUCTION -> getString(R.string.attente_moteur)
            Moteur.Etat.ECHEC -> getString(R.string.attente_echec)
            else -> getString(R.string.attente_moteur)
        }
        rangee.removeAllViews()
        rangee.addView(TextView(this).apply {
            this.text = texte
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setTextColor(KeyboardTheme.palette().encreEtiquette)
            includeFontPadding = false
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dpToPx(14), 0, dpToPx(14), 0)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.MATCH_PARENT)
        })
        if (Moteur.etat == Moteur.Etat.ECHEC) { arreterAttente(); return }
        arreterAttente()
        val r = Runnable { attenteEnCours = null; proposer() }
        attenteEnCours = r
        poigneeSync.postDelayed(r, ATTENTE_ANNONCE_MS)
    }

    private fun arreterAttente() {
        attenteEnCours?.let { poigneeSync.removeCallbacks(it) }
        attenteEnCours = null
    }

    private fun contexteGauche(mot: String): String {
        val ic = currentInputConnection ?: return ""
        val avant = ic.getTextBeforeCursor(80, 0)?.toString() ?: return ""
        return avant.dropLast(mot.length).trim().takeLast(60)
    }

    private fun afficher(formes: List<String>, prediction: Boolean = false) {
        val rangee = barre ?: return
        // La rangée appartient aux outils tant qu'ils sont ouverts.
        if (outils.mode != Outils.Mode.PROPOSITIONS) return
        rangee.removeAllViews()
        rangee.showDividers = LinearLayout.SHOW_DIVIDER_MIDDLE
        dicteeARelire?.let { dicte ->
            rangee.addView(outils.puceDeBarre(getString(R.string.relire_dictee), R.drawable.ic_relire) {
                dicteeARelire = null
                (rangee.getChildAt(0) as? View)?.let { rangee.removeView(it) }
                outils.relire(dicte)
            })
        }
        formes.take(MAX_PROPOSITIONS).forEachIndexed { rang, forme ->
            rangee.addView(pastille(forme, rang, prediction))
        }
    }

    /** Une proposition. */
    private fun pastille(forme: String, rang: Int, prediction: Boolean): TextView = TextView(this).apply {
        text = forme
        setTextSize(TypedValue.COMPLEX_UNIT_SP, TEXTE_SP)
        includeFontPadding = false
        val p = KeyboardTheme.palette()
        setTextColor(p.encre)
        setTypeface(typeface, if (!prediction && rang == 0) Typeface.BOLD else Typeface.NORMAL)
        background = traitDeNature(when {
            prediction -> p.traitPrediction
            rang == 0 -> p.traitContexte
            else -> p.traitCandidat
        }, when {
            prediction -> TraitDeNature.Motif.POINTS
            rang == 0 -> TraitDeNature.Motif.PLEIN
            else -> TraitDeNature.Motif.TIRETS
        })
        setPadding(dpToPx(14), dpToPx(PUCE_PAD_V_DP), dpToPx(14), dpToPx(PUCE_PAD_V_DP))
        ajusterAuxBornes(this)
        // Le son de frappe est joue par KeyFeedback : sans cette ligne,
        // performClick ajouterait son clic d'interface et la puce sonnerait deux fois.
        isSoundEffectsEnabled = false
        minWidth = dpToPx(PUCE_LARGEUR_MIN_DP)
        minimumWidth = dpToPx(PUCE_LARGEUR_MIN_DP)
        gravity = Gravity.CENTER
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.MATCH_PARENT
        ).apply {
            // La moitie de l'intervalle de chaque cote : deux puces voisines
            // portent chacune la sienne, et leur somme fait l'ecart voulu.
            val demi = dpToPx(PUCE_ECART_DP) / 2
            setMargins(demi, 0, demi, 0)
        }
        setOnClickListener { puce ->
            // Au clic et non au toucher.
            KeyFeedback.onKeyPress(puce)
            appliquerChoix(forme)
        }
        // Asegzawal : la fiche de la forme avant de la choisir, et pour la
        // correction en contexte, la raison d'un changement d'état.
        val raison = if (!prediction && rang == 0) raisonDeTete else null
        setOnLongClickListener { puce ->
            KeyFeedback.onKeyPress(puce)
            outils.ouvrirFiche(forme, raison, proposerLaForme = true) { choisie -> appliquerChoix(choisie) }
            true
        }
    }

    /** Le trait de nature d'une proposition. */
    private fun traitDeNature(couleur: Int, motif: TraitDeNature.Motif): Drawable {
        // Traits lisibles sans la couleur : le motif redit ce que dit la couleur.
        if (KeyboardPreferences.traitsFormes(this)) {
            return TraitDeNature(couleur, motif, dpToPx(KeyboardTheme.TRAIT_NATURE_DP),
                dpToPx(TRAIT_RETRAIT_DP), dpToPx(TRAIT_HAUT_DP))
        }
        val trait = GradientDrawable().apply {
            setColor(couleur)
            cornerRadius = dpToPx(1).toFloat()
        }
        return LayerDrawable(arrayOf(trait)).apply {
            setLayerGravity(0, Gravity.BOTTOM or Gravity.FILL_HORIZONTAL)
            setLayerHeight(0, dpToPx(KeyboardTheme.TRAIT_NATURE_DP))
            setLayerInset(0, dpToPx(TRAIT_RETRAIT_DP), 0,
                             dpToPx(TRAIT_RETRAIT_DP), dpToPx(TRAIT_HAUT_DP))
        }
    }

    /** Le mot ne doit pas depasser la hauteur que la barre lui laisse. */
    private fun ajusterAuxBornes(vue: TextView) {
        val hauteurPx = dpToPx(if (estPaysage()) BARRE_HAUTEUR_PAYSAGE_DP else BARRE_HAUTEUR_DP) -
            dpToPx(RANGEE_PAD_EXT_DP) - dpToPx(2) - hauteurBande()
        val dispo = hauteurPx - 2 * dpToPx(PUCE_PAD_V_DP)
        val m = vue.paint.fontMetricsInt
        val ligne = m.descent - m.ascent
        if (ligne > dispo && dispo > 0)
            vue.setTextSize(TypedValue.COMPLEX_UNIT_PX, vue.textSize * dispo / ligne)
    }

    // ===== ETATS DU CLAVIER =====

    override fun estPaysage() = KeyboardLayoutManager.isLandscape(this)

    private fun dpToPx(dp: Int): Int = (dp * resources.displayMetrics.density).toInt()

    // ===== ECRIRE COMME ON PARLE =====

    /**
     * Si la lettre tapée forme une paire avec la précédente, les deux deviennent une lettre kabyle
     * (EcritureParlee).
     */
    private fun ecrireCommeOnParle(ic: InputConnection?, texte: String): Boolean {
        derniereConversion = null
        if (ic == null || texte.length != 1 || champSensible) return false
        if (!KeyboardPreferences.ecrireCommeOnParle(this)) return false
        if (!EcritureParlee.accepte(currentInputEditorInfo?.inputType ?: 0)) return false
        if (ic.getSelectedText(0)?.isNotEmpty() == true) return false
        val avant = ic.getTextBeforeCursor(1, 0)?.toString()
        if (avant == null || avant.length != 1) return false
        val lettre = EcritureParlee.convertir(avant[0], texte) ?: return false
        ic.beginBatchEdit()
        ic.deleteSurroundingText(1, 0)
        ic.commitText(lettre, 1)
        ic.endBatchEdit()
        derniereConversion = Conversion(lettre, avant + texte)
        return true
    }

    /** Effacer juste après une conversion rend les deux lettres tapées. */
    private fun defaireConversion(ic: InputConnection): Boolean {
        val c = derniereConversion ?: return false
        derniereConversion = null
        if (ic.getSelectedText(0)?.isNotEmpty() == true) return false
        if (ic.getTextBeforeCursor(c.lettre.length, 0)?.toString() != c.lettre) return false
        ic.beginBatchEdit()
        ic.deleteSurroundingText(c.lettre.length, 0)
        ic.commitText(c.tape, 1)
        ic.endBatchEdit()
        return true
    }

    // ===== OUTILS =====

    override val contexte: Context get() = this

    override val connexion: InputConnection? get() = currentInputConnection

    override fun dp(valeur: Int): Int = dpToPx(valeur)

    override fun remplacerMotCourant(forme: String) {
        appliquerChoix(forme)
    }

    /** Un mot trouvé par un outil, au curseur, séparé de ce qui précède et suivi d'un espace. */
    override fun insererMot(forme: String) {
        val ic = currentInputConnection ?: return
        val avant = ic.getTextBeforeCursor(1, 0)?.toString() ?: ""
        val separateur = if (avant.isEmpty() || avant.last().isWhitespace()) "" else " "
        dicteeARelire = null
        ic.commitText("$separateur$forme ", 1)
    }

    override fun noterChoix(avant: String, apres: String) {
        Journal.noter(this, avant, apres, champSensible)
    }

    override fun reconstruireVue() {
        setInputView(onCreateInputView())
    }

    override fun rendreLaBarre() {
        proposer()
    }

    /** La touche retour ferme d'abord un panneau ou les outils, avant de replier le clavier. */
    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && isInputViewShown && outils.retour()) return true
        return super.onKeyDown(keyCode, event)
    }
}
