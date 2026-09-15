package taqbaylit.clavier

import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.StateListDrawable
import android.text.TextUtils
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.inputmethod.ExtractedTextRequest
import android.view.inputmethod.InputConnection
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import taqbaylit.moteur.MotDuJour
import taqbaylit.moteur.Normalisation
import taqbaylit.moteur.RechercheFrancais
import java.util.TimeZone

/** Les outils du clavier, ouverts depuis la gauche de la barre de suggestions. */
class Outils(private val hote: Hote) {

    /** Ce que le service prête aux outils. */
    interface Hote {
        val contexte: Context
        val connexion: InputConnection?
        val champSensible: Boolean
        val portee: CoroutineScope
        fun motCourant(): String
        fun dp(valeur: Int): Int
        fun estPaysage(): Boolean
        /** Remplace le mot en cours, comme le toucher d'une proposition. */
        fun remplacerMotCourant(forme: String)
        /** Insère un mot au curseur, séparé de ce qui précède. */
        fun insererMot(forme: String)
        /** Note un choix au journal, sous ses consentements. */
        fun noterChoix(avant: String, apres: String)
        /** Refait la vue du clavier, après un changement de thème. */
        fun reconstruireVue()
        /** Rend la barre aux propositions du mot en cours. */
        fun rendreLaBarre()
    }

    /** À qui appartient la barre. */
    enum class Mode { PROPOSITIONS, OUTILS, RECHERCHE }

    private enum class Panneau { AUCUN, RESULTATS, FICHE, RELIRE, MOT_DU_JOUR, THEME }

    /** Un mot signalé par la relecture. */
    private class Signal(var debut: Int, val mot: String, val propositions: List<String>, val faute: Boolean)

    private class Infos(
        val forme: String,
        val glose: String,
        val frequence: Int,
        val categorie: String?,
        val verbe: Boolean,
        val etats: FicheMot.Etats?
    )

    companion object {
        private const val PANNEAU_HAUTEUR_DP = 220
        private const val RESULTATS_HAUTEUR_DP = 144
        private const val RESULTATS_HAUTEUR_PAYSAGE_DP = 96
        private const val RESULTAT_LIGNE_DP = 36
        private const val RESULTAT_FORME_DP = 120
        private const val RESULTATS_MAX = 8
        private const val ATTENTE_RECHERCHE_MS = 150L
        private const val PROPOSITIONS_RELIRE = 4
        private const val PUCE_HAUTEUR_DP = 32
        private const val ICONE_DP = 18

        /** Ces touches ne changent que le clavier affiché : elles gardent leur rôle partout. */
        private val TOUCHES_DE_MODE = setOf("⇧", "123", "ABC")

        fun libelleTheme(mode: KeyboardTheme.Mode): Int = when (mode) {
            KeyboardTheme.Mode.SYSTEME -> R.string.aspect_systeme
            KeyboardTheme.Mode.CLAIR -> R.string.aspect_clair
            KeyboardTheme.Mode.SOMBRE -> R.string.aspect_sombre
            KeyboardTheme.Mode.CONTRASTE -> R.string.aspect_contraste
            KeyboardTheme.Mode.TAMAZGHA -> R.string.aspect_tamazgha
        }

        /** Le nom d'une catégorie du lexique (lexcat.noms), ou null si elle est inconnue. */
        fun libelleCategorie(categorie: String): Int? = when (categorie) {
            "adj_fem" -> R.string.cat_adj_fem
            "adj_masc" -> R.string.cat_adj_masc
            "adverb" -> R.string.cat_adverb
            "ambig" -> R.string.cat_ambig
            "conj" -> R.string.cat_conj
            "fem" -> R.string.cat_fem
            "fem_pl" -> R.string.cat_fem_pl
            "interj" -> R.string.cat_interj
            "locution" -> R.string.cat_locution
            "masc" -> R.string.cat_masc
            "num" -> R.string.cat_num
            "particle" -> R.string.cat_particle
            "prep" -> R.string.cat_prep
            "presentat" -> R.string.cat_presentat
            "pron" -> R.string.cat_pron
            "propn" -> R.string.cat_propn
            else -> null
        }

        /** Un fond qui montre l'appui : [couleur] au repos, le voile du thème sous le doigt. */
        fun fondAppui(couleur: Int, rayon: Float): Drawable = StateListDrawable().apply {
            addState(intArrayOf(android.R.attr.state_pressed), GradientDrawable().apply {
                setColor(KeyboardTheme.palette().enfoncee)
                cornerRadius = rayon
            })
            addState(intArrayOf(), GradientDrawable().apply {
                setColor(couleur)
                cornerRadius = rayon
            })
        }
    }

