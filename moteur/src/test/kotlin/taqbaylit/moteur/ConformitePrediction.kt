package taqbaylit.moteur

import java.io.File

/** La prediction du mot suivant. */
fun main(args: Array<String>) {
    val res = Ressources(File(args[0]))
    ModeleLangue.chargerBibliotheque(File(args[1], "libkenlmjni.so"))
    val lm = ModeleLangue.ouvrir(File(args[0], "kabyle_3gram.binary"))
    val p = Prediction(lm, res.frequents)

    println("\n  Prediction du mot suivant\n")
    println("  candidats charges : ${res.frequents.size}")

    var echecs = 0
    fun verifier(nom: String, ok: Boolean) {
        println("  ${if (ok) "OK    " else "ECHEC "} $nom")
        if (!ok) echecs++
    }

    verifier("les candidats sont charges", res.frequents.size == 5000)
    verifier("disponible quand les candidats existent", p.disponible)

    val contextes = listOf(
        "ruḥeɣ ɣer", "yečča", "azul", "ad", "ɣer tmurt n", "aqcic yečča")
    println()
    for (c in contextes) {
        val t0 = System.nanoTime()
        val r = p.suivants(c, 5)
        println("  %-16s -> %-46s %3d ms".format(c, r.joinToString(", "), (System.nanoTime() - t0) / 1_000_000))
    }
    println()

    verifier("une reponse pour chaque contexte connu",
        contextes.all { p.suivants(it, 5).size == 5 })
    verifier("aucun doublon dans une reponse",
        contextes.all { val r = p.suivants(it, 5); r.size == r.distinct().size })
    verifier("deterministe d'une execution a l'autre",
        contextes.all { p.suivants(it, 5) == p.suivants(it, 5) })
    verifier("le nombre demande est respecte", p.suivants("ruḥeɣ ɣer", 3).size == 3)

    // Un contexte inconnu ne doit pas jeter : le repli de KenLM le ramene sur
    // un contexte plus court, jusqu'aux unigrammes s'il le faut.
    verifier("un contexte inconnu ne fait pas tomber",
        runCatching { p.suivants("zzzqqq xxxwww", 5) }.isSuccess)

    // Sans candidats, la prediction se tait au lieu de deviner.
    val muet = Prediction(lm, emptyList())
    verifier("sans candidats, aucune reponse", !muet.disponible && muet.suivants("azul", 5).isEmpty())

    // La coupe de phrase : ce qui suit le dernier point est seul pris en compte.
    verifier("la phrase precedente n'influence pas la suivante",
        p.suivants("aqcic yečča aɣrum. ruḥeɣ ɣer", 5) == p.suivants("ruḥeɣ ɣer", 5))

    lm.close()
    println()
    if (echecs == 0) println("  CONFORME : la prediction tient ses invariants.\n")
    else { println("  $echecs invariant(s) rompu(s)\n"); kotlin.system.exitProcess(1) }
}
