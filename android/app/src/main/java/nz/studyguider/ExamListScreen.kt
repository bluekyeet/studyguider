package nz.studyguider

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

// What the list showed last time, so coming back to it fills in at once and refreshes quietly.
private var examCache: Pair<String, List<ExamSummary>>? = null

private data class ExamSummary(val id: Long, val createdAt: String, val questionCount: Int, val kind: String, val totalMarks: Int, val title: String)

private suspend fun examMenuRequest(base: String, token: String, path: String, body: JSONObject? = null, method: String = if (body == null) "GET" else "POST"): String = withContext(Dispatchers.IO) {
    val c = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        c.connectTimeout = 10000; c.readTimeout = 200000
        c.requestMethod = method
        c.setRequestProperty("Authorization", "Bearer $token")
        if (body != null) {
            c.requestMethod = "POST"; c.doOutput = true; c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toString().toByteArray()) }
        }
        val text = (if (c.responseCode in 200..299) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (c.responseCode !in 200..299) throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrDefault(text))
        text
    } finally { c.disconnect() }
}

private suspend fun loadExamList(base: String, token: String): List<ExamSummary> = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + "/exams").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 20000
        connection.setRequestProperty("Authorization", "Bearer $token")
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)
            ?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        val data = JSONArray(text)
        List(data.length()) { index ->
            val exam = data.getJSONObject(index)
            val title = JSONObject(examMenuRequest(base, token, "/exams/${exam.getLong("id")}/details")).optString("title")
            ExamSummary(exam.getLong("id"), exam.getString("created_at"), exam.getInt("question_count"), exam.optString("kind", "manual"), exam.optInt("total_marks"), title)
        }
    } finally { connection.disconnect() }
}

