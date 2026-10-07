package com.example.d1check.requestrunner

/**
 * 삽입 순서를 지키는 작은 JSON 직렬화기 (출력 전용). A24 ModelProbeArtifacts.json 은 Android org.json 을 쓰지만
 * (JVM 단위 시험에서는 쓸 수 없다), 여기서는 Map / Iterable / 배열 / 수 / 문자열 / Boolean / null 만 쓴다.
 * 비유한 수는 거부한다 (org.json 과 같은 fail-closed). Float 는 double 로 넓혀 적는다 (Python json 과 같은 값).
 */
object Json {
    fun encode(value: Any?): String = StringBuilder(256).also { write(it, value) }.toString()

    private fun write(sb: StringBuilder, value: Any?) {
        when (value) {
            null -> sb.append("null")
            is String -> quote(sb, value)
            is Boolean -> sb.append(value)
            is Float -> number(sb, value.toDouble())
            is Double -> number(sb, value)
            is Number -> sb.append(value.toString())
            is Enum<*> -> quote(sb, value.name)
            is Map<*, *> -> {
                sb.append('{')
                var first = true
                for ((key, nested) in value) {
                    if (!first) sb.append(',')
                    first = false
                    quote(sb, key.toString())
                    sb.append(':')
                    write(sb, nested)
                }
                sb.append('}')
            }
            is FloatArray -> list(sb, value.size) { write(sb, value[it]) }
            is DoubleArray -> list(sb, value.size) { write(sb, value[it]) }
            is IntArray -> list(sb, value.size) { sb.append(value[it]) }
            is LongArray -> list(sb, value.size) { sb.append(value[it]) }
            is Array<*> -> list(sb, value.size) { write(sb, value[it]) }
            is Iterable<*> -> {
                sb.append('[')
                var first = true
                for (item in value) {
                    if (!first) sb.append(',')
                    first = false
                    write(sb, item)
                }
                sb.append(']')
            }
            else -> quote(sb, value.toString())
        }
    }

    private inline fun list(sb: StringBuilder, size: Int, item: (Int) -> Unit) {
        sb.append('[')
        for (i in 0 until size) {
            if (i > 0) sb.append(',')
            item(i)
        }
        sb.append(']')
    }

    private fun number(sb: StringBuilder, value: Double) {
        require(value.isFinite()) { "non-finite number cannot be serialized" }
        sb.append(value.toString())
    }

    private fun quote(sb: StringBuilder, text: String) {
        sb.append('"')
        for (ch in text) {
            when {
                ch == '"' -> sb.append("\\\"")
                ch == '\\' -> sb.append("\\\\")
                ch == '\n' -> sb.append("\\n")
                ch == '\r' -> sb.append("\\r")
                ch == '\t' -> sb.append("\\t")
                ch == '\b' -> sb.append("\\b")
                ch == '\u000C' -> sb.append("\\f")
                ch < ' ' -> sb.append(String.format("\\u%04x", ch.code))
                else -> sb.append(ch)
            }
        }
        sb.append('"')
    }
}
