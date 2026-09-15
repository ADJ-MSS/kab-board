package taqbaylit.clavier

import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.drawable.Drawable
import android.util.Log

/** Palette du clavier, en clair et en sombre. */
object KeyboardTheme {

    private const val TAG = "KeyboardTheme"

    /** Ce que l'utilisateur choisit dans l'écran de réglages. */
    enum class Mode(val cle: String, val libelle: String) {
        SYSTEME("systeme", "Comme le téléphone"),
        CLAIR("clair", "Toujours clair"),
        SOMBRE("sombre", "Toujours sombre"),
        CONTRASTE("contraste", "Contraste élevé"),
        TAMAZGHA("tamazgha", "Tamazɣa");

        companion object {
            /** Tolérante : une clé inconnue (préférence d'une version future,
             *  fichier recopié à la main) retombe sur le défaut plutôt que de jeter. */
            fun depuisCle(cle: String?): Mode =
                entries.firstOrNull { it.cle == cle } ?: SYSTEME
        }
    }

    /** Un fond de touche, du haut vers le bas. */
    data class Degrade(val haut: Int, val bas: Int) {
        /** Sous la forme qu'attend `GradientDrawable.setColors`. */
        fun couleurs(): IntArray = intArrayOf(haut, bas)
    }

    /** Un fond d'une seule couleur : le cas de tous. */
    private fun plat(hex: String): Degrade =
        Color.parseColor(hex).let { Degrade(it, it) }

    /** Les couleurs dont les quatre surfaces ont besoin, résolues. */
    data class Palette(
        /**
         * Fond d'une touche de lettre. C'est la couleur du fond du clavier : une lettre ne dessine
         * aucune surface, comme sur Gboard bordures éteintes.
         */
        val touche: Degrade,
        /**
         * Fond des touches qui ne sont pas des lettres et qu'on vise sans les lire : 123, ABC,
         * emoji, micro, entrée, barre d'espace.
         */
        val toucheFonction: Degrade,
        /** Fond du shift en majuscule ponctuelle. */
        val toucheMaj: Degrade,
        /** Fond du shift verrouillé en capitales, un cran plus marqué encore. */
        val toucheCaps: Degrade,
        /** Voile d'appui, commun à toutes les touches. */
        val enfoncee: Int,
        /** Encre d'un glyphe de touche, et d'un mot de la barre de suggestions. */
        val encre: Int,
        /** Encre atténuée : libellé de l'espace, libellés secondaires. */
        val encreAttenuee: Int,
        /** Message d'attente de la barre de suggestions. */
        val encreEtiquette: Int,
        /** Fond derrière les touches, et derrière le panneau emoji. */
        val fondClavier: Int,
        /** Fond de la barre de suggestions. */
        val fondSuggestions: Int,
        /** Filet de séparation : sous la barre de suggestions, et entre deux propositions. */
        val separateur: Int,
        /**
         * Trait de nature sous une suggestion : correction vue en contexte, candidat du mot isolé,
         * prédiction du mot suivant.
         */
        val traitContexte: Int,
        val traitCandidat: Int,
        val traitPrediction: Int,
        /** Popup d'appui long : fond et contour. */
        val popupFond: Int,
        val popupBordure: Int,
        /** Bouton d'accent de la popup : fond, contour, encre. */
        val popupAccentFond: Int,
        val popupAccentBordure: Int,
        val popupAccentEncre: Int,
        /** Bouton du caractère de base, volontairement en retrait. */
        val popupBaseFond: Int,
        val popupBaseBordure: Int,
        val popupBaseEncre: Int,
        /** Fond de l'onglet actif du panneau emoji. */
        val emojiOngletActif: Int,
        /**
         * Encre d'un glyphe posé sur une surface de fonction : 123, entrée, emoji, micro, et le
         * shift actif.
         */
        val encreFonction: Int = encre,
        /** Encre du libellé de la barre d'espace. */
        val encreEspace: Int = encreAttenuee,
        /** Contour d'une touche de lettre ; transparent quand elle n'en a pas. */
        val contourTouche: Int = Color.TRANSPARENT,
        /** Libellé de la barre d'espace. */
        val libelleEspace: String = LIBELLE_LANGUE,
        /** Bande d'identité sous la barre de suggestions, de gauche à droite ; null : aucune. */
        val bandeIdentite: List<Int>? = null
    )

    /** Le nom de la langue, libellé de l'espace par défaut. */
    const val LIBELLE_LANGUE = "Taqbaylit"

