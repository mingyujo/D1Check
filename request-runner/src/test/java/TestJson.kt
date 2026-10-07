package com.example.d1check.requestrunner

/**
 * 시험 전용 작은 JSON 파서 (org.json 은 Robolectric 없는 JVM 시험에서 쓸 수 없다). 객체 → LinkedHashMap, 배열 → List,
 * 수 → Long 또는 Double, 문자열 · Boolean · null. fixture 와 산출물을 읽는 데만 쓴다.
 */
object TestJson {
    fun parse(text: String): Any? = Parser(text).run { skipWs(); val v = value(); skipWs(); require(pos == text.length) { "trailing data" }; v }

    private class Parser(val s: String) {
        var pos = 0
        fun skipWs() { while (pos < s.length && s[pos].isWhitespace()) pos++ }
        fun value(): Any? {
            skipWs()
            return when (val c = s[pos]) {
                '{' -> obj()
                '[' -> arr()
                '"' -> str()
                't' -> { expect("true"); true }
                'f' -> { expect("false"); false }
                'n' -> { expect("null"); null }
                else -> if (c == '-' || c.isDigit()) num() else error("unexpected '$c' at $pos")
            }
        }
        fun expect(word: String) { require(s.startsWith(word, pos)) { "expected $word at $pos" }; pos += word.length }
        fun obj(): Map<String, Any?> {
            val out = LinkedHashMap<String, Any?>()
            pos++; skipWs()
            if (s[pos] == '}') { pos++; return out }
            while (true) {
                skipWs(); val k = str(); skipWs(); require(s[pos] == ':'); pos++
                out[k] = value(); skipWs()
                when (s[pos]) { ',' -> pos++; '}' -> { pos++; return out }; else -> error("bad object at $pos") }
            }
        }
        fun arr(): List<Any?> {
            val out = ArrayList<Any?>()
            pos++; skipWs()
            if (s[pos] == ']') { pos++; return out }
            while (true) {
                out.add(value()); skipWs()
                when (s[pos]) { ',' -> pos++; ']' -> { pos++; return out }; else -> error("bad array at $pos") }
            }
        }
        fun str(): String {
            require(s[pos] == '"'); pos++
            val sb = StringBuilder()
            while (true) {
                val c = s[pos++]
                when (c) {
                    '"' -> return sb.toString()
                    '\\' -> when (val e = s[pos++]) {
                        'n' -> sb.append('\n'); 'r' -> sb.append('\r'); 't' -> sb.append('\t'); 'b' -> sb.append('\b'); 'f' -> sb.append('\u000C')
                        'u' -> { sb.append(s.substring(pos, pos + 4).toInt(16).toChar()); pos += 4 }
                        else -> sb.append(e)
                    }
                    else -> sb.append(c)
                }
            }
        }
        fun num(): Any {
            val start = pos
            if (s[pos] == '-') pos++
            while (pos < s.length && (s[pos].isDigit() || s[pos] in ".eE+-")) pos++
            val t = s.substring(start, pos)
            return if (t.any { it in ".eE" }) t.toDouble() else t.toLong()
        }
    }
}
