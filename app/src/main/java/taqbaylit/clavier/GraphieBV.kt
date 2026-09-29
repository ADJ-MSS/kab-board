package taqbaylit.clavier

import android.content.Context

/**
 * Les mots qui s'ecrivent avec b ou avec v, selon le reglage.
 *
 * En aval du moteur : on recoit des formes deja calculees, on rend les memes
 * autrement ecrites. La table ne liste que des formes de base, alors un mot
 * flechi est ramene a l'une d'elles : segments d'un mot a tirets, etat
 * d'annexion, annexion en we-, pluriel i…en. Sans cela une phrase melange les
 * deux graphies. Un mot inconnu de la table ressort tel quel.
 */
object GraphieBV {

    /** Le reglage de l'utilisateur : tout en b, ou tout en v. */
    enum class Mode { B, V }

    private const val FICHIER = "graphie/table_bv.tsv"

    private var versV: Map<String, String> = emptyMap()
    private var versB: Map<String, String> = emptyMap()

    val chargee: Boolean get() = versV.isNotEmpty()

    /** Lit la table. Sans effet si elle l'est deja. A appeler hors du fil principal. */
    fun charger(context: Context) {
        if (chargee) return
        runCatching {
            context.assets.open(FICHIER).bufferedReader().useLines { charger(it) }
        }
    }

    /** Pour les tests : la table depuis des lignes deja ouvertes. */
    internal fun charger(lignes: Sequence<String>) {
        val v = HashMap<String, String>(16384)
        val b = HashMap<String, String>(16384)
        for (ligne in lignes) {
            if (ligne.isEmpty() || ligne.startsWith("forme_b")) continue
            val champs = ligne.split('\t')
            if (champs.size < 2) continue
            val (fb, fv) = champs[0] to champs[1]
            if (fb.isEmpty() || fv.isEmpty()) continue
            v[fb] = fv
            b[fv] = fb
        }
        versV = v
        versB = b
    }

    /** Les deux formes du mot, dans sa casse, ou null s'il n'alterne pas. */
    fun paire(mot: String): Pair<String, String>? {
        val m = mot.lowercase()
        if (versV.containsKey(m)) return casserComme(mot, m) to casserComme(mot, versV.getValue(m))
        if (versB.containsKey(m)) return casserComme(mot, versB.getValue(m)) to casserComme(mot, m)
        if (mot.contains('-')) return paireATirets(mot)
        return paireFlechie(mot, m)
    }

    /** Chaque segment pour son compte : baba-s -> vava-s, d-nebder -> d-nevder. */
    private fun paireATirets(mot: String): Pair<String, String>? {
        val segments = mot.split("-")
        val paires = segments.map { if (it.isEmpty()) null else paire(it) }
        if (paires.all { it == null }) return null
        val b = segments.indices.joinToString("-") { paires[it]?.first ?: segments[it] }
        val v = segments.indices.joinToString("-") { paires[it]?.second ?: segments[it] }
        return b to v
    }

    /** Forme flechie : la table donne le lexeme, l'annexion ne deplace jamais le b. */
    private fun paireFlechie(mot: String, m: String): Pair<String, String>? {
        for (cle in reductions(m)) {
            if (versV.containsKey(cle)) return mot to lettresBasculees(mot, true)
            if (versB.containsKey(cle)) return lettresBasculees(mot, false) to mot
        }
        return null
    }

    /** Les formes de base que ce mot pourrait flechir, la plus sure d'abord. */
    private fun reductions(mot: String): List<String> {
        val vues = LinkedHashSet<String>()
        when {
            R_WU_CONS.containsMatchIn(mot) -> vues.add("u" + mot.substring(2))
            R_WA.containsMatchIn(mot) -> vues.add("a" + mot.substring(2))
            R_WE_CONS.containsMatchIn(mot) -> vues.add("a" + mot.substring(2))
            R_YE_CONS.containsMatchIn(mot) -> vues.add("i" + mot.substring(2))
            R_YI.containsMatchIn(mot) -> vues.add("i" + mot.substring(2))
            R_U_CONS.containsMatchIn(mot) -> vues.add("a" + mot.substring(1))
            R_TE_CONS.containsMatchIn(mot) -> vues.add("ta" + mot.substring(2))
            R_T_CONS.containsMatchIn(mot) && !R_TAIU.containsMatchIn(mot) ->
                vues.add("ta" + mot.substring(1))
        }
        for (base in vues.toList() + mot) {                 // le pluriel d'une forme annexee
            val m = R_PLURIEL.find(base) ?: continue
            vues.add("a" + m.groupValues[1])
        }
        return vues.filter { it != mot && it.length >= 3 }
    }

    /** Tous les b en v, ou l'inverse : la table ne fait jamais autre chose. */
    private fun lettresBasculees(mot: String, enV: Boolean): String =
        if (enV) mot.replace("b", "v").replace("B", "V")
        else mot.replace("v", "b").replace("V", "B")

    /** Le mot dans la graphie reglee. Inchange s'il n'alterne pas. */
    fun basculer(mot: String, mode: Mode): String {
        val (fb, fv) = paire(mot) ?: return mot
        return if (mode == Mode.V) fv else fb
    }

    /** Une liste de propositions. Deux formes qui se rejoignent liberent une place. */
    fun appliquer(formes: List<String>, mode: Mode): List<String> =
        formes.map { basculer(it, mode) }.distinct()

    /** Un texte entier, mot a mot : la dictee, dont le modele vocal ne connait que le b. */
    fun appliquerTexte(texte: String, mode: Mode): String =
        MOTS.replace(texte) { basculer(it.value, mode) }

    private val MOTS = Regex("[\\p{L}-]+")

    // L'etat libre, comme moteur/Postprocess.versLibreBase, plus la regle we-
    // qu'il ne produit pas. Ces regles ne fabriquent qu'une cle de recherche :
    // une reduction fausse ne fait rien, sinon manquer la table.
    private const val CONS = "[bcdfghjklmnpqrstvwxyzɣɛḍṭṛṣẓčšžɣ]"
    private val R_WU_CONS = Regex("^wu$CONS")
    private val R_WA = Regex("^wa")
    private val R_WE_CONS = Regex("^we$CONS")
    private val R_YE_CONS = Regex("^ye$CONS")
    private val R_YI = Regex("^yi")
    private val R_U_CONS = Regex("^u$CONS")
    private val R_TE_CONS = Regex("^te$CONS")
    private val R_T_CONS = Regex("^t$CONS")
    private val R_TAIU = Regex("^(ta|ti|tu)")
    // Le pluriel des noms masculins : iɣriben <- aɣrib, ibridan <- abrid.
    private val R_PLURIEL = Regex("^i($CONS.+?)(en|an)$")

    /** Reporte la casse du modele : Abrid -> Avrid, ABRID -> AVRID. */
    private fun casserComme(modele: String, mot: String): String = when {
        modele.length > 1 && modele == modele.uppercase() -> mot.uppercase()
        modele.firstOrNull()?.isUpperCase() == true ->
            mot.replaceFirstChar { it.uppercaseChar() }
        else -> mot
    }
}