    // Thème clair
    private val CLAIR = Palette(
        touche = plat("#EEF0F2"),
        toucheFonction = plat("#DADCE0"),
        toucheMaj = plat("#CDD0D4"),
        toucheCaps = plat("#BFC3C7"),
        enfoncee = Color.parseColor("#BCC0C5"),
        encre = Color.parseColor("#1F1F1F"),
        encreAttenuee = Color.parseColor("#555A5F"),
        encreEtiquette = Color.parseColor("#555A5F"),
        fondClavier = Color.parseColor("#EEF0F2"),
        fondSuggestions = Color.parseColor("#EEF0F2"),
        separateur = Color.parseColor("#D0D3D7"),
        // Sur fond pâle ce sont les valeurs sombres qui se voient. L'ocre est
        // assombri, voir l'en-tête.
        traitContexte = Color.parseColor("#00843F"),
        traitCandidat = Color.parseColor("#0072BB"),
        traitPrediction = Color.parseColor("#A86A00"),
        popupFond = Color.parseColor("#FFFFFF"),
        popupBordure = Color.parseColor("#DADCE0"),
        popupAccentFond = Color.parseColor("#F1F3F4"),
        popupAccentBordure = Color.parseColor("#DADCE0"),
        popupAccentEncre = Color.parseColor("#1F1F1F"),
        popupBaseFond = Color.parseColor("#E8EAED"),
        popupBaseBordure = Color.parseColor("#DADCE0"),
        popupBaseEncre = Color.parseColor("#555A5F"),
        emojiOngletActif = Color.parseColor("#DADCE0")
    )

    // Thème sombre
    private val SOMBRE = Palette(
        touche = plat("#1A1A1A"),
        toucheFonction = plat("#303030"),
        toucheMaj = plat("#3C3C3C"),
        toucheCaps = plat("#4A4A4A"),
        enfoncee = Color.parseColor("#424242"),
        encre = Color.parseColor("#E8EAED"),
        encreAttenuee = Color.parseColor("#9AA0A6"),
        encreEtiquette = Color.parseColor("#9AA0A6"),
        fondClavier = Color.parseColor("#1A1A1A"),
        fondSuggestions = Color.parseColor("#1A1A1A"),
        separateur = Color.parseColor("#3C4043"),
        // Plus vives qu'en clair : sur un fond presque noir, ce sont elles qui
        // passent le seuil avec de la marge. Le vert redevient celui du drapeau.
        traitContexte = Color.parseColor("#00A550"),
        traitCandidat = Color.parseColor("#4DA3FF"),
        traitPrediction = Color.parseColor("#E8A33D"),
        popupFond = Color.parseColor("#303030"),
        popupBordure = Color.parseColor("#3C4043"),
        popupAccentFond = Color.parseColor("#424242"),
        popupAccentBordure = Color.parseColor("#4A4A4A"),
        popupAccentEncre = Color.parseColor("#E8EAED"),
        popupBaseFond = Color.parseColor("#262626"),
        popupBaseBordure = Color.parseColor("#3C4043"),
        popupBaseEncre = Color.parseColor("#9AA0A6"),
        emojiOngletActif = Color.parseColor("#303030")
    )

    // Contraste élevé
    private val CONTRASTE = Palette(
        touche = plat("#000000"),
        toucheFonction = plat("#FFD400"),
        toucheMaj = plat("#FFD400"),
        toucheCaps = plat("#FFE866"),
        enfoncee = Color.parseColor("#767676"),
        encre = Color.parseColor("#FFFFFF"),
        encreAttenuee = Color.parseColor("#E0E0E0"),
        encreEtiquette = Color.parseColor("#E0E0E0"),
        fondClavier = Color.parseColor("#000000"),
        fondSuggestions = Color.parseColor("#000000"),
        separateur = Color.parseColor("#BDBDBD"),
        traitContexte = Color.parseColor("#3DDC84"),
        traitCandidat = Color.parseColor("#7CC4FF"),
        traitPrediction = Color.parseColor("#FFB547"),
        popupFond = Color.parseColor("#000000"),
        popupBordure = Color.parseColor("#FFFFFF"),
        popupAccentFond = Color.parseColor("#000000"),
        popupAccentBordure = Color.parseColor("#FFFFFF"),
        popupAccentEncre = Color.parseColor("#FFFFFF"),
        popupBaseFond = Color.parseColor("#1A1A1A"),
        popupBaseBordure = Color.parseColor("#BDBDBD"),
        popupBaseEncre = Color.parseColor("#E0E0E0"),
        emojiOngletActif = Color.parseColor("#767676"),
        encreFonction = Color.parseColor("#000000"),
        // L'espace est une touche de fonction : son libellé est sur le jaune.
        encreEspace = Color.parseColor("#000000"),
        contourTouche = Color.parseColor("#FFFFFF")
    )

