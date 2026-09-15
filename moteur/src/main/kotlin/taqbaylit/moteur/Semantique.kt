package taqbaylit.moteur

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.StandardCharsets

/** Port de pipeline/v2/semantique.py : graphe racines → mots → concepts WOLF. */
class Semantique(dossier: File) {

    /** forme → (identifiants de concepts, poids de confiance) */
    private val ancrages = HashMap<String, Pair<IntArray, FloatArray>>()
    private val voisins = HashMap<Int, IntArray>()

    init {
        val f = File(dossier, "wordnet.ancrages")
        if (f.exists()) {
            val b = ByteBuffer.wrap(f.readBytes()).order(ByteOrder.LITTLE_ENDIAN)
            val n = b.getInt(6)
            var p = 10
            repeat(n) {
                val lm = b.getShort(p).toInt() and 0xFFFF
                val nd = b.getShort(p + 2).toInt() and 0xFFFF
                p += 4
                val mb = ByteArray(lm)
                for (k in 0 until lm) mb[k] = b.get(p + k)
                p += lm
                val ids = IntArray(nd); val poids = FloatArray(nd)
                for (k in 0 until nd) {
                    ids[k] = b.getInt(p); poids[k] = b.getFloat(p + 4); p += 8
                }
                ancrages[String(mb, StandardCharsets.UTF_8)] = ids to poids
            }
        }
        val g = File(dossier, "wordnet.voisins")
        if (g.exists()) {
            val b = ByteBuffer.wrap(g.readBytes()).order(ByteOrder.LITTLE_ENDIAN)
            val n = b.getInt(6)
            var p = 10
            repeat(n) {
                val sid = b.getInt(p)
                val nv = b.getShort(p + 4).toInt() and 0xFFFF
                p += 6
                val v = IntArray(nv)
                for (k in 0 until nv) { v[k] = b.getInt(p); p += 4 }
                voisins[sid] = v
            }
        }
    }

    /** Union des concepts des formes de la phrase, position [exclure] omise. */
    fun contexte(formes: List<String>, exclure: Int = -1): Set<Int> {
        val ctx = HashSet<Int>()
        for ((i, f) in formes.withIndex()) {
            if (i == exclure) continue
            ancrages[f]?.first?.forEach { ctx.add(it) }
        }
        return ctx
    }

    /** Lien sémantique [0..1] : le poids si concept partagé, 0,7 × poids si relié. */
    fun coherence(forme: String, contexteSids: Set<Int>): Float {
        if (contexteSids.isEmpty()) return 0f
        val a = ancrages[forme] ?: return 0f
        var meilleur = 0f
        for (k in a.first.indices) {
            val sid = a.first[k]
            val poids = a.second[k]
            if (sid in contexteSids) return poids
            val v = voisins[sid] ?: continue
            for (x in v) if (x in contexteSids) {
                val c = 0.7f * poids
                if (c > meilleur) meilleur = c
                break
            }
        }
        return meilleur
    }
}
