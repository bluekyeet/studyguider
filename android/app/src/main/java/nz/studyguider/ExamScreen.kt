package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.snapshots.SnapshotStateMap
import androidx.activity.compose.BackHandler
import androidx.activity.compose.LocalOnBackPressedDispatcherOwner
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

private suspend fun examRequest(base: String, token: String, path: String, answer: String? = null, feedback: Boolean = false): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 200000
        connection.setRequestProperty("Authorization", "Bearer $token")
        if (answer != null || feedback) {
            connection.requestMethod = if (feedback) "POST" else "PUT"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.doOutput = true
            connection.outputStream.use { it.write((if (feedback) JSONObject().put("second_review", false) else JSONObject().put("answer", answer)).toString().toByteArray(Charsets.UTF_8)) }
        }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)
            ?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        text
    } finally { connection.disconnect() }
}

private val answerMapSaver = Saver<SnapshotStateMap<Long, String>, ArrayList<String>>(
    save = { map -> ArrayList(map.flatMap { listOf(it.key.toString(), it.value) }) },
    restore = { values -> mutableStateMapOf<Long, String>().apply {
        values.chunked(2).forEach { put(it[0].toLong(), it[1]) }
    } }
)

/** The host must guard its own navigation when [onDirtyChange] reports unsaved answers. */
@Composable
fun ExamScreen(base: String, token: String, examId: Long, onOpenSource: (String, Int) -> Unit = { _, _ -> }, onDirtyChange: (Boolean) -> Unit = {}) {
    var exam by remember(base, token, examId) { mutableStateOf<JSONObject?>(null) }
    var error by remember(base, token, examId) { mutableStateOf("") }
    var busy by remember(base, token, examId) { mutableStateOf(false) }
    var marks by remember(base, token, examId) { mutableStateOf<JSONObject?>(null) }
    val answers = rememberSaveable(base, token, examId, saver = answerMapSaver) { mutableStateMapOf<Long, String>() }
    val saved = rememberSaveable(base, token, examId, saver = answerMapSaver) { mutableStateMapOf<Long, String>() }
    val feedback = remember(base, token, examId) { mutableStateMapOf<Long, JSONObject>() }
    val scope = rememberCoroutineScope()
    val dirty = answers.any { (id, answer) -> answer != saved[id] }
    var confirmLeave by remember { mutableStateOf(false) }
    var leaving by remember { mutableStateOf(false) }
    val dispatcher = LocalOnBackPressedDispatcherOwner.current?.onBackPressedDispatcher
    val currentOnDirtyChange by rememberUpdatedState(onDirtyChange)
    LaunchedEffect(dirty) { currentOnDirtyChange(dirty) }
    DisposableEffect(Unit) { onDispose { currentOnDirtyChange(false) } }
    BackHandler(enabled = dirty && !leaving && dispatcher != null) { confirmLeave = true }
    if (confirmLeave) {
        AlertDialog(
            onDismissRequest = { confirmLeave = false },
            title = { Text("Discard unsaved answers?") },
            text = { Text("Your unsaved changes will be lost.") },
            confirmButton = { TextButton(onClick = {
                confirmLeave = false
                leaving = true
            }) { Text("Discard") } },
            dismissButton = { TextButton(onClick = { confirmLeave = false }) { Text("Keep editing") } }
        )
    }
    LaunchedEffect(leaving) { if (leaving) { dispatcher?.onBackPressed(); leaving = false } }

    suspend fun load() {
        val result = JSONObject(examRequest(base, token, "/exams/$examId"))
        val questions = result.getJSONArray("questions")
        val serverAnswers = buildMap {
            for (i in 0 until questions.length()) {
                val question = questions.getJSONObject(i)
                put(question.getLong("id"), if (question.isNull("answer")) "" else question.getString("answer"))
            }
        }
        val drafts = answers.filter { (id, answer) -> answer != saved[id] }
        answers.clear()
        saved.clear()
        feedback.clear()
        for ((id, answer) in serverAnswers) {
            answers[id] = drafts[id] ?: answer
            saved[id] = answer
        }
        // ponytail: retain drafts for removed questions; add a recovery UI if exams become editable.
        drafts.forEach { (id, answer) -> if (id !in answers) answers[id] = answer }
        exam = result
        marks = runCatching { JSONObject(examRequest(base, token, "/exams/$examId/marks")) }.getOrNull()
    }

    LaunchedEffect(base, token, examId) {
        busy = true
        error = ""
        try { load() } catch (e: CancellationException) { throw e } catch (e: Exception) {
            error = e.message ?: "Unable to load exam"
        } finally { busy = false }
    }

    val colours = LocalStudyColours.current
    Column(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        StudyCard(tone = CardTone.Container) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("EXAM $examId", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                marks?.let { StudyChip("${it.optInt("marks_awarded")} / ${it.optInt("marks_available")}", MaterialTheme.colorScheme.onPrimaryContainer, MaterialTheme.colorScheme.primaryContainer) }
            }
            Text(exam?.optString("kind")?.replaceFirstChar { it.uppercase() }?.let { if (it == "Monthly") "Monthly exam" else "Practice exam" } ?: "Exam", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
            Text("Questions and marking schedules are not included here. Consult the original paper and schedule using the references below. Feedback is experimental AI-generated study feedback, not an official or verified grade.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (marks != null) StatusDot(colours.merit, "Indicative outcome: ${marks!!.optString("outcome")} (not official)")
            if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (exam == null && !busy) {
                Button(shape = RoundedCornerShape(50), onClick = {
                    scope.launch {
                        busy = true; error = ""
                        try { load() } catch (e: CancellationException) { throw e } catch (e: Exception) {
                            error = e.message ?: "Unable to load exam"
                        } finally { busy = false }
                    }
                }) { Text("Retry") }
            }
        }
        exam?.let { data ->
            val questions = data.getJSONArray("questions")
            if (questions.length() == 0) Text("This exam has no questions.")
            for (i in 0 until questions.length()) {
                val question = questions.getJSONObject(i)
                val id = question.getLong("id")
                key(id) {
                    StudyCard(tone = CardTone.Container) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text("${question.getInt("position")}. QUESTION ${question.getString("question_number")}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                            StudyChip("AS ${question.getInt("standard_number")} · ${question.getInt("year")}", MaterialTheme.colorScheme.onSurfaceVariant, colours.containerHigh)
                        }
                        val text = question.optString("question_text")
                        if (text.isNotBlank()) MathText(text, formulaStyle = true)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(shape = RoundedCornerShape(50), onClick = { onOpenSource(question.getString("paper_resource_id"), question.getInt("paper_page")) }) { Text("Paper p.${question.getInt("paper_page")}") }
                            OutlinedButton(shape = RoundedCornerShape(50), onClick = { onOpenSource(question.getString("schedule_resource_id"), question.getInt("schedule_page")) }) { Text("Schedule p.${question.getInt("schedule_page")}") }
                        }
                        MathField(answers[id].orEmpty(), { answers[id] = it; feedback.remove(id); currentOnDirtyChange(answers.any { (key, value) -> value != saved[key] }) }, label = "Your answer", enabled = !busy, minLines = 4, maxLines = 14, supportingText = "Maximum 100,000 characters")
                        if (answers[id] != saved[id]) Text("Unsaved changes", style = MaterialTheme.typography.labelSmall, color = colours.amber)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(shape = RoundedCornerShape(50), enabled = !busy && answers[id].orEmpty().length <= 100000, onClick = {
                                val answer = answers[id].orEmpty()
                                scope.launch {
                                    busy = true; error = ""
                                    try {
                                        examRequest(base, token, "/exams/$examId/answers/$id", answer)
                                        saved[id] = answer
                                    } catch (e: CancellationException) { throw e } catch (e: Exception) {
                                        error = e.message ?: "Unable to save answer"
                                    } finally { busy = false }
                                }
                            }) { Text("Save") }
                            Button(shape = RoundedCornerShape(50), enabled = !busy && answers[id].orEmpty().isNotBlank() && answers[id].orEmpty().length <= 100000, onClick = {
                                val answer = answers[id].orEmpty()
                                scope.launch {
                                    busy = true; error = ""; feedback.remove(id)
                                    try {
                                        examRequest(base, token, "/exams/$examId/answers/$id", answer)
                                        saved[id] = answer
                                        feedback[id] = JSONObject(examRequest(base, token, "/exams/$examId/answers/$id/feedback", feedback = true))
                                        marks = runCatching { JSONObject(examRequest(base, token, "/exams/$examId/marks")) }.getOrNull()
                                    } catch (e: CancellationException) { throw e } catch (e: Exception) {
                                        error = e.message ?: "Unable to get feedback"
                                    } finally { busy = false }
                                }
                            }) { Text("Save & mark") }
                        }
                    }
                    feedback[id]?.let { result -> FeedbackCard(result) }
                }
            }
        }
    }
}

@Composable
private fun FeedbackCard(result: JSONObject) {
    val colours = LocalStudyColours.current
    val outcome = result.optString("outcome").replace('_', ' ')
    val outcomeColour = when {
        outcome.startsWith("excellence") -> colours.excellence
        outcome.startsWith("merit") -> colours.merit
        outcome.startsWith("achieved") -> colours.achieved
        else -> colours.amber
    }
    StudyCard(tone = CardTone.Low) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text("AI FEEDBACK", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
            StudyChip(outcome, outcomeColour, colours.containerHighest)
        }
        Text(result.optString("disclaimer"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (result.has("marks_awarded")) Text("Suggested mark: ${result.optInt("marks_awarded")} — not a grade", style = MaterialTheme.typography.labelMedium)
        MathText(result.optString("feedback"))
        val evidence = result.optJSONArray("evidence")
        if (evidence != null) for (j in 0 until evidence.length()) {
            val item = evidence.getJSONObject(j)
            Text("Schedule quotation: “${item.optString("quote")}”", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            Text(item.optString("explanation"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("Feedback is not saved. Check the original schedule using the reference above.", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
