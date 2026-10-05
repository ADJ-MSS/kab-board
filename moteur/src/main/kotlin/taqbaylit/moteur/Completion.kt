package taqbaylit.moteur

/**
 * La complétion du mot en cours, de 1 à 3 lettres tapées.
 *
 * Jusqu'à SEUIL lettres, la barre propose les mots qui commencent par ce qui est tapé ;
 * au-delà, elle corrige comme avant. On ne complète jamais vers un mot de 2 ou 3 lettres :
 * ceux-là, on les a déjà tapés.
 *
 * Mesuré le 05/10/2026 sur 400 phrases du corpus, tapées lettre par lettre : 24,1 % de
 * frappes en moins avec SEUIL = 3, sans rien changer au filet de correction (191/200 sur
 * les fautes injectées). Compléter jusqu'à 4 lettres faisait tomber le filet à 90,5 %.
 *
 * Même règle que linux/completion.py.
 */
class Completion(mots: List<String>, freqs: List<Int>) {

    private val mots: Array<String>
    private val freqs: IntArray

    init {
        // Trié ici, dans l'ordre de compareTo, pour que la recherche binaire soit juste.
        val ordre = mots.indices.sortedBy { mots[it] }
        this.mots = Array(ordre.size) { mots[ordre[it]] }
        this.freqs = IntArray(ordre.size) { freqs[ordre[it]] }
    }

    companion object {
        const val SEUIL = 3            // complétion jusqu'à 3 lettres tapées, correction ensuite
        const val LONGUEUR_MIN = 4     // jamais vers un mot de 2 ou 3 lettres
        const val FREQ_MIN = 50        // assez fréquent pour être proposé sans être tapé
        const val PAR_PREFIXE = 400    // les plus fréquents d'un début, avant le modèle de langue

        /**
         * Le mot tapé reste en tête s'il est déjà un mot des dictionnaires : lexique par
         * catégories ou conjugaisons. La fiabilité du correcteur ne suffit pas ici : le
         * lexique agrégé compte des bouts de mots, « ẓr » ou « lx », présents dans plus de
         * trois sources.
         */
        fun motDeDictionnaire(res: Ressources): (String) -> Boolean =
            { m -> res.lexcat(m) != null || m in res.amyag }

        /** Les mots fiables de 4 lettres ou plus du lexique. */
        fun depuis(res: Ressources): Completion {
            val mots = ArrayList<String>(70_000)
            val freqs = ArrayList<Int>(70_000)
            res.lexique.forEachIndexed { i, m ->
                if (m.length >= LONGUEUR_MIN) {
                    val f = res.freqParIndex(i)
                    if (f >= FREQ_MIN) { mots.add(m); freqs.add(f) }
                }
            }
            return Completion(mots, freqs)
        }
    }

    val taille: Int get() = mots.size

    /** Les mots qui commencent par prefixe, les plus fréquents d'abord. */
    fun candidats(prefixe: String): List<String> {
        if (prefixe.isEmpty()) return emptyList()
        var lo = 0
        var hi = mots.size
        while (lo < hi) {
            val mid = (lo + hi) ushr 1
            if (mots[mid] < prefixe) lo = mid + 1 else hi = mid
        }
        val tranche = ArrayList<Int>()
        var i = lo
        while (i < mots.size && mots[i].startsWith(prefixe)) tranche.add(i++)
        return tranche.sortedByDescending { freqs[it] }.take(PAR_PREFIXE).map { mots[it] }
    }

    /** Les nb mots qui commencent par prefixe et vont le mieux après contexteGauche. */
    fun completer(contexteGauche: String, prefixe: String, nb: Int, lm: ModeleLangue?): List<String> {
        val cands = candidats(prefixe)
        if (cands.isEmpty() || lm == null) return cands.take(nb)
        val tokens = Normalisation.tokenize(contexteGauche).takeLast(2)
        lm.etat().use { entree ->
            lm.etat().use { sortie ->
                lm.debutPhrase(entree)
                for (t in tokens) { lm.baseScore(entree, t, sortie); lm.copier(sortie, entree) }
                return cands.map { it to lm.baseScore(entree, it, sortie) }
                    .sortedByDescending { it.second }
                    .take(nb)
                    .map { it.first }
            }
        }
    }

    /**
     * Ce que montre la barre pour un mot de 1 à SEUIL lettres : le mot tapé s'il est déjà un
     * mot (estUnMot, en pratique motDeDictionnaire), puis les complétions. null quand rien ne
     * commence ainsi : la barre corrige alors comme avant.
     */
    fun barre(contexteGauche: String, tape: String, nb: Int, lm: ModeleLangue?,
              estUnMot: (String) -> Boolean): List<String>? {
        if (tape.isEmpty() || tape.length > SEUIL) return null
        val comp = completer(contexteGauche, tape, nb, lm)
        if (comp.isEmpty()) return null
        val tete = if (estUnMot(tape)) listOf(tape) else emptyList()
        return (tete + comp.filter { it != tape }).take(nb)
    }
}
