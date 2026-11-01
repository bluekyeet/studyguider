package nz.studyguider

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

private val LocalAnswerPending = staticCompositionLocalOf<androidx.compose.runtime.snapshots.SnapshotStateMap<String, Boolean>?> { null }

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

private suspend fun explainLesson(base: String, token: String, lessonId: Long, question: String, paragraph: String = "", diagramId: Long? = null, history: List<Pair<String, String>> = emptyList(), onText: (suspend (String) -> Unit)? = null): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + "/lessons/$lessonId/explain" + if (onText != null) "?stream=1" else "").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000; connection.readTimeout = 100000
        connection.requestMethod = "POST"; connection.doOutput = true
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Content-Type", "application/json")
        val body = JSONObject().put("question", question)
        body.put("history", JSONArray().apply { history.takeLast(3).forEach { (q, a) -> put(JSONObject().put("question", q).put("answer", a.take(8000))) } })
        if (diagramId != null) body.put("diagram_id", diagramId)
        if (paragraph.isNotEmpty()) body.put("paragraph", paragraph.take(4000))
        connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val status = connection.responseCode
        if (status in 200..299 && onText != null) {
            val answer = StringBuilder()
            var done = false
            connection.inputStream.bufferedReader(Charsets.UTF_8).use { reader ->
                while (true) {
                    val line = reader.readLine() ?: break
                    if (!line.startsWith("data:")) continue
                    val event = JSONObject(line.substringAfter("data:").trim())
                    if (event.has("error")) throw IllegalStateException(event.getString("error"))
                    if (event.optBoolean("done")) { done = true; break }
                    if (event.has("text")) {
                        answer.append(event.getString("text"))
                        check(answer.length <= 100000) { "Explanation is too large" }
                        withContext(Dispatchers.Main) { onText(answer.toString()) }
                    }
                }
            }
            check(done && answer.isNotBlank()) { "Explanation interrupted. Partial text is incomplete; please retry." }
            return@withContext answer.toString()
        }
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        JSONObject(text).getString("explanation")
    } finally { connection.disconnect() }
}