    /** Tant que la barre n'est pas aux propositions, le service n'y écrit rien. */
    var mode = Mode.PROPOSITIONS
        private set

    private var panneauOuvert = Panneau.AUCUN

    private var rangee: LinearLayout? = null
    private var bouton: ImageView? = null
    private var panneau: FrameLayout? = null
    private var touches: View? = null

    /** Hauteur des touches à la dernière mesure : celle d'un panneau qui les remplace. */
    private var hauteurTouches = 0

    private var travail: Job? = null
    private var rouvrirTheme = false

    private val requete = StringBuilder()
    private var resultats: List<RechercheFrancais.Trouve> = emptyList()
    private var messageRecherche: Int? = R.string.recherche_invite

    /** Corrections faites pendant la relecture : position au moment de la correction, écart de longueur. */
    private val corrections = ArrayList<Pair<Int, Int>>()

    private val ctx: Context get() = hote.contexte
    private fun dp(v: Int) = hote.dp(v)
    private fun chaine(id: Int, vararg args: Any): String = ctx.getString(id, *args)

    // ===== BRANCHEMENT =====

    /** Appelé à chaque construction de la vue du clavier. */
    fun attacher(rangee: LinearLayout, bouton: ImageView, panneau: FrameLayout, touches: View) {
        travail?.cancel()
        this.rangee = rangee
        this.bouton = bouton
        this.panneau = panneau
        this.touches = touches
        requete.clear()
        mode = Mode.PROPOSITIONS
        panneauOuvert = Panneau.AUCUN
        majBouton()
        if (rouvrirTheme) {
            // Un changement de thème vient de refaire la vue : le panneau se rouvre, pour qu'on
            // puisse en essayer un autre.
            rouvrirTheme = false
            ouvrirOutils()
            touches.post { if (mode == Mode.OUTILS) ouvrirTheme() }
        }
    }

    fun detacher() {
        travail?.cancel()
        rangee = null; bouton = null; panneau = null; touches = null
    }

    /** Le bouton à gauche de la barre. */
    fun basculer() {
        if (mode == Mode.PROPOSITIONS) ouvrirOutils() else fermer()
    }

    /** Tout refermer. [rendre] : redonner aussitôt la barre aux propositions. */
    fun fermer(rendre: Boolean = true) {
        val etait = mode
        requete.clear()
        fermerPanneau()
        mode = Mode.PROPOSITIONS
        majBouton()
        if (rendre && etait != Mode.PROPOSITIONS) hote.rendreLaBarre()
    }

    /** La touche retour du téléphone : un panneau d'abord, les outils ensuite. */
    fun retour(): Boolean {
        if (panneauOuvert != Panneau.AUCUN && panneauOuvert != Panneau.RESULTATS) {
            revenirDuPanneau(); return true
        }
        if (mode != Mode.PROPOSITIONS) { fermer(); return true }
        return false
    }

