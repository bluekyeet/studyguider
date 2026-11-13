package nz.studyguider

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.withContext

// The answer box (the Android counterpart of server/web-answer.js): text with a maths and chemistry symbol bar, plus the
// table, drawing or graph the question asks for, and any the learner adds. The answer is still one piece of text (AnswerText.kt),
// so every screen keeps saving, drafting, hinting and marking a string. Call [AnswerBoxState.flush] before submitting, so a
// drawing that is still uploading is part of the answer.

/** One extra part of an answer, besides its text. */
sealed class AnswerBlock {
    class Table(form: AnswerForm.Table?, saved: List<List<String>>?) : AnswerBlock() {
        /** The given table: its headings and printed cells stay fixed. Null when the learner builds the table. */
        val template: AnswerForm.Table? = form?.takeIf { it.columns.isNotEmpty() }
        val columns = mutableStateListOf<String>().apply { addAll(saved?.firstOrNull() ?: template?.columns ?: listOf("", "", "")) }
        val rows = mutableStateListOf<List<String>>().apply {
            val start = saved?.drop(1) ?: template?.rows ?: listOf(listOf("", "", ""), listOf("", "", ""))
            addAll(start.map { row -> List(columns.size) { c -> row.getOrNull(c).orEmpty() } })
        }
        fun given(r: Int, c: Int) = template?.rows?.getOrNull(r)?.getOrNull(c)?.takeIf { it.isNotBlank() }
        fun text(): String {
            val filled = rows.withIndex().any { (r, row) -> row.withIndex().any { (c, cell) -> given(r, c) == null && cell.isNotBlank() } }
            if (!filled && !(template == null && columns.any { it.isNotBlank() })) return ""
            return tableMarkdown(listOf(columns.toList()) + rows.map { it })
        }
    }

    class Sketch(val state: SketchState) : AnswerBlock()

    /** Multiple choice: the keys chosen so far. */
    class Choice(val form: AnswerForm.Choice, chosen: List<String>) : AnswerBlock() {
        val chosen = mutableStateListOf<String>().apply { addAll(chosen.filter { key -> form.options.any { it.key == key } }) }
        fun toggle(key: String) {
            if (form.multiple) { if (key in chosen) chosen.remove(key) else chosen.add(key) }
            else { chosen.clear(); chosen.add(key) }
        }
    }

    /** A saved drawing whose strokes are still being fetched; until then it keeps its reference in the answer as it was. */
    class Pending(val image: AnswerImage, val description: String, val form: AnswerForm?) : AnswerBlock()
}

class AnswerBoxState(val api: Api, forms: List<AnswerForm>?, initial: String) {
    var forms by mutableStateOf(forms)
        private set
    var text by mutableStateOf(TextFieldValue(""))
    var palette by mutableStateOf("maths")
    val blocks = mutableStateListOf<AnswerBlock>()
    internal var figure: ImageBitmap? = null
    internal var measurer: androidx.compose.ui.text.TextMeasurer? = null

    init { load(initial) }

    /** The whole answer as text: each extra block in order, then the typed text, as the web writes it. */
    val value: String get() {
        var number = 0
        // The Choice line comes first, on its own line; everything else follows as optional working.
        val parts = blocks.filterIsInstance<AnswerBlock.Choice>().map { choiceText(it.chosen) } + blocks.map { block ->
            when (block) {
                is AnswerBlock.Choice -> ""
                is AnswerBlock.Table -> block.text()
                is AnswerBlock.Sketch -> { number++; block.state.text(number) }
                is AnswerBlock.Pending -> {
                    number++
                    val name = "${if (block.image.graph) "Graph" else "Drawing"} $number"
                    "![$name](/answer-images/${block.image.id})" + if (block.image.graph && block.description.isNotEmpty()) "\n$name: ${block.description}" else ""
                }
            }
        } + text.text.trim()
        return parts.filter { it.isNotBlank() }.joinToString("\n\n")
    }

