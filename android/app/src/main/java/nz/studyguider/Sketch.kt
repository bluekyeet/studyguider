package nz.studyguider

import android.graphics.BitmapFactory
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.CanvasDrawScope
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChange
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

// The drawing and graph canvas of the answer box. Marks are kept as vectors in the web canvas's coordinate space (AnswerText.kt),
// painted on screen, rendered to a PNG a moment after the last change, and uploaded with the strokes to /answer-images, so the
// web and the app read and edit the same drawings.

private val INKS = linkedMapOf("ink" to Color(0xFF1A1C24), "blue" to Color(0xFF2F48B8), "red" to Color(0xFFC0262D))
private val PAPER = Color.White
private val GRID = Color(0xFFDBE1EC)
private val AXIS = Color(0xFF3A3F4F)

/** One drawing or graph in an answer: its marks, axes, background, and the uploaded picture they produced. */
class SketchState(val graph: Boolean, axes: GraphAxes = GraphAxes(), background: String = "blank", items: List<SketchItem> = emptyList(),
                  imageId: Long? = null, val purpose: String = "") {
    val items = mutableStateListOf<SketchItem>().apply { addAll(items) }
    private val undone = mutableListOf<SketchItem>()
    var axes by mutableStateOf(axes)
    var background by mutableStateOf(background)
    var imageId by mutableStateOf(imageId)
    var tool by mutableStateOf("pen")
    var ink by mutableStateOf("ink")
    var live by mutableStateOf<SketchItem?>(null)
    /** Bumped on every change, so the box knows to upload again. */
    var version by mutableIntStateOf(0)
    var status by mutableStateOf("")
    /** True while marks are not yet in an uploaded picture. */
    var dirty by mutableStateOf(false)

    val height get() = sketchHeight(graph)
    val canUndo get() = items.isNotEmpty()
    val canRedo get() = undone.isNotEmpty()

    fun changed(clearRedo: Boolean = true) {
        if (clearRedo) undone.clear()
        dirty = true; version++
        if (items.isEmpty()) imageId = null
        status = if (items.isEmpty()) "" else "Not saved yet…"
    }
    fun add(item: SketchItem) { items.add(item); changed() }
    fun undo() { if (items.isNotEmpty()) { undone.add(items.removeAt(items.lastIndex)); changed(clearRedo = false) } }
    fun redo() { if (undone.isNotEmpty()) { items.add(undone.removeAt(undone.lastIndex)); changed(clearRedo = false) } }
    fun clear() { items.clear(); undone.clear(); changed() }
    fun erase(point: Pair<Float, Float>) {
        val before = items.size
        items.removeAll { touches(it, point) }
        if (items.size != before) changed()
    }

    /** The strokes as the server keeps them (the same JSON the web sends), so either app can open the drawing again. */
    fun strokesJson(): JSONObject = JSONObject().apply {
        put("kind", if (graph) "graph" else "drawing")
        put("background", background)
        put("items", JSONArray().apply {
            items.forEach { item ->
                put(JSONObject().put("t", item.t).put("c", item.c)
                    .put("p", JSONArray().apply { item.p.forEach { (x, y) -> put(JSONArray().put(x.toDouble()).put(y.toDouble())) } })
                    .apply { if (item.t == "text") put("s", item.s) })
            }
        })
        if (graph) {
            put("x_label", axes.xLabel); put("y_label", axes.yLabel)
            put("x_range", axes.xRange?.let { JSONArray().put(it.first ?: JSONObject.NULL).put(it.second ?: JSONObject.NULL) } ?: JSONObject.NULL)
            put("y_range", axes.yRange?.let { JSONArray().put(it.first ?: JSONObject.NULL).put(it.second ?: JSONObject.NULL) } ?: JSONObject.NULL)
        }
    }

    /** What goes into the answer text: the image reference, and for a graph the line describing it. Empty until uploaded. */
    fun text(number: Int): String {
        val id = imageId ?: return ""
        if (items.isEmpty()) return ""
        val name = "${if (graph) "Graph" else "Drawing"} $number"
        return "![$name](/answer-images/$id)" + if (graph) "\n$name: ${describeGraph(axes, items)}" else ""
    }

    companion object {
        /** A sketch from strokes saved by either app. */
        fun fromJson(graph: Boolean, json: JSONObject, imageId: Long?, form: AnswerForm? = null): SketchState {
            val items = json.optJSONArray("items")?.objectList().orEmpty().mapNotNull { item ->
                val points = item.optJSONArray("p") ?: return@mapNotNull null
                val p = (0 until points.length()).mapNotNull { i -> points.optJSONArray(i)?.let { it.optDouble(0).toFloat() to it.optDouble(1).toFloat() } }
                if (p.isEmpty()) null else SketchItem(item.optString("t"), p, item.optString("s"), item.optString("c", "ink"))
            }
            fun range(key: String): Pair<Double?, Double?>? = json.optJSONArray(key)?.takeIf { it.length() == 2 }?.let {
                (if (it.isNull(0)) null else it.optDouble(0)) to (if (it.isNull(1)) null else it.optDouble(1))
            }
            val formAxes = (form as? AnswerForm.Graph)?.axes ?: GraphAxes()
            val axes = GraphAxes(json.optString("x_label", formAxes.xLabel), json.optString("y_label", formAxes.yLabel),
                range("x_range") ?: formAxes.xRange, range("y_range") ?: formAxes.yRange)
            return SketchState(graph, axes, json.optString("background", "blank").ifBlank { "blank" }, items, imageId, (form as? AnswerForm.Drawing)?.purpose.orEmpty())
        }
    }
}

