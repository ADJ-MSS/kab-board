package taqbaylit.clavier

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.util.Log
import java.io.File
import java.nio.FloatBuffer

/**
 * Transcription de la parole kabyle, entierement sur l'appareil. Le modele vient de Mmeslay
 * (G1ya777, GPL-3).
 */
class Transcripteur private constructor(
    private val env: OrtEnvironment,
    private val session: OrtSession,
    private val jetons: List<String>
) : AutoCloseable {

    /** Les echantillons doivent etre en 16 kHz, mono, entre -1 et 1. */
    fun transcrire(echantillons: FloatArray): String {
        if (echantillons.size < MIN_ECHANTILLONS) return ""
        val forme = longArrayOf(1L, echantillons.size.toLong())
        OnnxTensor.createTensor(env, FloatBuffer.wrap(echantillons), forme).use { entree ->
            session.run(mapOf(NOM_ENTREE to entree)).use { sortie ->
                @Suppress("UNCHECKED_CAST")
                val logits = (sortie[0].value as Array<Array<FloatArray>>)[0]
                return decoder(logits)
            }
        }
    }

    /**
     * Decodage CTC glouton : le meilleur jeton par trame, on fusionne les repetitions et on retire
     * le blanc.
     */
    private fun decoder(logits: Array<FloatArray>): String {
        val sb = StringBuilder()
        var precedent = -1
        for (trame in logits) {
            var meilleur = 0
            var score = trame[0]
            for (i in 1 until trame.size) if (trame[i] > score) { score = trame[i]; meilleur = i }
            if (meilleur != precedent) {
                val j = jetons.getOrNull(meilleur)
                if (j != null && j != BLANC && j != SILENCE) sb.append(j)
            }
            precedent = meilleur
        }
        return sb.toString()
            .replace(DEBUT_DE_MOT, ' ')
            .replace(Regex("-{2,}"), "-")
            .trim()
            .replace(Regex("\\s+"), " ")
    }

    override fun close() {
        runCatching { session.close() }
    }

    companion object {
        private const val TAG = "Taqbaylit"
        private const val DOSSIER = "voix"
        private const val MODELE = "mmeslay.onnx"
        private const val JETONS = "jetons.txt"
        private const val NOM_ENTREE = "audio"

        private const val BLANC = "_"
        private const val SILENCE = "|"
        private const val DEBUT_DE_MOT = '▁'

        /** Un dixieme de seconde : en dessous, il n'y a pas de parole a chercher. */
        private const val MIN_ECHANTILLONS = 1600

        const val TAUX = 16000

        /** Ouvre le modele, en le deposant d'abord sur le disque. */
        fun ouvrir(ctx: Context): Transcripteur? = runCatching {
            val fichier = deposerModele(ctx)
            val jetons = ctx.assets.open("$DOSSIER/$JETONS").bufferedReader()
                .useLines { it.map(String::trim).toList() }
            require(jetons.size >= 2) { "jeu de jetons vide" }

            val env = OrtEnvironment.getEnvironment()
            val options = OrtSession.SessionOptions().apply {
                // Deux fils : le modele est petit et le telephone module.
                setIntraOpNumThreads(2)
                setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
            }
            val session = env.createSession(fichier.absolutePath, options)
            Log.i(TAG, "modele vocal pret (${jetons.size} jetons)")
            Transcripteur(env, session, jetons)
        }.onFailure { Log.e(TAG, "modele vocal indisponible", it) }.getOrNull()

        private fun deposerModele(ctx: Context): File {
            val cible = File(ctx.filesDir, DOSSIER).apply { mkdirs() }
            val definitif = File(cible, MODELE)
            val attendue = runCatching {
                ctx.assets.openFd("$DOSSIER/$MODELE").use { it.length }
            }.getOrDefault(-1L)
            if (definitif.isFile && (attendue <= 0 || definitif.length() == attendue)) return definitif

            val provisoire = File(cible, "$MODELE.partiel")
            provisoire.delete()
            try {
                ctx.assets.open("$DOSSIER/$MODELE").use { entree ->
                    provisoire.outputStream().use { sortie ->
                        entree.copyTo(sortie, 1 shl 16)
                        sortie.fd.sync()
                    }
                }
                if (!provisoire.renameTo(definitif)) throw java.io.IOException("depot impossible")
            } catch (e: Exception) {
                // Meme raison que pour les ressources du correcteur.
                provisoire.delete()
                throw e
            }
            Log.i(TAG, "modele vocal depose : ${definitif.length()} octets")
            return definitif
        }
    }
}
