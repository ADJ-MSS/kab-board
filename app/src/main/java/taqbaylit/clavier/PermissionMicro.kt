package taqbaylit.clavier

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast

/** Demande la permission du microphone pour le clavier. */
class PermissionMicro : Activity() {

    private var depart = 0L

    override fun onCreate(etat: Bundle?) {
        super.onCreate(etat)
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED) { finish(); return }
        depart = System.currentTimeMillis()
        requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), CODE)
    }

    override fun onRequestPermissionsResult(
        code: Int, permissions: Array<out String>, resultats: IntArray
    ) {
        super.onRequestPermissionsResult(code, permissions, resultats)
        val accordee = resultats.isNotEmpty() && resultats[0] == PackageManager.PERMISSION_GRANTED
        if (!accordee) {
            // Une reponse instantanee veut dire que le systeme n'a affiche aucun dialogue : la
            // permission est refusee definitivement, et redemander ne fera plus jamais rien.
            if (System.currentTimeMillis() - depart < SANS_DIALOGUE_MS) {
                runCatching {
                    startActivity(
                        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                               Uri.parse("package:$packageName"))
                            .addCategory(Intent.CATEGORY_DEFAULT)
                            .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                }
                Toast.makeText(this, getString(R.string.micro_reglages), Toast.LENGTH_LONG).show()
            }
        }
        finish()
    }

    companion object {
        private const val CODE = 4301
        private const val SANS_DIALOGUE_MS = 250L
    }
}