    /** Une touche du clavier, avant le service. */
    fun intercepter(touche: String, texte: String): Boolean {
        if (touche in TOUCHES_DE_MODE) return false
        return when (mode) {
            Mode.PROPOSITIONS -> false
            Mode.OUTILS -> { fermer(); false }
            Mode.RECHERCHE -> {
                when (touche) {
                    "⌫" -> {
                        if (requete.isNotEmpty()) requete.setLength(requete.length - 1)
                        chercher()
                    }
                    "⏎" -> fermer()
                    " " -> {
                        if (requete.isNotEmpty() && requete.last() != ' ') requete.append(' ')
                        afficherRecherche()
                    }
                    "EMOJI", "MICRO" -> { fermer(); return false }
                    else -> { requete.append(texte); chercher() }
                }
                true
            }
        }
    }

    fun fermerPanneau() {
        travail?.cancel()
        panneau?.apply { removeAllViews(); visibility = View.GONE }
        touches?.visibility = View.VISIBLE
        panneauOuvert = Panneau.AUCUN
    }

    private fun revenirDuPanneau() {
        fermerPanneau()
        if (mode == Mode.RECHERCHE) afficherRecherche()
    }

    private fun ouvrirOutils() {
        requete.clear()
        fermerPanneau()
        mode = Mode.OUTILS
        majBouton()
        afficherOutils()
    }

    private fun majBouton() {
        val b = bouton ?: return
        val ouverts = mode != Mode.PROPOSITIONS
        b.setImageResource(if (ouverts) R.drawable.ic_fermer else R.drawable.ic_outils)
        b.contentDescription = chaine(if (ouverts) R.string.outils_fermer else R.string.outils_ouvrir)
    }

    // ===== RANGÉE D'OUTILS =====

    private fun afficherOutils() {
        val r = rangee ?: return
        r.removeAllViews()
        r.showDividers = LinearLayout.SHOW_DIVIDER_NONE
        r.addView(puceDeBarre(chaine(R.string.outil_asegzawal), R.drawable.ic_dictionnaire) { ficheDuMotCourant() })
        r.addView(puceDeBarre(chaine(R.string.outil_recherche), R.drawable.ic_traduire) { ouvrirRecherche() })
        r.addView(puceDeBarre(chaine(R.string.outil_relire), R.drawable.ic_relire) { relire(null) })
        val parler = KeyboardPreferences.ecrireCommeOnParle(ctx)
        r.addView(puceDeBarre(coche(parler, chaine(R.string.outil_parler)), null) {
            KeyboardPreferences.setEcrireCommeOnParle(ctx, !parler)
            afficherOutils()
        }.apply {
            // L'état se lit à la coche et à la graisse, et TalkBack le dit.
            contentDescription = chaine(if (parler) R.string.parler_actif else R.string.parler_inactif)
            if (parler) setTypeface(typeface, Typeface.BOLD)
        })
        r.addView(puceDeBarre(chaine(R.string.outil_mot_du_jour), R.drawable.ic_mot_du_jour) { motDuJour() })
        r.addView(puceDeBarre(chaine(R.string.outil_theme), R.drawable.ic_theme) { ouvrirTheme() })
    }

    private fun coche(actif: Boolean, libelle: String) = if (actif) "✓ $libelle" else libelle

