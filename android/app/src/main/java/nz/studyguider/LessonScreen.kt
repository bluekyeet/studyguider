package nz.studyguider

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

private suspend fun requestLesson(base: String, token: String, topicId: Long, query: String): JSONObject = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + "/topics/$topicId/lessons").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 200000
        connection.requestMethod = "POST"
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        connection.outputStream.use { it.write(JSONObject().put("query", query).toString().toByteArray(Charsets.UTF_8)) }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        JSONObject(text)
    } finally { connection.disconnect() }
}

private suspend fun requestLessonHistory(base: String, token: String, topicId: Long): JSONArray = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + "/topics/$topicId/lessons").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 10000
        connection.setRequestProperty("Authorization", "Bearer $token")
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        JSONArray(text)
    } finally { connection.disconnect() }
}

private suspend fun explainLesson(base: String, token: String, lessonId: Long, question: String): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + "/lessons/$lessonId/explain").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000; connection.readTimeout = 100000
        connection.requestMethod = "POST"; connection.doOutput = true
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Content-Type", "application/json")
        connection.outputStream.use { it.write(JSONObject().put("question", question).toString().toByteArray(Charsets.UTF_8)) }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        JSONObject(text).getString("explanation")
    } finally { connection.disconnect() }
}

private suspend fun deleteLesson(base: String, token: String, lessonId: Long) = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + "/lessons/$lessonId").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000; connection.readTimeout = 20000
        connection.requestMethod = "DELETE"
        connection.setRequestProperty("Authorization", "Bearer $token")
        val status = connection.responseCode
        if (status !in 200..299) throw IllegalStateException("Deletion failed ($status)")
    } finally { connection.disconnect() }
}

/** A lesson section: a heading plus the material that follows it. */
data class LessonChunk(val title: String, val blocks: List<Pair<String, String>>) {
    val body get() = blocks.joinToString("\n\n") { it.second }
    /** Sections that are practice rather than reading. */
    val isPractice get() = title.contains("your turn", true) || title.contains("question", true) || title.contains("check", true) || title.contains("quiz", true)
}

/** Splits a Markdown lesson into titled chunks so the reader can fold them. */
fun lessonChunks(lesson: String): List<LessonChunk> {
    val chunks = mutableListOf<LessonChunk>()
    var title = "Overview"
    val current = mutableListOf<Pair<String, String>>()
    fun flush() { if (current.isNotEmpty()) { chunks.add(LessonChunk(title, current.toList())); current.clear() } }
    lesson.lineSequence().forEach { line ->
        val trim = line.trim()
        if (trim.startsWith("# ") || trim.startsWith("## ") || trim.startsWith("### ")) {
            flush()
            title = trim.dropWhile { it == '#' }.trim().ifBlank { "Overview" }
        } else if (trim.isNotEmpty()) {
            current.add("text" to trim)
        }
    }
    flush()
    return chunks
}

