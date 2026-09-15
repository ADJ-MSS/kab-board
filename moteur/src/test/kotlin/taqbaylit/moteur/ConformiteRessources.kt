package taqbaylit.moteur

import java.io.File

/** Étape 3 : le chargement des ressources reproduit-il ressources.py ? */
fun main(args: Array<String>) {
    val ref = File(if (args.isNotEmpty()) args[0] else "reference")
    val res = Ressources(File(if (args.size > 1) args[1] else "ressources"))

    var global = true
    fun bilan(nom: String, ok: Int, ko: Int, ex: List<String>) {
        // Un controle qui ne compare rien n'est pas un controle reussi.
        val vide = ok + ko == 0
        val etat = if (vide) "VIDE  " else if (ko == 0) "OK    " else "ÉCHEC "
        println("  $etat ${nom.padEnd(28)} ${ok}/${ok + ko}")
        ex.take(5).forEach { println("           $it") }
        if (ko != 0 || vide) global = false
    }

    println("\n  Étape 3 — conformité des ressources\n")

    // 1. lexique : mot, fréquence, nombre de sources, sur les 1 587 517
    run {
        var ok = 0; var ko = 0; val ex = ArrayList<String>()
        var i = 0
        File(ref, "09_lexique.tsv").forEachLine { l ->
            val p = l.split('\t')
            val mot = p[0]
            val fOk = res.freq(mot) == p[1].toInt()
            val nOk = res.nsrc(mot) == p[2].toInt()
            val iOk = res.lexique[i] == mot
            if (fOk && nOk && iOk) ok++ else {
                ko++
                if (ex.size < 5) ex.add("« $mot » freq ${res.freq(mot)}/${p[1]} " +
                        "nsrc ${res.nsrc(mot)}/${p[2]} ordre ${res.lexique[i]}")
            }
            i++
        }
        bilan("lexique (freq, nsrc, ordre)", ok, ko, ex)
    }

    // 2. vivier : contenu ET ordre
    run {
        var ok = 0; var ko = 0; val ex = ArrayList<String>()
        var i = 0
        File(ref, "10_pool.txt").forEachLine { m ->
            if (res.pool[i] == m) ok++ else {
                ko++; if (ex.size < 5) ex.add("position $i : ${res.pool[i]} ≠ $m")
            }
            i++
        }
        if (i != res.pool.taille) { ko++; ex.add("taille ${res.pool.taille} ≠ $i") }
        bilan("vivier (contenu + ordre)", ok, ko, ex)
    }

    // 3. seaux sonores : clés, contenu, ordre
    run {
        var ok = 0; var ko = 0; val ex = ArrayList<String>()
        var n = 0
        File(ref, "11_sdx.tsv").forEachLine { l ->
            n++
            val t = l.split('\t')
            val attendu = if (t.size > 1 && t[1].isNotEmpty()) t[1].split(' ') else emptyList()
            val idx = res.sdxIndex[t[0]]
            val obtenu = idx?.map { res.pool[it] } ?: emptyList()
            if (obtenu == attendu) ok++ else {
                ko++
                if (ex.size < 5) ex.add("seau « ${t[0]} » : ${obtenu.size} ≠ ${attendu.size}")
            }
        }
        if (n != res.sdxIndex.size) { ko++; ex.add("nb seaux ${res.sdxIndex.size} ≠ $n") }
        bilan("seaux sonores", ok, ko, ex)
    }

    // 4. amyag
    run {
        var ok = 0; var ko = 0; val ex = ArrayList<String>()
        var i = 0
        File(ref, "12_amyag.txt").forEachLine { m ->
            if (res.amyag[i] == m && m in res.amyag) ok++ else {
                ko++; if (ex.size < 5) ex.add("position $i : ${res.amyag[i]} ≠ $m")
            }
            i++
        }
        bilan("amyag", ok, ko, ex)
    }

    // 5. lexique par catégorie
    run {
        var ok = 0; var ko = 0; val ex = ArrayList<String>()
        File(ref, "13_lexcat.tsv").forEachLine { l ->
            val p = l.split('\t')
            if (res.lexcat(p[0]) == p[1]) ok++ else {
                ko++; if (ex.size < 5) ex.add("« ${p[0]} » → ${res.lexcat(p[0])} ≠ ${p[1]}")
            }
        }
        bilan("lexique par catégorie", ok, ko, ex)
    }

    // 6. les deux prédicats, sur les 449 112 formes du vivier
    run {
        var ok = 0; var ko = 0; val ex = ArrayList<String>()
        File(ref, "14_predicats.tsv").forEachLine { l ->
            val p = l.split('\t')
            val f = if (res.fiable(p[0])) 1 else 0
            val a = if (res.valideParAffixe(p[0])) 1 else 0
            if (f == p[1].toInt() && a == p[2].toInt()) ok++ else {
                ko++
                if (ex.size < 5) ex.add("« ${p[0]} » fiable $f/${p[1]} affixe $a/${p[2]}")
            }
        }
        bilan("fiable + valide_par_affixe", ok, ko, ex)
    }

    // 7. graphe sémantique : formes et gloses
    run {
        var ok = 0; var ko = 0; val ex = ArrayList<String>()
        File(ref, "15_wordnet.tsv").forEachLine { l ->
            val p = l.split('\t')
            val g = if (p.size > 1) p[1] else ""
            if (res.glose(p[0]) == g) ok++ else {
                ko++; if (ex.size < 5) ex.add("« ${p[0]} » → « ${res.glose(p[0])} » ≠ « $g »")
            }
        }
        bilan("graphe sémantique", ok, ko, ex)
    }

    println("\n  " + if (global) "CONFORME : les ressources sont identiques au Python."
                     else "NON CONFORME.")
    if (!global) kotlin.system.exitProcess(1)
}
