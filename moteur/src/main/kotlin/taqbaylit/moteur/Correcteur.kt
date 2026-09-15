package taqbaylit.moteur

import java.io.File

/** Port de pipeline/v2/correcteur.py : assemble les étapes. */
class Correcteur(
    dossierRessources: File,
    modeleKenlm: File? = null,
    modeleCrf: File? = null,
    libKenlm: File? = null,
    libCrf: File? = null
) : AutoCloseable {

    val res = Ressources(dossierRessources)
    private val gen = Generateur(res)
    val sem = Semantique(dossierRessources)

    /** Un modèle absent désactive sa couche, il ne fait pas tomber le moteur. */
    private val lm: ModeleLangue? = modeleKenlm?.takeIf { it.isFile }?.let {
        runCatching { ModeleLangue.chargerBibliotheque(libKenlm); ModeleLangue.ouvrir(it) }
            .getOrNull()
    }
    private val tagger: Etiqueteur? = modeleCrf?.takeIf { it.isFile }?.let {
        runCatching { Etiqueteur.chargerBibliotheque(libCrf); Etiqueteur.ouvrir(it) }
            .getOrNull()
    }
    private val post = Postprocess(dossierRessources, lm)

    /** Le modele de langue, en lecture, pour la prediction du mot suivant. */
    val modeleLangue: ModeleLangue? get() = lm

    /** Les règles d'état, en lecture, pour la fiche d'un mot au clavier. */
    val postprocess: Postprocess get() = post

    companion object { const val W_SEM = 0.6f }

    data class Resultat(
        val texteCorrige: String,
        val tokensEntree: List<String>,
        val nbCorrections: Int,
        val annexions: List<Postprocess.Proposition> = emptyList()
    )

    fun topCandidats(mot: String, nb: Int = 5) = gen.topCandidats(mot, nb)

    fun corriger(texte: String): Resultat {
        val tokens = Normalisation.tokenize(texte)
        if (tokens.isEmpty()) return Resultat("", emptyList(), 0)

        // Clitiques détachés avant tout calcul de distance, recollés après
        val prefs = ArrayList<String>(tokens.size)
        val bases = ArrayList<String>(tokens.size)
        val sufs = ArrayList<String>(tokens.size)
        for (t in tokens) {
            val (p, b, s) = Normalisation.detacherClitique(t)
            prefs.add(p); bases.add(b); sufs.add(s)
        }

        val tags = tagger?.etiqueter(bases) ?: emptyList()

        var candsParPos = bases.indices.map { i ->
            gen.generer(bases[i], tags.getOrElse(i) { "" })
               .take(Decodeur.MAX_CAND_BEAM)
        }

        // Cohérence sémantique, sur des copies pour ne pas polluer le cache
        if (bases.size > 1) {
            candsParPos = candsParPos.mapIndexed { i, cands ->
                val ctx = sem.contexte(bases, exclure = i)
                if (ctx.isEmpty()) cands
                else cands.map { c ->
                    val coh = sem.coherence(c.forme, ctx)
                    if (coh != 0f) c.copy(score = c.score + W_SEM * coh) else c
                }.sortedByDescending { it.score }
            }
        }

        val chemin = Decodeur.decoder(candsParPos, lm)

        var nb = 0
        val corrigee = ArrayList<String>(chemin.size)
        for ((i, c) in chemin.withIndex()) {
            corrigee.add(prefs[i] + c.forme + sufs[i])
            if (c.forme != bases[i]) nb++
        }

        val (apresChaker, corrChaker) = post.appliquerChakerValideLm(
            corrigee, res.amyagSet(), { m -> res.lexcat(m) })
        nb += corrChaker.size

        val finale = Normalisation.rejoindrePossessifs(apresChaker)
        return Resultat(finale.joinToString(" "), tokens, nb, corrChaker)
    }

    override fun close() {
        lm?.close()
        tagger?.close()
    }
}
