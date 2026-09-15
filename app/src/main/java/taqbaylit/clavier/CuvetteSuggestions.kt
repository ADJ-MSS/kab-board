package taqbaylit.clavier

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ColorFilter
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.drawable.Drawable

/** Fond de la barre de suggestions, dessiné comme un plateau creusé dans le clavier (v17.0.0). */
class CuvetteSuggestions(
    private val fond: Int,
    private val ombre: Int,
    private val lisere: Int,
    private val ombrePx: Int,
    private val liserePx: Int,
    private val rayonPx: Float
) : Drawable() {

    private val pinceau = Paint(Paint.ANTI_ALIAS_FLAG)
    private val chemin = Path()
    private var degrade: Shader? = null

    override fun onBoundsChange(bounds: Rect) {
        degrade = null
    }

    /** Le contour du plateau : angles vifs en haut, arrondis en bas. */
    private fun tracer(cadre: RectF): Path {
        chemin.reset()
        chemin.addRoundRect(
            cadre,
            floatArrayOf(
                0f, 0f,                 // haut gauche
                0f, 0f,                 // haut droit
                rayonPx, rayonPx,       // bas droit
                rayonPx, rayonPx        // bas gauche
            ),
            Path.Direction.CW
        )
        return chemin
    }

    override fun draw(canvas: Canvas) {
        val b = bounds
        if (b.isEmpty) return

        val cadre = RectF(
            b.left.toFloat(), b.top.toFloat(),
            b.right.toFloat(), b.bottom.toFloat()
        )

        pinceau.shader = null
        pinceau.color = lisere
        canvas.drawPath(tracer(cadre), pinceau)

        // Le même tracé remonté de l'épaisseur du liséré : il recouvre tout sauf la bande du bas,
        // qui suit donc la courbe des angles.
        cadre.offset(0f, -liserePx.toFloat())
        pinceau.color = fond
        canvas.drawPath(tracer(cadre), pinceau)

        // Sans ombre, rien à tracer : c'est le cas de la barre plate du clavier.
        if (ombrePx <= 0 || Color.alpha(ombre) == 0) return

        // Ombre interne du bord haut. Un rectangle simple suffit : les angles
        // hauts sont à vif, il n'y a aucune courbe à épouser ici.
        val basDeLOmbre = (b.top + ombrePx).toFloat()
        val teinte = degrade ?: LinearGradient(
            0f, b.top.toFloat(), 0f, basDeLOmbre,
            ombre,
            // Même teinte, alpha nul, pour que le dégradé s'éteigne au lieu de
            // virer vers un noir transparent qui laisserait un voile.
            ombre and 0x00FFFFFF,
            Shader.TileMode.CLAMP
        ).also { degrade = it }

        // Opaque avant de poser le shader : l'alpha du pinceau multiplie celui
        // du dégradé, et il porte encore celui du fond dessiné juste avant.
        pinceau.color = Color.BLACK
        pinceau.shader = teinte
        canvas.drawRect(
            b.left.toFloat(), b.top.toFloat(),
            b.right.toFloat(), basDeLOmbre,
            pinceau
        )
        pinceau.shader = null
    }

    /** Translucide, et il faut le dire : les angles bas laissent voir le fond du clavier. */
    @Deprecated("Deprecated in Java")
    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT

    // Ce fond n'est ni animé ni teinté par un appelant : les deux réglages que
    // Drawable impose d'exposer n'ont rien à piloter ici.
    override fun setAlpha(alpha: Int) = Unit
    override fun setColorFilter(colorFilter: ColorFilter?) = Unit
}
