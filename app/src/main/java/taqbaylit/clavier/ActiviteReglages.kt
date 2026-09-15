package taqbaylit.clavier

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/** Réglages, en langage simple et non en jargon. */
class ActiviteReglages : Activity() {

    private lateinit var caseJournal: CheckBox
    private lateinit var caseDiffusion: CheckBox
    private lateinit var compte: TextView
    private lateinit var etatCorrecteur: TextView

    override fun onCreate(etat: Bundle?) {
        super.onCreate(etat)
        val d = resources.displayMetrics.density
        val marge = (20 * d).toInt()

        val colonne = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(marge, marge, marge, marge)
            setBackgroundColor(FOND)
        }

        // ---- mise en place
        colonne.addView(titre(getString(R.string.etat_titre)))
        colonne.addView(texte(getString(R.string.etat_activer)))
        colonne.addView(bouton(getString(R.string.etat_bouton_activer)) {
            startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
        })
        colonne.addView(texte(getString(R.string.etat_choisir)))
        colonne.addView(bouton(getString(R.string.etat_bouton_choisir)) {
            (getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager)
                .showInputMethodPicker()
        })
        colonne.addView(texte(getString(R.string.etat_correcteur)))
        colonne.addView(bouton(getString(R.string.etat_bouton_correcteur)) {
            ouvrirChoixCorrecteur()
        })
        etatCorrecteur = petit("")
        colonne.addView(etatCorrecteur)
        colonne.addView(petit(getString(R.string.etat_correcteur_detail)))
        colonne.addView(petit(getString(R.string.etat_place,
            Ressources.taille(this) / 1048576)))

        // ---- apparence et retour de frappe
        colonne.addView(espace(d))
        colonne.addView(titre(getString(R.string.aspect_titre)))
        for (mode in KeyboardTheme.Mode.entries) {
            colonne.addView(bouton(getString(when (mode) {
                KeyboardTheme.Mode.SYSTEME -> R.string.aspect_systeme
                KeyboardTheme.Mode.CLAIR -> R.string.aspect_clair
                KeyboardTheme.Mode.SOMBRE -> R.string.aspect_sombre
                KeyboardTheme.Mode.CONTRASTE -> R.string.aspect_contraste
                KeyboardTheme.Mode.TAMAZGHA -> R.string.aspect_tamazgha
            })) {
                KeyboardPreferences.setThemeMode(this, mode)
                KeyboardTheme.refresh(this)
            })
        }
        colonne.addView(case(getString(R.string.theme_traits_formes)) { coche ->
            KeyboardPreferences.setTraitsFormes(this, coche)
        }.apply { isChecked = KeyboardPreferences.traitsFormes(this@ActiviteReglages) })
        colonne.addView(petit(getString(R.string.theme_traits_detail)))

        colonne.addView(espace(d))
        colonne.addView(titre(getString(R.string.ecriture_titre)))
        colonne.addView(case(getString(R.string.parler_titre)) { coche ->
            KeyboardPreferences.setEcrireCommeOnParle(this, coche)
        }.apply { isChecked = KeyboardPreferences.ecrireCommeOnParle(this@ActiviteReglages) })
        colonne.addView(petit(getString(R.string.parler_detail)))
        colonne.addView(texte(getString(R.string.outils_titre)))
        colonne.addView(petit(getString(R.string.outils_detail)))

        colonne.addView(espace(d))
        colonne.addView(titre(getString(R.string.frappe_titre)))
        colonne.addView(case(getString(R.string.frappe_vibration)) { coche ->
            KeyboardPreferences.setHapticEnabled(this, coche)
            KeyFeedback.refresh(this)
        }.apply { isChecked = KeyboardPreferences.hapticEnabled(this@ActiviteReglages) })
        colonne.addView(case(getString(R.string.frappe_son)) { coche ->
            KeyboardPreferences.setSoundEnabled(this, coche)
            KeyFeedback.refresh(this)
        }.apply { isChecked = KeyboardPreferences.soundEnabled(this@ActiviteReglages) })
        colonne.addView(petit(getString(R.string.frappe_detail)))

        colonne.addView(espace(d))
        colonne.addView(titre(getString(R.string.emoji_titre)))
        colonne.addView(bouton(getString(R.string.emoji_vider)) {
            EmojiRecents.vider(this)
        })

        // ---- contribution
        colonne.addView(espace(d))
        colonne.addView(titre(getString(R.string.journal_titre)))
        colonne.addView(texte(getString(R.string.journal_explication)))

