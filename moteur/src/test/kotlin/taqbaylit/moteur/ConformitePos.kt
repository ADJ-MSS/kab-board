package taqbaylit.moteur

import java.io.File

/** Étape 6 : l'étiqueteur natif donne-t-il les mêmes séquences que le Python ? */
fun main(args: Array<String>) {
    val ref = File(if (args.isNotEmpty()) args[0] else "reference")
    Etiqueteur.chargerBibliotheque(File(args[2]))

    val txt = File(ref, "18_pos.json").readText()
    val bloc = Regex("\\{\\s*\"toks\":\\s*\\[(.*?)\\]\\s*,\\s*\"tags\":\\s*\\[(.*?)\\]\\s*\\}")
    val chaine = Regex("\"((?:[^\"\\\\]|\\\\.)*)\"")
    fun liste(s: String) = chaine.findAll(s)
        .map { it.groupValues[1].replace("\\\"", "\"").replace("\\\\", "\\") }.toList()

    println("\n  Étape 6 — conformité de l'étiqueteur CRF\n")

    Etiqueteur.ouvrir(File(args[1])).use { tag ->
        println("  étiquettes du modèle : ${tag.nbEtiquettes}")

        var phrasesOk = 0; var phrasesKo = 0
        var motsOk = 0; var motsKo = 0
        val ex = ArrayList<String>()

        for (m in bloc.findAll(txt)) {
            val toks = liste(m.groupValues[1])
            val attendus = liste(m.groupValues[2])
            if (toks.isEmpty()) continue
            val obtenus = tag.etiqueter(toks)
            for (i in toks.indices) {
                if (i < obtenus.size && i < attendus.size && obtenus[i] == attendus[i]) motsOk++
                else {
                    motsKo++
                    if (ex.size < 6) ex.add(
                        "« ${toks[i]} » → ${obtenus.getOrNull(i)} ≠ ${attendus.getOrNull(i)}" +
                        "   dans « ${toks.joinToString(" ")} »")
                }
            }
            if (obtenus == attendus) phrasesOk++ else phrasesKo++
        }

        if (motsOk + motsKo == 0) {
            println("\n  TEST VIDE : la référence n'a pas été lue.")
            kotlin.system.exitProcess(2)
        }
        println("  ${if (phrasesKo == 0) "OK    " else "ÉCHEC "} phrases entières" +
                "            $phrasesOk/${phrasesOk + phrasesKo}")
        println("  ${if (motsKo == 0) "OK    " else "ÉCHEC "} étiquettes mot à mot" +
                "        $motsOk/${motsOk + motsKo}" +
                "  (${"%.2f".format(motsOk * 100.0 / (motsOk + motsKo))} %)")
        ex.forEach { println("      $it") }

        val bon = phrasesKo == 0 && motsKo == 0
        println("\n  " + if (bon) "CONFORME : l'étiqueteur reproduit le Python." else "NON CONFORME.")
        if (!bon) kotlin.system.exitProcess(1)
    }
}
