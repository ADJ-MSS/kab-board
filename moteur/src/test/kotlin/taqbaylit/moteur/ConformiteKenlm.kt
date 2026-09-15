package taqbaylit.moteur

import java.io.File

/** Étape 5 : le pont JNI donne-t-il les mêmes scores que le module Python ? */
fun main(args: Array<String>) {
    val ref = File(if (args.isNotEmpty()) args[0] else "reference")
    val modele = File(args[1])
    ModeleLangue.chargerBibliotheque(File(args[2]))

    val txt = File(ref, "17_kenlm.json").readText()

    println("\n  Étape 5 — conformité de KenLM via JNI\n")

    ModeleLangue.ouvrir(modele).use { lm ->
        println("  ordre du modèle : ${lm.ordre}")

        var okBase = 0; var koBase = 0
        var okBos = 0; var koBos = 0
        var okNu = 0; var koNu = 0
        val ex = ArrayList<String>()
        var ecartMax = 0.0

        val bloc = Regex("\\{\\s*\"toks\":\\s*\\[(.*?)\\]\\s*,\\s*\"base\":\\s*\\[(.*?)\\]\\s*," +
                         "\\s*\"s_bos_eos\":\\s*([-\\d.eE]+)\\s*,\\s*\"s_nu\":\\s*([-\\d.eE]+)\\s*\\}")
        for (m in bloc.findAll(txt)) {
            val toks = Regex("\"((?:[^\"\\\\]|\\\\.)*)\"").findAll(m.groupValues[1])
                .map { it.groupValues[1].replace("\\\"", "\"").replace("\\\\", "\\") }.toList()
            val base = m.groupValues[2].split(',').map { it.trim().toFloat() }
            val sBos = m.groupValues[3].toFloat()
            val sNu = m.groupValues[4].toFloat()
            if (toks.isEmpty()) continue

            // BaseScore pas à pas, comme le décodeur
            lm.etat().use { e ->
                lm.etat().use { s ->
                    lm.debutPhrase(e)
                    for ((i, t) in toks.withIndex()) {
                        val v = lm.baseScore(e, t, s)
                        val d = Math.abs(v - base[i]).toDouble()
                        if (d > ecartMax) ecartMax = d
                        if (d < 1e-4) okBase++ else {
                            koBase++
                            if (ex.size < 5) ex.add("« $t » $v ≠ ${base[i]}")
                        }
                        lm.copier(s, e)
                    }
                    val v = lm.baseScore(e, "</s>", s)
                    val d = Math.abs(v - base[toks.size]).toDouble()
                    if (d > ecartMax) ecartMax = d
                    if (d < 1e-4) okBase++ else koBase++
                }
            }

            val phrase = toks.joinToString(" ")
            if (Math.abs(lm.score(phrase, true, true) - sBos) < 1e-3) okBos++ else {
                koBos++
                if (ex.size < 5) ex.add("score bos/eos « $phrase » " +
                    "${lm.score(phrase, true, true)} ≠ $sBos")
            }
            if (Math.abs(lm.score(phrase, false, false) - sNu) < 1e-3) okNu++ else koNu++
        }

        fun ligne(n: String, ok: Int, ko: Int) =
            println("  ${if (ko == 0) "OK    " else "ÉCHEC "} ${n.padEnd(26)} ${ok}/${ok + ko}")

        ligne("BaseScore mot à mot", okBase, koBase)
        ligne("score(phrase, bos, eos)", okBos, koBos)
        ligne("score(phrase, nu)", okNu, koNu)
        println("  écart maximal observé      : ${"%.2e".format(ecartMax)}")
        ex.forEach { println("      $it") }

        // Un test qui ne vérifie rien n'est pas un test qui passe.
        if (okBase + koBase == 0 || okBos + koBos == 0) {
            println("\n  TEST VIDE : la référence n'a pas été lue, rien n'a été vérifié.")
            kotlin.system.exitProcess(2)
        }
        val bon = koBase == 0 && koBos == 0 && koNu == 0
        println("\n  " + if (bon) "CONFORME : KenLM répond comme en Python." else "NON CONFORME.")
        if (!bon) kotlin.system.exitProcess(1)
    }
}
