package taqbaylit.moteur

import kotlin.math.log10
import kotlin.math.min

/** Port de pipeline/v2/candidats.py. */

data class Candidat(
    val forme: String,
    val source: String,      // "keep" | "amyag" | "lexcat_<cat>" | "wordnet" | "lexique" | "abrev"
    val distP: Double,       // distance pondérée kabyle
    val dist: Int,           // distance DL brute
    val freq: Int,
    val nsrc: Int,
    val memeSdx: Boolean,
    var score: Double = 0.0
)

object ConfigCand {
    const val MAX_DIST_BRUTE = 2

    const val W_DIST = 2.0
    const val W_FREQ = 0.6
    const val W_NSRC = 0.4
    const val W_SDX = 0.35
    const val W_POS = 0.5
    const val PEN_DOUTEUX = 0.7

    const val FREQ_PLANCHER_DICO = 50
    const val NSRC_PLANCHER_DICO = 4

    const val BONUS_VARIANTE = 1.2
    const val VAR_MAX_DIST_P = 0.7

    const val BONUS_KEEP_DICO = 2.2
    const val BONUS_KEEP_SEMI = 1.2
    const val BONUS_KEEP_VALIDE = 0.1
    const val BONUS_KEEP_OOV = -1.4

    val ABREVIATIONS = mapOf("ɣ" to listOf("ɣer", "ɣef"))

    fun seuilDistPonderee(longueur: Int): Double = when {
        longueur <= 3 -> 1.0
        longueur <= 5 -> 1.8
        else -> 2.4
    }

    val POS_VERB_TAGS = setOf(
        "VAI", "VP", "VAF", "VPN", "VAIT", "VPPP",
        "VS", "VII", "VPA", "VPPN", "VPAIP", "VPAIN"
    )
    val POS_NOUN_TAGS = setOf("NMC", "NMP", "NCM", "NC", "ADJ")

    private val PREP_ANNEXION = setOf(
        "n", "i", "gg", "deg", "g", "ɣef", "ddaw", "nnig",
        "ɣer", "fell", "di", "si", "afella", "tama", "idis"
    )
    private val PREP_LIBRE = setOf("ar")
    private val ETAT_LIBRE_FORCE = setOf("d", "ur", "mačči")

    val MOTS_INTOUCHABLES: Set<String> =
        PREP_ANNEXION + PREP_LIBRE + ETAT_LIBRE_FORCE +
        Normalisation.PARTICULES + Normalisation.POSSESSIFS + setOf(
            "nekk", "nekki", "kečč", "kemmi", "netta", "nettat", "nekni", "kunwi",
            "kunemti", "nutni", "nutenti", "nekenti",
            "wagi", "tagi", "wid", "tid", "win", "tin", "acu", "ma", "anda", "akken",
            "ad", "ara", "ur", "ulac", "ala", "ihi", "aṭas", "drus", "am", "mara",
            "ticki", "af", "khati",
            "ladɣa", "ɣas", "wissen", "sɣur", "acku", "imi", "mi", "yal",
            "kra", "yiwen", "yiwet"
        )
}

class Generateur(private val res: Ressources) {

    /** Signature des caractères d'un mot, un bit par classe. */
    private fun signature(m: String): Long {
        var s = 0L
        for (c in m) s = s or (1L shl (c.code and 63))
        return s
    }

    /** Tout ce qu'il faut savoir d'une forme du vivier, aligné sur son index. */
    private val poolFreq = IntArray(res.pool.taille)
    private val poolNsrc = ByteArray(res.pool.taille)
    private val poolSrc = arrayOfNulls<String>(res.pool.taille)
    private val poolSdx = arrayOfNulls<String>(res.pool.taille)

    /** Le vivier réordonné physiquement par longueur de mot. */
    private val ordSig: LongArray
    private val ordMots: Array<String?>
    private val debutLongueur: IntArray      // décalage du premier mot de chaque longueur
    private val plusLongMot: Int

    /** Un seul parcours du vivier, et trois tableaux de moins a garder. */
    init {
        val n = res.pool.taille
        val sig = LongArray(n)
        val len = IntArray(n)
        val mots = arrayOfNulls<String>(n)

        // Fréquence, nombre de sources et source viennent de tableaux produits à l'export.
        val fq = res.poolFreq()
        val ns = res.poolNsrc()
        val sr = res.poolSrc()
        var maxLocal = 0
        res.pool.forEachIndexed { i, m ->
            mots[i] = m
            sig[i] = signature(m)
            len[i] = m.length
            if (m.length > maxLocal) maxLocal = m.length
            poolFreq[i] = if (fq != null) fq(i) else res.freq(m)
            poolNsrc[i] = (if (ns != null) ns(i) else res.nsrc(m)).toByte()
            poolSrc[i] = if (sr != null) sr(i) else sourceDe(m)
        }
        // Le code sonore se déduit des seaux déjà chargés, sans le recalculer
        for ((cle, idx) in res.sdxIndex) for (i in idx) poolSdx[i] = cle

        plusLongMot = maxLocal
        val maxL = maxLocal + 1
        val comptes = IntArray(maxL + 1)
        for (l in len) comptes[l]++
        debutLongueur = IntArray(maxL + 2)
        for (l in 0..maxL) debutLongueur[l + 1] = debutLongueur[l] + comptes[l]
        val pos = debutLongueur.copyOf()
        ordSig = LongArray(n)
        ordMots = arrayOfNulls(n)
        for (i in 0 until n) {
            val p = pos[len[i]]++
            ordSig[p] = sig[i]
            ordMots[p] = mots[i]
        }
    }

