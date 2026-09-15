package taqbaylit.clavier

import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.drawable.Drawable

/** Le trait de nature sous une proposition, lisible sans la couleur. */
class TraitDeNature(
    private val couleur: Int,
    private val motif: Motif,
    private val epaisseurPx: Int,
    private val retraitPx: Int,
    private val hautPx: Int
) : Drawable() {

    enum class Motif { PLEIN, TIRETS, POINTS }

    companion object {
        /** Les segments début, fin) à tracer sur une [largeur, en pixels. */
        fun segments(largeur: Float, motif: Motif, epaisseur: Float): List<Pair<Float, Float>> {
            if (largeur <= 0f || epaisseur <= 0f) return emptyList()
            val (trace, blanc) = when (motif) {
                Motif.PLEIN -> return listOf(0f to largeur)
                Motif.TIRETS -> epaisseur * 4 to epaisseur * 2
                Motif.POINTS -> epaisseur to epaisseur * 1.5f
            }
            val out = ArrayList<Pair<Float, Float>>()
            var x = 0f
            while (x < largeur) {
                out.add(x to minOf(x + trace, largeur))
                x += trace + blanc
            }
            return out
        }
    }

    private val pinceau = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = couleur }
    private val rect = RectF()

    override fun draw(canvas: Canvas) {
        val b = bounds
        val largeur = (b.width() - 2 * retraitPx).toFloat()
        val bas = (b.bottom - hautPx).toFloat()
        val haut = bas - epaisseurPx
        val rayon = epaisseurPx / 2f
        for ((debut, fin) in segments(largeur, motif, epaisseurPx.toFloat())) {
            rect.set(b.left + retraitPx + debut, haut, b.left + retraitPx + fin, bas)
            canvas.drawRoundRect(rect, rayon, rayon, pinceau)
        }
    }

    /** Translucide : entre deux tirets, la barre doit rester visible. */
    @Deprecated("Deprecated in Java")
    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT
    override fun setAlpha(alpha: Int) = Unit
    override fun setColorFilter(colorFilter: ColorFilter?) = Unit
}
