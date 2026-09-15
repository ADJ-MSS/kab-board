package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Contrôles des actifs livrés dans l'APK. */
class ActifsLivresTest {

    private val actifs = File("src/main/assets")

    private fun fichier(nom: String): File {
        val f = File(actifs, nom)
        assertTrue("$nom manquant — lancez outils/exporter_ressources.py", f.exists())
        return f
    }

    /** L'obligation de la licence MIT : conserver la notice de copyright dans toute copie. */
    @Test
    fun `l'attribution de KreyolKeyb voyage avec l'application`() {
        val notice = fichier("NOTICE.txt").readText()
        assertTrue("licence MIT absente", notice.contains("MIT License"))
        assertTrue("copyright absent", notice.contains("Copyright (c) 2025 Potomitan"))
        assertTrue("clause de conservation absente",
            notice.contains("above copyright notice"))
        assertTrue("dépôt d'origine non cité", notice.contains("famibelle/KreyolKeyb"))
    }

    @Test
    fun `les fichiers cites par l'attribution existent bien`() {
        val notice = fichier("NOTICE.txt").readText()
        val source = File("src/main/java/taqbaylit/clavier")
        for (nom in listOf("KeyboardLayoutManager", "KeyboardTheme", "AccentHandler",
                           "KeyFeedback", "CuvetteSuggestions", "KeyboardPreferences",
                           "EmojiPickerView", "EmojiData", "EmojiRecents", "Constants")) {
            assertTrue("$nom cité dans NOTICE mais absent du code",
                File(source, "$nom.kt").exists())
            assertTrue("$nom présent dans le code mais absent de NOTICE",
                notice.contains("$nom.kt"))
        }
    }

    /**
     * Le vivier de prédiction. Sans lui la prédiction se tait, ce qui est le bon comportement mais
     * ne se voit pas : le test le voit.
     */
    @Test
    fun `le vivier de prediction est complet et bien forme`() {
        val lignes = fichier("moteur/pool.frequents").readLines().filter { it.isNotBlank() }
        assertEquals("le vivier doit compter 5 000 formes", 5000, lignes.size)
        assertEquals("des doublons dans le vivier", lignes.size, lignes.distinct().size)
        assertTrue("des formes d'une seule lettre", lignes.all { it.length >= 2 })
        assertTrue("des espaces dans une forme", lignes.none { it.contains(' ') })
        // Trié par fréquence décroissante : les mots-outils du kabyle doivent
        // ouvrir la liste, sinon l'export n'a pas trié ce qu'il croyait trier.
        assertTrue("« ad » attendu en tête", lignes.take(5).contains("ad"))
        for (attendu in listOf("ɣer", "deg", "ur", "akken"))
            assertTrue("« $attendu » absent des 100 premières formes",
                lignes.take(100).contains(attendu))
    }

    /**
     * Le fichier de tailles, qui porte à lui seul le contrôle anti-troncature des ressources
     * déposées.
     */
    @Test
    fun `le fichier de tailles couvre toutes les ressources`() {
        val dossier = File(actifs, "moteur")
        val tailles = fichier("moteur/tailles.txt").readLines()
            .filter { it.isNotBlank() }
            .associate { val p = it.split('\t'); p[0] to p[1].toLong() }

        val presents = dossier.listFiles()!!.filter { it.isFile && it.name != "tailles.txt" }
        assertTrue("aucune ressource trouvée", presents.isNotEmpty())
        for (f in presents) {
            val attendue = tailles[f.name]
            assertTrue("${f.name} absent de tailles.txt", attendue != null)
            assertEquals("${f.name} : taille déclarée fausse", f.length(), attendue)
        }
        for (nom in tailles.keys)
            assertTrue("$nom déclaré dans tailles.txt mais absent", File(dossier, nom).exists())
    }

    /** Le modele vocal et son jeu de jetons. */
    @Test
    fun `le modele vocal est present et bien forme`() {
        val modele = fichier("voix/mmeslay.onnx")
        assertTrue("modele etonnamment petit : ${modele.length()} octets",
            modele.length() > 40L * 1024 * 1024)
        // Un fichier ONNX commence par un en-tete protobuf qui cite le producteur.
        val tete = modele.inputStream().use { f -> ByteArray(64).also { f.read(it) } }
            .decodeToString()
        assertTrue("signature ONNX absente", tete.contains("onnx") || tete.contains("pytorch"))
    }

    @Test
    fun `le jeu de jetons couvre l'alphabet kabyle`() {
        val jetons = fichier("voix/jetons.txt").readLines().map { it.trim() }
        assertEquals("le modele declare 129 classes", 129, jetons.size)
        assertTrue("le blanc CTC manque", jetons.contains("_"))
        for (lettre in listOf("ɣ", "ɛ", "ḥ", "ẓ", "ṭ", "ḍ", "ṣ", "č", "ǧ"))
            assertTrue("aucun jeton ne porte « $lettre »",
                jetons.any { it.contains(lettre) })
        // Le trait d'union lie les clitiques : sans lui, « yid-k » sortirait colle.
        assertTrue("le trait d'union manque", jetons.any { it.contains("-") })
    }

    @Test
    fun `l'attribution du modele vocal voyage avec l'application`() {
        val notice = fichier("NOTICE.txt").readText()
        assertTrue("Mmeslay non cite", notice.contains("Mmeslay"))
        assertTrue("depot d'origine non cite", notice.contains("G1ya777/Mmeslay"))
        // Obligation de la GPL-3 : la licence sous laquelle l'ensemble est
        // distribue doit etre dite, et rien d'autre ne la retient.
        assertTrue("licence GPL-3 non annoncee", notice.contains("GPL-3.0"))
        assertTrue("NeMo non cite", notice.contains("NeMo"))
        assertTrue("FUTO non cite", notice.contains("FUTO"))
    }

    @Test
    fun `le modele de langue est present et porte sa signature`() {
        val modele = fichier("moteur/kabyle_3gram.binary")
        val tete = modele.inputStream().use { flux ->
            ByteArray(52).also { flux.read(it) }
        }.decodeToString()
        assertTrue("signature KenLM absente", tete.startsWith("mmap lm"))
        // Le format TRIE, deux fois plus compact que PROBING à scores égaux.
        assertTrue("modèle étonnamment petit : ${modele.length()} octets",
            modele.length() > 200L * 1024 * 1024)
    }
}
