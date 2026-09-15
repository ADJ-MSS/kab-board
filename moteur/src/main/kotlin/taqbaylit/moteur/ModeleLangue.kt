package taqbaylit.moteur

import java.io.File

/** Pont vers KenLM, via natif/kenlm_jni.cc. */
class ModeleLangue private constructor(private val h: Long) : AutoCloseable {

    class Etat internal constructor(internal val p: Long) : AutoCloseable {
        override fun close() = etatLiberer(p)
    }

    val ordre: Int get() = ordre(h)

    fun etat(): Etat = Etat(etatNouveau(h))

    fun debutPhrase(e: Etat) = debutPhrase(h, e.p)
    fun contexteVide(e: Etat) = contexteVide(h, e.p)
    fun copier(src: Etat, dst: Etat) = etatCopier(h, src.p, dst.p)
    fun memeEtat(a: Etat, b: Etat) = etatEgal(h, a.p, b.p)

    /** log10 P(mot | entrée), et écrit l'état résultant dans [sortie]. */
    fun baseScore(entree: Etat, mot: String, sortie: Etat): Float =
        baseScore(h, entree.p, mot, sortie.p)

    /** Équivalent de kenlm.Model.score(phrase, bos, eos). */
    fun score(phrase: String, bos: Boolean = true, eos: Boolean = true): Float =
        scorePhrase(h, phrase, bos, eos)

    override fun close() = fermer(h)

    companion object {
        @Volatile private var chargee = false

        /** Charge la bibliothèque native, depuis un chemin explicite ou java.library.path. */
        fun chargerBibliotheque(chemin: File? = null) {
            if (chargee) return
            synchronized(this) {
                if (chargee) return
                if (chemin != null) System.load(chemin.absolutePath)
                else System.loadLibrary("kenlmjni")
                chargee = true
            }
        }

        fun ouvrir(modele: File): ModeleLangue {
            chargerBibliotheque()
            val h = ouvrir(modele.absolutePath)
            require(h != 0L) { "KenLM : ouverture impossible de ${modele.name}" }
            return ModeleLangue(h)
        }

        @JvmStatic private external fun ouvrir(chemin: String): Long
        @JvmStatic private external fun fermer(h: Long)
        @JvmStatic private external fun ordre(h: Long): Int
        @JvmStatic private external fun etatNouveau(h: Long): Long
        @JvmStatic private external fun etatLiberer(e: Long)
        @JvmStatic private external fun debutPhrase(h: Long, e: Long)
        @JvmStatic private external fun contexteVide(h: Long, e: Long)
        @JvmStatic private external fun etatCopier(h: Long, src: Long, dst: Long)
        @JvmStatic private external fun etatEgal(h: Long, a: Long, b: Long): Boolean
        @JvmStatic private external fun baseScore(h: Long, entree: Long, mot: String, sortie: Long): Float
        @JvmStatic private external fun scorePhrase(h: Long, phrase: String, bos: Boolean, eos: Boolean): Float
    }
}
