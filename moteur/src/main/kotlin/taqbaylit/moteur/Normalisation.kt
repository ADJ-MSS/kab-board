package taqbaylit.moteur

import java.text.Normalizer

/** Port de pipeline/v2/normalisation.py. */
object Normalisation {

    /** L'ordre compte : une HashMap donnerait un résultat dépendant du hachage. */
    private val NORM_TABLE = linkedMapOf(
        "gh" to "ɣ", "aa" to "ɛ", "ou" to "u", "dh" to "ḍ",
        "th" to "t", "kh" to "x", "ch" to "c"
    )

    /** Géminées d'abord, sinon le remplacement est partiel. */
    private val LABIALISEES = listOf(
        "ggʷ" to "ww", "bbʷ" to "ww", "ppʷ" to "ww",
        "gʷ" to "g", "bʷ" to "b", "pʷ" to "p"
    )

    private val TOKEN_RE =
        Regex("[a-zàâæçéèêëîïôœùûüÿɣɛḍṭxṛṣẓčšžɣḥǧ'\\-]+", RegexOption.IGNORE_CASE)

    val PARTICULES = setOf("n", "d", "i", "g", "s", "w")
    private val UN_CHAR_GARDES = PARTICULES + "ɣ"

    val POSSESSIFS = setOf("iw", "ik", "im", "is", "nneɣ", "nwen", "nkent", "nsen", "nsent")

    val CLITIQUES_SUFF = POSSESSIFS + setOf(
        "d",
        "yas", "yasen", "yasent",
        "yi",
        "ak", "am",
        "nni", "ni"
    )

    val PREFIXES_DIRECTIONNELS = setOf("d", "as", "aɣ", "iyi", "ak", "am", "ay")

    fun normalize(t: String): String {
        var s = Normalizer.normalize(t.lowercase().trim(), Normalizer.Form.NFC)
        for ((k, v) in LABIALISEES) s = s.replace(k, v)
        for ((k, v) in NORM_TABLE) s = s.replace(k, v)
        return s
    }

    fun tokenize(t: String): List<String> =
        TOKEN_RE.findAll(normalize(t))
            .map { it.value }
            .filter { it.length >= 2 || it in UN_CHAR_GARDES }
            .toList()

    /** (prefixe, base, suffixe), tiret compris. */
    fun detacherClitique(tok: String): Triple<String, String, String> {
        val pos = tok.lastIndexOf('-')
        if (pos > 1) {
            val base = tok.substring(0, pos)
            val suf = tok.substring(pos + 1)
            if (suf in CLITIQUES_SUFF) return Triple("", base, "-$suf")
        }
        if (tok.count { it == '-' } == 1) {
            val i = tok.indexOf('-')
            val pref = tok.substring(0, i)
            val base = tok.substring(i + 1)
            if (pref in PREFIXES_DIRECTIONNELS && base.length >= 2)
                return Triple("$pref-", base, "")
        }
        return Triple("", tok, "")
    }

    fun rejoindrePossessifs(tokens: List<String>): List<String> {
        if (tokens.size < 2) return tokens
        val out = ArrayList<String>(tokens.size)
        for ((i, tok) in tokens.withIndex()) {
            if (i > 0 && tok in POSSESSIFS && out.isNotEmpty())
                out[out.size - 1] = out[out.size - 1] + "-" + tok
            else out.add(tok)
        }
        return out
    }
}
