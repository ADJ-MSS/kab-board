package taqbaylit.moteur

import java.io.File

/**
 * Port de pipeline/v2/postprocess.py : état d'annexion (Chaker 1988) et rattachement des
 * possessifs.
 */
class Postprocess(dossier: File, private val lm: ModeleLangue?) {

    private val listes: Map<String, Set<String>> = run {
        val m = HashMap<String, MutableSet<String>>()
        var courante: MutableSet<String>? = null
        File(dossier, "listes.txt").forEachLine { l ->
            if (l.startsWith("[") && l.endsWith("]"))
                courante = m.getOrPut(l.substring(1, l.length - 1)) { LinkedHashSet() }
            else if (l.isNotEmpty()) courante?.add(l)
        }
        m
    }

    private fun liste(n: String) = listes[n] ?: emptySet()
    private val verbesWhitelist = liste("verbes_whitelist")
    private val nomsInvariables = liste("noms_invariables")
    private val numeraux = liste("numeraux")
    private val prepAnnexion = liste("prep_annexion")
    private val prepLibre = liste("prep_libre")
    private val etatLibreForce = liste("etat_libre_force")

    private companion object {
        const val CONS = "[bcdfghjklmnpqrstvwxyzɣɛḍṭṛṣẓčšžɣ]"
        val VOYELLES_ETENDUES = setOf('a', 'e', 'i', 'o', 'u', 'ɛ')
        const val LM_REJET_CHAKER = 2.5

        val R_U_CONS = Regex("^u$CONS")
        val R_A_GEM_SOURDE = Regex("^a(xx|ɣɣ|qq|ṭṭ|ḍḍ|ẓẓ|čč|šš|ṛṛ|ṣṣ)")
        val R_A_GEM_AUTRE = Regex("^a(ss|mm|ff|bb|nn|ll|rr|tt|dd|gg|kk|ww)")
        val R_AM_VOY = Regex("^am[aeiou]")
        val R_A_CONS = Regex("^a$CONS")
        val R_I_CONS_EN = Regex("^i$CONS.+en$")
        val R_I_LRFWMNB = Regex("^i[lrfwmnb]")
        val R_TA_CONS = Regex("^ta$CONS")
        val R_TI_CONS = Regex("^ti$CONS")
        val R_TU_CONS = Regex("^tu$CONS")
        val R_WU_CONS = Regex("^wu$CONS")
        val R_WA = Regex("^wa")
        val R_YE_CONS = Regex("^ye$CONS")
        val R_YI = Regex("^yi")
        val R_TE_CONS = Regex("^te$CONS")
        val R_T_CONS = Regex("^t$CONS")
        val R_TAIU = Regex("^(ta|ti|tu)")
        val R_I_CONS = Regex("^i$CONS")
        val R_REPETE = Regex("(.)\\1+")

        val LEXCAT_NOMINAL = setOf("masc", "fem", "fem_pl", "adj_masc", "adj_fem", "ambig")
    }

    private fun aTripleConsonne(motIn: String): Boolean {
        val mot = R_REPETE.replace(motIn) { it.groupValues[1] }
        var n = 0
        for (c in mot) {
            if (c !in VOYELLES_ETENDUES) { n++; if (n >= 3) return true } else n = 0
        }
        return false
    }

    private fun versAnnexionBase(base: String): String {
        if (base in verbesWhitelist || base in numeraux) return base
        if (R_U_CONS.containsMatchIn(base)) return "wu" + base.substring(1)
        if (R_A_GEM_SOURDE.containsMatchIn(base)) return "wu" + base.substring(1)
        if (R_A_GEM_AUTRE.containsMatchIn(base)) return "wa" + base.substring(1)
        if (R_AM_VOY.containsMatchIn(base)) return "wa" + base.substring(1)
        if (R_A_CONS.containsMatchIn(base)) return "u" + base.substring(1)
        if (R_I_CONS_EN.containsMatchIn(base)) return "ye" + base.substring(1)
        if (R_I_LRFWMNB.containsMatchIn(base)) return "yi" + base.substring(1)
        if (R_TA_CONS.containsMatchIn(base)) {
            val cand = "t" + base.substring(2)
            return if (aTripleConsonne(cand)) "te" + base.substring(2) else cand
        }
        if (R_TI_CONS.containsMatchIn(base)) return "te" + base.substring(2)
        return base
    }

    private fun versLibreBase(base: String): String {
        if (base in verbesWhitelist || base in numeraux) return base
        if (R_WU_CONS.containsMatchIn(base)) return "u" + base.substring(2)
        if (R_WA.containsMatchIn(base)) return "a" + base.substring(2)
        if (R_YE_CONS.containsMatchIn(base)) return "i" + base.substring(2)
        if (R_YI.containsMatchIn(base)) return "i" + base.substring(2)
        if (R_U_CONS.containsMatchIn(base)) return "a" + base.substring(1)
        if (R_TE_CONS.containsMatchIn(base)) return "ta" + base.substring(2)
        if (R_T_CONS.containsMatchIn(base) && !R_TAIU.containsMatchIn(base))
            return "ta" + base.substring(1)
        return base
    }

