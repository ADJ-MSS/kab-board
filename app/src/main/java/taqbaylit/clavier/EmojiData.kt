package taqbaylit.clavier

import android.content.Context
import android.util.Log
import org.json.JSONObject

/** Une catégorie d'emojis (ex. "Smileys & Emotion") avec son icône d'onglet. */
data class EmojiCategory(
    val name: String,
    val icon: String,
    val emojis: List<String>
)

/**
 * Jeu de données emoji complet, chargé une seule fois depuis assets/emoji_data.json (généré à
 * partir du emoji-test.txt officiel d'Unicode 16.0, entrées fully-qualified, groupe "Component"
 * exclu).
 */
class EmojiData private constructor(
    val categories: List<EmojiCategory>,
    val skinTones: Map<String, List<String>>
) {
    companion object {
        private const val TAG = "EmojiData"
        private const val ASSET_FILE = "emoji_data.json"

        @Volatile
        private var cached: EmojiData? = null

        fun load(context: Context): EmojiData {
            cached?.let { return it }

            synchronized(this) {
                cached?.let { return it }

                val loaded = try {
                    val jsonString = context.assets.open(ASSET_FILE).bufferedReader().use { it.readText() }
                    val root = JSONObject(jsonString)

                    val categoriesJson = root.getJSONArray("categories")
                    val categories = (0 until categoriesJson.length()).map { i ->
                        val obj = categoriesJson.getJSONObject(i)
                        val emojisJson = obj.getJSONArray("emojis")
                        val emojis = (0 until emojisJson.length()).map { emojisJson.getString(it) }
                        EmojiCategory(
                            name = obj.getString("name"),
                            icon = obj.getString("icon"),
                            emojis = emojis
                        )
                    }

                    val skinTonesJson = root.getJSONObject("skinTones")
                    val skinTones = skinTonesJson.keys().asSequence().associateWith { key ->
                        val arr = skinTonesJson.getJSONArray(key)
                        (0 until arr.length()).map { arr.getString(it) }
                    }

                    Log.d(TAG, "Chargé : ${categories.sumOf { it.emojis.size }} emojis sur ${categories.size} catégories, ${skinTones.size} avec tons de peau")
                    EmojiData(categories, skinTones)
                } catch (e: Exception) {
                    Log.e(TAG, "Échec du chargement de $ASSET_FILE : ${e.message}", e)
                    EmojiData(emptyList(), emptyMap())
                }

                cached = loaded
                return loaded
            }
        }
    }
}