    // Tamazɣa
    private val TAMAZGHA = Palette(
        touche = plat("#16191D"),
        toucheFonction = plat("#26303A"),
        toucheMaj = plat("#2F3A45"),
        toucheCaps = plat("#3A4754"),
        enfoncee = Color.parseColor("#45535F"),
        encre = Color.parseColor("#EEF2F5"),
        encreAttenuee = Color.parseColor("#A9B4BE"),
        encreEtiquette = Color.parseColor("#A9B4BE"),
        fondClavier = Color.parseColor("#16191D"),
        fondSuggestions = Color.parseColor("#16191D"),
        separateur = Color.parseColor("#34404B"),
        traitContexte = Color.parseColor("#2FBF71"),
        traitCandidat = Color.parseColor("#4DA3FF"),
        traitPrediction = Color.parseColor("#F2C94C"),
        popupFond = Color.parseColor("#26303A"),
        popupBordure = Color.parseColor("#34404B"),
        popupAccentFond = Color.parseColor("#2F3A45"),
        popupAccentBordure = Color.parseColor("#3A4754"),
        popupAccentEncre = Color.parseColor("#EEF2F5"),
        popupBaseFond = Color.parseColor("#1E242A"),
        popupBaseBordure = Color.parseColor("#34404B"),
        popupBaseEncre = Color.parseColor("#A9B4BE"),
        emojiOngletActif = Color.parseColor("#2F3A45"),
        encreEspace = Color.parseColor("#FF7A70"),
        libelleEspace = "ⵣ",
        bandeIdentite = listOf(
            Color.parseColor("#1E88E5"),
            Color.parseColor("#2FBF71"),
            Color.parseColor("#F2C94C")
        )
    )

    // Résolue une fois par prise de focus plutôt qu'à chaque touche.
    @Volatile
    private var courante: Palette = CLAIR

    /** La palette en vigueur. Sûre à appeler depuis le dessin d'une touche. */
    fun palette(): Palette = courante

    /** Épaisseur du filet qui sépare la barre de suggestions des touches. */
    private const val LISERE_DP = 1

    /** Épaisseur du trait de nature sous une proposition. */
    const val TRAIT_NATURE_DP = 2

    /** Le fond de la barre de suggestions. */
    fun cuvetteSuggestions(context: Context): Drawable {
        val densite = context.resources.displayMetrics.density
        val p = palette()
        return CuvetteSuggestions(
            fond = p.fondSuggestions,
            ombre = Color.TRANSPARENT,
            lisere = p.separateur,
            ombrePx = 0,
            // Au moins un pixel : sous mdpi le filet s'arrondirait à zéro et la
            // barre ne se séparerait plus des touches.
            liserePx = maxOf(1, (LISERE_DP * densite).toInt()),
            rayonPx = 0f
        )
    }

    /** Relit le réglage et la configuration système. */
    fun refresh(context: Context) {
        val avant = courante
        courante = resoudre(KeyboardPreferences.themeMode(context), systemeEnSombre(context))
        if (avant !== courante) {
            Log.d(TAG, "Palette : ${nom(courante)}")
        }
    }

    private fun nom(p: Palette): String = when {
        p === SOMBRE -> "sombre"
        p === CONTRASTE -> "contraste"
        p === TAMAZGHA -> "tamazgha"
        else -> "claire"
    }

    /**
     * La table de décision, séparée de la lecture du contexte pour être vérifiable hors appareil
     * (voir KeyboardThemeTest).
     */
    internal fun resoudre(mode: Mode, systemeEnSombre: Boolean): Palette =
        when (mode) {
            Mode.CLAIR -> CLAIR
            Mode.SOMBRE -> SOMBRE
            Mode.SYSTEME -> if (systemeEnSombre) SOMBRE else CLAIR
            Mode.CONTRASTE -> CONTRASTE
            Mode.TAMAZGHA -> TAMAZGHA
        }

    /** Le téléphone est-il en mode sombre ? */
    private fun systemeEnSombre(context: Context): Boolean =
        (context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
                Configuration.UI_MODE_NIGHT_YES
}