// ---- painting ---------------------------------------------------------------------------------------------------------------

/** Paints the sketch into [size], scaling the canvas coordinates to fit. Used on screen and for the uploaded PNG. */
private fun DrawScope.paintSketch(state: SketchState, figure: ImageBitmap?, measurer: TextMeasurer) {
    val k = size.width / SKETCH_WIDTH
    val h = state.height
    fun at(x: Float, y: Float) = Offset(x * k, y * k)
    drawRect(PAPER)
    if (state.background == "figure" && figure != null) {
        val fit = minOf(SKETCH_WIDTH / figure.width, h / figure.height)
        val w = figure.width * fit; val fh = figure.height * fit
        drawImage(figure, dstOffset = androidx.compose.ui.unit.IntOffset(((SKETCH_WIDTH - w) / 2 * k).toInt(), ((h - fh) / 2 * k).toInt()),
            dstSize = androidx.compose.ui.unit.IntSize((w * k).toInt(), (fh * k).toInt()))
    }
    if (state.graph || state.background == "grid") {
        var x = 40f
        while (x < SKETCH_WIDTH) { drawLine(GRID, at(x, 0f), at(x, h), strokeWidth = maxOf(1f, k)); x += 40f }
        var y = 40f
        while (y < h) { drawLine(GRID, at(0f, y), at(SKETCH_WIDTH, y), strokeWidth = maxOf(1f, k)); y += 40f }
    }
    if (state.graph) {
        val (ox, oy) = graphOrigin(state.axes)
        val ax = ox.coerceIn(1f, SKETCH_WIDTH - 1); val ay = oy.coerceIn(1f, h - 1)
        drawLine(AXIS, at(ax, h), at(ax, 0f), strokeWidth = 2 * k)
        drawLine(AXIS, at(0f, ay), at(SKETCH_WIDTH, ay), strokeWidth = 2 * k)
        val xName = measurer.label(state.axes.xLabel.ifEmpty { "x" }, 20 * k, AXIS, italicSerif = true)
        drawText(xName, topLeft = at(SKETCH_WIDTH - 8, oy.coerceIn(24f, h - 4) - 8) - Offset(xName.size.width.toFloat(), xName.size.height * 0.8f))
        drawText(measurer.label(state.axes.yLabel.ifEmpty { "y" }, 20 * k, AXIS, italicSerif = true), topLeft = at(ox.coerceIn(0f, SKETCH_WIDTH - 80) + 8, 4f))
        val small = Color(0xFF555B6E)
        state.axes.x()?.let { (lo, hi) ->
            val y = oy.coerceIn(14f, h - 22) + 4
            drawText(measurer.label(plain(lo), 13 * k, small), topLeft = at(4f, y))
            val right = measurer.label(plain(hi), 13 * k, small)
            drawText(right, topLeft = at(SKETCH_WIDTH - 4, y) - Offset(right.size.width.toFloat(), 0f))
        }
        state.axes.y()?.let { (lo, hi) ->
            val x = ox.coerceIn(0f, SKETCH_WIDTH - 60) + 6
            drawText(measurer.label(plain(hi), 13 * k, small), topLeft = at(x, 28f))
            drawText(measurer.label(plain(lo), 13 * k, small), topLeft = at(x, h - 20))
        }
    }
    (state.items + listOfNotNull(state.live)).forEach { item ->
        val colour = INKS[item.c] ?: INKS.getValue("ink")
        val width = (if (item.t == "pen") 3f else 2.5f) * k
        when (item.t) {
            "pen" -> {
                if (item.p.size == 1) drawCircle(colour, width / 2, at(item.p[0].first, item.p[0].second))
                else drawPath(Path().apply { item.p.forEachIndexed { i, (x, y) -> if (i == 0) moveTo(x * k, y * k) else lineTo(x * k, y * k) } }, colour,
                    style = Stroke(width, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
            "line", "arrow" -> if (item.p.size >= 2) {
                val (x0, y0) = item.p[0]; val (x1, y1) = item.p[1]
                drawLine(colour, at(x0, y0), at(x1, y1), strokeWidth = width, cap = StrokeCap.Round)
                if (item.t == "arrow") {
                    val a = atan2(y1 - y0, x1 - x0); val s = 16f
                    drawPath(Path().apply {
                        moveTo(x1 * k, y1 * k)
                        lineTo((x1 - s * cos(a - .4f)) * k, (y1 - s * sin(a - .4f)) * k)
                        lineTo((x1 - s * cos(a + .4f)) * k, (y1 - s * sin(a + .4f)) * k)
                        close()
                    }, colour)
                }
            }
            "point" -> {
                val (x, y) = item.p[0]
                drawCircle(colour, 5 * k, at(x, y))
                val label = measurer.label(formatPoint(state.axes, toData(state.axes, item.p[0])), 13 * k, colour)
                drawText(label, topLeft = at(x + 8, y - 8) - Offset(0f, label.size.height.toFloat()))
            }
            "text" -> {
                val label = measurer.label(item.s, 28 * k, colour)
                drawText(label, topLeft = at(item.p[0].first, item.p[0].second) - Offset(0f, label.size.height / 2f))
            }
        }
    }
}

private fun plain(value: Double): String = if (value == Math.floor(value) && kotlin.math.abs(value) < 1e15) value.toLong().toString() else value.toString()

/** The sketch as PNG bytes at 1.5 times the canvas size, as the web uploads it. */
fun sketchPng(state: SketchState, figure: ImageBitmap?, measurer: TextMeasurer): ByteArray {
    val width = (SKETCH_WIDTH * 1.5f).toInt(); val height = (state.height * 1.5f).toInt()
    val bitmap = ImageBitmap(width, height)
    CanvasDrawScope().draw(Density(1f), LayoutDirection.Ltr, androidx.compose.ui.graphics.Canvas(bitmap), Size(width.toFloat(), height.toFloat())) {
        paintSketch(state, figure, measurer)
    }
    val out = java.io.ByteArrayOutputStream()
    bitmap.asAndroidBitmap().compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out)
    return out.toByteArray()
}

/** Uploads the sketch if it changed; afterwards [SketchState.imageId] names the stored picture. */
suspend fun saveSketch(api: Api, state: SketchState, figure: ImageBitmap?, measurer: TextMeasurer) {
    if (!state.dirty) return
    if (state.items.isEmpty()) { state.dirty = false; state.imageId = null; state.status = ""; return }
    val version = state.version
    state.status = "Saving drawing…"
    val png = withContext(Dispatchers.Default) { sketchPng(state, figure, measurer) }
    val reply = JSONObject(api.multipart("/answer-images", mapOf("drawing" to state.strokesJson().toString()), listOf(Api.Part("image", "drawing.png", "image/png", png))))
    // A change made during the upload keeps the sketch dirty, so the next save sends the newer version.
    if (state.version == version) { state.imageId = reply.getLong("id"); state.dirty = false; state.status = "Drawing saved" }
}

/** Loads the question's figure (an authorised server image) for drawing over. */
@Composable
fun rememberFigure(api: Api?, path: String?): ImageBitmap? {
    var figure by remember(path) { mutableStateOf<ImageBitmap?>(null) }
    LaunchedEffect(path) {
        if (api == null || path.isNullOrBlank()) return@LaunchedEffect
        figure = try { withContext(Dispatchers.IO) { api.bytes(path).let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() } } }
            catch (e: CancellationException) { throw e } catch (e: Exception) { null }
    }
    return figure
}

// ---- the canvas on screen ---------------------------------------------------------------------------------------------------

/** The drawing surface: draws with a finger or stylus. Vertical page scrolling does not start on it, so strokes never scroll. */
@Composable
fun SketchCanvas(state: SketchState, figure: ImageBitmap?, enabled: Boolean, modifier: Modifier = Modifier, onLabel: (Pair<Float, Float>) -> Unit) {
    val measurer = rememberTextMeasurer()
    val outline = MaterialTheme.colorScheme.outlineVariant
    Canvas(
        modifier
            .fillMaxWidth()
            .aspectRatio(SKETCH_WIDTH / state.height)
            .clip(RoundedCornerShape(10.dp))
            .border(1.dp, outline, RoundedCornerShape(10.dp))
            .semantics { contentDescription = if (state.graph) "Graph area: draw with your finger" else "Drawing area: draw with your finger" }
            .pointerInput(state, enabled) {
                if (!enabled) return@pointerInput
                awaitEachGesture {
                    val down = awaitFirstDown()
                    down.consume()
                    fun units(o: Offset) = (o.x / size.width * SKETCH_WIDTH).coerceIn(0f, SKETCH_WIDTH) to (o.y / size.width * SKETCH_WIDTH).coerceIn(0f, state.height)
                    val start = units(down.position)
                    when (state.tool) {
                        "text" -> { onLabel(start); return@awaitEachGesture }
                        "point" -> { state.add(SketchItem("point", listOf(start), c = state.ink)); return@awaitEachGesture }
                        "erase" -> state.erase(start)
                        else -> state.live = SketchItem(state.tool, if (state.tool == "pen") listOf(start) else listOf(start, start), c = state.ink)
                    }
                    while (true) {
                        val event = awaitPointerEvent()
                        val change = event.changes.firstOrNull { it.id == down.id } ?: break
                        if (!change.pressed) break
                        if (change.positionChange() != Offset.Zero) change.consume()
                        val p = units(change.position)
                        val live = state.live
                        when {
                            state.tool == "erase" -> state.erase(p)
                            live != null && live.t == "pen" -> {
                                val last = live.p.last()
                                if (hypot(p.first - last.first, p.second - last.second) > 1.5f) state.live = live.copy(p = live.p + p)
                            }
                            live != null -> state.live = live.copy(p = listOf(live.p[0], p))
                        }
                    }
                    state.live?.let { live ->
                        val long = live.t == "pen" || hypot(live.p[1].first - live.p[0].first, live.p[1].second - live.p[0].second) > 4f
                        state.live = null
                        if (long) state.add(live)
                    }
                }
            },
    ) { paintSketch(state, figure, measurer) }
}

/** Tools under the canvas: what to draw, ink, undo, redo, clear and the background. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SketchTools(state: SketchState, hasFigure: Boolean, enabled: Boolean) {
    var confirmClear by remember { mutableStateOf(false) }
    val tools = if (state.graph) listOf("pen" to "Curve", "line" to "Line", "point" to "Point", "text" to "Label", "erase" to "Erase")
        else listOf("pen" to "Pen", "line" to "Line", "arrow" to "Arrow", "text" to "Label", "erase" to "Erase")
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
            tools.forEach { (key, label) ->
                FilterChip(selected = state.tool == key, enabled = enabled, onClick = { state.tool = key }, label = { Text(label) })
            }
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(4.dp), itemVerticalAlignment = Alignment.CenterVertically) {
            INKS.forEach { (key, colour) ->
                val chosen = state.ink == key
                Surface(onClick = { state.ink = key }, enabled = enabled, shape = CircleShape, color = colour,
                    border = if (chosen) androidx.compose.foundation.BorderStroke(3.dp, MaterialTheme.colorScheme.primary) else null,
                    modifier = Modifier.size(34.dp).semantics { contentDescription = "${if (key == "ink") "Black" else key.replaceFirstChar { it.uppercase() }} ink" }) {}
            }
            Spacer(Modifier.width(4.dp))
            TextButton(enabled = enabled && state.canUndo, onClick = state::undo) { Text("Undo") }
            TextButton(enabled = enabled && state.canRedo, onClick = state::redo) { Text("Redo") }
            TextButton(enabled = enabled && state.items.isNotEmpty(), onClick = { confirmClear = true }) { Text("Clear") }
        }
        if (!state.graph) Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Background", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            (listOf("blank" to "Blank", "grid" to "Grid") + if (hasFigure) listOf("figure" to "The figure") else emptyList()).forEach { (key, label) ->
                FilterChip(selected = state.background == key, enabled = enabled, onClick = { state.background = key; state.changed() }, label = { Text(label) })
            }
        }
    }
    if (confirmClear) AlertDialog(onDismissRequest = { confirmClear = false }, title = { Text("Clear this drawing?") },
        confirmButton = { TextButton(onClick = { state.clear(); confirmClear = false }) { Text("Clear", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirmClear = false }) { Text("Keep it") } })
}

/** Axis labels and optional ranges for a graph. */
@Composable
fun GraphAxesFields(state: SketchState, enabled: Boolean) {
    fun number(text: String) = text.trim().toDoubleOrNull()
    var xMin by remember(state) { mutableStateOf(state.axes.xRange?.first?.let(::plain).orEmpty()) }
    var xMax by remember(state) { mutableStateOf(state.axes.xRange?.second?.let(::plain).orEmpty()) }
    var yMin by remember(state) { mutableStateOf(state.axes.yRange?.first?.let(::plain).orEmpty()) }
    var yMax by remember(state) { mutableStateOf(state.axes.yRange?.second?.let(::plain).orEmpty()) }
    fun ranges() {
        fun pair(lo: String, hi: String) = (number(lo) to number(hi)).takeIf { it.first != null || it.second != null }
        state.axes = state.axes.copy(xRange = pair(xMin, xMax), yRange = pair(yMin, yMax)); state.changed(clearRedo = false)
    }
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(state.axes.xLabel, { state.axes = state.axes.copy(xLabel = it.take(40)); state.changed(clearRedo = false) }, Modifier.weight(1f),
                enabled = enabled, singleLine = true, label = { Text("x-axis label") })
            OutlinedTextField(state.axes.yLabel, { state.axes = state.axes.copy(yLabel = it.take(40)); state.changed(clearRedo = false) }, Modifier.weight(1f),
                enabled = enabled, singleLine = true, label = { Text("y-axis label") })
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            val keyboard = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Decimal)
            OutlinedTextField(xMin, { xMin = it; ranges() }, Modifier.weight(1f), enabled = enabled, singleLine = true, label = { Text("x min") }, keyboardOptions = keyboard)
            OutlinedTextField(xMax, { xMax = it; ranges() }, Modifier.weight(1f), enabled = enabled, singleLine = true, label = { Text("x max") }, keyboardOptions = keyboard)
            OutlinedTextField(yMin, { yMin = it; ranges() }, Modifier.weight(1f), enabled = enabled, singleLine = true, label = { Text("y min") }, keyboardOptions = keyboard)
            OutlinedTextField(yMax, { yMax = it; ranges() }, Modifier.weight(1f), enabled = enabled, singleLine = true, label = { Text("y max") }, keyboardOptions = keyboard)
        }
        Text("Ranges are optional: leave them empty to sketch, and positions are then given in grid squares from the origin.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/**
 * A drawing or graph block. In the answer it is a picture of the drawing that scrolls with the page; tapping it opens the
 * editor over the whole screen, where a finger draws and never scrolls. Saving happens in the background after each change.
 */
@Composable
fun SketchBlock(api: Api, state: SketchState, number: Int, figure: ImageBitmap?, enabled: Boolean, onRemove: () -> Unit, onSaved: () -> Unit) {
    val measurer = rememberTextMeasurer()
    var labelAt by remember { mutableStateOf<Pair<Float, Float>?>(null) }
    var editing by remember { mutableStateOf(false) }
    var confirmRemove by remember { mutableStateOf(false) }
    // Upload a moment after the last change; retry every few seconds if it fails.
    LaunchedEffect(state.version) {
        if (!state.dirty) return@LaunchedEffect
        delay(1200)
        while (state.dirty) {
            try { saveSketch(api, state, figure, measurer); onSaved() }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { state.status = "Drawing not saved (${e.message ?: "offline"}). Retrying…"; delay(5000) }
        }
    }
    val kind = if (state.graph) "Graph" else "Drawing"
    val name = "$kind $number"
    val empty = state.items.isEmpty()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(name, style = MaterialTheme.typography.titleSmall)
                if (state.status.isNotEmpty()) Text(state.status, style = MaterialTheme.typography.labelSmall,
                    color = if (state.status.startsWith("Drawing not")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
            }
            TextButton(enabled = enabled, onClick = { if (empty) onRemove() else confirmRemove = true }) { Text("Remove") }
        }
        Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).clickable(enabled = enabled, onClickLabel = "Open the ${kind.lowercase()} editor") { editing = true }) {
            SketchCanvas(state, figure, enabled = false, onLabel = {})
            if (empty) Surface(shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.primary, modifier = Modifier.align(Alignment.Center)) {
                Text(if (state.graph) "Tap to sketch the graph" else "Tap to draw", color = MaterialTheme.colorScheme.onPrimary,
                    style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(horizontal = 18.dp, vertical = 10.dp))
            }
        }
        if (!empty) OutlinedButton(enabled = enabled, onClick = { editing = true }, shape = RoundedCornerShape(50)) { Text("Edit ${kind.lowercase()}") }
    }
    if (editing) FullScreenDialog(onDismissRequest = { editing = false }) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().systemBarsPadding()) {
                Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 12.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(name, style = MaterialTheme.typography.titleLarge)
                        Text(state.status.ifEmpty { if (state.graph) "Sketch with your finger" else "Draw with your finger" }, style = MaterialTheme.typography.labelSmall,
                            color = if (state.status.startsWith("Drawing not")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Button(onClick = { editing = false }, shape = RoundedCornerShape(50)) { Text("Done") }
                }
                SketchCanvas(state, figure, enabled, Modifier.padding(horizontal = 12.dp), onLabel = { labelAt = it })
                // Between the canvas and the tools: advice for this kind of drawing, and a graph's axes. Only this part scrolls.
                Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    when (state.purpose) {
                        "lewis" -> Text("Use Label for each atom symbol, Line for bonds and Pen for lone-pair dots.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        "structure" -> Text("Use Label for atoms and groups (CH₃, OH, C=O), Line for bonds and Arrow for reaction steps with the reagents labelled over them.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    if (state.graph) {
                        Text("Axes", style = MaterialTheme.typography.titleSmall)
                        GraphAxesFields(state, enabled)
                    }
                }
                // The tools sit at the bottom of the screen, within reach of a thumb.
                Surface(color = LocalStudyColours.current.container, shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) { SketchTools(state, figure != null, enabled) }
                }
            }
        }
    }
    if (confirmRemove) AlertDialog(onDismissRequest = { confirmRemove = false }, title = { Text("Remove this ${kind.lowercase()} from your answer?") },
        confirmButton = { TextButton(onClick = { confirmRemove = false; onRemove() }) { Text("Remove", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirmRemove = false }) { Text("Keep it") } })
    labelAt?.let { at ->
        var words by remember { mutableStateOf("") }
        AlertDialog(onDismissRequest = { labelAt = null }, title = { Text("Label") },
            text = { OutlinedTextField(words, { words = it.take(40) }, singleLine = true, placeholder = { Text(if (state.graph) "For example 2, A or y = x²" else "For example Cl, δ+, N or Weight") }) },
            confirmButton = { TextButton(enabled = words.isNotBlank(), onClick = {
                // The label is centred where the finger tapped; its stored point is its left edge, as the web draws it.
                val half = measurer.label(words.trim(), 28f, Color.Black).size.width / 2f
                state.add(SketchItem("text", listOf((at.first - half).coerceAtLeast(0f) to at.second), words.trim(), state.ink)); labelAt = null
            }) { Text("Add") } },
            dismissButton = { TextButton(onClick = { labelAt = null }) { Text("Cancel") } })
    }
}

/** Text measured at one pixel per sp, so a label is [px] pixels tall whatever the screen density. */
private fun TextMeasurer.label(text: String, px: Float, colour: Color, italicSerif: Boolean = false) = measure(
    text, TextStyle(color = colour, fontSize = px.sp, fontStyle = if (italicSerif) FontStyle.Italic else FontStyle.Normal,
        fontFamily = if (italicSerif) FontFamily.Serif else FontFamily.SansSerif), density = Density(1f, 1f))
