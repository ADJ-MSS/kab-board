package taqbaylit.clavier

import android.content.Context
import android.util.Log
import taqbaylit.moteur.Correcteur
import java.io.File

/** Le correcteur, construit une seule fois pour toute l'application. */
object Moteur {

    private const val TAG = "Taqbaylit"
    private val verrou = Any()
    private var correcteur: Correcteur? = null
    private var echoue = false

    /** Ou en est la preparation, pour que la barre puisse le dire. */
    enum class Etat { ATTENTE, DEPOT, CONSTRUCTION, PRET, ECHEC }

    @Volatile var etat: Etat = Etat.ATTENTE
        private set

    /** Avancement du depot, en pour cent. */
    @Volatile var avancement: Int = 0
        private set

    /** La complétion se construit quelques secondes après le moteur. */
    @Volatile var completionPrete = false
        private set

    /** Le moteur, en le construisant au besoin. */
    fun obtenir(ctx: Context): Correcteur? = synchronized(verrou) {
        correcteur?.let { return it }
        if (echoue) return null
        val t0 = System.currentTimeMillis()
        val r = runCatching {
            val base = Ressources.dossier(ctx.applicationContext) { pct ->
                etat = Etat.DEPOT; avancement = pct
            }
            Log.i(TAG, "ressources pretes en ${System.currentTimeMillis() - t0} ms")
            etat = Etat.CONSTRUCTION
            Correcteur(
                dossierRessources = base,
                modeleKenlm = File(base, "kabyle_3gram.binary"),
                modeleCrf = File(base, "pos_kab.crfsuite")
            )
        }
        r.onSuccess {
            correcteur = it
            etat = Etat.PRET
            Log.i(TAG, "MOTEUR PRET en ${System.currentTimeMillis() - t0} ms")
            // Le vocabulaire de complétion parcourt tout le lexique. Hors du verrou : sinon toutes
            // les propositions attendaient derrière, le message de chargement déjà disparu.
            Thread {
                val t1 = System.currentTimeMillis()
                runCatching { it.completion.taille }
                    .onSuccess { n ->
                        completionPrete = true
                        Log.i(TAG, "complétion prête : $n mots en ${System.currentTimeMillis() - t1} ms")
                    }
                    .onFailure { e -> Log.e(TAG, "complétion indisponible", e) }
            }.start()
        }.onFailure {
            echoue = true
            etat = Etat.ECHEC
            Log.e(TAG, "moteur indisponible", it)
        }
        return r.getOrNull()
    }

    /** Deja construit ? Sans le construire, et sans bloquer. */
    fun dejaPret(): Boolean = correcteur != null

    /** Execute un travail sur le moteur, seul a la fois. */
    fun <T> avec(ctx: Context, travail: (Correcteur) -> T): T? = synchronized(verrou) {
        val c = obtenir(ctx) ?: return null
        return runCatching { travail(c) }
            .onFailure { Log.e(TAG, "travail impossible", it) }
            .getOrNull()
    }
}
