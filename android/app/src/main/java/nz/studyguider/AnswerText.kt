package nz.studyguider

import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.pow
import kotlin.math.roundToLong

// The answer as one piece of text, in the same format as the web answer box (server/web-answer.js), so an answer written on
// one device opens on the other and marking, drafts and history are unchanged: the typed text, then each table as a Markdown
// table, each drawing as ![Drawing 1](/answer-images/42), and each graph as its image plus a "Graph 1:" description line.
// Nothing in this file touches Android, so the checks in src/test run on the JVM.

/** A drawing or graph referenced from answer text. */
data class AnswerImage(val graph: Boolean, val id: Long, val caption: String = if (graph) "Graph" else "Drawing")

/** Saved answer text split back into its blocks: tables (rows of cells, header first), images, and the rest as text. */
data class AnswerParts(val tables: List<List<List<String>>>, val images: List<AnswerImage>, val text: String)

private val tableRow = Regex("^\\s*\\|.*\\|\\s*$")
private val ruleRow = Regex("^\\s*\\|(\\s*:?-{3,}:?\\s*\\|)+\\s*$")
private val imageLine = Regex("^!\\[((?:Drawing|Graph) \\d+)\\]\\(/answer-images/(\\d{1,18})\\)\\s*$")
private val anyImageLine = Regex("^\\s*!\\[([^\\]\\n]{0,80})\\]\\((/answer-images/(\\d{1,18}))\\)\\s*$")

fun isTableRow(line: String) = tableRow.matches(line)
fun isRuleRow(line: String) = ruleRow.matches(line)

/** Cells of a Markdown table row; "\|" is a literal bar inside a cell. */
fun tableCells(line: String): List<String> =
    line.trim().removePrefix("|").removeSuffix("|").split(Regex("(?<!\\\\)\\|")).map { it.trim().replace("\\|", "|") }

fun splitAnswer(value: String): AnswerParts {
    val lines = value.replace("\r\n", "\n").split("\n")
    val tables = mutableListOf<List<List<String>>>()
    val images = mutableListOf<AnswerImage>()
    val text = mutableListOf<String>()
    var i = 0
    while (i < lines.size) {
        val line = lines[i]
        if (isTableRow(line) && i + 1 < lines.size && isRuleRow(lines[i + 1])) {
            val rows = mutableListOf(tableCells(line)); i += 2
            while (i < lines.size && isTableRow(lines[i])) rows.add(tableCells(lines[i++]))
            tables.add(rows); continue
        }
        val image = imageLine.matchEntire(line.trim())
        if (image != null) {
            val caption = image.groupValues[1]
            val graph = caption.startsWith("Graph")
            if (graph && lines.getOrNull(i + 1)?.startsWith("$caption:") == true) i++
            images.add(AnswerImage(graph, image.groupValues[2].toLong(), caption))
            i++; continue
        }
        text.add(line); i++
    }
    return AnswerParts(tables, images, text.joinToString("\n").replace(Regex("\n{3,}"), "\n\n").trim())
}

/** A table as Markdown: header row, rule, body rows. Bars and line breaks inside cells are escaped or folded. */
fun tableMarkdown(rows: List<List<String>>): String {
    if (rows.isEmpty()) return ""
    val clean = { cell: String -> cell.replace("|", "\\|").replace(Regex("\\s*\n\\s*"), " ").trim() }
    val line = { row: List<String> -> "| " + row.joinToString(" | ") { clean(it) } + " |" }
    return (listOf(line(rows[0]), "| " + rows[0].joinToString(" | ") { "---" } + " |") + rows.drop(1).map(line)).joinToString("\n")
}

/** How a saved answer is shown again: text (rendered as maths), a table, or a drawing with any description below it. */
sealed class ShownBlock {
    data class Text(val text: String) : ShownBlock()
    data class Table(val rows: List<List<String>>) : ShownBlock()
    data class Image(val caption: String, val path: String, val description: String = "") : ShownBlock()
}

