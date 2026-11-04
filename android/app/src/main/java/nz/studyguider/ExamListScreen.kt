package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.font.FontWeight
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
    var topics by remember { mutableStateOf<List<Pair<String, Long>>>(emptyList()) }
    var topic by remember { mutableStateOf<Pair<String, Long>?>(null) }
    var papers by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var mode by remember { mutableStateOf("mixed") }
    var answerMode by remember { mutableStateOf("digital") }
    var paper by remember { mutableStateOf<JSONObject?>(null) }
    var topicMenu by remember { mutableStateOf(false) }
    var paperMenu by remember { mutableStateOf(false) }
    var deleteTarget by remember { mutableStateOf<ExamSummary?>(null) }
    var deleting by remember { mutableStateOf(false) }
    LaunchedEffect(base, token) {
        try {
            val subjects = JSONArray(examMenuRequest(base, token, "/subjects"))
            val found = mutableListOf<Pair<String, Long>>()
            for (i in 0 until subjects.length()) {
                val subject = subjects.getJSONObject(i)
                val list = JSONArray(examMenuRequest(base, token, "/subjects/${subject.getLong("id")}/topics"))
                for (j in 0 until list.length()) {
                    val t = list.getJSONObject(j)
                    found.add("${subject.optString("name")} · ${t.optString("name")}" to t.getLong("id"))
                }
            }
            topics = found
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load topics" }
    }
    LaunchedEffect(topic) {
        paper = null; papers = emptyList(); paperMenu = false
        topic?.let { t ->
            try {
                val list = JSONArray(examMenuRequest(base, token, "/exam-papers?topic_id=${t.second}"))
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
        Text("Take an exam", style = MaterialTheme.typography.titleLarge)
        Text("How will you answer?", style = MaterialTheme.typography.titleMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = answerMode == "digital", onClick = { answerMode = "digital" }, label = { Text("Digital") })
            FilterChip(selected = answerMode == "handwritten", onClick = { answerMode = "handwritten" }, label = { Text("Handwritten") })
        }
        Box {
            OutlinedButton(enabled = !busy, onClick = { topicMenu = true }, modifier = Modifier.fillMaxWidth()) { Text(topic?.first ?: "Choose a topic") }
            DropdownMenu(expanded = topicMenu, onDismissRequest = { topicMenu = false }) {
                topics.forEach { t -> DropdownMenuItem(text = { Text(t.first) }, onClick = { topic = t; topicMenu = false }) }
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("original" to "Past paper", "mixed" to "Collated paper", "ai" to "AI-written practice").forEach { (value, label) ->
                FilterChip(modifier = Modifier.weight(1f).heightIn(min = 56.dp), selected = mode == value, enabled = !busy,
                    onClick = { mode = value; paperMenu = false },
                    label = { Text(label, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center) })
            }
        }
        if (mode == "ai") Text("AI-written practice uses an unofficial rubric.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (mode == "original") {
            if (topic != null && papers.isEmpty()) Text("No past papers are registered for this topic yet. Upload an NZQA exam paper and its marking schedule in Resources (named like 91577-exm-2023.pdf and 91577-ass-2023.pdf) and they are added automatically. Until then, use AI-written practice, which needs notes or files uploaded for the topic.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (papers.isNotEmpty()) Box(Modifier.fillMaxWidth()) {
                OutlinedButton(enabled = !busy, onClick = { paperMenu = true }, modifier = Modifier.fillMaxWidth()) {
                    Text(paper?.let { "${it.optInt("year")} · AS ${it.optInt("standard_number")}" } ?: "Choose a year", modifier = Modifier.weight(1f))
                    Text("▾")
                }
                DropdownMenu(expanded = paperMenu, onDismissRequest = { paperMenu = false }) {
                    papers.forEach { p ->
                        DropdownMenuItem(text = {
                            Column {
                                Text("${p.optInt("year")} · AS ${p.optInt("standard_number")}")
                                Text("${p.optInt("question_count")} registered questions", style = MaterialTheme.typography.bodySmall)
                            }
                        }, onClick = { paper = p; paperMenu = false })
                    }
                }
            }
        }
        Button(enabled = !busy && topic != null && (mode != "original" || paper != null), modifier = Modifier.fillMaxWidth(), onClick = {
            scope.launch {
                busy = true; error = ""
                try {
                    val body = JSONObject().put("topic_id", topic!!.second).put("mode", mode).put("answer_mode", answerMode).put("question_count", 3)
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
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        if (busy) LoadingBar(Modifier.fillMaxWidth())
        OutlinedButton(enabled = !busy, shape = RoundedCornerShape(50), onClick = { scope.launch { load() } }) { Text(if (exams == null && error.isNotEmpty()) "Retry" else "Refresh") }
        if (exams?.isEmpty() == true) StudyCard(tone = CardTone.Low) {
            Text("No exams yet", style = MaterialTheme.typography.titleMedium)
            Text("Assemble a monthly paper from the web manager, then it will appear here.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("Saved exams", style = MaterialTheme.typography.titleMedium)
        exams?.forEach { exam ->
            key(exam.id) {
                StudyCard(tone = CardTone.Container) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(if (exam.kind == "monthly") "MONTHLY PAPER" else "PRACTICE PAPER", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                        StudyChip("${exam.totalMarks} marks", MaterialTheme.colorScheme.onPrimaryContainer, MaterialTheme.colorScheme.primaryContainer)
                    }
                    Text(exam.title, style = MaterialTheme.typography.titleLarge)
                    Text(exam.kind.replace('-', ' ').replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.bodySmall)
                    Text("${exam.questionCount} ${if (exam.questionCount == 1) "question" else "questions"} · created ${exam.createdAt.take(10)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Button(enabled = !deleting, shape = RoundedCornerShape(50), onClick = { onChooseExam(exam.id) }) { Text("Open exam") }
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