    /** Index d'une forme dans le vivier, ou -1. */
    private fun motVersIndex(forme: String): Int = res.pool.indexDe(forme)

    private fun sourceDe(forme: String): String = when {
        forme in res.amyag -> "amyag"
        res.lexcat(forme) != null -> "lexcat_" + res.lexcat(forme)
        forme in res.wnFormes -> "wordnet"
        else -> "lexique"
    }

    private fun estDico(source: String) =
        source == "amyag" || source == "wordnet" || source.startsWith("lexcat_")

    private fun scorer(c: Candidat, posTag: String, bonusKeep: Double): Double {
        if (c.source == "keep")
            return bonusKeep +
                ConfigCand.W_FREQ * min(log10(c.freq + 1.0) / 6.0, 1.0) +
                ConfigCand.W_NSRC * min(c.nsrc, 8) / 8.0

        val estVerbal = c.source == "amyag"
        val estNominal = c.source.startsWith("lexcat_")
        val dico = estDico(c.source)
        val freq = if (dico) maxOf(c.freq, ConfigCand.FREQ_PLANCHER_DICO) else c.freq
        val nsrc = if (dico) maxOf(c.nsrc, ConfigCand.NSRC_PLANCHER_DICO) else c.nsrc

        var s = -ConfigCand.W_DIST * c.distP
        s += ConfigCand.W_FREQ * min(log10(freq + 1.0) / 6.0, 1.0)
        s += ConfigCand.W_NSRC * min(nsrc, 8) / 8.0
        if (c.memeSdx) s += ConfigCand.W_SDX
        if (dico && c.memeSdx && c.distP <= ConfigCand.VAR_MAX_DIST_P) s += ConfigCand.BONUS_VARIANTE
        if (posTag in ConfigCand.POS_NOUN_TAGS && estVerbal && !estNominal) s -= ConfigCand.W_POS
        if (posTag in ConfigCand.POS_VERB_TAGS && estNominal && !estVerbal) s -= ConfigCand.W_POS
        if (c.source == "lexique" && c.nsrc < Config.MIN_SOURCES_FIABLE) s -= ConfigCand.PEN_DOUTEUX
        return s
    }

    /** Damerau-Levenshtein NON RESTREINT, celui de rapidfuzz. */
    /**
     * Ardoise de travail de la distance, allouee une fois par appel et non a chaque paire comparee.
     */
    private class Ardoise(cote: Int) {
        val d = Array(cote + 2) { IntArray(cote + 2) }
        val derniere = HashMap<Char, Int>(64)
    }

    /** Cote de l'ardoise, calcule une fois. */
    private val coteArdoise: Int = maxOf(plusLongMot, 64)

    private fun ardoise(): Ardoise = Ardoise(coteArdoise)

    private fun distBrute(a: String, b: String, cutoff: Int, w: Ardoise = ardoise()): Int {
        if (a == b) return 0
        val la = a.length; val lb = b.length
        if (la == 0) return lb
        if (lb == 0) return la
        if (Math.abs(la - lb) > cutoff) return cutoff + 1

        val maxDist = la + lb
        val d = w.d
        d[0][0] = maxDist
        for (i in 0..la) { d[i + 1][0] = maxDist; d[i + 1][1] = i }
        for (j in 0..lb) { d[0][j + 1] = maxDist; d[1][j + 1] = j }

        val derniere = w.derniere
        derniere.clear()
        for (i in 1..la) {
            var db = 0
            var mini = Int.MAX_VALUE
            for (j in 1..lb) {
                val k = derniere[b[j - 1]] ?: 0
                val l = db
                val cout: Int
                if (a[i - 1] == b[j - 1]) { cout = 0; db = j } else cout = 1
                d[i + 1][j + 1] = minOf(
                    d[i][j] + cout,                                  // substitution
                    d[i + 1][j] + 1,                                 // insertion
                    d[i][j + 1] + 1,                                 // suppression
                    d[k][l] + (i - k - 1) + 1 + (j - l - 1)          // transposition
                )
                if (d[i + 1][j + 1] < mini) mini = d[i + 1][j + 1]
            }
            derniere[a[i - 1]] = i
            if (mini > cutoff) return cutoff + 1
        }
        return d[la + 1][lb + 1]
    }