/** Saved answer text in reading order, with tables and this app's own drawings pulled out of the text. */
fun shownBlocks(value: String): List<ShownBlock> {
    val lines = value.replace("\r\n", "\n").split("\n")
    val blocks = mutableListOf<ShownBlock>()
    val text = mutableListOf<String>()
    fun flush() { text.joinToString("\n").trim().takeIf { it.isNotEmpty() }?.let { blocks.add(ShownBlock.Text(it)) }; text.clear() }
    var i = 0
    while (i < lines.size) {
        val line = lines[i]
        if (isTableRow(line) && i + 1 < lines.size && isRuleRow(lines[i + 1])) {
            flush()
            val rows = mutableListOf(tableCells(line)); i += 2
            while (i < lines.size && isTableRow(lines[i])) rows.add(tableCells(lines[i++]))
            blocks.add(ShownBlock.Table(rows)); continue
        }
        val image = anyImageLine.matchEntire(line)
        if (image != null) {
            flush()
            val caption = image.groupValues[1].ifBlank { "Drawing" }
            val description = lines.getOrNull(i + 1)?.takeIf { it.startsWith("$caption:") }?.removePrefix("$caption:")?.trim().orEmpty()
            if (description.isNotEmpty()) i++
            blocks.add(ShownBlock.Image(caption, image.groupValues[2], description)); i++; continue
        }
        text.add(line); i++
    }
    flush()
    return blocks
}

fun hasAnswerImages(value: String) = value.lineSequence().any { anyImageLine.matches(it) }

// ---- the drawing and graph model ------------------------------------------------------------------------------------------
// Coordinates are in the web canvas's own space: 800 wide, 500 tall for a drawing and 560 for a graph, so strokes saved on
// either device open on the other at the same place. Graph squares are 40 units, 20 across and 14 down.

const val SKETCH_WIDTH = 800f
fun sketchHeight(graph: Boolean) = if (graph) 560f else 500f
private const val CELL = SKETCH_WIDTH / 20

/** One mark: "pen" (freehand), "line", "arrow", "point" or "text" (a label), in ink "ink", "blue" or "red". */
data class SketchItem(val t: String, val p: List<Pair<Float, Float>>, val s: String = "", val c: String = "ink")

/** A graph's axes: labels and optional ranges. Without both ends of a range the grid is counted in squares from the origin. */
data class GraphAxes(val xLabel: String = "", val yLabel: String = "", val xRange: Pair<Double?, Double?>? = null, val yRange: Pair<Double?, Double?>? = null) {
    fun x(): Pair<Double, Double>? = complete(xRange)
    fun y(): Pair<Double, Double>? = complete(yRange)
    private fun complete(r: Pair<Double?, Double?>?): Pair<Double, Double>? {
        val (lo, hi) = r ?: return null
        return if (lo != null && hi != null && lo.isFinite() && hi.isFinite() && lo < hi) lo to hi else null
    }
}

/** Where the axes cross, in canvas units. */
fun graphOrigin(axes: GraphAxes): Pair<Float, Float> {
    val w = SKETCH_WIDTH; val h = sketchHeight(true)
    val xr = axes.x(); val yr = axes.y()
    val ox = if (xr != null) (if (xr.first >= 0) 0f else if (xr.second <= 0) w else (-xr.first / (xr.second - xr.first) * w).toFloat()) else Math.round(20 / 2f) * CELL
    val oy = if (yr != null) (if (yr.first >= 0) h else if (yr.second <= 0) 0f else (h - (-yr.first / (yr.second - yr.first)) * h).toFloat()) else Math.round(14 / 2f) * CELL
    return ox to oy
}

/** A canvas point as graph data: in the axis ranges when given, otherwise in grid squares from the origin. */
fun toData(axes: GraphAxes, point: Pair<Float, Float>): Pair<Double, Double> {
    val w = SKETCH_WIDTH; val h = sketchHeight(true)
    val xr = axes.x(); val yr = axes.y(); val (ox, oy) = graphOrigin(axes)
    val x = if (xr != null) xr.first + point.first / w * (xr.second - xr.first) else ((point.first - ox) / CELL).toDouble()
    val y = if (yr != null) yr.first + (h - point.second) / h * (yr.second - yr.first) else ((oy - point.second) / CELL).toDouble()
    return x to y
}