    /** Lays the blocks out for the question's forms, filled from saved answer text. */
    fun load(saved: String) {
        val wanted = forms.orEmpty()
        palette = wanted.filterIsInstance<AnswerForm.Text>().firstOrNull()?.palette?.takeIf { it in SYMBOLS } ?: palette
        val parts = splitAnswer(saved)
        // A saved Choice line stays in the text when this question has no choice form to show it in.
        val typed = if (parts.choice.isNotEmpty() && wanted.none { it is AnswerForm.Choice }) listOf(choiceText(parts.choice), parts.text).filter { it.isNotBlank() }.joinToString("\n\n") else parts.text
        text = TextFieldValue(typed, TextRange(typed.length))
        blocks.clear()
        val tables = parts.tables.toMutableList()
        val images = parts.images.toMutableList()
        fun description(image: AnswerImage) = saved.lineSequence().firstOrNull { it.startsWith("${image.caption}:") }?.removePrefix("${image.caption}:")?.trim().orEmpty()
        for (form in wanted) when (form) {
            is AnswerForm.Text -> {}
            is AnswerForm.Choice -> blocks.add(AnswerBlock.Choice(form, parts.choice))
            is AnswerForm.Table -> blocks.add(AnswerBlock.Table(form, tables.removeFirstOrNull()))
            is AnswerForm.Drawing, is AnswerForm.Graph -> {
                val graph = form is AnswerForm.Graph
                val at = images.indexOfFirst { it.graph == graph }
                blocks.add(if (at >= 0) images.removeAt(at).let { AnswerBlock.Pending(it, description(it), form) } else newSketch(form))
            }
        }
        tables.forEach { blocks.add(AnswerBlock.Table(null, it)) }
        images.forEach { blocks.add(AnswerBlock.Pending(it, description(it), null)) }
    }

    /** Forms that arrive after the box was shown (lesson questions ask the server) are added unless that kind is already there. */
    fun receive(found: List<AnswerForm>) {
        forms = found
        found.filterIsInstance<AnswerForm.Text>().firstOrNull()?.palette?.takeIf { it in SYMBOLS && text.text.isEmpty() }?.let { palette = it }
        for (form in found) when (form) {
            is AnswerForm.Text -> {}
            is AnswerForm.Choice -> if (blocks.none { it is AnswerBlock.Choice }) blocks.add(0, AnswerBlock.Choice(form, emptyList()))
            is AnswerForm.Table -> if (blocks.none { it is AnswerBlock.Table }) blocks.add(AnswerBlock.Table(form, null))
            is AnswerForm.Drawing -> if (blocks.none { (it as? AnswerBlock.Sketch)?.state?.graph == false || (it as? AnswerBlock.Pending)?.image?.graph == false }) blocks.add(newSketch(form))
            is AnswerForm.Graph -> if (blocks.none { (it as? AnswerBlock.Sketch)?.state?.graph == true || (it as? AnswerBlock.Pending)?.image?.graph == true }) blocks.add(newSketch(form))
        }
    }

    fun newSketch(form: AnswerForm): AnswerBlock.Sketch = when (form) {
        is AnswerForm.Graph -> AnswerBlock.Sketch(SketchState(true, form.axes))
        is AnswerForm.Drawing -> AnswerBlock.Sketch(SketchState(false, background = form.background, purpose = form.purpose))
        else -> AnswerBlock.Sketch(SketchState(false))
    }

    val hasChoice get() = blocks.any { it is AnswerBlock.Choice }

    /** Replaces only the typed text, keeping tables and drawings (used when handwriting is read from a photo). */
    fun setText(value: String) { text = TextFieldValue(value, TextRange(value.length)) }

    /** Waits for saved drawings to load and uploads any drawing not yet saved. */
    suspend fun flush() {
        repeat(50) { if (blocks.none { it is AnswerBlock.Pending }) return@repeat; delay(100) }
        val measurer = measurer ?: return
        blocks.filterIsInstance<AnswerBlock.Sketch>().forEach { saveSketch(api, it.state, figure, measurer) }
    }
}

@Composable
fun rememberAnswerBox(api: Api, key: Any?, forms: List<AnswerForm>?, initial: String): AnswerBoxState =
    remember(key) { AnswerBoxState(api, forms, initial) }