    /** Candidats triés, « garder » compris. large=true pour le top-5. */
    fun generer(token: String, posTag: String = "", nbMax: Int = 24,
                large: Boolean = false): List<Candidat> {

        // Une seule ardoise pour tout l'appel : c'est la portee qui evite a la
        // fois les vingt mille allocations et le partage entre fils.
        val w = ardoise()

        val keep = Candidat(token, "keep", 0.0, 0,
            res.freq(token), res.nsrc(token), true)

        if ((token in ConfigCand.MOTS_INTOUCHABLES ||
             token in Normalisation.PARTICULES ||
             token in Normalisation.POSSESSIFS || token.length < 2) &&
            token !in ConfigCand.ABREVIATIONS) {
            keep.score = scorer(keep, posTag, ConfigCand.BONUS_KEEP_DICO)
            if (!large) return listOf(keep)
        }

        val bonusKeep: Double
        val niveauDico: Boolean
        when {
            token in ConfigCand.ABREVIATIONS -> {
                bonusKeep = ConfigCand.BONUS_KEEP_OOV; niveauDico = false
            }
            token in res.amyag || res.lexcat(token) != null || token in res.wnFormes -> {
                bonusKeep = ConfigCand.BONUS_KEEP_DICO; niveauDico = true
            }
            res.nsrc(token) >= Config.MIN_SOURCES_FIABLE ||
            res.freq(token) >= Config.FREQ_FIABLE -> {
                bonusKeep = ConfigCand.BONUS_KEEP_SEMI; niveauDico = false
            }
            res.valideParAffixe(token) -> {
                bonusKeep = ConfigCand.BONUS_KEEP_VALIDE; niveauDico = false
            }
            else -> { bonusKeep = ConfigCand.BONUS_KEEP_OOV; niveauDico = false }
        }
        keep.score = scorer(keep, posTag, bonusKeep)

        val sdxTok = Phonologie.soundexKabyle(token)
        val formes = HashSet<String>()

        // Groupe sonore : rattrape ce que la distance seule rate
        res.sdxIndex[sdxTok]?.forEach { i ->
            val cand = res.pool[i]
            if (cand != token && distBrute(token, cand, ConfigCand.MAX_DIST_BRUTE, w)
                    <= ConfigCand.MAX_DIST_BRUTE)
                formes.add(cand)
        }

        // Balayage du vivier, exhaustif : pas de coupe arbitraire.
        if ((large || !niveauDico) && token.length >= 2) {
            val k = ConfigCand.MAX_DIST_BRUTE
            val sigTok = signature(token)
            val lenTok = token.length

            val lo = maxOf(0, lenTok - k)
            val hi = minOf(debutLongueur.size - 2, lenTok + k)
            var i = debutLongueur[lo]
            val fin = debutLongueur[hi + 1]
            while (i < fin) {
                val sc = ordSig[i]
                if (java.lang.Long.bitCount(sigTok and sc.inv()) <= k &&
                    java.lang.Long.bitCount(sc and sigTok.inv()) <= k) {
                    val cand = ordMots[i]!!
                    if (cand != token && distBrute(token, cand, k, w) <= k) formes.add(cand)
                }
                i++
            }
        }

        val abrevs = ConfigCand.ABREVIATIONS[token]?.toSet() ?: emptySet()
        formes.addAll(abrevs)

        val seuil = ConfigCand.seuilDistPonderee(token.length) * (if (large) 1.4 else 1.0)
        val cands = ArrayList<Candidat>()
        cands.add(keep)
        // Ordre alphabétique : rend les ex æquo de score reproductibles
        for (f in formes.sorted()) {
            val estAbrev = f in abrevs
            val dp = if (estAbrev) 0.5 else Phonologie.distanceKabyle(token, f)
            if (!estAbrev && dp > seuil) continue
            val idx = motVersIndex(f)           // -1 : abréviation, hors vivier
            val c = Candidat(
                forme = f,
                source = if (estAbrev) "abrev" else if (idx >= 0) poolSrc[idx]!! else sourceDe(f),
                distP = Math.round(dp * 1000.0) / 1000.0,
                dist = distBrute(token, f, 99, w),
                freq = if (idx >= 0) poolFreq[idx] else res.freq(f),
                nsrc = if (idx >= 0) poolNsrc[idx].toInt() and 0xFF else res.nsrc(f),
                memeSdx = (if (idx >= 0) poolSdx[idx] else Phonologie.soundexKabyle(f)) == sdxTok
            )
            c.score = scorer(c, posTag, bonusKeep)
            cands.add(c)
        }
        return cands.sortedByDescending { it.score }.take(nbMax)
    }

    /** Les nb meilleures formes pour un mot isolé. */
    fun topCandidats(motBrut: String, nb: Int = 5): List<Candidat> {
        val mot = Normalisation.normalize(motBrut)
        fun freqAff(c: Candidat) =
            if (c.source != "lexique" && c.source != "keep")
                maxOf(c.freq, ConfigCand.FREQ_PLANCHER_DICO) else c.freq
        return generer(mot, "", nbMax = 40, large = true)
            .filter { it.forme != mot }
            .sortedWith(
                compareBy({ it.dist }, { -freqAff(it) }, { it.distP }, { it.forme })
            )
            .take(nb)
    }
}
