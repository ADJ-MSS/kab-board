package taqbaylit.moteur

/** Analyseur JSON minimal pour les fichiers de référence. */
object JsonMini {

    fun parse(s: String): Any? = Lecteur(s).apply { blancs() }.valeur()

    private class Lecteur(val s: String) {
        var i = 0

        fun blancs() { while (i < s.length && s[i].isWhitespace()) i++ }

        fun valeur(): Any? {
            blancs()
            return when (s[i]) {
                '{' -> objet()
                '[' -> tableau()
                '"' -> chaine()
                't' -> { i += 4; true }
                'f' -> { i += 5; false }
                'n' -> { i += 4; null }
                else -> nombre()
            }
        }

        fun objet(): LinkedHashMap<String, Any?> {
            val m = LinkedHashMap<String, Any?>()
            i++; blancs()
            if (s[i] == '}') { i++; return m }
            while (true) {
                blancs()
                val k = chaine()
                blancs(); i++                       // ':'
                m[k] = valeur()
                blancs()
                if (s[i] == ',') i++ else { i++; return m }
            }
        }

        fun tableau(): ArrayList<Any?> {
            val l = ArrayList<Any?>()
            i++; blancs()
            if (s[i] == ']') { i++; return l }
            while (true) {
                l.add(valeur())
                blancs()
                if (s[i] == ',') i++ else { i++; return l }
            }
        }

        fun chaine(): String {
            val sb = StringBuilder()
            i++
            while (s[i] != '"') {
                if (s[i] == '\\') {
                    i++
                    when (s[i]) {
                        'n' -> sb.append('\n')
                        't' -> sb.append('\t')
                        'r' -> sb.append('\r')
                        'b' -> sb.append('\b')
                        'f' -> sb.append('')
                        'u' -> { sb.append(s.substring(i + 1, i + 5).toInt(16).toChar()); i += 4 }
                        else -> sb.append(s[i])
                    }
                } else sb.append(s[i])
                i++
            }
            i++
            return sb.toString()
        }

        fun nombre(): Double {
            val d = i
            while (i < s.length && (s[i].isDigit() || s[i] in "-+.eE")) i++
            return s.substring(d, i).toDouble()
        }
    }
}
