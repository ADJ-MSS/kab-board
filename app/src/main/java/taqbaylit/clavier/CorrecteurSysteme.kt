package taqbaylit.clavier

import android.os.Build
import android.service.textservice.SpellCheckerService
import android.util.Log
import android.util.LruCache
import android.view.textservice.SentenceSuggestionsInfo
import android.view.textservice.SuggestionsInfo
import android.view.textservice.TextInfo
import taqbaylit.moteur.Correcteur
import taqbaylit.moteur.Normalisation

/** Le correcteur orthographique du systeme, distinct du clavier. Repris de KreyolKeyb (MIT). */
class CorrecteurSysteme : SpellCheckerService() {

    enum class Soulignement { AUCUN, DOUTE, FAUTE }

    /** Un verdict et les formes a proposer, deja a la casse du mot. */
    data class Jugement(val soulignement: Soulignement, val propositions: List<String>)

    companion object {
        private const val TAG = "Taqbaylit"
        private const val NB_PAR_DEFAUT = 5

        /** La borne de contexte de la barre du clavier (ClavierKabyle.contexteGauche). */
        internal const val CONTEXTE_MAX = 60

        /** Assez pour une longue saisie : le systeme renvoie la phrase a chaque modification. */
        private const val MEMOIRE = 256

        private val RIEN = Jugement(Soulignement.AUCUN, emptyList())

        /** Faut-il souligner ce mot, et comment ? */
        fun verdict(mot: String, absolue: String, cinq: List<String>, connu: Boolean): Soulignement {
            val forme = Normalisation.normalize(mot)
            if (absolue == forme) return Soulignement.AUCUN
            // Une forme connue n'est jamais une faute. Si le contexte n'a pas pu
            // etre lu, il n'y a rien a departager non plus.
            if (connu) return if (absolue.isBlank()) Soulignement.AUCUN else Soulignement.DOUTE
            // Inconnu : on ne souligne que si l'on a quelque chose a proposer.
            val propositions = (listOf(absolue) + cinq).filter { it.isNotBlank() && it != forme }
            return if (propositions.isEmpty()) Soulignement.AUCUN else Soulignement.FAUTE
        }

        /** Les mots d'un texte avec leur debut, en unites UTF-16. */
        fun mots(texte: String): List<Pair<Int, String>> {
            val trouves = ArrayList<Pair<Int, String>>()
            var i = 0
            while (i < texte.length) {
                if (!ClavierKabyle.estCaractereMot(texte[i])) { i++; continue }
                val debut = i
                while (i < texte.length && ClavierKabyle.estCaractereMot(texte[i])) i++
                trouves.add(debut to texte.substring(debut, i))
            }
            return trouves
        }

        /** Le jugement d'un mot et ses propositions. */
        fun jugerMot(c: Correcteur, gauche: String, mot: String, nb: Int): Jugement {
            val forme = Normalisation.normalize(mot)
            // « Connu » au sens du pipeline lui-meme, et selon ses deux niveaux : la forme de
            // confiance et la forme construite sur une racine fiable.
            val connu = c.res.fiable(forme) || c.res.valideParAffixe(forme)
            val six = Propositions.calculer(c, gauche, mot)
            val s = verdict(mot, six.absolue, six.cinq, connu)
            val propositions = if (s == Soulignement.AUCUN) emptyList() else
                // La correction absolue en tete, puis le top-5.
                (listOf(six.absolue) + six.cinq)
                    .filter { it.isNotBlank() && it != forme }
                    .map { ClavierKabyle.casserComme(mot, it) }
                    .distinct()
                    .take(nb)
            return Jugement(s, propositions)
        }
    }

    override fun createSession(): Session = SessionKabyle()

    private inner class SessionKabyle : Session() {

        /** Jugements deja rendus, par contexte et mot. */
        private val memoire = LruCache<Pair<String, String>, Jugement>(MEMOIRE)

        override fun onCreate() {
            // onCreate et les onGet* tournent sur un fil interne au service, jamais sur celui de
            // l'application ou l'on tape.
            Moteur.obtenir(applicationContext)
            Log.i(TAG, "session du correcteur systeme prete")
        }

        override fun onGetSuggestions(info: TextInfo?, limite: Int): SuggestionsInfo =
            reponse(juger("", info?.text.orEmpty(), limite), info)

        override fun onGetSuggestionsMultiple(
            infos: Array<TextInfo>?, limite: Int, motsSuccessifs: Boolean
        ): Array<SuggestionsInfo> {
            if (infos == null) return emptyArray()
            // Des mots successifs se servent de contexte les uns aux autres.
            val gauche = StringBuilder()
            return infos.map { info ->
                val mot = info.text.orEmpty()
                val contexte =
                    if (motsSuccessifs) gauche.toString().trim().takeLast(CONTEXTE_MAX) else ""
                gauche.append(' ').append(mot)
                reponse(juger(contexte, mot, limite), info)
            }.toTypedArray()
        }

        override fun onGetSentenceSuggestionsMultiple(
            infos: Array<TextInfo>?, limite: Int
        ): Array<SentenceSuggestionsInfo> {
            if (infos == null) return emptyArray()
            return infos.map { phrase ->
                val texte = phrase.text.orEmpty()
                val trouves = mots(texte)
                val decalages = IntArray(trouves.size)
                val longueurs = IntArray(trouves.size)
                // Tous les mots sont rendus, les justes compris.
                val reponses = trouves.mapIndexed { k, (debut, mot) ->
                    decalages[k] = debut
                    longueurs[k] = mot.length
                    val gauche = texte.substring(0, debut).trim().takeLast(CONTEXTE_MAX)
                    reponse(juger(gauche, mot, limite), phrase)
                }.toTypedArray()
                SentenceSuggestionsInfo(reponses, decalages, longueurs)
            }.toTypedArray()
        }

        private fun juger(gauche: String, brut: String, limite: Int): Jugement {
            val mot = brut.trim()
            if (mot.length < 2 || mot.none { it.isLetter() }) return RIEN
            val cle = gauche to mot
            memoire.get(cle)?.let { return it }

            val nb = if (limite > 0) limite else NB_PAR_DEFAUT
            // Un mot a la fois sous le verrou du moteur, et non une phrase entiere.
            val jugement = Moteur.avec(applicationContext) { c -> jugerMot(c, gauche, mot, nb) }
                ?: return RIEN // moteur indisponible : ce non-verdict n'est pas memorise

            memoire.put(cle, jugement)
            return jugement
        }

        private fun reponse(j: Jugement, origine: TextInfo?): SuggestionsInfo {
            val attributs = when (j.soulignement) {
                Soulignement.FAUTE -> SuggestionsInfo.RESULT_ATTR_LOOKS_LIKE_TYPO
                Soulignement.DOUTE ->
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
                        SuggestionsInfo.RESULT_ATTR_LOOKS_LIKE_GRAMMAR_ERROR
                    else SuggestionsInfo.RESULT_ATTR_IN_THE_DICTIONARY
                Soulignement.AUCUN -> SuggestionsInfo.RESULT_ATTR_IN_THE_DICTIONARY
            }
            val formes =
                if (attributs == SuggestionsInfo.RESULT_ATTR_IN_THE_DICTIONARY) emptyArray()
                else j.propositions.toTypedArray()
            // Le couple (cookie, sequence) de la demande, reporte sur chaque mot : c'est lui qui
            // rattache un resultat a son texte.
            return SuggestionsInfo(attributs, formes).apply {
                if (origine != null) setCookieAndSequence(origine.cookie, origine.sequence)
            }
        }
    }
}
