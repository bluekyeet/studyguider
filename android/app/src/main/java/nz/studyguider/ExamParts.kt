package nz.studyguider

/** Preserve printed wording; only split explicit parenthesised part markers. */
fun examParts(text: String): List<Pair<String, String>> {
    val markers = Regex("(?<![A-Za-z0-9])\\(([a-h]|[ivx]{1,4})\\)(?=\\s)").findAll(text).toList()
    if (markers.isEmpty()) return listOf("" to text.trim())
    val parts = mutableListOf<Pair<String, String>>()
    text.substring(0, markers.first().range.first).trim().takeIf { it.isNotEmpty() }?.let { parts.add("" to it) }
    var parent = ""
    markers.forEachIndexed { index, marker ->
        val label = marker.groupValues[1]
        if (label.length == 1 && label[0] in 'a'..'h') parent = label
        val fullLabel = if (label == parent) "($label)" else "($parent)($label)"
        val end = markers.getOrNull(index + 1)?.range?.first ?: text.length
        val content = text.substring(marker.range.last + 1, end).trim()
        if (content.isNotEmpty()) parts.add(fullLabel to content)
    }
    return parts
}
