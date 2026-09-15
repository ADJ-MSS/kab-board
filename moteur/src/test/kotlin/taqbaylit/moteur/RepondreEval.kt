package taqbaylit.moteur

import java.io.File

/** Étape 8 : le moteur Kotlin répond aux entrées de l'évaluation. */
@Suppress("UNCHECKED_CAST")
fun main(args: Array<String>) {
    val ref = File(args[0])
    val ressources = File(args[1])
    val data = File(args[2])
    val natif = File(args[3])
    val modeleCrf = File(args[4])
    val sortie = File(args[5])

    val entrees = JsonMini.parse(File(ref, "20_eval_entrees.json").readText())
        as Map<String, Any?>
    val aCorriger = (entrees["corriger"] as List<Any?>).map { it as String }
    val aTop5 = (entrees["top5"] as List<Any?>).map { it as String }

    println("\n  Étape 8 — le moteur Kotlin répond à l'évaluation\n")
    println("  ${aCorriger.size} phrases à corriger, ${aTop5.size} demandes de top-5")

    Correcteur(
        dossierRessources = ressources,
        modeleKenlm = File(data, "kabyle_3gram.binary"),
        modeleCrf = modeleCrf,
        libKenlm = File(natif, "libkenlmjni.so"),
        libCrf = File(natif, "libcrfjni.so")
    ).use { cor ->
        val debut = System.currentTimeMillis()

        val sb = StringBuilder(1 shl 22)
        fun echappe(s: String): String {
            val b = StringBuilder(s.length + 8)
            for (c in s) when (c) {
                '"' -> b.append("\\\""); '\\' -> b.append("\\\\")
                '\n' -> b.append("\\n"); '\r' -> b.append("\\r"); '\t' -> b.append("\\t")
                else -> if (c < ' ') b.append("\\u%04x".format(c.code)) else b.append(c)
            }
            return b.toString()
        }

        sb.append("{\"corriger\":{")
        for ((i, texte) in aCorriger.withIndex()) {
            if (i > 0) sb.append(',')
            sb.append('"').append(echappe(texte)).append("\":\"")
              .append(echappe(cor.corriger(texte).texteCorrige)).append('"')
        }
        sb.append("},\"top5\":{")
        for ((i, cle) in aTop5.withIndex()) {
            if (i > 0) sb.append(',')
            val p = cle.split('\t')
            val cands = cor.topCandidats(p[0], p[1].toInt()).map { it.forme }
            sb.append('"').append(echappe(cle)).append("\":[")
            cands.forEachIndexed { k, f ->
                if (k > 0) sb.append(',')
                sb.append('"').append(echappe(f)).append('"')
            }
            sb.append(']')
        }
        sb.append("}}")

        sortie.writeText(sb.toString())
        val duree = (System.currentTimeMillis() - debut) / 1000.0
        println("  réponses écrites dans ${sortie.name}")
        println("  durée : ${"%.1f".format(duree)} s")
    }
}
