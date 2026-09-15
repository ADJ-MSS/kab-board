package taqbaylit.moteur

import java.io.File

/** Étiqueteur morphosyntaxique, port de _pos_features + pos_tags de pipeline/v2/ressources.py. */
class Etiqueteur private constructor(private val h: Long) : AutoCloseable {

    val nbEtiquettes: Int get() = nbEtiquettes(h)

    /** Traits d'un mot, exactement ceux de _pos_features. */
    private fun traits(phrase: List<String>, i: Int,
                       noms: MutableList<String>, poids: MutableList<Double>) {
        val w = phrase[i]
        // Les accès ci-dessous sont écrits sans indice nu : un mot vide y levait une exception
        // d'indice, en plein service de saisie.
        fun chaine(k: String, v: String) { noms.add("$k:$v"); poids.add(1.0) }
        fun bool(k: String, v: Boolean) { noms.add(k); poids.add(if (v) 1.0 else 0.0) }

        chaine("word", w)
        bool("is_one_letter", w.length == 1)
        bool("is_first", i == 0)
        bool("is_last", i == phrase.size - 1)
        bool("is_capitalized", w.firstOrNull()?.let { it.uppercaseChar() == it } ?: false)
        bool("is_all_caps", w.uppercase() == w)
        bool("is_all_lower", w.lowercase() == w)
        chaine("prefix-1", w.take(1))
        chaine("prefix-2", w.take(2))
        chaine("prefix-3", w.take(3))
        chaine("prefix-4", w.take(4))
        chaine("prefix-5", w.take(5))
        chaine("suffix-1", w.takeLast(1))
        chaine("suffix-2", w.takeLast(2))
        chaine("suffix-3", w.takeLast(3))
        chaine("suffix-4", w.takeLast(4))
        chaine("prev_word", if (i == 0) "" else phrase[i - 1])
        chaine("next_word", if (i == phrase.size - 1) "" else phrase[i + 1])
        bool("is_numeric", w.isNotEmpty() && w.all { it.isDigit() })
        bool("capitals_inside", w.drop(1).lowercase() != w.drop(1))
    }

    /** Étiquette une phrase. Renvoie une étiquette par mot. */
    fun etiqueter(phrase: List<String>): List<String> {
        if (phrase.isEmpty()) return emptyList()
        val noms = ArrayList<String>(phrase.size * 21)
        val poids = ArrayList<Double>(phrase.size * 21)
        val bornes = IntArray(phrase.size)
        for (i in phrase.indices) {
            traits(phrase, i, noms, poids)
            bornes[i] = noms.size
        }
        return etiqueter(h, noms.toTypedArray(), poids.toDoubleArray(), bornes).toList()
    }

    override fun close() = fermer(h)

    companion object {
        @Volatile private var chargee = false

        fun chargerBibliotheque(chemin: File? = null) {
            if (chargee) return
            synchronized(this) {
                if (chargee) return
                if (chemin != null) System.load(chemin.absolutePath)
                else System.loadLibrary("crfjni")
                chargee = true
            }
        }

        fun ouvrir(modele: File): Etiqueteur {
            chargerBibliotheque()
            val h = ouvrir(modele.absolutePath)
            require(h != 0L) { "CRFsuite : ouverture impossible de ${modele.name}" }
            return Etiqueteur(h)
        }

        @JvmStatic private external fun ouvrir(chemin: String): Long
        @JvmStatic private external fun fermer(h: Long)
        @JvmStatic private external fun nbEtiquettes(h: Long): Int
        @JvmStatic private external fun etiqueter(
            h: Long, plat: Array<String>, poids: DoubleArray, bornes: IntArray
        ): Array<String>
    }
}
