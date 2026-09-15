package taqbaylit.moteur

import java.io.File

/** Étape 4 : le générateur de candidats reproduit-il candidats.py ? */
fun main(args: Array<String>) {
    val refDir = File(if (args.isNotEmpty()) args[0] else "reference")
    val res = Ressources(File(if (args.size > 1) args[1] else "ressources"))
    val gen = Generateur(res)

    val txt = File(refDir, "16_top5_deterministe.json").readText()

    // Analyse minimale : la référence est produite par nous, pas hostile.
    val cas = ArrayList<Pair<String, List<Map<String, String>>>>()
    Regex("\\{\\s*\"mot\":\\s*\"((?:[^\"\\\\]|\\\\.)*)\",\\s*\"cands\":\\s*\\[(.*?)\\]\\s*\\}",
          RegexOption.DOT_MATCHES_ALL).findAll(txt).forEach { m ->
        val mot = m.groupValues[1].replace("\\\"", "\"").replace("\\\\", "\\")
        val cands = Regex("\\{(.*?)\\}", RegexOption.DOT_MATCHES_ALL)
            .findAll(m.groupValues[2]).map { c ->
                val champs = HashMap<String, String>()
                Regex("\"(\\w+)\":\\s*(\"(?:[^\"\\\\]|\\\\.)*\"|[-\\d.eE]+)")
                    .findAll(c.groupValues[1]).forEach { f ->
                        champs[f.groupValues[1]] =
                            f.groupValues[2].trim('"').replace("\\\"", "\"").replace("\\\\", "\\")
                    }
                champs
            }.toList()
        cas.add(mot to cands)
    }

    println("\n  Étape 4 — conformité du générateur de candidats")
    println("  ${cas.size} mots à vérifier\n")

    // Un harnais qui ne lit rien annonce « CONFORME » sur zéro cas, et certifie ainsi un portage
    // cassé.
    if (cas.isEmpty()) {
        println("  TEST VIDE : la référence n'a pas été lue.")
        kotlin.system.exitProcess(2)
    }

    var identiques = 0
    var formesOk = 0
    var ko = 0
    val exemples = ArrayList<String>()
    val debut = System.currentTimeMillis()

    for ((mot, attendus) in cas) {
        val obtenus = gen.topCandidats(mot, 5)
        val fA = attendus.map { it["forme"]!! }
        val fO = obtenus.map { it.forme }

        if (fO == fA) {
            formesOk++
            // champs détaillés : source, distances, fréquences
            var tout = true
            for ((i, a) in attendus.withIndex()) {
                val o = obtenus[i]
                if (o.source != a["source"] ||
                    o.dist != a["dist"]!!.toInt() ||
                    Math.abs(o.distP - a["dist_p"]!!.toDouble()) > 1e-9 ||
                    o.freq != a["freq"]!!.toInt() ||
                    o.nsrc != a["nsrc"]!!.toInt() ||
                    Math.abs(o.score - a["score"]!!.toDouble()) > 1e-5) {
                    tout = false
                    if (exemples.size < 5) exemples.add(
                        "« $mot » [$i] ${o.forme} : src ${o.source}/${a["source"]} " +
                        "d ${o.dist}/${a["dist"]} dp ${o.distP}/${a["dist_p"]} " +
                        "score ${o.score}/${a["score"]}")
                    break
                }
            }
            if (tout) identiques++ else ko++
        } else {
            ko++
            if (exemples.size < 5) exemples.add("« $mot »\n             obtenu   $fO\n             attendu  $fA")
        }
    }
    val duree = (System.currentTimeMillis() - debut) / 1000.0

    println("  formes du top-5 identiques   : $formesOk/${cas.size}" +
            "  (${"%.2f".format(formesOk * 100.0 / cas.size)} %)")
    println("  + tous les champs identiques : $identiques/${cas.size}" +
            "  (${"%.2f".format(identiques * 100.0 / cas.size)} %)")
    println("  écarts                       : $ko")
    println("  durée                        : ${"%.1f".format(duree)} s" +
            "   soit ${"%.0f".format(duree * 1000 / cas.size)} ms par mot")
    exemples.forEach { println("      $it") }

    println("\n  " + if (ko == 0) "CONFORME : le générateur reproduit le Python."
                     else "NON CONFORME.")
    if (ko != 0) kotlin.system.exitProcess(1)
}
