package taqbaylit.clavier

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.MicrophoneDirection
import android.os.Build
import android.util.Log

/** Capture de la parole, pour la transcription. */
class Ecouteur(private val ctx: Context) {

    /** Un enregistrement plus long que cela est coupe : c'est une phrase, pas un discours. */
    private val maxEchantillons = Transcripteur.TAUX * DUREE_MAX_S

    private var enregistreur: AudioRecord? = null
    @Volatile private var enCours = false

    val actif: Boolean get() = enCours

    fun permissionAccordee(): Boolean =
        ctx.checkSelfPermission(Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    /** Demande la permission du microphone. */
    fun demanderPermission() {
        runCatching {
            ctx.startActivity(
                Intent(ctx, PermissionMicro::class.java).setFlags(
                    Intent.FLAG_ACTIVITY_NEW_TASK or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP or
                        Intent.FLAG_ACTIVITY_CLEAR_TOP
                )
            )
        }.onFailure { Log.e(TAG, "demande de permission impossible", it) }
    }

    /** Enregistre jusqu'a l'appel de arreter, au plus DUREE_MAX_S secondes. */
    fun enregistrer(): FloatArray? {
        if (!permissionAccordee()) return null
        val minimum = AudioRecord.getMinBufferSize(
            Transcripteur.TAUX, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minimum <= 0) { Log.e(TAG, "taille de tampon refusee : $minimum"); return null }

        val rec = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                Transcripteur.TAUX,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                // Cinq secondes d'avance : le fil de lecture peut etre retarde
                // sans que le systeme jette des echantillons.
                maxOf(minimum, Transcripteur.TAUX * 2 * 5)
            )
        } catch (e: SecurityException) {
            Log.e(TAG, "permission retiree entre-temps", e); return null
        }
        if (rec.state != AudioRecord.STATE_INITIALIZED) {
            Log.e(TAG, "microphone indisponible"); rec.release(); return null
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            runCatching {
                rec.setPreferredMicrophoneDirection(
                    MicrophoneDirection.MIC_DIRECTION_TOWARDS_USER)
            }
        }

        enregistreur = rec
        enCours = true
        val accumule = ShortArray(maxEchantillons)
        var total = 0
        try {
            rec.startRecording()
            val tranche = ShortArray(TRANCHE)
            while (enCours && total < maxEchantillons) {
                val lus = rec.read(tranche, 0, TRANCHE, AudioRecord.READ_BLOCKING)
                if (lus <= 0) break
                val place = minOf(lus, maxEchantillons - total)
                System.arraycopy(tranche, 0, accumule, total, place)
                total += place
            }
        } catch (e: Exception) {
            Log.e(TAG, "capture interrompue", e)
        } finally {
            enCours = false
            runCatching { rec.stop() }
            runCatching { rec.release() }
            enregistreur = null
        }

        if (total < TRANCHE) return null
        // Entiers 16 bits vers flottants : c'est ce que le modele attend.
        val sortie = FloatArray(total)
        for (i in 0 until total) sortie[i] = accumule[i] / 32768f
        Log.i(TAG, "capture : %.1f s".format(total.toFloat() / Transcripteur.TAUX))
        return sortie
    }

    /** Demande l'arret. La boucle de enregistrer se termine a la tranche suivante. */
    fun arreter() { enCours = false }

    companion object {
        private const val TAG = "Taqbaylit"

        /** Cent millisecondes par lecture. */
        private const val TRANCHE = Transcripteur.TAUX / 10

        /**
         * Trente secondes. Au dela, ce n'est plus une phrase dictee, et le temps de calcul comme la
         * memoire grimpent avec la duree.
         */
        private const val DUREE_MAX_S = 30
    }
}