/** Displays exams for an authenticated session. The caller supplies scrolling. */
@Composable
fun ExamListScreen(base: String, token: String, onChooseExam: (Long) -> Unit) {
    var exams by remember(base, token) { mutableStateOf<List<ExamSummary>?>(examCache?.takeIf { it.first == token }?.second) }
    var error by remember(base, token) { mutableStateOf("") }
    var busy by remember(base, token) { mutableStateOf(true) }
    val scope = rememberCoroutineScope()
    var topics by remember { mutableStateOf<List<PickableTopic>>(emptyList()) }
    var topic by remember { mutableStateOf<Long?>(null) }
    var papers by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var mode by remember { mutableStateOf("mixed") }
    var answerMode by remember { mutableStateOf("digital") }
    var paper by remember { mutableStateOf<JSONObject?>(null) }
    var paperMenu by remember { mutableStateOf(false) }
    var deleteTarget by remember { mutableStateOf<ExamSummary?>(null) }
    var deleting by remember { mutableStateOf(false) }
    LaunchedEffect(base, token) {
        try {
            val subjects = JSONArray(examMenuRequest(base, token, "/subjects"))
            val found = mutableListOf<PickableTopic>()
            for (i in 0 until subjects.length()) {
                val subject = subjects.getJSONObject(i)
                val list = JSONArray(examMenuRequest(base, token, "/subjects/${subject.getLong("id")}/topics"))
                for (j in 0 until list.length()) {
                    val t = list.getJSONObject(j)
                    found.add(PickableTopic(t.getLong("id"), subject.optInt("level"), subject.optString("name"), t.optString("name")))
                }
            }
            topics = found
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load topics" }
    }
    LaunchedEffect(topic) {
        paper = null; papers = emptyList(); paperMenu = false
        topic?.let { t ->
            try {
                val list = JSONArray(examMenuRequest(base, token, "/exam-papers?topic_id=$t"))
                papers = (0 until list.length()).map { list.getJSONObject(it) }
            } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load papers" }
        }
    }

    suspend fun load() {
        if (exams == null) busy = true
        error = ""
        try { exams = loadExamList(base, token); exams?.let { examCache = token to it } }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Unable to load exams" }
        finally { busy = false }
    }

    LaunchedEffect(base, token) { load() }

    Column(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        StudyCard(tone = CardTone.Container) {
        Text("New exam", style = MaterialTheme.typography.titleLarge)
        TopicPicker(topics, topic, { topic = it }, enabled = !busy)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("original" to "Past paper", "mixed" to "Mixed", "ai" to "AI practice").forEach { (value, label) ->
                FilterChip(modifier = Modifier.weight(1f), selected = mode == value, enabled = !busy,
                    onClick = { mode = value; paperMenu = false },
                    label = { Text(label, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center, maxLines = 1) })
            }
        }
        if (mode == "ai") Text("AI-written practice uses an unofficial rubric.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (mode == "original") {
            if (topic != null && papers.isEmpty()) Text("No past papers for this topic yet. Upload an NZQA paper and its schedule in Resources, or use AI practice.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (papers.isNotEmpty()) Box(Modifier.fillMaxWidth()) {
                OutlinedButton(enabled = !busy, onClick = { paperMenu = true }, modifier = Modifier.fillMaxWidth()) {
                    Text(paper?.let { listOfNotNull(it.optInt("year").toString(), it.optInt("standard_number").takeIf { n -> n > 0 }?.let { n -> "AS $n" }).joinToString(" · ") } ?: "Choose a year", modifier = Modifier.weight(1f))
                    Text("▾")
                }
                DropdownMenu(expanded = paperMenu, onDismissRequest = { paperMenu = false }) {
                    papers.forEach { p ->
                        DropdownMenuItem(text = {
                            Column {
                                Text(listOfNotNull(p.optInt("year").toString(), p.optInt("standard_number").takeIf { n -> n > 0 }?.let { n -> "AS $n" }).joinToString(" · "))
                                Text("${p.optInt("question_count")} registered questions", style = MaterialTheme.typography.bodySmall)
                            }
                        }, onClick = { paper = p; paperMenu = false })
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Text("Answer on paper and scan it", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            Switch(checked = answerMode == "handwritten", enabled = !busy, onCheckedChange = { answerMode = if (it) "handwritten" else "digital" })
        }
        Button(enabled = !busy && topic != null && (mode != "original" || paper != null), modifier = Modifier.fillMaxWidth(), onClick = {
            scope.launch {
                busy = true; error = ""
                try {
                    val body = JSONObject().put("topic_id", topic!!).put("mode", mode).put("answer_mode", answerMode).put("question_count", 3)
                    paper?.takeIf { mode == "original" }?.let { body.put("year", it.getInt("year")).put("paper_resource_id", it.getString("paper_resource_id")) }
                    val result = JSONObject(examMenuRequest(base, token, "/exams/start", body))
                    onChooseExam(result.getLong("id"))
                } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not start exam" }
                finally { busy = false }
            }
        }) { Text(if (mode == "ai") "Generate practice exam" else "Start exam") }
        // Say what is missing instead of leaving the button greyed out without a reason.
        if (!busy && (topic == null || (mode == "original" && paper == null))) Text(
            when {
                topic == null -> "Choose a topic to start."
                papers.isEmpty() -> "This topic has no past papers yet. Pick AI-written practice, or add papers in Resources."
                else -> "Choose a year to start."
            },
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        }
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        if (busy) LoadingBar(Modifier.fillMaxWidth())
        if (exams == null && error.isNotEmpty()) OutlinedButton(shape = RoundedCornerShape(50), onClick = { scope.launch { load() } }) { Text("Retry") }
        Text("Saved exams", style = MaterialTheme.typography.titleMedium)
        if (exams?.isEmpty() == true) Text("Exams you start appear here.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        // One short line per exam; tapping opens it, and its marks and questions show there.
        if (!exams.isNullOrEmpty()) StudyCard(tone = CardTone.Low) {
            exams!!.forEachIndexed { index, exam ->
                key(exam.id) {
                    if (index > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    Row(Modifier.fillMaxWidth().clickable(enabled = !deleting) { onChooseExam(exam.id) }.padding(vertical = 6.dp),
                        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(exam.title, style = MaterialTheme.typography.titleSmall, maxLines = 2)
                            Text(listOf(if (exam.kind == "monthly") "Monthly" else "Practice", "${exam.totalMarks} marks", exam.createdAt.take(10)).joinToString(" · "),
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        TextButton(enabled = !deleting, onClick = { deleteTarget = exam }) { Text("Delete", color = MaterialTheme.colorScheme.error) }
                    }
                }
            }
        }
    }
    deleteTarget?.let { exam ->
        AlertDialog(
            onDismissRequest = { if (!deleting) deleteTarget = null },
            title = { Text("Delete saved exam?") },
            text = { Text("${exam.title}\n\nThis permanently removes this attempt, its answers, scans and feedback. Original papers and bank questions are kept.") },
            confirmButton = { TextButton(enabled = !deleting, onClick = {
                scope.launch {
                    deleting = true; error = ""
                    try {
                        examMenuRequest(base, token, "/exams/${exam.id}", method = "DELETE")
                        exams = exams?.filterNot { it.id == exam.id }
                        deleteTarget = null
                    } catch (e: CancellationException) { throw e }
                    catch (e: Exception) { error = e.message ?: "Could not delete exam"; deleteTarget = null }
                    finally { deleting = false }
                }
            }) { Text(if (deleting) "Deleting…" else "Delete", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(enabled = !deleting, onClick = { deleteTarget = null }) { Text("Cancel") } },
        )
    }
}