/**
 * The answer box on screen. [onChange] gets the whole answer text whenever it changes. [collapsed] hides the symbol bar behind
 * a button, for screens with several boxes; [figurePath] is the question's figure, which a drawing can be made over.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AnswerBox(
    state: AnswerBoxState,
    enabled: Boolean = true,
    label: String = "Your answer",
    collapsed: Boolean = false,
    minLines: Int = 4,
    figurePath: String? = null,
    onChange: (String) -> Unit = {},
) {
    val figure = rememberFigure(state.api, figurePath)
    val measurer = rememberTextMeasurer()
    SideEffect { state.figure = figure; state.measurer = measurer }
    val latest by rememberUpdatedState(onChange)
    LaunchedEffect(state) { snapshotFlow { state.value }.distinctUntilChanged().collect { latest(it) } }
    val colours = LocalStudyColours.current
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        state.blocks.toList().forEach { block ->
            key(block) {
                Surface(shape = RoundedCornerShape(14.dp), color = colours.containerHigh, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        when (block) {
                            is AnswerBlock.Choice -> ChoiceBlock(state.api, block, enabled)
                            is AnswerBlock.Table -> TableBlock(block, enabled, onRemove = { state.blocks.remove(block) })
                            is AnswerBlock.Sketch -> SketchBlock(state.api, block.state, sketchNumber(state, block), figure, enabled,
                                onRemove = { state.blocks.remove(block) }, onSaved = {})
                            is AnswerBlock.Pending -> PendingSketch(state, block)
                        }
                    }
                }
            }
        }
        // With options to choose from, written working is optional and stays folded away until asked for.
        var working by rememberSaveable(state) { mutableStateOf(!state.hasChoice || state.text.text.isNotBlank() || state.blocks.any { it !is AnswerBlock.Choice }) }
        if (state.hasChoice && !working) {
            TextButton(enabled = enabled, onClick = { working = true }, contentPadding = PaddingValues(horizontal = 4.dp)) { Text("Add working or a reason (optional)") }
            return@Column
        }
        RichTextField(state, enabled, if (state.hasChoice) "Working or reason (optional)" else label, collapsed || state.hasChoice, if (state.hasChoice) 2 else minLines)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(4.dp), itemVerticalAlignment = Alignment.CenterVertically) {
            Text("Add to your answer", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            AssistChip(enabled = enabled, onClick = { state.blocks.add(AnswerBlock.Table(null, null)) }, label = { Text("+ Table") })
            AssistChip(enabled = enabled, onClick = { state.blocks.add(state.newSketch(AnswerForm.Drawing(if (figure != null) "figure" else "blank"))) }, label = { Text("+ Drawing") })
            AssistChip(enabled = enabled, onClick = { state.blocks.add(state.newSketch(AnswerForm.Graph())) }, label = { Text("+ Graph") })
        }
    }
}

private fun sketchNumber(state: AnswerBoxState, block: AnswerBlock): Int =
    state.blocks.filter { it is AnswerBlock.Sketch || it is AnswerBlock.Pending }.indexOf(block) + 1

/** Fetches a saved drawing's strokes, then swaps in an editable block. */
@Composable
private fun PendingSketch(state: AnswerBoxState, block: AnswerBlock.Pending) {
    var failed by remember(block) { mutableStateOf(false) }
    LaunchedEffect(block) {
        try {
            val strokes = state.api.getObject("/answer-images/${block.image.id}/drawing")
            val sketch = SketchState.fromJson(block.image.graph, strokes, block.image.id, block.form)
            val at = state.blocks.indexOf(block)
            if (at >= 0) state.blocks[at] = AnswerBlock.Sketch(sketch)
        } catch (e: CancellationException) { throw e } catch (e: Exception) { failed = true }
    }
    Text(block.image.caption, style = MaterialTheme.typography.titleSmall)
    if (failed) {
        Text("This drawing could not be loaded for editing; it is still part of your saved answer.", style = MaterialTheme.typography.bodySmall)
        AnswerImageView(state.api, "/answer-images/${block.image.id}", block.image.caption)
    } else LoadingBar(Modifier.fillMaxWidth())
}

// ---- text with symbols ------------------------------------------------------------------------------------------------------

