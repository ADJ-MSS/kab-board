package taqbaylit.moteur

import java.io.File

/** Compare le portage Kotlin à la référence d'or produite par le correcteur Python. */

private class Bilan(val nom: String) {
    var ok = 0
    var ko = 0
    val exemples = ArrayList<String>()
    fun verifie(cond: Boolean, detail: () -> String) {
        if (cond) ok++ else {
            ko++
            if (exemples.size < 5) exemples.add(detail())
        }
    }
    fun rapport(): Boolean {
        val total = ok + ko
        // Zero verification n'est pas zero echec : une reference qui ne se lit
        // pas affichait « OK 0/0 » et le harnais concluait a la conformite.
        val vide = total == 0
        val etat = if (vide) "VIDE  " else if (ko == 0) "OK    " else "ÉCHEC "
        println("  $etat ${nom.padEnd(26)} ${ok}/${total}")
        exemples.forEach { println("           $it") }
        return ko == 0 && !vide
    }
}

/** Lecteur JSON minimal : la référence est produite par nous, pas hostile. */
private object Json {
    fun parse(s: String): Any? = Lecteur(s).valeur()

    private class Lecteur(val s: String) {
        var i = 0
        fun blancs() { while (i < s.length && s[i].isWhitespace()) i++ }
        fun valeur(): Any? {
            blancs()
            return when (s[i]) {
                '{' -> objet()
                '[' -> tableau()
                '"' -> chaine()
                't' -> { i += 4; true }
                'f' -> { i += 5; false }
                'n' -> { i += 4; null }
                else -> nombre()
            }
        }
        fun objet(): LinkedHashMap<String, Any?> {
            val m = LinkedHashMap<String, Any?>()
            i++; blancs()
            if (s[i] == '}') { i++; return m }
            while (true) {
                blancs()
                val k = chaine()
                blancs(); i++            // ':'
                m[k] = valeur()
                blancs()
                if (s[i] == ',') { i++ } else { i++; return m }
            }
        }
        fun tableau(): ArrayList<Any?> {
            val l = ArrayList<Any?>()
            i++; blancs()
            if (s[i] == ']') { i++; return l }
            while (true) {
                l.add(valeur())
                blancs()
                if (s[i] == ',') { i++ } else { i++; return l }
            }
        }
        fun chaine(): String {
            val sb = StringBuilder()
            i++
            while (s[i] != '"') {
                if (s[i] == '\\') {
                    i++
                    when (s[i]) {
                        'n' -> sb.append('\n'); 't' -> sb.append('\t')
                        'r' -> sb.append('\r'); 'b' -> sb.append('\b')
                        'f' -> sb.append('')
                        'u' -> { sb.append(s.substring(i + 1, i + 5).toInt(16).toChar()); i += 4 }
                        else -> sb.append(s[i])
                    }
                } else sb.append(s[i])
                i++
            }
            i++
            return sb.toString()
        }
        fun nombre(): Double {
            val d = i
            while (i < s.length && (s[i].isDigit() || s[i] in "-+.eE")) i++
            return s.substring(d, i).toDouble()
        }
    }
}

@Suppress("UNCHECKED_CAST")
fun main(args: Array<String>) {
    val ref = File(if (args.isNotEmpty()) args[0] else "reference")
    fun charge(n: String) = Json.parse(File(ref, n).readText()) as List<Map<String, Any?>>

    println("\n  Conformité du portage Kotlin contre la référence Python\n")
    val bilans = ArrayList<Bilan>()

    Bilan("normalize").also { b ->
        for (c in charge("01_normalize.json")) {
            val attendu = c["out"] as String
            val obtenu = Normalisation.normalize(c["in"] as String)
            b.verifie(obtenu == attendu) { "« ${c["in"]} » → « $obtenu » ≠ « $attendu »" }
        }
        bilans.add(b)
    }

    Bilan("tokenize").also { b ->
        for (c in charge("02_tokenize.json")) {
            val attendu = (c["out"] as List<Any?>).map { it as String }
            val obtenu = Normalisation.tokenize(c["in"] as String)
            b.verifie(obtenu == attendu) { "« ${c["in"]} » → $obtenu ≠ $attendu" }
        }
        bilans.add(b)
    }

    Bilan("detacher_clitique").also { b ->
        for (c in charge("03_clitiques.json")) {
            val a = (c["out"] as List<Any?>).map { it as String }
            val o = Normalisation.detacherClitique(c["in"] as String)
            val ol = listOf(o.first, o.second, o.third)
            b.verifie(ol == a) { "« ${c["in"]} » → $ol ≠ $a" }
        }
        bilans.add(b)
    }

    Bilan("rejoindre_possessifs").also { b ->
        for (c in charge("04_possessifs.json")) {
            val entree = (c["in"] as List<Any?>).map { it as String }
            val attendu = (c["out"] as List<Any?>).map { it as String }
            val obtenu = Normalisation.rejoindrePossessifs(entree)
            b.verifie(obtenu == attendu) { "$entree → $obtenu ≠ $attendu" }
        }
        bilans.add(b)
    }

    Bilan("soundex_kabyle").also { b ->
        for (c in charge("05_soundex.json")) {
            val attendu = c["out"] as String
            val obtenu = Phonologie.soundexKabyle(c["in"] as String)
            b.verifie(obtenu == attendu) { "« ${c["in"]} » → « $obtenu » ≠ « $attendu »" }
        }
        bilans.add(b)
    }

    Bilan("distance_kabyle").also { b ->
        for (c in charge("06_distance.json")) {
            val attendu = c["d"] as Double
            val obtenu = Phonologie.distanceKabyle(c["a"] as String, c["b"] as String)
            b.verifie(Math.abs(obtenu - attendu) < 1e-9) {
                "« ${c["a"]} » / « ${c["b"]} » → $obtenu ≠ $attendu"
            }
        }
        bilans.add(b)
    }

    println()
    val tout = bilans.all { it.rapport() }
    println("\n  " + if (tout) "CONFORME : le portage reproduit le Python à l'identique."
                     else "NON CONFORME : voir les écarts ci-dessus.")
    if (!tout) kotlin.system.exitProcess(1)
}