private fun steps(axes: GraphAxes): Pair<Double, Double> {
    val xr = axes.x(); val yr = axes.y()
    return (if (xr != null) (xr.second - xr.first) / 100 else 0.1) to (if (yr != null) (yr.second - yr.first) / 100 else 0.1)
}

/** Rounded to a step, written without trailing zeros, as JavaScript's Number(...) would print it. */
fun roundTo(value: Double, step: Double): String {
    val digits = maxOf(0, -floor(log10(if (step == 0.0) 1.0 else step)).toInt()).coerceAtMost(6)
    val rounded = Math.round(value / step) * step
    val scale = 10.0.pow(digits)
    val fixed = (rounded * scale).roundToLong() / scale
    if (fixed == 0.0) return "0"
    return if (fixed == floor(fixed) && abs(fixed) < 1e15) fixed.toLong().toString() else fixed.toBigDecimal().stripTrailingZeros().toPlainString()
}

fun formatPoint(axes: GraphAxes, data: Pair<Double, Double>): String {
    val (sx, sy) = steps(axes)
    return "(${roundTo(data.first, sx)}, ${roundTo(data.second, sy)})"
}

/** What the marker reads about a graph besides the picture: axes, points, lines and the shape of each curve (web describe()). */
fun describeGraph(axes: GraphAxes, items: List<SketchItem>): String {
    val xr = axes.x(); val yr = axes.y()
    val units = if (xr != null && yr != null) "" else " (no scale given: positions are in grid squares from the origin)"
    val parts = mutableListOf("x-axis \"${axes.xLabel.ifEmpty { "x" }}\"${xr?.let { " from ${num(it.first)} to ${num(it.second)}" } ?: ""}, " +
        "y-axis \"${axes.yLabel.ifEmpty { "y" }}\"${yr?.let { " from ${num(it.first)} to ${num(it.second)}" } ?: ""}$units.")
    val fmt = { p: Pair<Float, Float> -> formatPoint(axes, toData(axes, p)) }
    val points = items.filter { it.t == "point" }.map { fmt(it.p[0]) }
    if (points.isNotEmpty()) parts.add("Points plotted: ${points.joinToString(", ")}.")
    items.filter { it.t == "line" }.forEachIndexed { n, item -> parts.add("Straight line ${n + 1} from ${fmt(item.p[0])} to ${fmt(item.p[1])}.") }
    val (sx, sy) = steps(axes)
    items.filter { it.t == "pen" && it.p.size > 2 }.take(6).forEachIndexed { n, item ->
        val data = item.p.map { toData(axes, it) }
        fun crossings(axis: Int): List<String> {
            val found = mutableListOf<Double>()
            val step = if (axis == 1) sx else sy           // the other coordinate's step, for de-duplicating
            for (k in 1 until data.size) {
                val a = if (axis == 1) data[k - 1].second else data[k - 1].first
                val b = if (axis == 1) data[k].second else data[k].first
                if (a == 0.0 || (a < 0) != (b < 0)) {
                    val t = if (a == b) 0.0 else a / (a - b)
                    val from = if (axis == 1) data[k - 1].first else data[k - 1].second
                    val to = if (axis == 1) data[k].first else data[k].second
                    val value = from + t * (to - from)
                    if (found.none { abs(it - value) < step * 4 }) found.add(value)
                }
            }
            return found.take(6).map { roundTo(it, step) }
        }
        val xs = crossings(1); val ys = crossings(0)
        // Turning points: where the curve's vertical direction reverses by more than a small wobble.
        val turns = mutableListOf<String>()
        var direction = 0
        var extreme = data[0]
        for (p in data.drop(1)) {
            val change = p.second - extreme.second
            val wobble = sy * 3
            if (direction >= 0 && p.second >= extreme.second) { extreme = p; direction = 1; continue }
            if (direction <= 0 && p.second <= extreme.second) { extreme = p; direction = -1; continue }
            if (abs(change) > wobble) { turns.add("${if (direction > 0) "maximum" else "minimum"} near ${formatPoint(axes, extreme)}"); direction = -direction; extreme = p }
        }
        var line = "Curve ${n + 1} drawn from ${formatPoint(axes, data.first())} to ${formatPoint(axes, data.last())}"
        if (xs.isNotEmpty()) line += "; crosses the x-axis near x = ${xs.joinToString(", ")}"
        if (ys.isNotEmpty()) line += "; crosses the y-axis near y = ${ys.joinToString(", ")}"
        if (turns.isNotEmpty()) line += "; ${turns.take(6).joinToString(", ")}"
        parts.add("$line.")
    }
    val labels = items.filter { it.t == "text" }.map { "\"${it.s}\" at ${fmt(it.p[0])}" }
    if (labels.isNotEmpty()) parts.add("Labels: ${labels.joinToString(", ")}.")
    return parts.joinToString(" ")
}