@Composable
private fun RichTextField(state: AnswerBoxState, enabled: Boolean, label: String, collapsed: Boolean, minLines: Int) {
    var open by rememberSaveable { mutableStateOf(!collapsed) }
    var equation by remember { mutableStateOf("") }
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if (open) SymbolBar(state, enabled)
        if (open && state.palette == "chemistry") Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            OutlinedTextField(equation, { equation = it }, Modifier.weight(1f), enabled = enabled, singleLine = true, label = { Text("Type an equation") },
                placeholder = { Text("Fe^3+ + 3OH- -> Fe(OH)3(s)") }, shape = RoundedCornerShape(12.dp),
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(autoCorrectEnabled = false, capitalization = androidx.compose.ui.text.input.KeyboardCapitalization.None))
            FilledTonalButton(enabled = enabled && equation.isNotBlank(), onClick = { state.setText(appendEquation(state.text.text, equation)); equation = "" }) { Text("Add") }
        }
        if (open && state.palette == "chemistry" && equation.isNotBlank()) FormulaPreview("\\ce{${equation.trim()}}")
        OutlinedTextField(
            value = state.text,
            onValueChange = { state.text = it },
            label = { Text(label) },
            modifier = Modifier.fillMaxWidth(),
            enabled = enabled,
            minLines = minLines,
            maxLines = 16,
            shape = RoundedCornerShape(12.dp),
        )
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (collapsed) TextButton(onClick = { open = !open }, contentPadding = PaddingValues(horizontal = 8.dp)) { Text(if (open) "Hide symbols" else "Σ Symbols") }
            if (open) Text("Maths goes between dollar signs, like \$v = f\\lambda\$; the buttons add it for you.",
                style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
        }
        MathPreview(state.text.text)
    }
}

/** Symbol-set tabs and a scrolling row of symbols, inserted at the cursor. */
@Composable
private fun SymbolBar(state: AnswerBoxState, enabled: Boolean) {
    val colours = LocalStudyColours.current
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            SYMBOLS.keys.forEach { key ->
                FilterChip(selected = state.palette == key, onClick = { state.palette = key }, label = { Text(SYMBOL_SET_NAMES.getValue(key)) })
            }
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            SYMBOLS.getValue(state.palette).forEach { symbol ->
                Surface(
                    onClick = {
                        val current = state.text
                        val (next, caret) = insertSnippet(current.text, current.selection.min, current.selection.max, symbol.latex, symbol.ce)
                        state.text = TextFieldValue(next, TextRange(caret))
                    },
                    enabled = enabled,
                    shape = RoundedCornerShape(10.dp),
                    color = colours.containerHighest,
                    modifier = Modifier.heightIn(min = 44.dp).widthIn(min = 44.dp).semantics { contentDescription = symbol.name },
                ) {
                    Box(Modifier.padding(horizontal = 10.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
                        Text(symbol.label, style = MaterialTheme.typography.titleMedium, maxLines = 1)
                    }
                }
            }
        }
    }
}

/** The typed answer rendered as it will be read, once it has some maths in it; updated after a short pause in typing. */
@Composable
private fun MathPreview(text: String) {
    var shown by remember { mutableStateOf("") }
    LaunchedEffect(text) { delay(400); shown = text }
    if (!Regex("\\$[^$]+\\$").containsMatchIn(shown)) return
    val colours = LocalStudyColours.current
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(colours.formulaBackground).border(1.dp, colours.formulaBorder, RoundedCornerShape(10.dp)).padding(10.dp)) {
        Text("PREVIEW", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
        MathText(shown)
    }
}

// ---- tables -----------------------------------------------------------------------------------------------------------------

@Composable
private fun TableBlock(block: AnswerBlock.Table, enabled: Boolean, onRemove: () -> Unit) {
    val outline = MaterialTheme.colorScheme.outlineVariant
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(if (block.template != null) "Complete the table" else "Your table", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
        TextButton(enabled = enabled, onClick = onRemove) { Text("Remove") }
    }
    Column(Modifier.horizontalScroll(rememberScrollState()).border(1.dp, outline, RoundedCornerShape(8.dp))) {
        Row {
            block.columns.forEachIndexed { c, name ->
                Box(Modifier.width(150.dp).border(0.5.dp, outline).padding(6.dp)) {
                    if (block.template != null) CellText(name, bold = true)
                    else OutlinedTextField(name, { block.columns[c] = it }, enabled = enabled, singleLine = true, placeholder = { Text("Heading ${c + 1}") },
                        textStyle = MaterialTheme.typography.bodySmall.copy(fontWeight = FontWeight.SemiBold))
                }
            }
        }
        block.rows.forEachIndexed { r, row ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                row.forEachIndexed { c, cell ->
                    Box(Modifier.width(150.dp).heightIn(min = 56.dp).border(0.5.dp, outline).padding(4.dp), contentAlignment = Alignment.CenterStart) {
                        val given = block.given(r, c)
                        if (given != null) CellText(given)
                        else OutlinedTextField(cell, { text -> block.rows[r] = block.rows[r].toMutableList().also { it[c] = text } }, enabled = enabled,
                            textStyle = MaterialTheme.typography.bodySmall, maxLines = 4)
                    }
                }
            }
        }
    }
    if (block.template == null) Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        TextButton(enabled = enabled, onClick = { block.rows.add(List(block.columns.size) { "" }) }) { Text("+ Row") }
        TextButton(enabled = enabled && block.rows.size > 1, onClick = { block.rows.removeAt(block.rows.lastIndex) }) { Text("− Row") }
        TextButton(enabled = enabled && block.columns.size < 8, onClick = {
            block.columns.add(""); for (i in block.rows.indices) block.rows[i] = block.rows[i] + ""
        }) { Text("+ Column") }
        TextButton(enabled = enabled && block.columns.size > 1, onClick = {
            block.columns.removeAt(block.columns.lastIndex); for (i in block.rows.indices) block.rows[i] = block.rows[i].dropLast(1)
        }) { Text("− Column") }
    }
}