    private fun avecSuffixe(mot: String, f: (String) -> String): String {
        if (mot in nomsInvariables) return mot
        val p = mot.split("-")
        val suf = if (p.size > 1) "-" + p.drop(1).joinToString("-") else ""
        return f(p[0]) + suf
    }

    fun versAnnexion(mot: String) = avecSuffixe(mot, ::versAnnexionBase)
    fun versLibre(mot: String) = avecSuffixe(mot, ::versLibreBase)

    /** (est un nom, état, type) */
    fun identifierNomEtat(mot: String): Triple<Boolean, String?, String?> {
        val base = mot.split("-")[0]
        if (base in verbesWhitelist) return Triple(false, null, null)
        if (base in numeraux) return Triple(false, null, null)
        if (base in nomsInvariables) return Triple(true, "invariable", "syncrétisme")
        if (R_WU_CONS.containsMatchIn(base)) return Triple(true, "annexion", "Type3")
        if (R_WA.containsMatchIn(base)) return Triple(true, "annexion", "Type2")
        if (R_YE_CONS.containsMatchIn(base)) return Triple(true, "annexion", "Type4")
        if (R_YI.containsMatchIn(base)) return Triple(true, "annexion", "Type5")
        if (R_U_CONS.containsMatchIn(base)) return Triple(true, "annexion", "Type1")
        if (R_A_CONS.containsMatchIn(base)) return Triple(true, "libre", "Type1/2")
        if (R_I_CONS.containsMatchIn(base)) return Triple(true, "libre", "Type4/5/6")
        if (R_TE_CONS.containsMatchIn(base)) return Triple(true, "annexion", "Type7/10")
        if (R_T_CONS.containsMatchIn(base) && !R_TAIU.containsMatchIn(base))
            return Triple(true, "annexion", "Type7")
        if (R_TA_CONS.containsMatchIn(base)) return Triple(true, "libre", "Type7")
        if (R_TI_CONS.containsMatchIn(base)) return Triple(true, "libre", "Type10/11")
        if (R_TU_CONS.containsMatchIn(base)) return Triple(true, "libre", "Type9")
        return Triple(false, null, null)
    }

    private fun contexteAnnexion(tokens: List<String>, idx: Int): Pair<String?, String?> {
        if (idx == 0) return "libre" to "sujet initial"
        val prec = tokens[idx - 1].split("-")[0].lowercase()
        if (prec in etatLibreForce) return "libre" to "après '$prec'"
        if (prec in prepLibre) return "libre" to "après '$prec' (exception Chaker)"
        if (prec in prepAnnexion) return "annexion" to "après préposition '$prec'"
        if (prec in numeraux) return "annexion" to "après numéral '$prec'"
        if (prec in verbesWhitelist) return "annexion" to "sujet post-verbal après '$prec'"
        return null to null
    }

    data class Proposition(val idx: Int, val avant: String, val apres: String, val raison: String)

    fun propositionsChaker(tokens: List<String>, verbes: Set<String>?,
                           lexcat: ((String) -> String?)?): List<Proposition> {
        val out = ArrayList<Proposition>()
        for ((i, tok) in tokens.withIndex()) {
            if (verbes != null && (tok in verbes || tok.split("-")[0] in verbes)) continue
            var (estN, etat, _) = identifierNomEtat(tok)
            val cat = lexcat?.invoke(tok)
            if (cat != null && cat in LEXCAT_NOMINAL) {
                estN = true
                if (etat == "invariable") etat = "libre"
            }
            if (!estN || etat == "invariable") continue
            val (requis, raison) = contexteAnnexion(tokens, i)
            if (requis == null) continue
            val forme = when {
                requis == "annexion" && etat == "libre" -> versAnnexion(tok)
                requis == "libre" && etat == "annexion" -> versLibre(tok)
                else -> continue
            }
            if (forme != tok) out.add(Proposition(i, tok, forme, raison ?: ""))
        }
        return out
    }

    /** Chaker, chaque réécriture annulée si le modèle de langue chute de trop. */
    fun appliquerChakerValideLm(tokens: List<String>, verbes: Set<String>?,
                                lexcat: ((String) -> String?)?
    ): Pair<List<String>, List<Proposition>> {
        val corrigee = ArrayList(tokens)
        val corrections = ArrayList<Proposition>()
        for (p in propositionsChaker(tokens, verbes, lexcat)) {
            if (lm != null) {
                val avantS = corrigee.joinToString(" ")
                val essai = ArrayList(corrigee)
                essai[p.idx] = p.apres
                val delta = lm.score(essai.joinToString(" "), true, true) -
                            lm.score(avantS, true, true)
                if (delta < -LM_REJET_CHAKER) continue
            }
            corrigee[p.idx] = p.apres
            corrections.add(p)
        }
        return corrigee to corrections
    }
}
