package taqbaylit.clavier

import android.content.Context
import android.util.Log
import java.io.File
import java.io.IOException

/** Dépose les ressources du correcteur au premier lancement. */
object Ressources {

    private const val TAG = "Taqbaylit"
    private const val DOSSIER = "moteur"
    private const val TAILLES = "tailles.txt"

    /** Incrémenté : la 5 ajoute les candidats de prédiction. */
    private const val VERSION = 5

    fun dossier(ctx: Context, surAvancement: (Int) -> Unit = {}): File {
        val cible = File(ctx.filesDir, DOSSIER)
        val marqueur = File(cible, ".version")
        if (marqueur.isFile &&
            marqueur.readText().trim() == VERSION.toString() &&
            complet(ctx, cible)
        ) return cible

        // Version differente ou depot incomplet : on repart de zero plutot
        // que de faire confiance a ce qui traine.
        Log.i(TAG, "depot des ressources")
        cible.deleteRecursively()
        cible.mkdirs()
        deposer(ctx, cible, surAvancement)
        marqueur.writeText(VERSION.toString())
        return cible
    }

    /** Chaque fichier attendu est-il present, et de la bonne taille ? */
    private fun complet(ctx: Context, cible: File): Boolean {
        val attendues = tailles(ctx)
        if (attendues.isEmpty()) { Log.w(TAG, "tailles.txt illisible"); return false }
        for (nom in ctx.assets.list(DOSSIER).orEmpty()) {
            if (nom == TAILLES) continue
            val f = File(cible, nom)
            if (!f.isFile) { Log.w(TAG, "ressource absente : $nom"); return false }
            val attendue = attendues[nom]
            if (attendue == null) { Log.w(TAG, "taille inconnue : $nom"); return false }
            if (f.length() != attendue) {
                Log.w(TAG, "ressource tronquee : $nom ${f.length()}/$attendue")
                return false
            }
        }
        return true
    }

    /** Tailles attendues, lues dans un actif produit a la construction. */
    private fun tailles(ctx: Context): Map<String, Long> = runCatching {
        ctx.assets.open("$DOSSIER/$TAILLES").bufferedReader().useLines { lignes ->
            lignes.mapNotNull { l ->
                val p = l.split('\t')
                if (p.size == 2) p[0] to (p[1].toLongOrNull() ?: return@mapNotNull null) else null
            }.toMap()
        }
    }.getOrElse { emptyMap() }

    private fun deposer(ctx: Context, cible: File, surAvancement: (Int) -> Unit) {
        val attendues = tailles(ctx)
        verifierLaPlace(ctx, attendues)
        val total = attendues.values.sum().coerceAtLeast(1)
        var ecrits = 0L
        surAvancement(0)
        for (nom in ctx.assets.list(DOSSIER).orEmpty()) {
            val t0 = System.currentTimeMillis()
            val definitif = File(cible, nom)
            val provisoire = File(cible, "$nom.partiel")
            provisoire.delete()
            try {
                ctx.assets.open("$DOSSIER/$nom").use { entree ->
                    provisoire.outputStream().use { sortie ->
                        entree.copyTo(sortie, 1 shl 16)
                        sortie.fd.sync()           // sur le disque avant de renommer
                    }
                }
                // Verifie ici et pas seulement au lancement suivant.
                val attendue = attendues[nom]
                if (attendue != null && provisoire.length() != attendue)
                    throw IOException("$nom tronque : ${provisoire.length()}/$attendue")
                if (!provisoire.renameTo(definitif))
                    throw IOException("copie impossible : $nom")
            } catch (e: Exception) {
                // Sans ce nettoyage, une copie interrompue laisse son fichier partiel sur le disque
                // — jusqu'a 268 Mio pour le modele de langue — et la tentative suivante a d'autant
                // moins de place.
                provisoire.delete()
                throw e
            }
            ecrits += definitif.length()
            surAvancement(((ecrits * 100) / total).toInt().coerceIn(0, 100))
            Log.i(TAG, "depose : $nom ${definitif.length()} octets " +
                "en ${System.currentTimeMillis() - t0} ms")
        }
    }

    /** Refuse de commencer si la place manque. */
    private fun verifierLaPlace(ctx: Context, attendues: Map<String, Long>) {
        if (attendues.isEmpty()) return
        val besoin = attendues.values.sum()
        val libre = ctx.filesDir.usableSpace
        val marge = 64L * 1024 * 1024
        Log.i(TAG, "depot : ${besoin / 1048576} Mio a ecrire, ${libre / 1048576} Mio libres")
        if (libre < besoin + marge)
            throw IOException(
                "place insuffisante : ${besoin / 1048576} Mio a deposer, " +
                "${libre / 1048576} Mio libres")
    }

    /** Place occupée, pour l'écran de réglages. */
    fun taille(ctx: Context): Long =
        File(ctx.filesDir, DOSSIER).walkTopDown().filter { it.isFile }.sumOf { it.length() }
}
