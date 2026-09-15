package taqbaylit.moteur

import java.io.File

/** Étape 7 : la chaîne complète reproduit-elle corriger() ? */
@Suppress("UNCHECKED_CAST")
fun main(args: Array<String>) {
    val ref = File(args.getOrElse(0) { "reference" })
    val ressources = File(args.getOrElse(1) { "ressources" })
    val data = File(args[2])
    val natif = File(args[3])

    println("\n  Étape 7 — conformité de la chaîne complète\n")

    val cas = JsonMini.parse(File(ref, "19_corriger.json").readText()) as List<Map<String, Any?>>
    println("  ${cas.size} phrases de référence chargées")

    Correcteur(
        dossierRessources = ressources,
        modeleKenlm = File(data, "kabyle_3gram.binary"),
        modeleCrf = File(args[4]),
        libKenlm = File(natif, "libkenlmjni.so"),
        libCrf = File(natif, "libcrfjni.so")
    ).use { cor ->

        var ok = 0; var ko = 0
        val ex = ArrayList<String>()
        val debut = System.currentTimeMillis()

        for (c in cas) {
            val entree = c["in"] as String
            val attendu = c["out"] as String
            val obtenu = cor.corriger(entree).texteCorrige
            if (obtenu == attendu) ok++ else {
                ko++
                if (ex.size < 8) ex.add(
                    "  « $entree »\n       obtenu   « $obtenu »\n       attendu  « $attendu »")
            }
        }
        val duree = (System.currentTimeMillis() - debut) / 1000.0

        if (ok + ko == 0) {
            println("  TEST VIDE : la référence n'a pas été lue.")
            kotlin.system.exitProcess(2)
        }
        println("  ${if (ko == 0) "OK    " else "ÉCHEC "} phrases corrigées" +
                "          $ok/${ok + ko}  (${"%.2f".format(ok * 100.0 / (ok + ko))} %)")
        println("  durée : ${"%.1f".format(duree)} s" +
                "   soit ${"%.0f".format(duree * 1000 / (ok + ko))} ms par phrase")
        ex.forEach { println(it) }

        println("\n  " + if (ko == 0) "CONFORME : la chaîne complète reproduit le Python."
                         else "NON CONFORME.")
        if (ko != 0) kotlin.system.exitProcess(1)
    }
}