        caseJournal = case(getString(R.string.journal_activer)) { coche ->
            Journal.activer(this, coche)
            if (!coche) {
                caseDiffusion.isChecked = false
                Journal.autoriserDiffusion(this, false)
            }
            majEtat()
        }
        colonne.addView(caseJournal)
        colonne.addView(petit(getString(R.string.journal_detail)))

        caseDiffusion = case(getString(R.string.journal_diffusion)) { coche ->
            Journal.autoriserDiffusion(this, coche)
        }
        colonne.addView(caseDiffusion)
        colonne.addView(petit(getString(R.string.journal_diffusion_detail)))

        compte = petit("")
        colonne.addView(compte)
        colonne.addView(bouton(getString(R.string.journal_voir)) { voirJournal() })
        colonne.addView(bouton(getString(R.string.journal_envoyer)) { preparerEnvoi() })
        colonne.addView(bouton(getString(R.string.journal_effacer)) {
            Journal.toutEffacer(this); majEtat()
        })

        // ---- ce qui n'est jamais enregistré
        colonne.addView(espace(d))
        colonne.addView(titre(getString(R.string.prive_titre)))
        colonne.addView(texte(getString(R.string.prive_detail)))

        setContentView(ScrollView(this).apply {
            setBackgroundColor(FOND); addView(colonne)
        })
    }

    override fun onResume() {
        super.onResume()
        caseJournal.isChecked = Journal.actif(this)
        caseDiffusion.isChecked = Journal.diffusionAutorisee(this)
        majEtat()
    }

    private fun majEtat() {
        val n = Journal.nombreLignes(this)
        compte.text = if (n == 0) getString(R.string.journal_vide)
                      else getString(R.string.journal_compte, n)
        caseDiffusion.isEnabled = caseJournal.isChecked
        // Relu a chaque retour sur l'ecran : l'utilisateur revient justement
        // d'avoir fait, ou pas, le choix que le bouton propose.
        etatCorrecteur.text = getString(
            if (correcteurChoisi()) R.string.etat_correcteur_actif
            else R.string.etat_correcteur_inactif)
    }

    /** Les lignes du journal, sans l'en-tete explicatif ni les lignes vides. */
    private fun lignesDuJournal(): List<String> =
        Journal.extrait(this, Int.MAX_VALUE)
            ?.lineSequence()
            ?.filter { it.isNotBlank() && !it.startsWith("#") }
            ?.toList()
            .orEmpty()

    /** Ce qui est enregistre, dans une fenetre qu'on fait defiler. */
    private fun voirJournal() {
        val lignes = lignesDuJournal()
        val d = resources.displayMetrics.density
        val marge = (20 * d).toInt()
        val vue = TextView(this).apply {
            text = if (lignes.isEmpty()) getString(R.string.journal_vide)
                   else lignes.joinToString("\n")
            setTextIsSelectable(true)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            typeface = android.graphics.Typeface.MONOSPACE
            setPadding(marge, marge / 2, marge, 0)
        }
        android.app.AlertDialog.Builder(this)
            .setTitle(R.string.journal_voir)
            .setView(ScrollView(this).apply { addView(vue) })
            .setPositiveButton(android.R.string.ok, null)
            .show()
    }

    /**
     * Prepare l'envoi du journal : le message est ecrit, le fichier est joint, et l'utilisateur
     * choisit son application puis appuie lui-meme sur « envoyer ».
     */
    private fun preparerEnvoi() {
        val lignes = lignesDuJournal()
        if (lignes.isEmpty()) {
            // Sans ce message, le bouton ne ferait rien : on croirait a une panne.
            Toast.makeText(this, getString(R.string.journal_vide), Toast.LENGTH_LONG).show()
            majEtat()
            return
        }
        val destinataire = "massil.aoudj@lecnam.net"

        // Copie dans cache/partage/, seul dossier declare dans res/xml/partage.xml :
        // les ressources du correcteur et le modele vocal restent hors d'atteinte.
        val pieceJointe = runCatching {
            val dossier = java.io.File(cacheDir, "partage").apply { mkdirs() }
            val copie = java.io.File(dossier, "mes-choix-kabyle.txt")
            Journal.fichier(this).copyTo(copie, overwrite = true)
            androidx.core.content.FileProvider.getUriForFile(this, "$packageName.fichiers", copie)
        }.getOrNull()

        // Un corps de message trop long est refuse par certaines messageries : au-dela,
        // on garde la fin et on renvoie a la piece jointe, qui contient tout.
        val corpsMax = 60_000
        val choix = lignes.joinToString("\n")
        val tronque = choix.length > corpsMax
        val corps = buildString {
            appendLine("Voici mes choix de correction en kabyle.")
            appendLine()
            appendLine("Qui je suis (nom, pseudonyme ou « anonyme ») :")
            appendLine()
            appendLine("J'autorise la publication dans un corpus librement reutilisable : " +
                       if (Journal.diffusionAutorisee(this@ActiviteReglages)) "oui" else "non")
            appendLine()
            appendLine("Ma region ou ma variete (facultatif) :")
            appendLine()
            appendLine("Mes choix (${lignes.size}) — date | mot saisi | forme retenue :")
            if (tronque) appendLine("[debut coupe : le fichier joint contient tout]")
            appendLine(if (tronque) choix.takeLast(corpsMax) else choix)
        }

        val envoi = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_EMAIL, arrayOf(destinataire))
            putExtra(Intent.EXTRA_SUBJECT, "Contributions au correcteur kabyle")
            putExtra(Intent.EXTRA_TEXT, corps)
            if (pieceJointe != null) {
                putExtra(Intent.EXTRA_STREAM, pieceJointe)
                // Sans ClipData, l'autorisation de lecture ne suit pas l'intention
                // jusqu'a l'application choisie dans le selecteur.
                clipData = android.content.ClipData.newRawUri("", pieceJointe)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        }
        runCatching {
            startActivity(Intent.createChooser(envoi, getString(R.string.journal_envoyer)))
        }.onFailure {
            // Aucune application d'envoi : au moins l'adresse, pour ecrire autrement.
            Toast.makeText(this, destinataire, Toast.LENGTH_LONG).show()
        }
    }

    // ---- fabriques de vues, sans XML : l'écran est simple et linéaire
    /** Ouvre l'ecran ou se choisit le correcteur orthographique du systeme. */
    private fun ouvrirChoixCorrecteur() {
        val direct = Intent().apply {
            setClassName("com.android.settings",
                "com.android.settings.Settings\$SpellCheckersSettingsActivity")
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        if (runCatching { startActivity(direct) }.isSuccess) return
        val repli = Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)
            .apply { flags = Intent.FLAG_ACTIVITY_NEW_TASK }
        if (runCatching { startActivity(repli) }.isSuccess) {
            // Seul cas ou une instruction reste utile : l'ecran atteint n'est
            // pas celui que le bouton annonce.
            Toast.makeText(this, getString(R.string.etat_correcteur_repli),
                Toast.LENGTH_LONG).show()
            return
        }
        runCatching { startActivity(Intent(Settings.ACTION_SETTINGS)) }
    }

    /** Le correcteur du systeme est-il le notre ? */
    private fun correcteurChoisi(): Boolean = runCatching {
        Settings.Secure.getString(contentResolver, "selected_spell_checker")
            ?.contains(packageName) == true
    }.getOrDefault(false)

    private fun titre(t: String) = TextView(this).apply {
        text = t; setTextColor(BLEU)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
        setPadding(0, 28, 0, 12)
    }
    private fun texte(t: String) = TextView(this).apply {
        text = t; setTextColor(TEXTE)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
        setPadding(0, 6, 0, 6)
    }
    private fun petit(t: String) = TextView(this).apply {
        text = t; setTextColor(GRIS)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        setPadding(0, 2, 0, 14)
    }
    private fun case(t: String, surChangement: (Boolean) -> Unit) = CheckBox(this).apply {
        text = t; setTextColor(TEXTE)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
        minHeight = 132                       // ≥ 48 dp
        setOnCheckedChangeListener { _, coche -> surChangement(coche) }
    }
    private fun bouton(t: String, action: () -> Unit) = Button(this).apply {
        text = t; minHeight = 132
        gravity = Gravity.CENTER
        setOnClickListener { action() }
    }
    private fun espace(d: Float) = View(this).apply {
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, (16 * d).toInt())
    }

    private companion object {
        val FOND = Color.parseColor("#151C24")
        val TEXTE = Color.parseColor("#E8EDF2")
        val GRIS = Color.parseColor("#9AA3AB")
        val BLEU = Color.parseColor("#7FB2E5")
    }
}