/** A table cell: plain text unless it holds maths, which is rendered. */
@Composable
private fun CellText(text: String, bold: Boolean = false) {
    if ('$' in text || "\\ce{" in text) MathText(if (bold) "**$text**" else text, fontSize = 13)
    else Text(text, style = MaterialTheme.typography.bodySmall, fontWeight = if (bold) FontWeight.SemiBold else null, modifier = Modifier.padding(4.dp))
}

// ---- answers shown again ----------------------------------------------------------------------------------------------------

/** A saved answer as it was written: rendered maths, tables and drawings, wherever an answer is shown again. */
@Composable
fun AnswerContent(api: Api, text: String, modifier: Modifier = Modifier) {
    val blocks = remember(text) { shownBlocks(text) }
    val outline = MaterialTheme.colorScheme.outlineVariant
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        blocks.forEach { block ->
            when (block) {
                is ShownBlock.Text -> MathText(block.text)
                is ShownBlock.Table -> Column(Modifier.horizontalScroll(rememberScrollState()).border(1.dp, outline, RoundedCornerShape(8.dp))) {
                    block.rows.forEachIndexed { r, row ->
                        Row { row.forEach { cell -> Box(Modifier.width(140.dp).heightIn(min = 40.dp).border(0.5.dp, outline).padding(4.dp), contentAlignment = Alignment.CenterStart) { CellText(cell, bold = r == 0) } } }
                    }
                }
                is ShownBlock.Image -> {
                    AnswerImageView(api, block.path, block.caption)
                    if (block.description.isNotEmpty()) Text(block.description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/** A drawing from an answer, fetched with the session token, on white paper whatever the theme, under its caption. */
@Composable
fun AnswerImageView(api: Api, path: String, caption: String) {
    var image by remember(path) { mutableStateOf<ImageBitmap?>(null) }
    var failed by remember(path) { mutableStateOf(false) }
    LaunchedEffect(path) {
        try { image = withContext(Dispatchers.IO) { api.bytes(path).let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() } } ?: run { failed = true; null } }
        catch (e: CancellationException) { throw e } catch (e: Exception) { failed = true }
    }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        when {
            image != null -> Image(image!!, contentDescription = caption, contentScale = ContentScale.FillWidth,
                modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(Color.White).border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(10.dp)))
            failed -> Text("$caption could not be loaded.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            else -> Box(Modifier.fillMaxWidth().height(120.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp) }
        }
        Text(caption, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

// ---- multiple choice --------------------------------------------------------------------------------------------------------

private val richText = Regex("[$*`\\\\]")

/** Option text: rendered when it holds maths or Markdown, plain otherwise; then the option's picture, if it has one. */
@Composable
private fun OptionBody(api: Api, text: String, image: String, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if (text.isNotBlank()) {
            if (richText.containsMatchIn(text)) MathText(text) else Text(text, style = MaterialTheme.typography.bodyLarge)
        }
        if (image.isNotBlank()) AuthorisedImage(api.base, api.token, image, Modifier.fillMaxWidth(), contentDescription = "Picture for this option")
    }
}

/** Selectable options: one answer (radio) or select all that apply (checkboxes), lettered by position. */
@Composable
internal fun ChoiceBlock(api: Api, block: AnswerBlock.Choice, enabled: Boolean) {
    val form = block.form
    val colours = LocalStudyColours.current
    if (form.group.isNotBlank()) Text(form.group.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
    Text(form.instructions.ifBlank { if (form.multiple) "Select all that apply." else "Choose one answer." }, style = MaterialTheme.typography.titleSmall)
    if (form.penalty > 0) Text("Wrong answers lose ${form.penalty.toBigDecimal().stripTrailingZeros().toPlainString()} marks.", style = MaterialTheme.typography.bodySmall, color = colours.amber)
    form.options.forEachIndexed { position, option ->
        val chosen = option.key in block.chosen
        val letter = choiceLetter(position)
        Surface(
            shape = RoundedCornerShape(14.dp),
            color = if (chosen) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
            border = androidx.compose.foundation.BorderStroke(if (chosen) 2.dp else 1.dp, if (chosen) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Box {
                Row(Modifier.padding(start = 4.dp, end = 12.dp, top = 6.dp, bottom = 6.dp).heightIn(min = 48.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (form.multiple) Checkbox(checked = chosen, onCheckedChange = null, modifier = Modifier.padding(horizontal = 10.dp))
                    else RadioButton(selected = chosen, onClick = null, modifier = Modifier.padding(horizontal = 10.dp))
                    Text(letter, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(end = 10.dp))
                    OptionBody(api, option.text, option.image, Modifier.weight(1f))
                }
                // Rendered maths is a web view, which would swallow the tap; this layer takes it for the whole row.
                Box(Modifier.matchParentSize().clip(RoundedCornerShape(14.dp)).selectable(
                    selected = chosen, enabled = enabled, role = if (form.multiple) androidx.compose.ui.semantics.Role.Checkbox else androidx.compose.ui.semantics.Role.RadioButton,
                    onClick = { block.toggle(option.key) }).semantics { contentDescription = "Option $letter" })
            }
        }
    }
}

/**
 * A marked multiple-choice answer (choice_result): each option with whether it is right, whether it was chosen, and why.
 * Options are named by their text, as the feedback does, so the order they were shown in does not matter.
 */
@Composable
fun ChoiceResultView(api: Api, result: org.json.JSONObject) {
    val colours = LocalStudyColours.current
    val options = result.optJSONArray("options")?.objectList().orEmpty()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { option ->
            val correct = option.optBoolean("correct"); val chosen = option.optBoolean("chosen")
            val tone = when { correct -> colours.achieved; chosen -> MaterialTheme.colorScheme.error; else -> MaterialTheme.colorScheme.outlineVariant }
            Surface(shape = RoundedCornerShape(14.dp), color = if (correct) colours.achieved.copy(alpha = 0.10f) else if (chosen) MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.45f) else MaterialTheme.colorScheme.surface,
                border = androidx.compose.foundation.BorderStroke(if (correct || chosen) 2.dp else 1.dp, tone), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(when {
                        correct && chosen -> "✓ Correct · your choice"
                        correct -> "✓ Correct answer"
                        chosen -> "✗ Your choice"
                        else -> "Not correct"
                    }, style = MaterialTheme.typography.labelLarge, color = if (correct) colours.achieved else if (chosen) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                    OptionBody(api, option.optString("text"), option.stringOrNull("image").orEmpty())
                    option.optString("explanation").takeIf { it.isNotBlank() }?.let {
                        if (richText.containsMatchIn(it)) MathText(it, fontSize = 14) else Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        val available = result.optDouble("marks_available", Double.NaN)
        val lines = mutableListOf<String>()
        fun n(v: Double) = v.toBigDecimal().stripTrailingZeros().toPlainString()
        if (!available.isNaN() && available > 0) lines.add("${n(result.optDouble("marks_awarded", 0.0))} of ${n(available)} mark${if (available == 1.0) "" else "s"}")
        if (result.optDouble("penalty_applied", 0.0) > 0) lines.add("${n(result.optDouble("penalty_applied"))} taken off for wrong choices, net ${n(result.optDouble("net_marks", 0.0))}")
        lines.add(when (result.optString("key_source")) { "official" -> "Marked from the paper's own answer key"; "ai" -> "AI-written answer key: check it"; "lesson" -> "Checked on this device from the lesson, which is AI-written"; else -> "Marked from the answer key" })
        Text(lines.joinToString(" · "), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
