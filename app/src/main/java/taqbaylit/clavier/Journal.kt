package taqbaylit.clavier

import android.content.Context
import android.util.Log
import java.io.File
import java.util.concurrent.Executors
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Journal des formes retenues, tel que la charte le décrit. */
object Journal {

    private const val PREFS = "taqbaylit"
    private const val CLE_ACTIF = "journal_actif"
    private const val CLE_DIFFUSION = "consent_diffusion"
    private const val FICHIER = "mes-choix.txt"

    private val ENTETE = """
        # Correcteur kabyle · journal de vos choix
        # Ce fichier reste sur votre appareil. Vous seul decidez de l'envoyer.
        # Pour tout effacer : bouton « Tout effacer » dans les reglages.
        # Ce qui est enregistre et pourquoi : voir la charte de contribution.
        #
        # date | mot saisi | forme retenue
        
    """.trimIndent() + "\n"

    fun actif(ctx: Context) =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(CLE_ACTIF, false)

    fun activer(ctx: Context, valeur: Boolean) =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(CLE_ACTIF, valeur).apply()

    fun diffusionAutorisee(ctx: Context) =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(CLE_DIFFUSION, false)

    fun autoriserDiffusion(ctx: Context, valeur: Boolean) =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(CLE_DIFFUSION, valeur).apply()

    fun fichier(ctx: Context) = File(ctx.filesDir, FICHIER)

    /** Toutes les operations sur le fichier passent par ce fil. */
    private val fil = Executors.newSingleThreadExecutor { r ->
        Thread(r, "TaqbaylitJournal").apply { isDaemon = true }
    }

    /**
     * Note un choix. Ne fait rien si le journal est éteint, ou si le champ est un mot de passe — la
     * charte l'exclut explicitement.
     */
    fun noter(ctx: Context, saisi: String, retenu: String, champSensible: Boolean) {
        if (champSensible || !actif(ctx)) return
        if (saisi.isBlank() || retenu.isBlank()) return
        val f = fichier(ctx)
        val date = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(Date())
        val ligne = "$date | ${propre(saisi)} | ${propre(retenu)}\n"
        fil.execute {
            runCatching {
                if (!f.exists()) f.writeText(ENTETE)
                f.appendText(ligne)
            }.onFailure { Log.w("Taqbaylit", "journal non ecrit", it) }
        }
    }

    /** Attend que les ecritures en attente soient sur le disque. */
    private fun <T> surLeFil(travail: () -> T): T =
        fil.submit(travail).get()

    /** La barre verticale sépare les champs, on la retire du contenu. */
    private fun propre(s: String) = s.replace("|", "/").replace("\n", " ").trim()

    /** Compte les lignes, une fois les ecritures en attente ecoulees. */
    fun nombreLignes(ctx: Context): Int = surLeFil {
        val f = fichier(ctx)
        if (!f.exists()) 0
        else f.readLines().count { it.isNotBlank() && !it.startsWith("#") }
    }

    /** Les derniers caracteres du journal, pour l'apercu des reglages. */
    fun extrait(ctx: Context, taille: Int): String? = surLeFil {
        val f = fichier(ctx)
        if (f.exists()) f.readText().takeLast(taille) else null
    }

    /** Efface. Sur le meme fil, sinon une ecriture en vol ressusciterait le fichier. */
    fun toutEffacer(ctx: Context) { surLeFil { fichier(ctx).delete() } }
}
