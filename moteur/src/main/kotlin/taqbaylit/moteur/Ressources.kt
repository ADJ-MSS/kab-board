package taqbaylit.moteur

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.FileChannel
import java.nio.charset.StandardCharsets

/** Port de pipeline/v2/ressources.py. */

private const val MAGIC = 0x4C42_5154   // "TQBL" en little-endian
private const val BLOC = 16

private fun mappe(f: File): ByteBuffer =
    FileChannel.open(f.toPath(), java.nio.file.StandardOpenOption.READ).use { ch ->
        ch.map(FileChannel.MapMode.READ_ONLY, 0, ch.size()).order(ByteOrder.LITTLE_ENDIAN)
    }

/** Liste de mots triés, préfixes factorisés par blocs de 16. */
class ListeMots(fichier: File) {
    private val buf = mappe(fichier)
    val taille: Int
    private val nbBlocs: Int
    private val debutOffsets: Int
    private val debutDonnees: Int

    init {
        require(buf.getInt(0) == MAGIC) { "signature absente : ${fichier.name}" }
        taille = buf.getInt(6)
        nbBlocs = buf.getInt(10)
        debutOffsets = 14
        debutDonnees = debutOffsets + nbBlocs * 4
    }

    /** Premier mot de chaque bloc, gardé en clair. */
    private val premiers: Array<String> by lazy {
        Array(nbBlocs) { blocBrut(it)[0] }
    }

    /** Décode un bloc entier. Peu coûteux : 16 mots. */
    private fun bloc(nb: Int): Array<String> = blocBrut(nb)

    private fun blocBrut(nb: Int): Array<String> {
        var p = debutDonnees + buf.getInt(debutOffsets + nb * 4)
        val n = minOf(BLOC, taille - nb * BLOC)
        val out = arrayOfNulls<String>(n)
        var prec = ""
        for (j in 0 until n) {
            if (j == 0) {
                val len = buf.getShort(p).toInt() and 0xFFFF; p += 2
                val b = ByteArray(len)
                for (k in 0 until len) b[k] = buf.get(p + k)
                p += len
                prec = String(b, StandardCharsets.UTF_8)
            } else {
                val c = buf.get(p).toInt() and 0xFF; p += 1
                val len = buf.getShort(p).toInt() and 0xFFFF; p += 2
                val b = ByteArray(len)
                for (k in 0 until len) b[k] = buf.get(p + k)
                p += len
                prec = prec.substring(0, c) + String(b, StandardCharsets.UTF_8)
            }
            out[j] = prec
        }
        @Suppress("UNCHECKED_CAST")
        return out as Array<String>
    }

    operator fun get(i: Int): String = bloc(i / BLOC)[i % BLOC]

    /** Index du mot, ou -1. Recherche binaire sur les blocs puis balayage. */
    fun indexDe(mot: String): Int {
        val p = premiers
        var lo = 0
        var hi = nbBlocs - 1
        var cible = 0
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            if (p[mid] <= mot) { cible = mid; lo = mid + 1 } else hi = mid - 1
        }
        val b = bloc(cible)          // un seul bloc décodé, pas quinze
        for (j in b.indices) if (b[j] == mot) return cible * BLOC + j
        return -1
    }

    operator fun contains(mot: String) = indexDe(mot) >= 0

    /** Parcours séquentiel. */
    fun forEachIndexed(action: (Int, String) -> Unit) {
        var nb = 0
        var i = 0
        while (i < taille) {
            val b = bloc(nb)
            for (j in b.indices) { action(i, b[j]); i++ }
            nb++
        }
    }
}

private class TableauU32(fichier: File) {
    private val buf = mappe(fichier)
    val taille: Int = buf.getInt(6)
    operator fun get(i: Int): Int = buf.getInt(10 + i * 4)
}

private class TableauU8(fichier: File) {
    private val buf = mappe(fichier)
    val taille: Int = buf.getInt(6)
    operator fun get(i: Int): Int = buf.get(10 + i).toInt() and 0xFF
}

class Ressources(dossier: File) {

    val lexique = ListeMots(File(dossier, "lexique.mots"))
    private val lexFreq = TableauU32(File(dossier, "lexique.freq"))
    private val lexNsrc = TableauU8(File(dossier, "lexique.nsrc"))

    val amyag = ListeMots(File(dossier, "amyag.mots"))

    private val lexcatMots = ListeMots(File(dossier, "lexcat.mots"))
    private val lexcatCat = TableauU8(File(dossier, "lexcat.cat"))
    private val catNoms = File(dossier, "lexcat.noms").readLines()

    val wnFormes = ListeMots(File(dossier, "wordnet.formes"))
    private val wnGloses = File(dossier, "wordnet.gloses").readLines()

    val pool = ListeMots(File(dossier, "pool.mots"))
    val sdxIndex: Map<String, IntArray>

    init {
        val buf = mappe(File(dossier, "pool.sdx"))
        val n = buf.getInt(6)
        val m = HashMap<String, IntArray>(n * 2)
        var p = 10
        repeat(n) {
            val lk = buf.get(p).toInt() and 0xFF
            val nb = buf.getShort(p + 1).toInt() and 0xFFFF
            p += 3
            val kb = ByteArray(lk)
            for (k in 0 until lk) kb[k] = buf.get(p + k)
            p += lk
            val idx = IntArray(nb)
            for (k in 0 until nb) idx[k] = buf.getInt(p + k * 4)
            p += nb * 4
            m[String(kb, StandardCharsets.UTF_8)] = idx
        }
        sdxIndex = m
    }