/** Generates and saves an experimental lesson for the selected topic. */
@Composable
fun LessonScreen(
    base: String,
    token: String,
    topicId: Long,
    topicName: String,
    subjectName: String,
    allTopics: List<Pair<String, JSONObject>>,
    onSwitchTopic: (Long, String) -> Unit,
    onOpenResources: () -> Unit,
) {
    var query by remember(base, token, topicId) { mutableStateOf("") }
    var result by remember(base, token, topicId) { mutableStateOf<JSONObject?>(null) }
    var error by remember(base, token, topicId) { mutableStateOf("") }
    var busy by remember(base, token, topicId) { mutableStateOf(false) }
    var history by remember(base, token, topicId) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var historyError by remember(base, token, topicId) { mutableStateOf("") }
    var historyLoading by remember(base, token, topicId) { mutableStateOf(false) }
    var deleteId by remember(base, token, topicId) { mutableStateOf<Long?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(base, token, topicId) {
        if (topicId > 0) {
            historyLoading = true
            try {
                val items = requestLessonHistory(base, token, topicId)
                history = (0 until items.length()).map { items.getJSONObject(it) }
            } catch (e: Exception) { historyError = e.message ?: "Could not load lesson history" }
            finally { historyLoading = false }
        }
    }

    Column(Modifier.fillMaxWidth().padding(top = 4.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        // Always reachable: change topic or subject without hunting through Resources.
        TopicSwitcher(
            topicId = topicId, topicName = topicName, subjectName = subjectName,
            allTopics = allTopics, onSwitchTopic = onSwitchTopic, onOpenResources = onOpenResources,
        )
        result?.let { draft -> LessonArticle(base, token, draft) } ?: LessonEmptyState(
            query = query,
            onQueryChange = { query = it },
            busy = busy,
            error = error,
            canGenerate = !busy && !historyLoading && query.isNotBlank() && query.length <= 200 && topicId > 0,
            onGenerate = {
                val submitted = query.trim()
                scope.launch {
                    busy = true; error = ""
                    try {
                        val draft = requestLesson(base, token, topicId, submitted)
                        result = draft
                        history = listOf(draft) + history
                    } catch (e: Exception) { error = e.message ?: "Request failed" }
                    finally { busy = false }
                }
            },
        )
        result?.let { draft -> SourcesCard(draft, citedResourceIds(draft)) { deleteId = draft.getLong("id") } }
        if (error.isNotEmpty() && result != null) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        SavedLessons(
            history = history,
            loading = historyLoading,
            error = historyError,
            busy = busy,
            onOpen = { draft -> result = draft },
            onClose = { result = null },
            openId = result?.optLong("id"),
        )
    }
    deleteId?.let { id ->
        AlertDialog(
            onDismissRequest = { if (!busy) deleteId = null },
            title = { Text("Delete this lesson?") },
            text = { Text("The saved draft, review and source excerpts will be permanently removed.") },
            confirmButton = { TextButton(enabled = !busy, onClick = {
                scope.launch {
                    busy = true; error = ""
                    try {
                        deleteLesson(base, token, id)
                        history = history.filterNot { it.optLong("id") == id }
                        if (result?.optLong("id") == id) result = null
                        deleteId = null
                    } catch (e: Exception) { error = e.message ?: "Deletion failed"; deleteId = null }
                    finally { busy = false }
                }
            }) { Text("Delete") } },
            dismissButton = { TextButton(enabled = !busy, onClick = { deleteId = null }) { Text("Cancel") } }
        )
    }
}

@Composable
private fun LessonEmptyState(
    query: String,
    onQueryChange: (String) -> Unit,
    busy: Boolean,
    error: String,
    canGenerate: Boolean,
    onGenerate: () -> Unit,
) {
    val ideas = listOf("Momentum", "Banked curves", "Moles and concentration", "Titration curves", "Projectile motion")
    StudyCard(tone = CardTone.Container) {
        SectionLabel("Create a lesson", "TODAY'S LESSON")
        Text("Your search, matching excerpts and linked standards are sent to your configured model providers.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        StudyChip("Draft only — check the sources", MaterialTheme.colorScheme.onErrorContainer, MaterialTheme.colorScheme.errorContainer)
        OutlinedTextField(query, onQueryChange, label = { Text("Lesson topic or search") }, modifier = Modifier.fillMaxWidth(), enabled = !busy, singleLine = true, shape = RoundedCornerShape(12.dp))
        Text("1–200 characters", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("Try", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
        @OptIn(ExperimentalLayoutApi::class)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            ideas.forEach { idea -> AssistChip(enabled = !busy, onClick = { onQueryChange(idea) }, label = { Text(idea) }) }
        }
        Button(enabled = canGenerate, onClick = onGenerate, modifier = Modifier.fillMaxWidth().heightIn(min = 50.dp), shape = RoundedCornerShape(50)) { Text("Generate lesson draft") }
        if (busy) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
            Text("Generating and reviewing the draft may take several minutes.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    }
}

/**
 * Interactive reader. Each section folds so the learner works one chunk at a
 * time, and practice sections offer "Check my answer" (AI explanation) and
 * "Reveal the model answer" (the lesson's own worked answer).
 */
@Composable
private fun LessonArticle(base: String, token: String, draft: JSONObject) {
    val standards = draft.optJSONArray("standards")
    val standardText = remember(draft) {
        if (standards == null || standards.length() == 0) "NCEA STANDARD"
        else (0 until minOf(standards.length(), 2)).joinToString(" • ") { "AS ${standards.getJSONObject(it).optInt("number")}" }
    }
    val sources = draft.optJSONArray("sources")
    // The reviewer runs in the background on the server; the learner is not shown reviewer output.
    // Citations become S1, S2… so the prose stays readable and still points at a source.
    val citedIds = remember(draft) { citedResourceIds(draft) }
    val chunks = remember(draft) { lessonChunks(shortCitations(draft.optString("lesson"), citedIds)) }
    var openIndex by remember(draft) { mutableIntStateOf(0) }
    val progress = animateFloatAsState(if (chunks.isEmpty()) 0f else (openIndex + 1).toFloat() / chunks.size, label = "lesson progress")
    val colours = LocalStudyColours.current

    Surface(shape = RoundedCornerShape(20.dp), color = colours.container, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(standardText, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                StudyChip("Draft", MaterialTheme.colorScheme.onErrorContainer, MaterialTheme.colorScheme.errorContainer)
            }
            Text(draft.optString("query"), style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.onSurface)
            Text("Section ${openIndex + 1} of ${chunks.size} · ${if (sources == null) 0 else sources.length()} grounded source(s)", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            LinearProgressIndicator(progress = { progress.value }, modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(50)), color = MaterialTheme.colorScheme.primary, trackColor = colours.containerHigh)
        }
    }

    chunks.forEachIndexed { index, chunk ->
        val expanded = openIndex == index
        val practice = chunk.isPractice
        Surface(shape = RoundedCornerShape(16.dp), color = if (practice) colours.containerLow else colours.container, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(
                    Modifier.fillMaxWidth().clickable { openIndex = if (expanded) -1 else index },
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(chunk.title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(1f))
                    if (practice) StudyChip("Your turn", MaterialTheme.colorScheme.onSecondaryContainer, MaterialTheme.colorScheme.secondaryContainer)
                    Text("⌄", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.secondary, modifier = Modifier.rotate(if (expanded) 180f else 0f))
                }
                AnimatedVisibility(visible = expanded) {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        chunk.blocks.forEach { (kind, content) ->
                            when (kind) {
                                "bullet" -> Row(Modifier.padding(top = 2.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("•", color = MaterialTheme.colorScheme.secondary, style = MaterialTheme.typography.bodyLarge)
                                    MathText(content, modifier = Modifier.weight(1f))
                                }
                                "bullet2" -> Row(Modifier.padding(start = 18.dp, top = 2.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("–", color = MaterialTheme.colorScheme.outline, style = MaterialTheme.typography.bodyLarge)
                                    MathText(content, modifier = Modifier.weight(1f), fontSize = 15)
                                }
                                "number" -> Row(Modifier.padding(top = 2.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    val digits = content.takeWhile { it.isDigit() || it == '.' }
                                    Text(digits, color = MaterialTheme.colorScheme.secondary, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                                    MathText(content.removePrefix(digits).trim(), modifier = Modifier.weight(1f))
                                }
                                "number2" -> Row(Modifier.padding(start = 18.dp, top = 2.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    val digits = content.takeWhile { it.isDigit() || it == '.' }
                                    Text(digits, color = MaterialTheme.colorScheme.outline, style = MaterialTheme.typography.bodySmall)
                                    MathText(content.removePrefix(digits).trim(), modifier = Modifier.weight(1f), fontSize = 15)
                                }
                                "quote" -> Surface(shape = RoundedCornerShape(10.dp), color = colours.containerHigh, modifier = Modifier.fillMaxWidth()) {
                                    MathText(content, modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp), fontSize = 15)
                                }
                                else -> MathText(content)
                            }
                        }
                        if (practice) PracticePanel(base, token, draft, chunk)
                        if (!practice) SectionQuestion(base, token, draft, chunk)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                            if (index < chunks.size - 1) Button(shape = RoundedCornerShape(50), onClick = { openIndex = index + 1 }) { Text("Next section") }
                            else if (index > 0) OutlinedButton(shape = RoundedCornerShape(50), onClick = { openIndex = index - 1 }) { Text("Previous") }
                        }
                    }
                }
            }
        }
    }

    // Reviewer output stays on the server; the learner only sees the draft warning.
    val warning = draft.optString("warning")
    if (warning.isNotBlank()) {
        StudyCard(tone = CardTone.Low) {
            SectionLabel("Check before you rely on this", "DRAFT")
            Text(warning, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }
    }
}

/**
 * One question after a reading section, built from that section's own wording,
 * so every chunk ends with something to answer rather than only reading.
 */
@Composable
private fun SectionQuestion(base: String, token: String, draft: JSONObject, chunk: LessonChunk) {
    val questions = remember(chunk) { practiceQuestions(chunk.body) }
    if (questions.isEmpty()) return
    var index by remember(chunk) { mutableIntStateOf(0) }
    val question = questions[index]
    var answer by remember(chunk, index) { mutableStateOf("") }
    var revealed by remember(chunk, index) { mutableStateOf(false) }
    var feedback by remember(chunk, index) { mutableStateOf("") }
    var busy by remember(chunk, index) { mutableStateOf(false) }
    var error by remember(chunk, index) { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val colours = LocalStudyColours.current

    HorizontalDivider()
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("QUICK CHECK", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
        if (questions.size > 1) Text("${index + 1} of ${questions.size}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    MathText(question.prompt)
    MathField(answer, { answer = it; feedback = "" }, label = "Your answer", minLines = 3, maxLines = 12, enabled = !busy)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Button(shape = RoundedCornerShape(50), enabled = !busy && answer.isNotBlank() && answer.length <= 2000, onClick = {
            scope.launch {
                busy = true; error = ""
                try {
                    feedback = explainLesson(base, token, draft.getLong("id"),
                        "Mark my answer to this question from the lesson. Say what is right, what is wrong and what a stronger answer would add.\nQuestion: ${question.prompt}\nMy answer: $answer")
                } catch (e: Exception) { error = e.message ?: "Could not check the answer" }
                finally { busy = false }
            }
        }) { Text("Check my answer") }
        TextButton(onClick = { revealed = !revealed }) { Text(if (revealed) "Hide answer" else question.revealLabel) }
        if (questions.size > 1) TextButton(onClick = { index = (index + 1) % questions.size }) { Text("Another") }
    }
    if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
    if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    if (feedback.isNotBlank()) Surface(shape = RoundedCornerShape(12.dp), color = colours.containerHigh, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("TUTOR FEEDBACK — AI, CHECK THE SOURCES", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
            MathText(feedback)
        }
    }
    AnimatedVisibility(visible = revealed) {
        Surface(shape = RoundedCornerShape(12.dp), color = colours.containerLow, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("ANSWER FROM THE LESSON", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline, fontWeight = FontWeight.Bold)
                MathText(question.answer)
            }
        }
    }
}

/** Practice controls: reveal the lesson's answer, or ask the tutor to mark working. */
@Composable
private fun PracticePanel(base: String, token: String, draft: JSONObject, chunk: LessonChunk) {
    val scope = rememberCoroutineScope()
    var working by remember(chunk) { mutableStateOf("") }
    var revealed by remember(chunk) { mutableStateOf(false) }
    var reply by remember(chunk) { mutableStateOf("") }
    var busy by remember(chunk) { mutableStateOf(false) }
    var error by remember(chunk) { mutableStateOf("") }
    HorizontalDivider()
    Text("Check your understanding", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.secondary)
    MathField(working, { working = it }, label = "Your working", minLines = 3, maxLines = 12, enabled = !busy)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(shape = RoundedCornerShape(50), enabled = !busy && working.isNotBlank() && working.length <= 2000, onClick = {
            scope.launch {
                busy = true; error = ""
                try { reply = explainLesson(base, token, draft.getLong("id"), "Check my working for this question and point out errors:\n" + working) }
                catch (e: Exception) { error = e.message ?: "Could not get feedback" }
                finally { busy = false }
            }
        }) { Text("Check my answer") }
        OutlinedButton(shape = RoundedCornerShape(50), onClick = { revealed = !revealed }) { Text(if (revealed) "Hide answer" else "Reveal answer") }
    }
    if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
    if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    if (reply.isNotBlank()) StudyCard(tone = CardTone.High) {
        Text("TUTOR FEEDBACK", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
        MathText(reply)
        TextButton(onClick = { reply = "" }) { Text("Dismiss") }
    }
    AnimatedVisibility(visible = revealed) {
        StudyCard(tone = CardTone.Low) {
            Text("LESSON CONTENT — CHECK AGAINST SOURCES", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline, fontWeight = FontWeight.Bold, textAlign = TextAlign.Start)
            MathText(chunk.body)
        }
    }
}

@Composable
private fun SourcesCard(draft: JSONObject, citedIds: List<String>, onDelete: () -> Unit) {
    val colours = LocalStudyColours.current
    StudyCard(tone = CardTone.High) {
        SectionLabel("Sources", "WHERE THIS CAME FROM")
        Text("S1, S2… in the lesson refer to these files.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        val sources = draft.optJSONArray("sources")
        if (sources == null || sources.length() == 0) Text("No sources saved with this draft.", style = MaterialTheme.typography.bodySmall)
        else for (i in 0 until sources.length()) {
            val source = sources.getJSONObject(i)
            val marker = citedIds.indexOf(source.optString("resource_id")).let { if (it >= 0) "S${it + 1}" else "§" }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(marker, color = colours.teal, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, modifier = Modifier.width(28.dp))
                Column(Modifier.weight(1f)) {
                    Text(source.optString("filename"), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                    Text("Page or slide ${source.optInt("page")}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        OutlinedButton(onClick = onDelete, shape = RoundedCornerShape(50)) { Text("Delete lesson") }
    }
}

/** Unique resource IDs cited by a lesson, in first-use order; used for the S1, S2 markers. */
fun citedResourceIds(draft: JSONObject): List<String> {
    val text = draft.optString("lesson")
    val ids = mutableListOf<String>()
    Regex("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}").findAll(text).forEach { if (it.value !in ids) ids.add(it.value) }
    draft.optJSONArray("sources")?.let { list ->
        for (i in 0 until list.length()) {
            val id = list.getJSONObject(i).optString("resource_id")
            if (id.isNotBlank() && id !in ids) ids.add(id)
        }
    }
    return ids
}

/**
 * Sticky topic bar for the lesson screen. Shows where you are and opens a sheet
 * listing every topic, grouped by subject, so switching is one tap from
 * anywhere in a lesson.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TopicSwitcher(
    topicId: Long,
    topicName: String,
    subjectName: String,
    allTopics: List<Pair<String, JSONObject>>,
    onSwitchTopic: (Long, String) -> Unit,
    onOpenResources: () -> Unit,
) {
    var open by remember { mutableStateOf(false) }
    val colours = LocalStudyColours.current
    Surface(
        onClick = { open = true },
        shape = RoundedCornerShape(14.dp),
        color = colours.containerLow,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Column(Modifier.weight(1f)) {
                Text(if (subjectName.isBlank()) "TOPIC" else subjectName.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                Text(topicName.ifBlank { "Choose a topic" }, style = MaterialTheme.typography.titleMedium, maxLines = 1)
            }
            Text("Change", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            Text("⌄", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
        }
    }
    if (open) {
        ModalBottomSheet(onDismissRequest = { open = false }, containerColor = MaterialTheme.colorScheme.surface) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp).padding(bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Change topic", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
                allTopics.groupBy({ it.first }, { it.second }).forEach { (subject, list) ->
                    Text(subject, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                    list.forEach { topic ->
                        val id = topic.getLong("id")
                        val selected = id == topicId
                        Surface(
                            onClick = { open = false; onSwitchTopic(id, topic.optString("name")) },
                            shape = RoundedCornerShape(12.dp),
                            color = if (selected) MaterialTheme.colorScheme.primaryContainer else colours.container,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Row(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                                Text(topic.optString("name"), style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                                if (selected) Text("Reading now", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                }
                OutlinedButton(onClick = { open = false; onOpenResources() }, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth()) { Text("Manage topics and files") }
            }
        }
    }
}

@Composable
private fun SavedLessons(
    history: List<JSONObject>,
    loading: Boolean,
    error: String,
    busy: Boolean,
    onOpen: (JSONObject) -> Unit,
    onClose: () -> Unit,
    openId: Long?,
) {
    StudyCard(tone = CardTone.Container) {
        SectionLabel("Saved lessons", if (loading) "LOADING" else "${history.size} RECENT")
        // ponytail: The API defaults to the latest 50; add pagination when older drafts are needed.
        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        else if (error.isNotEmpty()) Text("Could not load lesson history: $error", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        else if (history.isEmpty()) Text("No saved lessons yet. Generate one to start.", style = MaterialTheme.typography.bodySmall)
        history.take(50).forEach { draft ->
            val selected = openId == draft.optLong("id")
            Surface(
                onClick = { if (selected) onClose() else onOpen(draft) },
                enabled = !busy,
                shape = RoundedCornerShape(12.dp),
                color = if (selected) MaterialTheme.colorScheme.primaryContainer else LocalStudyColours.current.containerHighest,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text(draft.optString("query"), style = MaterialTheme.typography.titleMedium, maxLines = 2)
                    Text(draft.optString("created_at").take(16).replace('T', ' '), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}
