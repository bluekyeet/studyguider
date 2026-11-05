package nz.studyguider

import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

// Practice aids: one saved hint per practice question, and fill-in tables answered cell by cell.

private suspend fun hintRequest(base: String, token: String, path: String, body: JSONObject? = null): JSONObject = withContext(Dispatchers.IO) {
    val c = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        c.connectTimeout = 10000; c.readTimeout = 120000
        c.setRequestProperty("Authorization", "Bearer $token")
        if (body != null) {
            c.requestMethod = "POST"; c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val ok = c.responseCode in 200..299
        val text = (if (ok) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (!ok) throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrNull()?.takeIf { it.isNotBlank() } ?: "Request failed (${c.responseCode})")
        JSONObject(text)
    } finally { c.disconnect() }
}

/**
 * One hint per practice question (server hints.py). The first tap writes it from the answer so far; every later tap, on any
 * device, shows the same hint. Kinds: "review" (also revision packs), "lesson" (send the question) and "rapid". Never in exams.
 */
@Composable
fun HintButton(base: String, token: String, kind: String, ref: String, answer: () -> String, question: () -> String = { "" }) {
    var saved by remember(kind, ref) { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var shown by remember { mutableStateOf<String?>(null) }
    var failure by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val path = "/hints/$kind/" + android.net.Uri.encode(ref)
    LaunchedEffect(kind, ref, token) {
        saved = try { !hintRequest(base, token, path).isNull("hint") } catch (e: CancellationException) { throw e } catch (e: Exception) { false }
    }
    TextButton(enabled = !busy, onClick = {
        scope.launch {
            busy = true
            try {
                val reply = hintRequest(base, token, path, JSONObject().put("answer", answer()).put("question", question()))
                shown = reply.optString("hint"); failure = null; saved = true
            } catch (e: CancellationException) { throw e } catch (e: Exception) { failure = e.message ?: "Could not get a hint"; shown = null }
            finally { busy = false }
        }
    }) { Text(if (busy) "Thinking…" else if (saved) "Show hint" else "Hint") }
    if (shown != null || failure != null) {
        AlertDialog(
            onDismissRequest = { shown = null; failure = null },
            confirmButton = { TextButton(onClick = { shown = null; failure = null }) { Text("Close") } },
            title = { Text("Hint") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    shown?.let {
                        MathText(it)
                        Text("One hint per question. It stays the same here and on your other devices.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    failure?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            },
        )
    }
}

/** A Markdown table in a question with cells left empty for the learner: header row, then body rows. */
data class FillTable(val header: List<String>, val rows: List<List<String>>)

private fun cells(line: String): List<String> =
    line.trim().removePrefix("|").removeSuffix("|").split("|").map { it.trim() }

private fun isRule(line: String) = line.trim().removePrefix("|").removeSuffix("|").split("|").all { it.trim().matches(Regex(":?-{3,}:?")) }

/** Blocks of consecutive lines starting with "|", as (first line index, lines). */
private fun tableBlocks(text: String): List<Pair<Int, List<String>>> {
    val lines = text.replace("\r\n", "\n").split("\n")
    val blocks = mutableListOf<Pair<Int, List<String>>>()
    var i = 0
    while (i < lines.size) {
        if (lines[i].trimStart().startsWith("|")) {
            val start = i
            while (i < lines.size && lines[i].trimStart().startsWith("|")) i++
            blocks += start to lines.subList(start, i)
        } else i++
    }
    return blocks
}

/** The first table in [question] with at least one empty body cell, or null. */
fun fillTable(question: String): FillTable? = tableBlocks(question).firstNotNullOfOrNull { (_, block) ->
    if (block.size < 3 || !isRule(block[1])) return@firstNotNullOfOrNull null
    val header = cells(block[0])
    val rows = block.drop(2).map { row -> cells(row).let { it + List((header.size - it.size).coerceAtLeast(0)) { "" } }.take(header.size) }
    if (rows.any { row -> row.drop(1).any { it.isEmpty() } }) FillTable(header, rows) else null
}

private fun markdown(table: FillTable, values: List<List<String>>): String {
    val line = { row: List<String> -> "| " + row.joinToString(" | ") { it.replace("|", "\\|").replace("\n", " ") } + " |" }
    return (listOf(line(table.header), line(table.header.map { "---" })) + values.map(line)).joinToString("\n")
}

/** The answer with its first table replaced by [table], or the table put first when the answer has none. */
fun withTable(answer: String, table: String): String {
    val lines = answer.replace("\r\n", "\n").split("\n")
    val block = tableBlocks(answer).firstOrNull() ?: return if (answer.isBlank()) table else table + "\n\n" + answer
    val (start, rows) = block
    return (lines.subList(0, start) + table.split("\n") + lines.subList(start + rows.size, lines.size)).joinToString("\n")
}

/**
 * The question's fill-in table as a grid: printed cells stay as they are, empty ones become text boxes, and the filled table is
 * written into the answer as Markdown (replacing any table already there), so drafts and marking see one plain-text answer.
 */
@Composable
fun TableAnswer(question: String, answer: String, onAnswer: (String) -> Unit, enabled: Boolean = true) {
    val table = remember(question) { fillTable(question) } ?: return
    // Cells already in the answer (a restored draft) are read back into the grid.
    val values = remember(question) {
        val previous = tableBlocks(answer).firstOrNull()?.second?.takeIf { it.size >= 3 }?.drop(2)?.map(::cells)
        mutableStateListOf(*table.rows.mapIndexed { r, row ->
            row.mapIndexed { c, cell -> if (cell.isNotEmpty()) cell else previous?.getOrNull(r)?.getOrNull(c).orEmpty() }
        }.toTypedArray())
    }
    val outline = MaterialTheme.colorScheme.outlineVariant
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("Fill in the table", style = MaterialTheme.typography.labelLarge)
        Column(Modifier.horizontalScroll(rememberScrollState()).border(1.dp, outline)) {
            Row {
                table.header.forEach { Text(it, Modifier.width(150.dp).border(0.5.dp, outline).padding(8.dp), fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall) }
            }
            table.rows.forEachIndexed { r, row ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    row.forEachIndexed { c, printed ->
                        Box(Modifier.width(150.dp).heightIn(min = 56.dp).border(0.5.dp, outline).padding(4.dp), contentAlignment = Alignment.CenterStart) {
                            if (printed.isNotEmpty()) Text(printed, Modifier.padding(4.dp), style = MaterialTheme.typography.bodySmall)
                            else OutlinedTextField(
                                value = values[r][c], enabled = enabled, textStyle = MaterialTheme.typography.bodySmall,
                                onValueChange = { text ->
                                    values[r] = values[r].toMutableList().also { it[c] = text }
                                    onAnswer(withTable(answer, markdown(table, values)))
                                },
                            )
                        }
                    }
                }
            }
        }
    }
}

/** All the wording of a past-paper or rapid question: its main text and every part, as shown on screen. */
fun fullQuestionText(question: JSONObject): String {
    val parts = question.optJSONArray("parts")
    val texts = (0 until (parts?.length() ?: 0)).mapNotNull { parts!!.optJSONObject(it)?.optString("text") }
    return (listOf(question.optString("question_text")) + texts).filter { it.isNotBlank() }.joinToString("\n\n")
}