    /** Tableaux alignés sur le vivier, produits à l'export. */
    private val pFreq = File(dossier, "pool.freq").takeIf { it.isFile }?.let { TableauU32(it) }
    private val pNsrc = File(dossier, "pool.nsrc").takeIf { it.isFile }?.let { TableauU8(it) }
    private val pSrc  = File(dossier, "pool.src").takeIf { it.isFile }?.let { TableauU8(it) }
    private val srcNoms = File(dossier, "pool.srcnoms")
        .takeIf { it.isFile }?.readLines() ?: emptyList()

    fun poolFreq(): ((Int) -> Int)? = pFreq?.let { t -> { i: Int -> t[i] } }
    fun poolNsrc(): ((Int) -> Int)? = pNsrc?.let { t -> { i: Int -> t[i] } }
    fun poolSrc(): ((Int) -> String)? =
        if (pSrc != null && srcNoms.isNotEmpty())
            { i: Int -> srcNoms[pSrc[i]] } else null

    /** Formes les plus frequentes du vivier, arretees a l'export. */
    val frequents: List<String> =
        File(dossier, "pool.frequents").takeIf { it.isFile }?.readLines() ?: emptyList()

    /** Vue ensembliste des formes verbales, pour les appels qui attendent un Set. */
    private val amyagSet: Set<String> = object : AbstractSet<String>() {
        override val size: Int get() = amyag.taille
        override fun contains(element: String): Boolean = amyag.indexDe(element) >= 0
        override fun iterator(): Iterator<String> = object : Iterator<String> {
            private var i = 0
            override fun hasNext() = i < amyag.taille
            override fun next(): String = amyag[i++]
        }
    }
    fun amyagSet(): Set<String> = amyagSet

    fun freq(mot: String): Int { val i = lexique.indexDe(mot); return if (i < 0) 0 else lexFreq[i] }
    fun nsrc(mot: String): Int { val i = lexique.indexDe(mot); return if (i < 0) 0 else lexNsrc[i] }
    fun lexcat(mot: String): String? {
        val i = lexcatMots.indexDe(mot); return if (i < 0) null else catNoms[lexcatCat[i]]
    }
    fun glose(mot: String): String {
        val i = wnFormes.indexDe(mot); return if (i < 0) "" else wnGloses[i]
    }

    /** Formes et gloses pliées du graphe, pour la recherche depuis le français. */
    private val wnListe: List<String> by lazy {
        val l = ArrayList<String>(wnFormes.taille)
        wnFormes.forEachIndexed { _, f -> l.add(f) }
        l
    }
    private val glosesPliees: List<String> by lazy { wnGloses.map { RechercheFrancais.plier(it) } }

    /** Les [nb] formes dont la glose répond le mieux au mot français [requete]. */
    fun chercherFrancais(requete: String, nb: Int): List<RechercheFrancais.Trouve> {
        val q = RechercheFrancais.plier(requete)
        if (q.length < RechercheFrancais.REQUETE_MIN) return emptyList()
        val formes = wnListe
        val gloses = glosesPliees
        val trouves = ArrayList<RechercheFrancais.Trouve>()
        for (i in 0 until minOf(formes.size, gloses.size)) {
            val r = RechercheFrancais.rang(gloses[i], q) ?: continue
            trouves.add(RechercheFrancais.Trouve(formes[i], wnGloses[i], r, freq(formes[i])))
        }
        return RechercheFrancais.classer(trouves, nb)
    }

    /** Candidats du mot du jour, calculés au premier appel. */
    val motsDuJour: List<String> by lazy { MotDuJour.candidats(frequents, ::glose) }

    private val contentCats = setOf("masc", "fem", "fem_pl", "adj_masc", "adj_fem", "adverb", "ambig")
    fun estContent(mot: String) = lexcat(mot) in contentCats

    private val fiableCache = HashMap<String, Boolean>()

    /** Mot de confiance : forme verbale, lexique par catégorie, multi-sources ou très fréquent. */
    fun fiable(mot: String): Boolean = fiableCache.getOrPut(mot) {
        mot in amyag || lexcat(mot) != null ||
            nsrc(mot) >= Config.MIN_SOURCES_FIABLE ||
            freq(mot) >= Config.FREQ_FIABLE
    }

    private val PREF = listOf("y", "t", "n", "tt", "d", "i", "a", "u", "m", "ms", "s")
    private val SUFF = listOf("en", "ent", "iɣ", "eɣ", "aɣ", "iḍ", "id", "an", "in")

    /** Préfixe/suffixe productif + racine fiable (morphologie légère). */
    fun valideParAffixe(mot: String): Boolean {
        for (p in PREF)
            if (mot.startsWith(p) && mot.length - p.length >= 2 && fiable(mot.substring(p.length)))
                return true
        for (s in SUFF)
            if (mot.endsWith(s) && mot.length - s.length >= 2 &&
                fiable(mot.substring(0, mot.length - s.length)))
                return true
        return false
    }
}

object Config {
    const val MIN_SOURCES_FIABLE = 3
    const val FREQ_FIABLE = 300
    const val FREQ_MIN_CANDIDAT = 10
}
