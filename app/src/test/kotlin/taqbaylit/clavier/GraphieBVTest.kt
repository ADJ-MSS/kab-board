package taqbaylit.clavier

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/**
 * La graphie reglee, sur la vraie table livree dans les actifs.
 *
 * Trois promesses y sont verifiees : un mot qui n'alterne pas ressort intact,
 * la casse du mot tape est rendue, et le reglage vaut pour les six propositions
 * et non pour la seule correction.
 */
class GraphieBVTest {

    private val table = File("src/main/assets/graphie/table_bv.tsv")

    @Before
    fun charger() {
        table.useLines { GraphieBV.charger(it) }
    }

    @Test
    fun `la table est livree avec l'application`() {
        assertTrue("table absente des actifs", table.exists())
        assertTrue("table chargee", GraphieBV.chargee)
    }

    @Test
    fun `un mot de la liste s'ecrit dans la graphie reglee`() {
        assertEquals("abrid", GraphieBV.basculer("abrid", GraphieBV.Mode.B))
        assertEquals("avrid", GraphieBV.basculer("abrid", GraphieBV.Mode.V))
        assertEquals("abrid", GraphieBV.basculer("avrid", GraphieBV.Mode.B))
    }

    @Test
    fun `une forme conjuguee heritee du paradigme suit le meme reglage`() {
        assertEquals("neḍlev", GraphieBV.basculer("neḍleb", GraphieBV.Mode.V))
        assertEquals("neḍleb", GraphieBV.basculer("neḍlev", GraphieBV.Mode.B))
    }

    @Test
    fun `un mot qui n'alterne pas ressort intact`() {
        assertNull(GraphieBV.paire("axxam"))
        assertEquals("axxam", GraphieBV.basculer("axxam", GraphieBV.Mode.V))
        assertEquals("axxam", GraphieBV.basculer("axxam", GraphieBV.Mode.B))
    }

    @Test
    fun `la casse du mot est rendue`() {
        assertEquals("Avrid", GraphieBV.basculer("Abrid", GraphieBV.Mode.V))
        assertEquals("AVRID", GraphieBV.basculer("ABRID", GraphieBV.Mode.V))
        assertEquals("Abrid", GraphieBV.basculer("Avrid", GraphieBV.Mode.B))
    }

    @Test
    fun `le reglage vaut pour tout le top-5, pas seulement pour la correction`() {
        val cinq = listOf("abrid", "axxam", "neḍleb")
        assertEquals(listOf("avrid", "axxam", "neḍlev"),
            GraphieBV.appliquer(cinq, GraphieBV.Mode.V))
        assertEquals(cinq, GraphieBV.appliquer(cinq, GraphieBV.Mode.B))
    }

    @Test
    fun `deux formes qui se rejoignent n'occupent qu'une place`() {
        assertEquals(listOf("avrid"),
            GraphieBV.appliquer(listOf("abrid", "avrid"), GraphieBV.Mode.V))
    }

    @Test
    fun `la geminee bascule entierement`() {
        // Decision du 27/09 : toute occurrence de b bascule, y compris geminee.
        assertEquals("nqevvel", GraphieBV.basculer("nqebbel", GraphieBV.Mode.V))
    }

    @Test
    fun `un texte dicte est converti mot a mot`() {
        assertEquals("ruḥeɣ ɣer wevrid, yusa-d vava.",
            GraphieBV.appliquerTexte("ruḥeɣ ɣer webrid, yusa-d baba.", GraphieBV.Mode.V))
    }

    @Test
    fun `la ponctuation et les espaces sont preserves`() {
        val texte = "abrid : axxam, abrid !"
        assertEquals("avrid : axxam, avrid !",
            GraphieBV.appliquerTexte(texte, GraphieBV.Mode.V))
        assertEquals(texte, GraphieBV.appliquerTexte(texte, GraphieBV.Mode.B))
    }

    // --- les formes flechies, que la table ne liste pas -------------------
    // Mesure du 28/09 : la liste donne « ubrid » et « webrid » mais pas
    // « wabrid », ni aucun mot a tiret. Les regles comblent, sans inventer.

    @Test
    fun `une annexion absente de la table bascule quand meme`() {
        assertNull(GraphieBV.paire("wabrid")?.let { if (it.first == "wabrid") null else it })
        assertEquals("wavrid", GraphieBV.basculer("wabrid", GraphieBV.Mode.V))
        assertEquals("uɣvalu", GraphieBV.basculer("uɣbalu", GraphieBV.Mode.V))
        assertEquals("weqvu", GraphieBV.basculer("weqbu", GraphieBV.Mode.V))
        assertEquals("tvadut", GraphieBV.basculer("tbadut", GraphieBV.Mode.V))
        assertEquals("yiɣvu", GraphieBV.basculer("yiɣbu", GraphieBV.Mode.V))
    }

    @Test
    fun `le pluriel suit son singulier`() {
        assertEquals("iɣriven", GraphieBV.basculer("iɣriben", GraphieBV.Mode.V))
        assertEquals("ivridan", GraphieBV.basculer("ibridan", GraphieBV.Mode.V))
    }

    @Test
    fun `une forme flechie revient en b`() {
        assertEquals("ubrid", GraphieBV.basculer("uvrid", GraphieBV.Mode.B))
        assertEquals("baba-k", GraphieBV.basculer("vava-k", GraphieBV.Mode.B))
    }

    @Test
    fun `chaque segment d'un mot a tirets bascule`() {
        assertEquals("vava-s", GraphieBV.basculer("baba-s", GraphieBV.Mode.V))
        assertEquals("avrid-is", GraphieBV.basculer("abrid-is", GraphieBV.Mode.V))
        assertEquals("yettvan-d", GraphieBV.basculer("yettban-d", GraphieBV.Mode.V))
        assertEquals("d-nevder", GraphieBV.basculer("d-nebder", GraphieBV.Mode.V))
        assertEquals("aqrav-nni", GraphieBV.basculer("aqrab-nni", GraphieBV.Mode.V))
        assertEquals("Vava-s", GraphieBV.basculer("Baba-s", GraphieBV.Mode.V))
        assertEquals("VAVA-S", GraphieBV.basculer("BABA-S", GraphieBV.Mode.V))
    }

    @Test
    fun `un mot a tirets dont aucun segment n'alterne reste intact`() {
        assertEquals("yusa-d", GraphieBV.basculer("yusa-d", GraphieBV.Mode.V))
        assertNull(GraphieBV.paire("yusa-d"))
    }

    @Test
    fun `les emprunts hors liste gardent leur b`() {
        // Leur b ne se spirantise pas : la liste les ecarte, les regles aussi.
        for (mot in listOf("belli", "ṛebbi", "mebla", "beṛa", "ṣebba", "boston", "ib")) {
            assertEquals(mot, GraphieBV.basculer(mot, GraphieBV.Mode.V))
        }
    }

    @Test
    fun `une phrase entiere ne mele plus les deux graphies`() {
        assertEquals("vava-s yettvan-d deg uvrid",
            GraphieBV.appliquerTexte("baba-s yettban-d deg ubrid", GraphieBV.Mode.V))
        assertEquals("yenna-d belli uvrid",
            GraphieBV.appliquerTexte("yenna-d belli ubrid", GraphieBV.Mode.V))
    }
}
