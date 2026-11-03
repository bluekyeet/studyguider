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
import androidx.compose.ui.platform.LocalContext
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

private suspend fun examRequest(base: String, token: String, path: String, answer: String? = null, feedback: Boolean = false, revision: Int = 0, scanRevision: Int = 0): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 200000
        connection.setRequestProperty("Authorization", "Bearer $token")
        if (answer != null || feedback) {
            connection.requestMethod = if (feedback) "POST" else "PUT"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.doOutput = true
            connection.outputStream.use { it.write((if (feedback) JSONObject().put("second_review", false) else JSONObject().put("answer", answer).put("revision", revision).put("scan_revision", scanRevision)).toString().toByteArray(Charsets.UTF_8)) }
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
fun ExamScreen(base: String, token: String, examId: Long, onOpenSource: (String, Int) -> Unit = { _, _ -> }, onDirtyChange: (Boolean) -> Unit = {}, onPageChange: () -> Unit = {}) = key(base, token, examId) {
    var exam by remember(base, token, examId) { mutableStateOf<JSONObject?>(null) }
    var error by remember(base, token, examId) { mutableStateOf("") }
    var busy by remember(base, token, examId) { mutableStateOf(false) }
    var marks by remember(base, token, examId) { mutableStateOf<JSONObject?>(null) }
    var scheduleGrade by remember(base, token, examId) { mutableStateOf<JSONObject?>(null) }
    var answerMode by remember(base, token, examId) { mutableStateOf("digital") }
    var examTitle by remember(base, token, examId) { mutableStateOf("") }
    var page by rememberSaveable(examId) { mutableIntStateOf(0) }
    var scanReady by remember(examId) { mutableStateOf(false) }
    LaunchedEffect(page) { onPageChange() }
    val answers = rememberSaveable(base, token, examId, saver = answerMapSaver) { mutableStateMapOf<Long, String>() }
    val saved = rememberSaveable(base, token, examId, saver = answerMapSaver) { mutableStateMapOf<Long, String>() }
    val revisionStrings = rememberSaveable(base, token, examId, saver = answerMapSaver) { mutableStateMapOf<Long, String>() }
    val scanRevisions = rememberSaveable(base, token, examId, saver = answerMapSaver) { mutableStateMapOf<Long, String>() }
    val feedback = remember(base, token, examId) { mutableStateMapOf<Long, JSONObject>() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val printPicker = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/pdf")) { uri ->
        if (uri != null) scope.launch {
            busy = true; error = ""
            try {
                withContext(Dispatchers.IO) {
                    val c = URL(base.trimEnd('/') + "/exams/$examId/print").openConnection() as HttpURLConnection
                    try {
                        c.connectTimeout = 10000; c.readTimeout = 30000; c.setRequestProperty("Authorization", "Bearer $token")
                        if (c.responseCode !in 200..299) throw IllegalStateException("PDF export failed (${c.responseCode})")
                        context.contentResolver.openOutputStream(uri)?.use { out -> c.inputStream.use { it.copyTo(out) } } ?: throw IllegalStateException("Cannot save PDF")
                    } finally { c.disconnect() }
                }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { error = e.message ?: "Could not export paper" }
            finally { busy = false }
        }
    }
    var scanQuestion by remember { mutableStateOf<Long?>(null) }
    val scanPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(10)) { uris ->
        val id = scanQuestion
        if (uris.isNotEmpty()) scope.launch {
            busy = true; error = ""
            try {
                val reply = withContext(Dispatchers.IO) {
                    val boundary = "scan-${java.util.UUID.randomUUID()}"
                    val path = if (id == null) "/exams/$examId/scan" else "/exams/$examId/answers/$id/scan"
                    val c = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
                    try {
                        c.connectTimeout = 10000; c.readTimeout = 200000; c.requestMethod = "POST"; c.doOutput = true
                        c.setRequestProperty("Authorization", "Bearer $token")
                        c.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
                        c.outputStream.use {
                            var total = 0
                            uris.forEachIndexed { index, uri ->
                                val bytes = context.contentResolver.openInputStream(uri)?.use { stream -> stream.readNBytes(10 * 1024 * 1024 + 1) } ?: throw IllegalStateException("Cannot open image")
                                total += bytes.size
                                if (total > 10 * 1024 * 1024) throw IllegalStateException("Selected images exceed 10 MiB in total")
                                it.write("--$boundary\r\nContent-Disposition: form-data; name=\"files\"; filename=\"page-${index + 1}.jpg\"\r\nContent-Type: application/octet-stream\r\n\r\n".toByteArray())
                                it.write(bytes); it.write("\r\n".toByteArray())
                            }
                            it.write("--$boundary--\r\n".toByteArray())
                        }
                        if (c.responseCode !in 200..299) throw IllegalStateException("Scan failed (${c.responseCode})")
                        JSONObject(c.inputStream.bufferedReader().use { it.readText() })
                    } finally { c.disconnect() }
                }
                if (id != null) { answers[id] = reply.getString("transcription"); scanRevisions[id] = reply.getInt("scan_revision").toString(); feedback.remove(id) }
                else {
                    feedback.clear()
                    val recognised = reply.getJSONArray("answers")
                    for (i in 0 until recognised.length()) {
                        val item = recognised.getJSONObject(i)
                        answers[item.getLong("question_id")] = item.getString("transcription")
                        scanRevisions[item.getLong("question_id")] = item.getInt("scan_revision").toString()
                    }
                    scanReady = true; page = 0
                }
                error = reply.optString("notice")
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { error = e.message ?: "Could not read handwriting" }
            finally { busy = false }
        }
    }
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
        val details = JSONObject(examRequest(base, token, "/exams/$examId/details"))
        answerMode = details.optString("answer_mode", "digital"); examTitle = details.optString("title")
        val result = JSONObject(examRequest(base, token, "/exams/$examId"))
        val questions = result.getJSONArray("questions")
        val serverAnswers = buildMap {
            for (i in 0 until questions.length()) {
                val question = questions.getJSONObject(i)
                put(question.getLong("id"), if (question.isNull("answer")) "" else question.getString("answer"))
                val id = question.getLong("id")
                if (answers[id] == saved[id] || id !in revisionStrings) revisionStrings[id] = question.optInt("answer_revision").toString()
                if (answers[id] == saved[id] || id !in scanRevisions) scanRevisions[id] = question.optInt("scan_revision").toString()
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
        scheduleGrade = runCatching { JSONObject(examRequest(base, token, "/exams/$examId/schedule-grade")) }.getOrNull()
    }

    LaunchedEffect(base, token, examId) {
        busy = true
        error = ""
        try { load() } catch (e: CancellationException) { throw e } catch (e: Exception) {
            error = e.message ?: "Unable to load exam"
        } finally { busy = false }
    }

    OutlinedButton(enabled = !busy, onClick = { printPicker.launch("exam-$examId.pdf") }) { Text("Save printable paper (text-only)") }
    val colours = LocalStudyColours.current
    Column(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        StudyCard(tone = CardTone.Container) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("EXAM $examId", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                marks?.let { StudyChip("${it.optInt("marks_awarded")} / ${it.optInt("marks_available")}", MaterialTheme.colorScheme.onPrimaryContainer, MaterialTheme.colorScheme.primaryContainer) }
            }
            Text(examTitle.ifBlank { "Exam" }, style = MaterialTheme.typography.titleLarge)
            ExamTimer(examId, base)
            Text(if (answerMode == "handwritten") "Handwritten · work through the questions, then upload your pages at the end." else "Digital · save and mark your answers below.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("digital" to "Type answers", "handwritten" to "Write on paper").forEach { (mode, label) ->
                    FilterChip(selected = answerMode == mode, enabled = !busy, onClick = {
                        scope.launch {
                            busy = true; error = ""
                            try {
                                withContext(Dispatchers.IO) {
                                    val c = URL(base.trimEnd('/') + "/exams/$examId/answer-mode").openConnection() as HttpURLConnection
                                    try {
                                        c.connectTimeout = 10000; c.readTimeout = 20000; c.requestMethod = "PUT"; c.doOutput = true
                                        c.setRequestProperty("Authorization", "Bearer $token"); c.setRequestProperty("Content-Type", "application/json")
                                        c.outputStream.use { it.write(JSONObject().put("answer_mode", mode).toString().toByteArray()) }
                                        if (c.responseCode !in 200..299) throw IllegalStateException("Could not change answer mode (${c.responseCode})")
                                    } finally { c.disconnect() }
                                }
                                answerMode = mode
                                if (page >= (exam?.getJSONArray("questions")?.length() ?: 0)) page = 0
                            } catch (e: CancellationException) { throw e }
                            catch (e: Exception) { error = e.message ?: "Could not change answer mode" }
                            finally { busy = false }
                        }
                    }, label = { Text(label) })
                }
            }
            scheduleGrade?.let { grade ->
                if (grade.optString("outcome") != "uncertain") Text("Schedule-based result: ${grade.optString("outcome").replace('_', ' ')} · AI-marked, not an official result", style = MaterialTheme.typography.bodySmall)
                else Text(grade.optString("reason", "Overall grade pending schedule-based marking"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
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
            Text(if (page < questions.length()) "Question ${page + 1} of ${questions.length()}" else "Upload your completed paper", style = MaterialTheme.typography.titleMedium)
            LinearProgressIndicator(progress = { if (questions.length() == 0) 0f else ((page + 1).toFloat() / questions.length()).coerceAtMost(1f) }, modifier = Modifier.fillMaxWidth())
            for (i in 0 until questions.length()) {
                if (i != page) continue
                val question = questions.getJSONObject(i)
                val id = question.getLong("id")
                key(id) {
                    StudyCard(tone = CardTone.Container) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text("${question.getInt("position")}. QUESTION ${question.getString("question_number")}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                            StudyChip("AS ${question.getInt("standard_number")} · ${question.getInt("year")}", MaterialTheme.colorScheme.onSurfaceVariant, colours.containerHigh)
                        }
                        val text = question.optString("question_text")
                        val paperId = question.optString("paper_resource_id").takeUnless { it.isBlank() || it == "null" }
                        val structured = question.optJSONArray("parts")
                        val structuredParts = remember(id, text) {
                            if (structured == null) emptyList() else (0 until structured.length()).map { structured.getJSONObject(it) }.filter { it.has("text") }
                        }
                        val parts = remember(id, text) {
                            if (structuredParts.isEmpty()) examParts(text)
                            else structuredParts.map { part ->
                                val label = part.optString("label")
                                (if (label == "context") "" else "(" + label.replace("(", ")(") + if (label.endsWith(")")) "" else ")") to part.optString("text").replaceFirst(Regex("^\\s*\\([a-hivx]+\\)\\s*"), "")
                            }
                        }
                        val partAnswers = remember(id) { mutableStateMapOf<String, String>() }
                        LaunchedEffect(saved[id]) {
                            val existing = answers[id].orEmpty()
                            if (existing.startsWith("{\"parts\":")) {
                                runCatching { JSONObject(existing).getJSONObject("parts") }.getOrNull()?.let { values ->
                                    values.keys().forEach { partAnswers[it] = values.getString(it) }
                                }
                            }
                        }
                        if (question.optBoolean("maths_restored")) Text("Equations were read from the original page by AI. Check them against the paper.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (text.isNotBlank()) parts.forEachIndexed { partIndex, (label, wording) ->
                            if (wording.isNotBlank() && !wording.trim().matches(Regex("QUESTION\\s+(ONE|TWO|THREE|[0-9]+)", RegexOption.IGNORE_CASE))) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                if (label.isNotEmpty()) Text(label, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.secondary, modifier = Modifier.widthIn(min = 36.dp))
                                MathText(reflow(wording), modifier = Modifier.weight(1f))
                            }
                            structuredParts.getOrNull(partIndex)?.optJSONArray("diagrams")?.let { diagrams ->
                                if (paperId != null) for (d in 0 until diagrams.length()) {
                                    val diagram = diagrams.getJSONObject(d)
                                    val box = diagram.getJSONArray("bbox")
                                    val query = listOf("x0", "y0", "x1", "y1").mapIndexed { n, name -> "$name=${box.getDouble(n)}" }.joinToString("&")
                                    AuthorisedImage(base, token, "/resources/$paperId/pages/${diagram.getInt("page")}/diagram-image?$query")
                                }
                            }
                            val parentOnly = label.isNotEmpty() && parts.any { it.first.startsWith(label + "(") }
                            if (label.isNotEmpty() && !parentOnly && answerMode == "digital") MathField(partAnswers[label].orEmpty(), { value ->
                                partAnswers[label] = value
                                answers[id] = JSONObject().put("parts", JSONObject(partAnswers.toMap())).toString()
                                feedback.remove(id)
                            }, label = "Answer $label", enabled = !busy, minLines = 2, maxLines = 10)
                        }
                        if (paperId != null) {
                            if (structuredParts.isEmpty()) InlineExamDiagrams(base, token, paperId, question.getInt("paper_page"))
                            val figures = question.optJSONArray("figure_pages")
                            if (figures != null && figures.length() > 0) {
                                var showFigures by remember(id) { mutableStateOf(false) }
                                TextButton(onClick = { showFigures = !showFigures }) { Text(if (showFigures) "Hide original diagrams" else "View original diagram pages") }
                                if (showFigures) for (p in 0 until figures.length()) AuthorisedImage(base, token, "/resources/$paperId/pages/${figures.getInt(p)}/image")
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (paperId != null) OutlinedButton(shape = RoundedCornerShape(50), onClick = { onOpenSource(paperId, question.getInt("paper_page")) }) { Text("Paper p.${question.getInt("paper_page")}") }
                            if (!question.isNull("schedule_resource_id")) OutlinedButton(shape = RoundedCornerShape(50), onClick = { onOpenSource(question.getString("schedule_resource_id"), question.getInt("schedule_page")) }) { Text("Schedule p.${question.getInt("schedule_page")}") }
                        }
                        val scheduleText = question.optString("schedule_text")
                        if (scheduleText.isNotBlank()) {
                            var compare by remember(id) { mutableStateOf(false) }
                            TextButton(onClick = { compare = !compare }) { Text(if (compare) "Hide answer comparison" else "Compare with schedule / rubric") }
                            if (compare) StudyCard(tone = CardTone.Low) {
                                Text("Your current answer", style = MaterialTheme.typography.titleSmall)
                                val current = answers[id].orEmpty()
                                val answerParts = if (current.startsWith("{\"parts\":")) runCatching { JSONObject(current).getJSONObject("parts") }.getOrNull() else null
                                if (answerParts != null) {
                                    answerParts.keys().forEach { label -> MathText("$label: ${answerParts.getString(label)}") }
                                } else MathText(current.ifBlank { "No answer entered yet." })
                                Text(if (question.isNull("schedule_resource_id")) "Unofficial AI practice rubric" else "Registered schedule excerpt", style = MaterialTheme.typography.titleSmall)
                                Text(if (question.isNull("schedule_resource_id")) "AI-generated, not an official NZQA schedule." else "Extracted text may be incomplete. Check the original schedule page before changing your judgement.", style = MaterialTheme.typography.bodySmall)
                                MathText(scheduleText)
                            }
                        }
                        if (answerMode == "digital" || scanReady || answers[id].orEmpty().isNotBlank()) {
                        if (answerMode == "digital" && requestsDiagram(text)) ExamDiagram(base, token, examId, id, !busy) { transcription, scanRevision ->
                            scanRevisions[id] = scanRevision.toString()
                            if (answers[id].orEmpty().startsWith("{\"parts\":")) {
                                partAnswers["diagram"] = transcription
                                answers[id] = JSONObject().put("parts", JSONObject(partAnswers.toMap())).toString()
                            } else answers[id] = answers[id].orEmpty() + "\n\nAttached diagram recognition (check before marking):\n" + transcription
                            feedback.remove(id)
                        }
                        if (partAnswers.containsKey("diagram")) MathField(partAnswers["diagram"].orEmpty(), { value ->
                            partAnswers["diagram"] = value; answers[id] = JSONObject().put("parts", JSONObject(partAnswers.toMap())).toString()
                            feedback.remove(id)
                        }, label = "Check diagram recognition", enabled = !busy, minLines = 2)
                        if (answerMode == "handwritten" || parts.none { it.first.isNotEmpty() } || (answers[id].orEmpty().isNotBlank() && !answers[id].orEmpty().startsWith("{\"parts\":"))) MathField(answers[id].orEmpty(), { answers[id] = it; feedback.remove(id); currentOnDirtyChange(answers.any { (key, value) -> value != saved[key] }) }, label = if (answerMode == "handwritten") "Check recognised answer" else "Your answer", enabled = !busy, minLines = 4, maxLines = 14, supportingText = "Maximum 100,000 characters")
                        if (answers[id] != saved[id]) Text("Unsaved changes", style = MaterialTheme.typography.labelSmall, color = colours.amber)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(shape = RoundedCornerShape(50), enabled = !busy && answers[id].orEmpty().length <= 100000, onClick = {
                                val answer = answers[id].orEmpty()
                                scope.launch {
                                    busy = true; error = ""
                                    try {
                                        val result = JSONObject(examRequest(base, token, "/exams/$examId/answers/$id", answer, revision = revisionStrings[id]?.toIntOrNull() ?: 0, scanRevision = scanRevisions[id]?.toIntOrNull() ?: 0))
                                        revisionStrings[id] = result.getInt("revision").toString()
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
                                        val result = JSONObject(examRequest(base, token, "/exams/$examId/answers/$id", answer, revision = revisionStrings[id]?.toIntOrNull() ?: 0, scanRevision = scanRevisions[id]?.toIntOrNull() ?: 0))
                                        revisionStrings[id] = result.getInt("revision").toString()
                                        saved[id] = answer
                                        feedback[id] = JSONObject(examRequest(base, token, "/exams/$examId/answers/$id/feedback", feedback = true))
                                        marks = runCatching { JSONObject(examRequest(base, token, "/exams/$examId/marks")) }.getOrNull()
                                        scheduleGrade = runCatching { JSONObject(examRequest(base, token, "/exams/$examId/schedule-grade")) }.getOrNull()
                                    } catch (e: CancellationException) { throw e } catch (e: Exception) {
                                        error = e.message ?: "Unable to get feedback"
                                    } finally { busy = false }
                                }
                            }) { Text("Save & mark") }
                        }
                        }
                    }
                    feedback[id]?.let { result ->
                        FeedbackCard(result)
                        ExamOverride(base, token, examId, id, result.optJSONObject("override"))
                    }
                    if (feedback[id] == null) {
                        TextButton(enabled = !busy && answers[id] == saved[id], onClick = {
                            scope.launch {
                                busy = true; error = ""
                                try {
                                    val stored = JSONObject(examRequest(base, token, "/exams/$examId/answers/$id/feedback"))
                                    val restored = savedExamFeedback(stored)
                                    feedback[id] = restored
                                } catch (e: CancellationException) { throw e }
                                catch (e: Exception) { error = e.message ?: "No saved feedback for this answer" }
                                finally { busy = false }
                            }
                        }) { Text("Load saved feedback") }
                    }
                }
            }
            if (page == questions.length() && answerMode == "handwritten") StudyCard(tone = CardTone.Container) {
                Text("Upload your answer pages", style = MaterialTheme.typography.titleLarge)
                Text("Select up to 10 photos in page order. Include question numbers and diagrams. Check each recognised answer before saving and marking. Maximum 10 MiB combined.")
                Button(enabled = !busy, onClick = { scanQuestion = null; scanPicker.launch(androidx.activity.result.PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }) { Text("Select photos from gallery") }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                TextButton(enabled = !busy && page > 0, onClick = { page-- }) { Text("Previous") }
                Button(enabled = !busy && page < questions.length() - if (answerMode == "handwritten") 0 else 1, onClick = { page++ }) { Text(if (answerMode == "handwritten" && page == questions.length() - 1) "Upload answers" else "Next question") }
            }
        }
    }
}

@Composable
private fun InlineExamDiagrams(base: String, token: String, resource: String, page: Int) {
    var regions by remember(resource, page) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var error by remember(resource, page) { mutableStateOf("") }
    LaunchedEffect(base, resource, page) {
        try {
            val result = JSONObject(examRequest(base, token, "/resources/$resource/pages/$page/diagrams")).getJSONArray("regions")
            regions = (0 until result.length()).map { result.getJSONObject(it) }
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = "Diagram extraction unavailable. Use the original paper link." }
    }
    regions.forEach { region ->
        val query = listOf("x0", "y0", "x1", "y1").joinToString("&") { "$it=${region.getDouble(it)}" }
        AuthorisedImage(base, token, "/resources/$resource/pages/$page/diagram-image?$query")
    }
    if (error.isNotEmpty()) Text(error, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
}

internal fun savedExamFeedback(stored: JSONObject): JSONObject {
    val marks = stored.getJSONArray("marks")
    val first = (0 until marks.length()).map { marks.getJSONObject(it) }.firstOrNull { it.optString("kind") == "first" }
        ?: throw IllegalStateException("No saved first mark for this answer")
    return JSONObject(first.toString()).apply {
        put("disclaimer", "Saved AI study feedback, not an official or verified grade. Check the original schedule.")
        val second = (0 until marks.length()).map { marks.getJSONObject(it) }.firstOrNull { it.optString("kind") == "second" }
        if (second != null) {
            put("second_review", second)
            put("disagreement", first.optBoolean("disagreement") || second.optInt("marks_awarded") != first.optInt("marks_awarded") || second.optString("outcome") != first.optString("outcome"))
        }
        if (!stored.isNull("override")) put("override", stored.getJSONObject("override"))
    }
}

@Composable
internal fun ExamOverride(base: String, token: String, examId: Long, questionId: Long, savedOverride: JSONObject?) = key(base, token, examId, questionId) {
    var outcome by rememberSaveable { mutableStateOf(savedOverride?.optString("outcome") ?: "uncertain") }
    var note by rememberSaveable { mutableStateOf(savedOverride?.optString("note").orEmpty()) }
    var savedOutcome by rememberSaveable { mutableStateOf(outcome) }
    var savedNote by rememberSaveable { mutableStateOf(note) }
    var expanded by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf("") }
    var loaded by remember(base, token, examId, questionId) { mutableStateOf(false) }
    var reload by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(base, token, examId, questionId, expanded, reload) {
        if (!expanded || loaded) return@LaunchedEffect
        try {
            val stored = JSONObject(examRequest(base, token, "/exams/$examId/answers/$questionId/override")).optJSONObject("override")
            val hasDraft = outcome != savedOutcome || note != savedNote
            savedOutcome = stored?.getString("outcome") ?: "uncertain"
            savedNote = stored?.getString("note").orEmpty()
            if (!hasDraft) { outcome = savedOutcome; note = savedNote }
            loaded = true; notice = ""
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { notice = e.message ?: "Could not load your saved judgement" }
    }
    TextButton(onClick = { expanded = !expanded }) { Text("Your judgement / override") }
    if (expanded) StudyCard(tone = CardTone.Low) {
        Text("Your judgement is saved separately. It does not change the AI mark or official-schedule result.", style = MaterialTheme.typography.bodySmall)
        Box {
            OutlinedButton(enabled = loaded && !saving, onClick = { menu = true }) { Text(outcome.replace('_', ' ')) }
            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                listOf("not_achieved", "achieved", "merit", "excellence", "uncertain").forEach { value ->
                    DropdownMenuItem(text = { Text(value.replace('_', ' ')) }, onClick = { outcome = value; menu = false; notice = "" })
                }
            }
        }
        if (!loaded) TextButton(onClick = { reload++ }) { Text("Load / retry saved judgement") }
        OutlinedTextField(note, { note = it; notice = "" }, enabled = loaded && !saving, label = { Text("Reason for your judgement") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
        TextButton(enabled = loaded && !saving && note.isNotBlank() && note.length <= 2000, onClick = {
            scope.launch {
                saving = true; notice = ""
                try {
                    withContext(Dispatchers.IO) {
                        val c = URL(base.trimEnd('/') + "/exams/$examId/answers/$questionId/override").openConnection() as HttpURLConnection
                        try {
                            c.connectTimeout = 10000; c.readTimeout = 20000; c.requestMethod = "PUT"; c.doOutput = true
                            c.setRequestProperty("Authorization", "Bearer $token"); c.setRequestProperty("Content-Type", "application/json")
                            c.outputStream.use { it.write(JSONObject().put("outcome", outcome).put("note", note).toString().toByteArray(Charsets.UTF_8)) }
                            val status = c.responseCode
                            check(status in 200..299) { "Override save failed ($status). Your note is retained." }
                        } finally { c.disconnect() }
                    }
                    savedOutcome = outcome; savedNote = note
                    notice = "Your judgement saved separately from the AI mark."
                } catch (e: CancellationException) { throw e }
                catch (e: Exception) { notice = e.message ?: "Could not save your judgement; your note is retained." }
                finally { saving = false }
            }
        }) { Text(if (saving) "Saving…" else "Save your judgement") }
        if (notice.isNotEmpty()) Text(notice, style = MaterialTheme.typography.bodySmall)
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
        result.optJSONObject("override")?.let { saved ->
            Text("Your saved judgement: ${saved.optString("outcome").replace('_', ' ')}", style = MaterialTheme.typography.labelMedium)
            Text(saved.optString("note"), style = MaterialTheme.typography.bodySmall)
        }
        MathText(result.optString("feedback"))
        result.optJSONObject("second_review")?.let { second ->
            val disagreement = result.optBoolean("disagreement") ||
                second.optInt("marks_awarded") != result.optInt("marks_awarded") ||
                second.optString("outcome") != result.optString("outcome")
            HorizontalDivider()
            Text(if (disagreement) "Markers disagree — check the original schedule" else "Second marker agrees on score and outcome",
                style = MaterialTheme.typography.titleSmall,
                color = if (disagreement) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
            Text("Second suggested mark: ${second.optInt("marks_awarded")} / ${second.optInt("marks_available")} · ${second.optString("outcome").replace('_', ' ')}", style = MaterialTheme.typography.labelMedium)
            MathText(second.optString("feedback"))
            Text("AI second review is advisory; different underlying providers are not verified.", style = MaterialTheme.typography.bodySmall)
        }
        val evidence = result.optJSONArray("evidence")
        if (evidence != null) for (j in 0 until evidence.length()) {
            val item = evidence.getJSONObject(j)
            Text("Schedule quotation:", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            MathText("“${item.optString("quote")}”")
            Text(item.optString("explanation"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("AI feedback is stored for this saved answer. Changes to the answer or scan require a new mark. Check the original schedule.", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