internal suspend fun saveExplanationNote(base: String, token: String, topicId: Long, content: String) = withContext(Dispatchers.IO) {
    require(content.isNotBlank() && content.length <= 50000) { "Explanation is too long to save as a note" }
    val connection = URL(base.trimEnd('/') + "/topics/$topicId/notes").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000; connection.readTimeout = 20000
        connection.requestMethod = "POST"; connection.doOutput = true
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Content-Type", "application/json")
        connection.outputStream.use { it.write(JSONObject().put("content", content).toString().toByteArray(Charsets.UTF_8)) }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        check(status in 200..299) { "Note save failed ($status): $text" }
        JSONObject(text).getLong("id")
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
        } else if (trim.isNotEmpty() && trim !in setOf("---", "***", "___")) {
            val blocks = markdownBlocks(line)
            blocks.forEach { (kind, _) ->
                val content = when (kind) {
                    "bullet", "bullet2" -> trim.drop(2).trim()
                    "number", "number2" -> trim
                    "quote" -> trim.drop(2).trim()
                    else -> trim
                }
                current.add(kind to content)
            }
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
    lessonId: Long = 0,
    onExit: () -> Unit = {},
    onPendingChange: (Boolean) -> Unit = {},
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

    LaunchedEffect(lessonId) {
        if (lessonId > 0) {
            try {
                val items = requestLessonHistory(base, token, topicId)
                result = (0 until items.length()).map { items.getJSONObject(it) }.firstOrNull { it.optLong("id") == lessonId }
                if (result == null) error = "Lesson not found"
            } catch (e: Exception) { error = e.message ?: "Could not load lesson" }
        }
    }

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

    Column(Modifier.fillMaxSize().padding(top = 4.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        // Always reachable: change topic or subject without hunting through Resources.
        if (lessonId == 0L) TopicSwitcher(
            topicId = topicId, topicName = topicName, subjectName = subjectName,
            allTopics = allTopics, onSwitchTopic = onSwitchTopic, onOpenResources = onOpenResources,
        )
        if (lessonId > 0 && result == null) {
            if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error) else LinearProgressIndicator(Modifier.fillMaxWidth())
        } else {
        result?.let { draft -> LessonArticle(base, token, draft, onExit, onPendingChange) } ?: LessonEmptyState(
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
        if (lessonId == 0L) result?.let { draft -> SourcesCard(draft, citedResourceIds(draft)) { deleteId = draft.getLong("id") } }
        if (error.isNotEmpty() && result != null) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        if (lessonId == 0L) SavedLessons(
            history = history,
            loading = historyLoading,
            error = historyError,
            busy = busy,
            onOpen = { draft -> result = draft },
            onClose = { result = null },
            openId = result?.optLong("id"),
        )
        }
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
private fun ColumnScope.LessonArticle(base: String, token: String, draft: JSONObject, onExit: () -> Unit, onPendingChange: (Boolean) -> Unit) {
    val standards = draft.optJSONArray("standards")
    val standardText = remember(draft) {
        if (standards == null || standards.length() == 0) "NCEA STANDARD"
        else (0 until minOf(standards.length(), 2)).joinToString(" • ") { "AS ${standards.getJSONObject(it).optInt("number")}" }
    }
    val sources = draft.optJSONArray("sources")
    // The reviewer runs in the background on the server; the learner is not shown reviewer output.
    // Citations become S1, S2… so the prose stays readable and still points at a source.
    val citedIds = remember(draft) { citedResourceIds(draft) }
    val chunks = remember(draft) { lessonChunks(withoutSourceMarkers(shortCitations(draft.optString("lesson"), citedIds))).filterNot { Regex("^(?:\\d+[.)]\\s*)?answers?(?:\\s|$)", RegexOption.IGNORE_CASE).containsMatchIn(it.title) } }
    val context = androidx.compose.ui.platform.LocalContext.current
    val progressPrefs = remember { context.getSharedPreferences("lesson_progress", android.content.Context.MODE_PRIVATE) }
    val progressKey = "${base}:${draft.optLong("id")}"
    var openIndex by remember(draft) { mutableIntStateOf(progressPrefs.getInt(progressKey, 0).coerceIn(0, (chunks.size - 1).coerceAtLeast(0))) }
    var progressLoaded by remember(draft) { mutableStateOf(false) }
    var progressRevision by remember(draft) { mutableIntStateOf(0) }
    var savedSection by remember(draft) { mutableIntStateOf(-1) }
    var progressError by remember(draft) { mutableStateOf("") }
    var progressRetry by remember(draft) { mutableIntStateOf(0) }
    LaunchedEffect(draft, progressRetry) {
        if (progressLoaded) return@LaunchedEffect
        try {
            val value = JSONObject(answerRequest(base, token, "/lessons/${draft.getLong("id")}/progress"))
            openIndex = value.getInt("section").coerceIn(0, (chunks.size - 1).coerceAtLeast(0))
            savedSection = openIndex; progressRevision = value.getInt("revision"); progressLoaded = true; progressError = ""
        } catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (e: Exception) { progressError = "Could not load reading progress. Retry before continuing." }
    }
    LaunchedEffect(openIndex, progressLoaded, progressRetry) {
        if (!progressLoaded || openIndex == savedSection) return@LaunchedEffect
        try {
            val value = JSONObject(answerRequest(base, token, "/lessons/${draft.getLong("id")}/progress", JSONObject().put("section", openIndex).put("revision", progressRevision)))
            progressRevision = value.getInt("revision"); savedSection = openIndex; progressError = ""
        } catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (e: Exception) { progressError = e.message ?: "Reading progress not saved" }
    }
    LaunchedEffect(openIndex, draft) { progressPrefs.edit().putInt(progressKey, openIndex).apply() }
    val progress = animateFloatAsState(if (chunks.isEmpty()) 0f else (openIndex + 1).toFloat() / chunks.size, label = "lesson progress")
    val colours = LocalStudyColours.current
    var showHelp by remember(draft) { mutableStateOf(false) }
    var helpQuestion by remember(draft) { mutableStateOf("") }
    var helpAnswer by remember(draft) { mutableStateOf("") }
    var helpBusy by remember(draft) { mutableStateOf(false) }
    var helpParagraph by remember(draft) { mutableStateOf("") }
    var helpDiagramId by remember(draft) { mutableStateOf<Long?>(null) }
    var helpHistory by remember(draft) { mutableStateOf<List<Pair<String, String>>>(emptyList()) }
    var helpNote by remember(draft) { mutableStateOf("") }
    var noteBusy by remember(draft) { mutableStateOf(false) }
    var noteSaved by remember(draft) { mutableStateOf(false) }
    var noteError by remember(draft) { mutableStateOf("") }
    val helpScope = rememberCoroutineScope()
    var finishBusy by remember(draft) { mutableStateOf(false) }
    var finishError by remember(draft) { mutableStateOf("") }
    val pendingAnswers = remember(draft) { mutableStateMapOf<String, Boolean>() }
    val canLeave = progressLoaded && savedSection == openIndex && pendingAnswers.values.none { it }
    val pendingCallback by rememberUpdatedState(onPendingChange)
    SideEffect { pendingCallback(!canLeave) }
    DisposableEffect(Unit) { onDispose { pendingCallback(false) } }
    androidx.activity.compose.BackHandler(enabled = !canLeave) { finishError = "Wait for your answer to save, or retry the failed save before leaving." }
    val scroll = rememberScrollState()
    LaunchedEffect(openIndex) { scroll.scrollTo(0) }

    Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(horizontal = 8.dp, vertical = 2.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                TextButton(enabled = canLeave, onClick = onExit, contentPadding = PaddingValues(horizontal = 4.dp)) { Text("‹ Save & exit") }
                Text("${openIndex + 1} / ${chunks.size}", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(draft.optString("query"), style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface)
            Text(standardText, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)
            LinearProgressIndicator(progress = { progress.value }, modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(50)), color = MaterialTheme.colorScheme.primary, trackColor = colours.containerHigh)
            if (progressError.isNotEmpty()) {
                Text(progressError, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                TextButton(onClick = { progressRetry++ }) { Text("Retry progress sync") }
                TextButton(onClick = { progressLoaded = false; progressRetry++ }) { Text("Reload server position") }
            }
        }
    }

    Box(Modifier.weight(1f)) {
    Column(Modifier.fillMaxSize().verticalScroll(scroll).padding(bottom = 80.dp)) {
    chunks.forEachIndexed { index, chunk ->
        if (index != openIndex) return@forEachIndexed
        val expanded = openIndex == index
        val practice = chunk.isPractice
        Surface(shape = RoundedCornerShape(16.dp), color = if (practice) colours.containerLow else colours.container, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    MathText("**${chunk.title}**", modifier = Modifier.weight(1f))
                    if (practice) StudyChip("Your turn", MaterialTheme.colorScheme.onSecondaryContainer, MaterialTheme.colorScheme.secondaryContainer)
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
                                else -> Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
                                    MathText(content, modifier = Modifier.weight(1f))
                                    IconButton(onClick = {
                                        helpParagraph = content.take(4000)
                                        helpDiagramId = null
                                        helpHistory = emptyList()
                                        helpQuestion = "Explain this part of the lesson."
                                        helpAnswer = ""
                                        helpNote = ""
                                        showHelp = true
                                    }, modifier = Modifier.size(28.dp)) {
                                        Text("?", style = MaterialTheme.typography.labelSmall,
                                             color = MaterialTheme.colorScheme.primary)
                                    }
                                }
                            }
                        }
                        if (!practice) LessonDiagram(base, token, draft, chunk, onExplain = { diagramId ->
                            helpDiagramId = diagramId
                            helpHistory = emptyList()
                            helpParagraph = ""
                            helpQuestion = "Explain this diagram's labels and relationships."
                            helpAnswer = ""
                            helpNote = ""
                            showHelp = true
                        })
                        CompositionLocalProvider(LocalAnswerPending provides pendingAnswers) {
                            if (practice) PracticePanel(base, token, draft, chunk)
                            if (!practice && !chunk.title.contains("worked", true) && !chunk.body.contains("Solution:", true)) SectionQuestion(base, token, draft, chunk)
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                            if (index > 0) TextButton(enabled = canLeave, onClick = { openIndex = index - 1 }) { Text("Previous") }
                            if (index < chunks.size - 1) Button(enabled = canLeave, shape = RoundedCornerShape(50), onClick = { openIndex = index + 1 }) { Text("Next section") }
                            else Button(enabled = !finishBusy && canLeave, onClick = {
                                helpScope.launch {
                                    finishBusy = true; finishError = ""
                                    try {
                                        withContext(Dispatchers.IO) {
                                            val c = URL(base.trimEnd('/') + "/lessons/${draft.getLong("id")}/complete").openConnection() as HttpURLConnection
                                            try {
                                                c.connectTimeout = 10000; c.readTimeout = 20000; c.requestMethod = "POST"
                                                c.setRequestProperty("Authorization", "Bearer $token")
                                                if (c.responseCode !in 200..299) throw IllegalStateException("Could not save completion (${c.responseCode})")
                                            } finally { c.disconnect() }
                                        }
                                        onExit()
                                    } catch (e: kotlinx.coroutines.CancellationException) { throw e }
                                    catch (e: Exception) { finishError = e.message ?: "Could not save completion" }
                                    finally { finishBusy = false }
                                }
                            }) { Text("Finish lesson") }
                        }
                        if (finishError.isNotEmpty()) Text(finishError, color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }
    }
    ExtendedFloatingActionButton(onClick = {
        val current = chunks.getOrNull(openIndex)
        helpParagraph = current?.let { "${it.title}\n\n${it.body}".take(4000) }.orEmpty()
        helpQuestion = "Explain this section in more detail."
        helpDiagramId = null; helpHistory = emptyList(); helpAnswer = ""; helpNote = ""; showHelp = true
    }, modifier = Modifier.align(Alignment.BottomEnd).padding(12.dp), text = { Text("Explain") }, icon = { Text("?") })
    }
    if (showHelp) AlertDialog(
        onDismissRequest = { showHelp = false },
        title = { Text(if (helpDiagramId != null) "Explain this diagram" else "Explain this section") },
        text = { Column(Modifier.verticalScroll(rememberScrollState())) {
            OutlinedTextField(helpQuestion, { helpQuestion = it }, label = { Text("What would you like explained?") }, enabled = !helpBusy)
            if (helpHistory.isNotEmpty()) {
                Text("Follow-up context: last ${helpHistory.size} exchanges in this panel only.", style = MaterialTheme.typography.bodySmall)
                TextButton(enabled = !helpBusy && !noteBusy, onClick = { helpHistory = emptyList(); helpAnswer = ""; helpNote = "" }) { Text("New conversation") }
            }
            if (helpBusy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (helpAnswer.isNotBlank()) MathText(withoutSourceMarkers(shortCitations(helpAnswer, citedIds)))
            if (helpNote.isNotEmpty()) {
                TextButton(enabled = !helpBusy && !noteBusy && !noteSaved && helpNote.length <= 50000, onClick = {
                    helpScope.launch {
                        noteBusy = true; noteError = ""
                        try { saveExplanationNote(base, token, draft.getLong("topic_id"), helpNote); noteSaved = true }
                        catch (e: kotlinx.coroutines.CancellationException) { throw e }
                        catch (e: Exception) { noteError = "${e.message}. If the connection failed, check topic notes before retrying to avoid duplicates." }
                        finally { noteBusy = false }
                    }
                }) { Text(if (noteBusy) "Saving…" else if (noteSaved) "Saved to topic notes" else "Save to notes") }
                if (helpNote.length > 50000) Text("This explanation exceeds the note size limit.", style = MaterialTheme.typography.bodySmall)
                if (noteError.isNotEmpty()) Text(noteError, color = MaterialTheme.colorScheme.error)
            }
        } },
        confirmButton = { TextButton(enabled = !helpBusy && !noteBusy && helpQuestion.isNotBlank() && helpQuestion.length <= 2000, onClick = {
            helpScope.launch {
                helpBusy = true
                helpAnswer = ""
                helpNote = ""; noteSaved = false; noteError = ""
                val askedQuestion = helpQuestion
                try {
                    helpAnswer = explainLesson(base, token, draft.getLong("id"), askedQuestion, helpParagraph, diagramId = helpDiagramId, history = helpHistory, onText = { helpAnswer = it })
                    helpHistory = (helpHistory + (askedQuestion to helpAnswer)).takeLast(3)
                    helpNote = "Lesson ${draft.getLong("id")} — $askedQuestion\n\n$helpAnswer\n\nAI-generated explanation; not verified. Check the original sources."
                }
                catch (e: kotlinx.coroutines.CancellationException) { throw e }
                catch (e: Exception) { helpAnswer += "\n\n${e.message ?: "Could not get an explanation"}" }
                finally { helpBusy = false }
            }
        }) { Text("Ask AI") } },
        dismissButton = { TextButton(onClick = { showHelp = false }) { Text("Close") } },
    )

    // Reviewer output stays on the server; the learner only sees the draft warning.
}

private suspend fun lessonDiagrams(base: String, token: String, topicId: Long, lessonId: Long): String = withContext(Dispatchers.IO) {
    val path = "/topics/$topicId/diagrams?lesson_id=$lessonId"
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000; connection.readTimeout = 200000
        connection.setRequestProperty("Authorization", "Bearer $token")
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        check(status in 200..299) { "Diagram request failed ($status): $text" }
        text
    } finally { connection.disconnect() }
}

@Composable
private fun LessonDiagram(base: String, token: String, draft: JSONObject, chunk: LessonChunk, onExplain: (Long) -> Unit) {
    val lessonId = draft.getLong("id")
    val topicId = draft.getLong("topic_id")
    val description = "Illustrate this lesson section: ${chunk.title}\n${chunk.body}".take(2000)
    var diagram by remember(base, token, lessonId, description) { mutableStateOf<JSONObject?>(null) }
    var error by remember(base, token, lessonId, description) { mutableStateOf("") }
    LaunchedEffect(base, token, lessonId, description) {
        try {
            val rows = JSONArray(lessonDiagrams(base, token, topicId, lessonId))
            diagram = (0 until rows.length()).map { rows.getJSONObject(it) }.firstOrNull { it.optString("description") == description }
        } catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Could not load diagram" }
    }
    if (diagram?.optString("status") == "passed") {
        Text("AI diagram — independently AI-reviewed, not verified", style = MaterialTheme.typography.labelSmall)
        AuthorisedImage(base, token, "/diagrams/${diagram!!.getLong("id")}/image", Modifier.fillMaxWidth(), contentDescription = "AI-generated diagram for ${chunk.title}")
        TextButton(onClick = { onExplain(diagram!!.getLong("id")) }) { Text("Explain this diagram") }
    } else {
        if (diagram != null) Text("Diagram withheld: independent review did not pass.", style = MaterialTheme.typography.bodySmall)
    }
    if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
}

/**
 * One question after a reading section, built from that section's own wording,
 * so every chunk ends with something to answer rather than only reading.
 */
@Composable
private fun SectionQuestion(base: String, token: String, draft: JSONObject, chunk: LessonChunk) {
    if (Regex("overview|prerequisite|prior knowledge|assumed|learning goal|learning objective|course position|progression|summary", RegexOption.IGNORE_CASE).containsMatchIn(chunk.title)) return
    val questions = remember(chunk) { practiceQuestions(chunk.body) }
    if (questions.isEmpty()) return
    var index by remember(chunk) { mutableIntStateOf(0) }
    val question = questions[index]
    var answer by remember(chunk, index) { mutableStateOf("") }
    var revealed by remember(chunk, index) { mutableStateOf(false) }
    var feedback by remember(chunk, index) { mutableStateOf("") }
    var busy by remember(chunk, index) { mutableStateOf(false) }
    var error by remember(chunk, index) { mutableStateOf("") }
    val answerLoaded = SavedAnswer(base, token, draft.getLong("id"), question.prompt, answer, feedback, { answer = it }, { feedback = it })
    val scope = rememberCoroutineScope()
    val colours = LocalStudyColours.current

    HorizontalDivider()
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("QUICK CHECK", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
        if (questions.size > 1) Text("${index + 1} of ${questions.size}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    MathText(question.prompt)
    if (question.choices.isEmpty()) MathField(answer, { answer = it; feedback = "" }, label = "Your answer", minLines = 3, maxLines = 12, enabled = !busy && answerLoaded)
    else question.choices.forEach { choice ->
        Row(Modifier.fillMaxWidth().clickable(enabled = !busy && answerLoaded) { answer = choice; feedback = "" }, verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = answer == choice, onClick = { answer = choice; feedback = "" }, enabled = !busy && answerLoaded)
            Text(choice, style = MaterialTheme.typography.bodyLarge)
        }
    }
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
    }
    if (questions.size > 1) TextButton(onClick = { index = (index + 1) % questions.size }) { Text("Another question") }
    if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
    if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    if (feedback.isNotBlank()) Surface(shape = RoundedCornerShape(12.dp), color = colours.containerHigh, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("TUTOR FEEDBACK — AI, CHECK THE SOURCES", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
            TutorText(feedback, draft)
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
    val answerLoaded = SavedAnswer(base, token, draft.getLong("id"), chunk.title + "\n" + chunk.body, working, reply, { working = it }, { reply = it })
    HorizontalDivider()
    Text("Check your understanding", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.secondary)
    MathField(working, { working = it; reply = "" }, label = "Your working", minLines = 3, maxLines = 12, enabled = !busy && answerLoaded)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(shape = RoundedCornerShape(50), enabled = !busy && working.isNotBlank() && working.length <= 2000, onClick = {
            scope.launch {
                busy = true; error = ""
                try { reply = explainLesson(base, token, draft.getLong("id"), "Mark my answer to the question in this lesson section. Keep feedback proportional to the question.\nSection: ${chunk.title}\nQuestion and context:\n${chunk.body}\nMy answer:\n$working") }
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
        TutorText(reply, draft)
        TextButton(onClick = { reply = "" }) { Text("Dismiss") }
    }
    AnimatedVisibility(visible = revealed) {
        StudyCard(tone = CardTone.Low) {
            Text("LESSON CONTENT — CHECK AGAINST SOURCES", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline, fontWeight = FontWeight.Bold, textAlign = TextAlign.Start)
            MathText(chunk.body)
        }
    }
}

/** Device-independent drafts and feedback; the server keeps the latest saved version. */
@Composable
private fun SavedAnswer(base: String, token: String, lessonId: Long, question: String, answer: String, feedback: String, restoreAnswer: (String) -> Unit, restoreFeedback: (String) -> Unit): Boolean {
    val key = remember(question) { java.security.MessageDigest.getInstance("SHA-256").digest(question.toByteArray()).joinToString("") { "%02x".format(it) } }
    val context = androidx.compose.ui.platform.LocalContext.current
    val recovery = remember { context.getSharedPreferences("lesson_answer_recovery", android.content.Context.MODE_PRIVATE) }
    val recoveryKey = "$base:$lessonId:$key"
    var loaded by remember(base, lessonId, key) { mutableStateOf(false) }
    var status by remember(base, lessonId, key) { mutableStateOf("Loading saved answer…") }
    var retry by remember { mutableIntStateOf(0) }
    var saved by remember(base, lessonId, key) { mutableStateOf<Pair<String, String>?>(null) }
    var revision by remember(base, lessonId, key) { mutableIntStateOf(0) }
    var showRecovery by remember(key) { mutableStateOf(false) }
    val pending = LocalAnswerPending.current
    SideEffect { pending?.set(key, !loaded || saved != (answer to feedback)) }
    DisposableEffect(key) { onDispose { pending?.remove(key) } }
    LaunchedEffect(base, lessonId, key, retry) {
        if (loaded) return@LaunchedEffect
        try {
            val text = answerRequest(base, token, "/lessons/$lessonId/answers")
            val rows = JSONArray(text)
            val row = (0 until rows.length()).map { rows.getJSONObject(it) }.firstOrNull { it.optString("question_key") == key }
            val oldAnswer = row?.optString("answer").orEmpty()
            val oldFeedback = row?.optString("feedback").orEmpty()
            revision = row?.optInt("revision", 0) ?: 0
            val local = recovery.getString(recoveryKey, null)?.let { runCatching { JSONObject(it) }.getOrNull() }
            if (local != null) revision = local.optInt("revision", revision)
            restoreAnswer(local?.optString("answer") ?: oldAnswer); restoreFeedback(local?.optString("feedback") ?: oldFeedback)
            saved = oldAnswer to oldFeedback; loaded = true; status = if (row == null) "" else "Saved to server"
        } catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (e: Exception) { status = "Could not load saved answer. Retry before editing." }
    }
    LaunchedEffect(answer, feedback, loaded, retry) {
        if (!loaded || saved == (answer to feedback)) return@LaunchedEffect
        status = "Saving…"
        delay(600)
        try {
            val result = JSONObject(answerRequest(base, token, "/lessons/$lessonId/answers/$key", JSONObject().put("question", question).put("answer", answer).put("feedback", feedback).put("revision", revision)))
            revision = result.getInt("revision")
            saved = answer to feedback; status = "Saved to server"
            recovery.edit().remove(recoveryKey).apply()
        } catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (e: Exception) { status = if (e.message?.contains("another device") == true) "Answer not saved: changed on another device. Local draft retained." else "Answer not saved. Retry before leaving." }
    }
    // Persist before the debounced network write so navigation/process death can recover it.
    DisposableEffect(answer, feedback, loaded) {
        if (loaded && saved != (answer to feedback)) recovery.edit().putString(recoveryKey, JSONObject().put("answer", answer).put("feedback", feedback).put("revision", revision).toString()).commit()
        onDispose { }
    }
    if (status.isNotEmpty()) Text(status, style = MaterialTheme.typography.bodySmall, color = if (status.contains("not saved") || status.contains("Could not")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
    if (status.contains("not saved") || status.contains("Could not")) TextButton(onClick = { retry++ }) { Text("Retry save/load") }
    if (status.contains("another device")) TextButton(onClick = {
        // Keep the conflicting draft for recovery; only discard its automatic replay pointer.
        recovery.getString(recoveryKey, null)?.let { recovery.edit().putString("$recoveryKey:conflict", it).remove(recoveryKey).commit() }
        loaded = false; retry++
    }) { Text("Load server answer (keep local recovery copy)") }
    if (recovery.contains("$recoveryKey:conflict")) TextButton(onClick = { showRecovery = true }) { Text("View recovered draft") }
    if (showRecovery) AlertDialog(onDismissRequest = { showRecovery = false }, title = { Text("Recovered draft") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState())) {
            Text("Restoring replaces this device's current draft. The next save checks the current server revision.")
            Text(runCatching { JSONObject(recovery.getString("$recoveryKey:conflict", "{}").orEmpty()).optString("answer") }.getOrDefault(""))
        }
    }, confirmButton = { TextButton(enabled = loaded, onClick = {
        val local = JSONObject(recovery.getString("$recoveryKey:conflict", "{}").orEmpty())
        restoreAnswer(local.optString("answer")); restoreFeedback(local.optString("feedback")); showRecovery = false
    }) { Text("Restore draft") } }, dismissButton = { TextButton(onClick = { showRecovery = false }) { Text("Keep current answer") } })
    return loaded
}

private suspend fun answerRequest(base: String, token: String, path: String, body: JSONObject? = null): String = withContext(Dispatchers.IO) {
    val c = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        c.connectTimeout = 10000; c.readTimeout = 20000
        c.setRequestProperty("Authorization", "Bearer $token")
        if (body != null) {
            c.requestMethod = "PUT"; c.doOutput = true; c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        if (c.responseCode == 409) throw IllegalStateException("This answer changed on another device. Your local draft is retained.")
        if (c.responseCode !in 200..299) throw IllegalStateException("Answer request failed (${c.responseCode})")
        c.inputStream.bufferedReader().use { it.readText() }
    } finally { c.disconnect() }
}

@Composable
private fun TutorText(text: String, draft: JSONObject) {
    val cleaned = withoutSourceMarkers(shortCitations(text, citedResourceIds(draft)))
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        markdownBlocks(cleaned).forEach { (kind, runs) ->
            val content = runs.joinToString("") { it.text }
            if (kind == "heading") Text(content, style = MaterialTheme.typography.titleSmall)
            else MathText(content)
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