    /** Une puce à la hauteur de la barre de suggestions. */
    fun puceDeBarre(libelle: CharSequence, icone: Int?, action: () -> Unit): TextView =
        puce(libelle, icone, action).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, dp(PUCE_HAUTEUR_DP)
            ).apply { setMargins(dp(4), 0, dp(4), 0) }
        }

    private fun puceDeColonne(libelle: CharSequence, action: (() -> Unit)?): TextView =
        puce(libelle, null, action).apply {
            if (action == null) setTypeface(typeface, Typeface.BOLD)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, dp(PUCE_HAUTEUR_DP + 4)
            ).apply { topMargin = dp(8) }
        }

    /**
     * Une puce sur la surface des touches de fonction, à leur encre : en
     * contraste élevé, du noir sur du jaune.
     */
    private fun puce(libelle: CharSequence, icone: Int?, action: (() -> Unit)?): TextView =
        TextView(ctx).apply {
            val p = KeyboardTheme.palette()
            text = libelle
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setTextColor(p.encreFonction)
            includeFontPadding = false
            gravity = Gravity.CENTER_VERTICAL
            maxLines = 1
            if (icone != null) ctx.getDrawable(icone)?.mutate()?.let { d ->
                d.setTint(p.encreFonction)
                d.setBounds(0, 0, dp(ICONE_DP), dp(ICONE_DP))
                setCompoundDrawablesRelative(d, null, null, null)
                compoundDrawablePadding = dp(6)
            }
            setPadding(dp(12), dp(6), dp(12), dp(6))
            background = fondAppui(p.toucheFonction.haut, dp(PUCE_HAUTEUR_DP / 2).toFloat())
            // Le son de frappe est joué par KeyFeedback, comme sur les propositions.
            isSoundEffectsEnabled = false
            if (action != null) setOnClickListener { v -> KeyFeedback.onKeyPress(v); action() }
        }

    // ===== PANNEAUX =====

    /** Montre [contenu] à la place des touches, à leur hauteur. */
    private fun ouvrirPanneau(type: Panneau, titre: String, contenu: View) {
        val cadre = panneau ?: return
        val clavier = touches ?: return
        if (clavier.visibility == View.VISIBLE && clavier.height > 0) hauteurTouches = clavier.height
        val hauteur = if (hauteurTouches > 0) hauteurTouches else dp(PANNEAU_HAUTEUR_DP)
        travail?.cancel()
        cadre.removeAllViews()
        cadre.layoutParams = cadre.layoutParams.apply { height = hauteur }
        // Le décalage de la barre de navigation, que portaient les touches.
        cadre.setPadding(0, 0, 0, clavier.paddingBottom)
        cadre.addView(LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            addView(entete(titre))
            addView(ScrollView(ctx).apply { addView(contenu) },
                LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        }, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        clavier.visibility = View.GONE
        cadre.visibility = View.VISIBLE
        panneauOuvert = type
    }

    /** Montre [contenu] au-dessus des touches, qui restent visibles. */
    private fun ouvrirBandeau(contenu: View) {
        val cadre = panneau ?: return
        cadre.removeAllViews()
        cadre.layoutParams = cadre.layoutParams.apply {
            height = dp(if (hote.estPaysage()) RESULTATS_HAUTEUR_PAYSAGE_DP else RESULTATS_HAUTEUR_DP)
        }
        cadre.setPadding(0, 0, 0, 0)
        cadre.addView(ScrollView(ctx).apply { addView(contenu) }, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        touches?.visibility = View.VISIBLE
        cadre.visibility = View.VISIBLE
        panneauOuvert = Panneau.RESULTATS
    }

    private fun entete(titre: String): View = LinearLayout(ctx).apply {
        val p = KeyboardTheme.palette()
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(16), dp(2), dp(4), 0)
        addView(TextView(ctx).apply {
            text = titre
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setTextColor(p.encreEtiquette)
            letterSpacing = 0.04f
        }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        addView(ImageView(ctx).apply {
            setImageResource(R.drawable.ic_fermer)
            setColorFilter(p.encre)
            scaleType = ImageView.ScaleType.CENTER_INSIDE
            contentDescription = chaine(R.string.panneau_fermer)
            background = fondAppui(Color.TRANSPARENT, dp(20).toFloat())
            isSoundEffectsEnabled = false
            setOnClickListener { v -> KeyFeedback.onKeyPress(v); revenirDuPanneau() }
        }, LinearLayout.LayoutParams(dp(44), dp(40)))
    }

    private fun colonne(): LinearLayout = LinearLayout(ctx).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(16), dp(4), dp(16), dp(12))
    }

    private fun ligneTexte(
        contenu: CharSequence,
        tailleSp: Float = 15f,
        attenuee: Boolean = false,
        gras: Boolean = false
    ): TextView = TextView(ctx).apply {
        val p = KeyboardTheme.palette()
        text = contenu
        setTextSize(TypedValue.COMPLEX_UNIT_SP, tailleSp)
        setTextColor(if (attenuee) p.encreEtiquette else p.encre)
        if (gras) setTypeface(typeface, Typeface.BOLD)
        setPadding(0, dp(3), 0, dp(3))
    }

    // ===== ASEGZAWAL =====

    private fun ficheDuMotCourant() {
        val mot = hote.motCourant()
        if (mot.isBlank()) {
            ouvrirPanneau(Panneau.FICHE, chaine(R.string.outil_asegzawal), colonne().apply {
                addView(ligneTexte(chaine(R.string.fiche_sans_mot), attenuee = true))
            })
            return
        }
        // Le mot est déjà écrit : la fiche ne le propose pas, ses états le remplacent.
        ouvrirFiche(mot, raison = null, proposerLaForme = false) { forme -> hote.remplacerMotCourant(forme) }
    }

    /** La fiche de mot. */
    fun ouvrirFiche(mot: String, raison: String?, proposerLaForme: Boolean, utiliser: (String) -> Unit) {
        val colonne = colonne()
        colonne.addView(ligneTexte(mot, tailleSp = 24f, gras = true))
        ouvrirPanneau(Panneau.FICHE, chaine(R.string.outil_asegzawal), colonne)
        if (!Moteur.dejaPret()) {
            colonne.addView(ligneTexte(chaine(R.string.moteur_pas_pret), attenuee = true))
            return
        }
        travail = hote.portee.launch {
            val infos = withContext(Dispatchers.Default) {
                Moteur.avec(ctx) { c ->
                    val forme = Normalisation.normalize(mot)
                    // « aɣrum-a » : la glose et la catégorie sont celles du nom.
                    val base = forme.substringBefore('-')
                    val categorie = c.res.lexcat(forme) ?: c.res.lexcat(base)
                    val verbe = forme in c.res.amyagSet() || base in c.res.amyagSet()
                    Infos(
                        forme = forme,
                        glose = c.res.glose(forme).ifBlank { c.res.glose(base) },
                        frequence = c.res.freq(forme),
                        categorie = categorie,
                        verbe = verbe,
                        etats = FicheMot.etats(c.postprocess, forme, verbe, categorie)
                    )
                }
            } ?: return@launch
            remplirFiche(colonne, mot, infos, raison, proposerLaForme, utiliser)
        }
    }

    private fun remplirFiche(
        colonne: LinearLayout,
        mot: String,
        infos: Infos,
        raison: String?,
        proposerLaForme: Boolean,
        utiliser: (String) -> Unit
    ) {
        colonne.addView(ligneTexte(
            infos.glose.ifBlank { chaine(R.string.fiche_sans_glose) },
            attenuee = infos.glose.isBlank()))
        val nature = when {
            infos.categorie != null ->
                libelleCategorie(infos.categorie)?.let { chaine(it) } ?: infos.categorie
            infos.verbe -> chaine(R.string.fiche_verbe)
            else -> null
        }
        val frequence = if (infos.frequence > 0) chaine(R.string.fiche_frequence, infos.frequence)
                        else chaine(R.string.fiche_absent)
        colonne.addView(ligneTexte(listOfNotNull(nature, frequence).joinToString(" · "),
            tailleSp = 13f, attenuee = true))
        if (raison != null) colonne.addView(ligneTexte(chaine(R.string.fiche_pourquoi, raison), tailleSp = 13f))
        infos.etats?.let { e ->
            for ((libelle, forme) in listOf(
                R.string.fiche_etat_libre to e.libre, R.string.fiche_etat_annexion to e.annexion)) {
                val actuelle = forme == infos.forme
                val ecrite = ClavierKabyle.casserComme(mot, forme)
                val action: (() -> Unit)? =
                    if (actuelle) null else ({ utiliser(ecrite); fermerPanneau() })
                colonne.addView(puceDeColonne(coche(actuelle, chaine(libelle, ecrite)), action))
            }
        }
        if (proposerLaForme) {
            colonne.addView(puceDeColonne(chaine(R.string.fiche_choisir, mot), action = {
                utiliser(mot); fermerPanneau()
            }))
        }
    }

    // ===== FRANÇAIS → KABYLE =====

    private fun ouvrirRecherche() {
        fermerPanneau()
        requete.clear()
        resultats = emptyList()
        messageRecherche = R.string.recherche_invite
        mode = Mode.RECHERCHE
        majBouton()
        afficherRecherche()
    }

    private fun chercher() {
        travail?.cancel()
        val q = requete.toString()
        if (RechercheFrancais.plier(q).length < RechercheFrancais.REQUETE_MIN) {
            resultats = emptyList()
            messageRecherche = R.string.recherche_invite
            afficherRecherche()
            return
        }
        if (!Moteur.dejaPret()) {
            messageRecherche = R.string.moteur_pas_pret
            afficherRecherche()
            return
        }
        // La requête s'affiche tout de suite, les résultats suivent.
        afficherRecherche()
        travail = hote.portee.launch {
            // La frappe suivante annule celle-ci, comme pour les propositions.
            delay(ATTENTE_RECHERCHE_MS)
            val trouves = withContext(Dispatchers.Default) {
                Moteur.avec(ctx) { c -> c.res.chercherFrancais(q, RESULTATS_MAX) }
            } ?: emptyList()
            resultats = trouves
            messageRecherche = if (trouves.isEmpty()) R.string.recherche_aucun else null
            afficherRecherche()
        }
    }

    private fun afficherRecherche() {
        if (mode != Mode.RECHERCHE) return
        val r = rangee ?: return
        val p = KeyboardTheme.palette()
        r.removeAllViews()
        r.showDividers = LinearLayout.SHOW_DIVIDER_NONE
        r.addView(TextView(ctx).apply {
            text = chaine(R.string.recherche_requete, "$requete|")
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            setTextColor(p.encre)
            includeFontPadding = false
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), 0, dp(12), 0)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.MATCH_PARENT)
        })
        // Une fiche ouverte depuis un résultat reste par-dessus.
        if (panneauOuvert != Panneau.AUCUN && panneauOuvert != Panneau.RESULTATS) return
        val liste = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL }
        val message = messageRecherche
        if (message != null) {
            liste.addView(ligneTexte(chaine(message), attenuee = true).apply {
                setPadding(dp(16), dp(8), dp(16), dp(8))
            })
        } else {
            resultats.forEach { liste.addView(ligneResultat(it)) }
        }
        ouvrirBandeau(liste)
    }

    private fun ligneResultat(t: RechercheFrancais.Trouve): View = LinearLayout(ctx).apply {
        val p = KeyboardTheme.palette()
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(16), 0, dp(16), 0)
        background = fondAppui(p.fondClavier, 0f)
        isSoundEffectsEnabled = false
        contentDescription = "${t.forme}, ${t.glose}"
        addView(TextView(ctx).apply {
            text = t.forme
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
            setTextColor(p.encre)
            setTypeface(typeface, Typeface.BOLD)
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
        }, LinearLayout.LayoutParams(dp(RESULTAT_FORME_DP), LinearLayout.LayoutParams.WRAP_CONTENT))
        addView(TextView(ctx).apply {
            text = FicheMot.gloseCourte(t.glose)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setTextColor(p.encreEtiquette)
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
        }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(RESULTAT_LIGNE_DP))
        setOnClickListener { v ->
            KeyFeedback.onKeyPress(v)
            hote.insererMot(t.forme)
            fermer()
        }
        setOnLongClickListener { v ->
            KeyFeedback.onKeyPress(v)
            ouvrirFiche(t.forme, raison = null, proposerLaForme = true) { forme ->
                hote.insererMot(forme)
                fermer()
            }
            true
        }
    }

    // ===== RELIRE =====

    private fun demandeDeTexte() = ExtractedTextRequest().apply {
        hintMaxChars = Relecture.CARACTERES_MAX
    }

    private fun positionActuelle(position: Int): Int {
        var p = position
        for ((ou, ecart) in corrections) if (ou < p) p += ecart
        return p
    }

    /**
     * Relit le texte du champ, ou seulement le texte [dicte] s'il est encore
     * juste avant le curseur.
     */
    fun relire(dicte: String?) {
        val colonne = colonne()
        val etat = ligneTexte("", tailleSp = 13f, attenuee = true)
        colonne.addView(etat)
        ouvrirPanneau(Panneau.RELIRE, chaine(R.string.relire_titre), colonne)
        if (hote.champSensible) { etat.text = chaine(R.string.relire_sensible); return }
        val extrait = hote.connexion?.getExtractedText(demandeDeTexte(), 0)
        val texte = extrait?.text?.toString()
        if (extrait == null || texte == null) { etat.text = chaine(R.string.relire_illisible); return }
        val plage = if (dicte != null && extrait.selectionStart >= 0)
            Relecture.plageDictee(texte, extrait.selectionStart, dicte) else null
        val choix = Relecture.aRelire(texte, plage)
        if (choix.mots.isEmpty()) { etat.text = chaine(R.string.relire_rien); return }
        if (!Moteur.dejaPret()) { etat.text = chaine(R.string.moteur_pas_pret); return }

        val origine = extrait.startOffset
        val signaux = ArrayList<Signal>()
        corrections.clear()
        travail = hote.portee.launch {
            for ((k, trouve) in choix.mots.withIndex()) {
                val (debut, mot) = trouve
                etat.text = chaine(R.string.relire_en_cours, k + 1, choix.mots.size)
                val gauche = texte.substring(0, debut).trim().takeLast(CorrecteurSysteme.CONTEXTE_MAX)
                // Un mot à la fois sous le verrou du moteur : la barre peut passer entre deux.
                val jugement = withContext(Dispatchers.Default) {
                    Moteur.avec(ctx) { c ->
                        CorrecteurSysteme.jugerMot(c, gauche, mot, PROPOSITIONS_RELIRE)
                    }
                } ?: continue
                if (jugement.soulignement == CorrecteurSysteme.Soulignement.AUCUN ||
                    jugement.propositions.isEmpty()) continue
                val s = Signal(positionActuelle(origine + debut), mot, jugement.propositions,
                    jugement.soulignement == CorrecteurSysteme.Soulignement.FAUTE)
                signaux.add(s)
                colonne.addView(ligneSignal(s, signaux, colonne, etat))
            }
            val bilan = if (signaux.isEmpty()) chaine(R.string.relire_rien)
                        else chaine(R.string.relire_fini, choix.mots.size)
            etat.text = if (choix.tronque) "$bilan ${chaine(R.string.relire_limite, Relecture.MOTS_MAX)}"
                        else bilan
        }
    }

    private fun ligneSignal(
        s: Signal,
        signaux: MutableList<Signal>,
        colonne: LinearLayout,
        etat: TextView
    ): View {
        val p = KeyboardTheme.palette()
        val defile = HorizontalScrollView(ctx).apply { isHorizontalScrollBarEnabled = false }
        val ligne = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(6), 0, dp(2))
        }
        ligne.addView(TextView(ctx).apply {
            text = s.mot
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            setTextColor(p.encre)
            setTypeface(typeface, Typeface.BOLD)
        })
        // La nature du signal en toutes lettres, et non par une couleur.
        ligne.addView(TextView(ctx).apply {
            text = chaine(if (s.faute) R.string.relire_faute else R.string.relire_doute)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
            setTextColor(p.encreEtiquette)
            setPadding(dp(8), 0, dp(4), 0)
        })
        for (proposition in s.propositions) {
            ligne.addView(puceDeBarre(proposition, null) {
                remplacer(s, proposition, signaux, defile, colonne, etat)
            })
        }
        defile.addView(ligne)
        return defile
    }

    /** Remplace un mot signalé dans le champ, puis remet le curseur où il était. */
    private fun remplacer(
        s: Signal,
        par: String,
        signaux: MutableList<Signal>,
        vue: View,
        colonne: LinearLayout,
        etat: TextView
    ) {
        val ic = hote.connexion ?: return
        val extrait = ic.getExtractedText(demandeDeTexte(), 0)
        val texte = extrait?.text?.toString()
        val relatif = if (extrait == null) -1 else s.debut - extrait.startOffset
        val fin = relatif + s.mot.length
        val intact = texte != null && relatif >= 0 && fin <= texte.length &&
            texte.regionMatches(relatif, s.mot, 0, s.mot.length) &&
            (relatif == 0 || !ClavierKabyle.estCaractereMot(texte[relatif - 1])) &&
            (fin == texte.length || !ClavierKabyle.estCaractereMot(texte[fin]))
        if (extrait == null || !intact) { etat.text = chaine(R.string.relire_modifie); return }

        val curseur = if (extrait.selectionStart >= 0 && extrait.selectionStart == extrait.selectionEnd)
            extrait.startOffset + extrait.selectionStart else -1
        ic.beginBatchEdit()
        ic.setSelection(s.debut, s.debut + s.mot.length)
        ic.commitText(par, 1)
        if (curseur >= 0) {
            val c = Relecture.curseurApres(curseur, s.debut, s.mot.length, par.length)
            ic.setSelection(c, c)
        }
        ic.endBatchEdit()
        hote.noterChoix(s.mot, par)

        val ecart = par.length - s.mot.length
        corrections.add(s.debut to ecart)
        signaux.remove(s)
        for (autre in signaux) if (autre.debut > s.debut) autre.debut += ecart
        colonne.removeView(vue)
    }

    // ===== MOT DU JOUR =====

    private fun motDuJour() {
        val colonne = colonne()
        ouvrirPanneau(Panneau.MOT_DU_JOUR, chaine(R.string.mot_du_jour_titre), colonne)
        if (!Moteur.dejaPret()) {
            colonne.addView(ligneTexte(chaine(R.string.moteur_pas_pret), attenuee = true))
            return
        }
        travail = hote.portee.launch {
            val maintenant = System.currentTimeMillis()
            val jour = MotDuJour.jourLocal(maintenant, TimeZone.getDefault().getOffset(maintenant))
            val choix = withContext(Dispatchers.Default) {
                Moteur.avec(ctx) { c ->
                    MotDuJour.choisir(c.res.motsDuJour, jour)?.let { it to c.res.glose(it) }
                }
            }
            if (choix == null) {
                colonne.addView(ligneTexte(chaine(R.string.mot_du_jour_aucun), attenuee = true))
                return@launch
            }
            val (mot, glose) = choix
            colonne.addView(ligneTexte(mot, tailleSp = 26f, gras = true))
            colonne.addView(ligneTexte(glose))
            colonne.addView(puceDeColonne(chaine(R.string.mot_du_jour_inserer), action = {
                hote.insererMot(mot)
                fermer()
            }))
        }
    }

    // ===== THÈME =====

    private fun ouvrirTheme() {
        val colonne = colonne()
        val courant = KeyboardPreferences.themeMode(ctx)
        for (m in KeyboardTheme.Mode.entries) {
            val action: (() -> Unit)? = if (m == courant) null else ({
                KeyboardPreferences.setThemeMode(ctx, m)
                rouvrirTheme = true
                hote.reconstruireVue()
            })
            colonne.addView(puceDeColonne(coche(m == courant, chaine(libelleTheme(m))), action))
        }
        val formes = KeyboardPreferences.traitsFormes(ctx)
        colonne.addView(puceDeColonne(coche(formes, chaine(R.string.theme_traits_formes)), action = {
            KeyboardPreferences.setTraitsFormes(ctx, !formes)
            ouvrirTheme()
        }))
        colonne.addView(ligneTexte(chaine(R.string.theme_traits_detail), tailleSp = 13f, attenuee = true))
        ouvrirPanneau(Panneau.THEME, chaine(R.string.theme_titre), colonne)
    }
}
