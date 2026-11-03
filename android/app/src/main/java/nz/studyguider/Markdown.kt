package nz.studyguider

/**
 * Converts the subset of Markdown that the lesson model produces into styled
 * spans: headings, bold, italics, bullets and inline code. LaTeX is kept
 * verbatim so [MathText] can render it.
 */
data class InlineRun(val text: String, val bold: Boolean = false, val italic: Boolean = false, val code: Boolean = false)

/**
 * Rewrites inline citations into short, readable references.
 *
 * The model cites like ``(`abd958b6-7763-4c58-81c0-95f60e54ebed`, p. 6)``.
 * Full UUIDs bury the sentence, so each unique id is replaced by a short marker
 * that matches a numbered source list under the lesson.
 */
fun shortCitations(text: String, ids: List<String>): String {
    var result = text
    ids.forEachIndexed { index, id ->
        result = result.replace(id, "S${index + 1}")
    }
    // `(S1, p. 6; S2, p. 1)` → `[S1 p. 6; S2 p. 1]`
    result = result.replace(Regex("`(S\\d+)((?:,? ?p\\.? ?\\d+)?)`"), "$1$2")
    return result.replace(Regex("\\(([S\\d][^()]*?(?:p\\.? ?\\d+)[^()]*?)\\)"), "[$1]")
}

/** Presentation only: retain original citations in saved lessons and notes. */
fun withoutSourceMarkers(text: String): String {
    val uuid = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    // Non-file evidence tags, e.g. `[S1, learner_answers]`, are internal labels, not reading content.
    val tagged = text.replace(Regex("[ \\t]*[\\[(](?:`?$uuid`?|S\\d+)\\s*[,;]\\s*[a-z]+(?:_[a-z]+)+\\s*[\\])]", RegexOption.IGNORE_CASE), "")
    val citationsRemoved = tagged.replace(Regex("[ \\t]*[\\[(]`?$uuid`?(?:\\s*[,;]\\s*(?:`?$uuid`?|pp?\\.?\\s*\\d+(?:[–-]\\d+)?))*\\s*[\\])]", RegexOption.IGNORE_CASE), "")
        .replace(Regex("`?$uuid`?", RegexOption.IGNORE_CASE), "")
    // A citation whose id was removed on its own leaves only its page behind: "(, p. 1)".
    val pagesOnly = Regex("[ \\t]*[(\\[]\\s*(?:,?\\s*(?:pp?\\.|pages?)\\s*\\d+(?:\\s*[-–,]\\s*\\d+)*\\s*;?\\s*)+[)\\]]", RegexOption.IGNORE_CASE)
    return citationsRemoved.replace(pagesOnly, "").replace(
    Regex("[ \\t]*[\\[(]S\\d+(?:\\s*(?:,|;)?\\s*(?:pp?\\.?\\s*\\d+(?:[–-]\\d+)?|S\\d+))*\\s*[\\])]", RegexOption.IGNORE_CASE),
    "",
    )
}

fun markdownBlocks(markdown: String): List<Pair<String, List<InlineRun>>> {
    val blocks = mutableListOf<Pair<String, List<InlineRun>>>()
    val paragraph = StringBuilder()
    fun flush() {
        val text = paragraph.toString().trim()
        if (text.isNotEmpty()) blocks.add("text" to inlineRuns(text))
        paragraph.clear()
    }
    markdown.lineSequence().forEach { rawLine ->
        // Keep the indent: it tells a nested bullet from a top-level one.
        val indent = rawLine.indexOfFirst { !it.isWhitespace() }.coerceAtLeast(0)
        val trimmed = rawLine.trim()
        val heading = trimmed.startsWith("#") && trimmed.dropWhile { it == '#' }.startsWith(" ")
        when {
            heading -> { flush(); blocks.add("heading" to inlineRuns(trimmed.dropWhile { it == '#' }.trim())) }
            trimmed == "---" || trimmed == "***" || trimmed == "___" -> flush()
            trimmed.startsWith("* ") || trimmed.startsWith("- ") || trimmed.startsWith("+ ") -> {
                flush(); blocks.add((if (indent >= 2) "bullet2" else "bullet") to inlineRuns(trimmed.drop(2).trim()))
            }
            trimmed.matches(Regex("^\\d+[.)]\\s.*")) -> {
                flush(); blocks.add((if (indent >= 2) "number2" else "number") to inlineRuns(trimmed.replaceFirst(Regex("^(\\d+)[.)]\\s"), "$1. ")))
            }
            trimmed.startsWith("> ") -> { flush(); blocks.add("quote" to inlineRuns(trimmed.drop(2).trim())) }
            trimmed.isEmpty() -> flush()
            else -> { if (paragraph.isNotEmpty()) paragraph.append(' '); paragraph.append(trimmed) }
        }
    }
    flush()
    return blocks
}

/** Splits on **bold**, *italic* and `code` markers; $...$ stays untouched. */
fun inlineRuns(text: String): List<InlineRun> {
    val runs = mutableListOf<InlineRun>()
    var index = 0
    val plain = StringBuilder()
    fun push() { if (plain.isNotEmpty()) { runs.add(InlineRun(plain.toString())); plain.clear() } }
    while (index < text.length) {
        when {
            text[index] == '$' -> {
                val delimiter = if (text.startsWith("$$", index)) "$$" else "$"
                val end = text.indexOf(delimiter, index + delimiter.length)
                if (end < 0) { plain.append(text.substring(index)); index = text.length }
                else { plain.append(text.substring(index, end + delimiter.length)); index = end + delimiter.length }
            }
            text.startsWith("**", index) -> {
                val end = text.indexOf("**", index + 2)
                if (end < 0) { plain.append(text.substring(index)); index = text.length }
                else { push(); runs.add(InlineRun(text.substring(index + 2, end), bold = true)); index = end + 2 }
            }
            text.startsWith("`", index) -> {
                val end = text.indexOf('`', index + 1)
                if (end < 0) { plain.append(text.substring(index)); index = text.length }
                else { push(); runs.add(InlineRun(text.substring(index + 1, end), code = true)); index = end + 1 }
            }
            // A lone * pairs with the next one; a stray asterisk stays literal.
            text[index] == '*' && !text.startsWith("**", index) -> {
                val end = text.indexOf('*', index + 1)
                if (end < 0 || end == index + 1) { plain.append(text[index]); index++ }
                else { push(); runs.add(InlineRun(text.substring(index + 1, end), italic = true)); index = end + 1 }
            }
            text[index] == '\\' && index + 1 < text.length -> { plain.append(text[index]).append(text[index + 1]); index += 2 }
            else -> { plain.append(text[index]); index++ }
        }
    }
    push()
    return runs.ifEmpty { listOf(InlineRun(text)) }
}