private fun num(value: Double): String = if (value == floor(value) && abs(value) < 1e15) value.toLong().toString() else value.toString()

/** True when [point] touches [item], for the eraser (same distances as the web). */
fun touches(item: SketchItem, point: Pair<Float, Float>): Boolean {
    val (x, y) = point
    if (item.p.any { (px, py) -> Math.hypot((px - x).toDouble(), (py - y).toDouble()) < 14 }) return true
    if ((item.t == "line" || item.t == "arrow") && item.p.size >= 2) {
        val (x0, y0) = item.p[0]; val (x1, y1) = item.p[1]
        val len = Math.hypot((x1 - x0).toDouble(), (y1 - y0).toDouble()).takeIf { it > 0 } ?: 1.0
        val t = (((x - x0) * (x1 - x0) + (y - y0) * (y1 - y0)) / (len * len)).coerceIn(0.0, 1.0)
        if (Math.hypot(x0 + t * (x1 - x0) - x, y0 + t * (y1 - y0) - y) < 12) return true
    }
    return item.t == "text" && x >= item.p[0].first - 6 && x <= item.p[0].first + 16 * item.s.length && abs(y - item.p[0].second) < 16
}

// ---- symbol insertion -------------------------------------------------------------------------------------------------------

/** Inside $...$ when an odd number of dollar signs come before [at]. */
fun inMaths(text: String, at: Int) = text.take(at).count { it == '$' } % 2 == 1

/** Inside \ce{...} when one is still open before [at]. */
fun inCe(text: String, at: Int): Boolean {
    val open = text.lastIndexOf("\\ce{", (at - 1).coerceAtLeast(0))
    if (open < 0 || open >= at) return false
    var depth = 0
    for (i in open + 3 until at) { if (text[i] == '{') depth++ else if (text[i] == '}') depth-- }
    return depth > 0
}

/**
 * Inserts a symbol's LaTeX at the selection (web insertSnippet): "|" in the snippet is where the cursor lands and where any
 * selected text goes; outside maths the snippet is wrapped in $...$; inside \ce{...} the mhchem form is used when there is one.
 * Returns the new text and the cursor position.
 */
fun insertSnippet(text: String, start: Int, end: Int, latex: String, ce: String? = null): Pair<String, Int> {
    val selected = text.substring(start, end)
    var body = if (ce != null && inCe(text, start)) ce else latex
    val cursor = body.indexOf('|')
    var caret = if (cursor >= 0) cursor + selected.length else body.length
    body = if (cursor >= 0) body.replaceFirst("|", selected) else body
    if (!inMaths(text, start)) {
        body = "$" + body.trimEnd() + "$"; caret += 1
        if (cursor < 0) caret = body.length
    }
    return (text.substring(0, start) + body + text.substring(end)) to (start + caret)
}

/** Appends a typed chemical equation to the answer as its own line, as $\ce{...}$. */
fun appendEquation(text: String, equation: String): String {
    val line = equation.trim()
    if (line.isEmpty()) return text
    return text + (if (text.isNotEmpty() && !text.endsWith("\n")) "\n" else "") + "\$\\ce{$line}\$\n"
}
