package nz.studyguider

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.ZoneId

/** Sends photos of handwritten working to the server and returns the text it read from them. */
private suspend fun scanPhotos(base: String, token: String, questionId: Long, uris: List<Uri>, context: android.content.Context): String = withContext(Dispatchers.IO) {
    val boundary = "scan-${java.util.UUID.randomUUID()}"
    val connection = URL(base.trimEnd('/') + "/review-questions/$questionId/scan").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 200000
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        connection.outputStream.use {
            var total = 0
            uris.forEachIndexed { index, uri ->
                val bytes = context.contentResolver.openInputStream(uri)?.use { stream -> stream.readNBytes(10 * 1024 * 1024 + 1) } ?: throw IllegalStateException("Cannot open image")
                total += bytes.size
                if (total > 10 * 1024 * 1024) throw IllegalStateException("The photos are over 10 MiB in total. Use fewer or smaller photos.")
                it.write("--$boundary\r\nContent-Disposition: form-data; name=\"files\"; filename=\"page-${index + 1}.jpg\"\r\nContent-Type: application/octet-stream\r\n\r\n".toByteArray())
                it.write(bytes); it.write("\r\n".toByteArray())
            }
            it.write("--$boundary--\r\n".toByteArray())
        }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException(runCatching { JSONObject(text).getString("detail") }.getOrNull() ?: "Could not read the photo ($status)")
        JSONObject(text).getString("transcription")
    } finally { connection.disconnect() }
}

private val CONFIDENCE = listOf("Not confident", "Slightly", "Somewhat", "Confident", "Very confident")

/** What came back after an answer: verdict, feedback, when it returns, and whether it comes back this session. */
private class ReviewResult(val reply: JSONObject, val relearn: Boolean)

/**
 * Review: today's list from the planner (capped and ordered, server review_plan.py), answered one question at a time. A miss
 * comes back after three other questions in the same session until it is answered right once (successive relearning). The All
 * questions tab lists every saved question for practising ahead.
 */
@Composable
fun ReviewScreen(base: String, token: String, onNextQuestion: () -> Unit = {}) {
    val api = remember(base, token) { Api(base, token) }
    var today by remember { mutableStateOf(LocalDate.now(ZoneId.of("Pacific/Auckland")).toString()) }
    var plan by remember(base, token) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var leftOut by remember(base, token) { mutableIntStateOf(0) }
    var cap by remember(base, token) { mutableIntStateOf(0) }
    var all by remember(base, token) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var labels by remember(base, token) { mutableStateOf<Map<Long, String>>(emptyMap()) }
    var tab by rememberSaveable { mutableStateOf("due") }
    var practising by remember { mutableStateOf<JSONObject?>(null) }     // one question opened from All questions
    var loaded by remember(base, token) { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var reload by remember { mutableIntStateOf(0) }

    LaunchedEffect(base, token, reload) {
        busy = true; error = ""
        try {
            // The server's date wins, so its planner and this screen agree on what "today" is.
            today = runCatching { api.getObject("/dev/clock").optString("today") }.getOrNull()?.takeIf { it.isNotBlank() } ?: today
            // The due call also writes review questions for lessons completed since the last visit; the plan then gives today's list.
            val due = api.getArray("/review-questions/due?as_of=$today")
            val planned = runCatching { api.getObject("/review-plan?as_of=$today") }.getOrNull()
            plan = planned?.optJSONArray("items")?.objectList() ?: due.objectList()
            leftOut = planned?.optInt("left_out") ?: 0
            cap = planned?.optInt("cap") ?: 0
            all = api.getArray("/review-questions?limit=500").objectList()
            labels = runCatching {
                val found = mutableMapOf<Long, String>()
                for (subject in api.getArray("/subjects").objectList())
                    for (topic in api.getArray("/subjects/${subject.getLong("id")}/topics").objectList()) found[topic.getLong("id")] = "${subject.optString("name")} · ${topic.optString("name")}"
                found
            }.getOrDefault(emptyMap())
            loaded = true
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = (e.message ?: "Could not load reviews") + ". Any draft is kept. Refresh to try again." }
        finally { busy = false }
    }
    fun labelOf(q: JSONObject) = labels[q.optLong("topic_id")] ?: listOf(q.optString("subject"), q.optString("topic")).filter { it.isNotBlank() }.joinToString(" · ").ifBlank { "Topic ${q.optLong("topic_id")}" }

    Column(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        StudyCard(tone = CardTone.Container) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("SPACED REVIEW", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                    Text(if (loaded) if (plan.isEmpty()) "All caught up" else "${plan.size} for today" else "Loading…", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
                }
                OutlinedButton(enabled = !busy, onClick = { reload++ }, shape = RoundedCornerShape(50)) { Text("Refresh") }
            }
            Text("Short questions on what you have learned, scheduled to come back just before you forget.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (loaded) Row(Modifier.fillMaxWidth().height(IntrinsicSize.Max), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ReviewStat("${plan.size}", "Due now", Modifier.weight(1f).fillMaxHeight())
                ReviewStat("${all.count { it.optString("due_date") > today }}", "Coming up", Modifier.weight(1f).fillMaxHeight())
                ReviewStat("${all.size}", "All questions", Modifier.weight(1f).fillMaxHeight())
            }
            if (leftOut > 0) Text("$leftOut more are due, kept for another day so today stays manageable (daily limit $cap).", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = tab == "due" && practising == null, onClick = { tab = "due"; practising = null }, label = { Text("Due now (${plan.size})") })
            FilterChip(selected = tab == "all" || practising != null, onClick = { tab = "all"; practising = null }, label = { Text("All questions (${all.size})") })
        }
        if (busy) LoadingBar(Modifier.fillMaxWidth())
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        val single = practising
        when {
            single != null -> ReviewCard(api, base, token, single, labelOf(single), today, left = null,
                onDone = { reply ->
                    all = all.map { if (it.optLong("id") == single.optLong("id")) JSONObject(it.toString()).put("due_date", reply.optString("next_due")).put("answer_count", it.optInt("answer_count") + 1) else it }
                },
                onNext = { practising = null; tab = "all" }, nextLabel = "Back to all questions")
            tab == "due" -> {
                val question = plan.firstOrNull()
                if (loaded && question == null) StudyCard(tone = CardTone.Low) {
                    Text(if (leftOut > 0) "Today's reviews are done" else "Nothing is due", style = MaterialTheme.typography.titleMedium)
                    Text(if (leftOut > 0) "$leftOut more are due but were kept for another day so the load stays manageable." else "You are all caught up. New questions come from the lessons you complete.",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (all.isNotEmpty()) OutlinedButton(onClick = { tab = "all" }, shape = RoundedCornerShape(50)) { Text("Browse all questions") }
                }
                if (question != null) key(question.optLong("id"), question.optBoolean("relearning")) {
                    ReviewCard(api, base, token, question, labelOf(question), today, left = plan.size,
                        onDone = { reply ->
                            val id = question.optLong("id")
                            all = all.map { if (it.optLong("id") == id) JSONObject(it.toString()).put("due_date", reply.optString("next_due")).put("answer_count", it.optInt("answer_count") + 1) else it }
                        },
                        onNext = { relearn ->
                            // Successive relearning: a miss comes back after a few other questions, until it is answered right once.
                            val rest = plan.drop(1).toMutableList()
                            if (relearn) rest.add(minOf(3, rest.size), JSONObject(question.toString()).put("relearning", true))
                            plan = rest
                            onNextQuestion()        // the next question starts at the top, with its topic and the count left
                        },
                        nextLabel = if (plan.size <= 1) "Finish review" else "Next question")
                }
            }
            else -> AllQuestions(all, today, ::labelOf, onOpen = { practising = it })
        }
    }
}

@Composable
private fun ReviewStat(value: String, label: String, modifier: Modifier) {
    StudyCard(tone = CardTone.Low, modifier = modifier) {
        Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** One question: the earlier answers, the answer box with photo and hint, confidence, then the result once submitted. */
@Composable
private fun ReviewCard(api: Api, base: String, token: String, question: JSONObject, label: String, today: String, left: Int?,
                       onDone: (JSONObject) -> Unit, onNext: (Boolean) -> Unit, nextLabel: String) {
    val id = question.getLong("id")
    val context = LocalContext.current
    val drafts = remember { context.getSharedPreferences("review_drafts", android.content.Context.MODE_PRIVATE) }
    val draftKey = "$base:$id"
    val saved = remember(id) { drafts.getString(draftKey, null)?.let { runCatching { JSONObject(it) }.getOrNull() } }
    val forms = remember(id) { answerForms(question.opt("answer_forms")) }
    val box = rememberAnswerBox(api, "$id:${question.optBoolean("relearning")}", forms, if (question.optBoolean("relearning")) "" else saved?.optString("answer").orEmpty())
    var answer by remember(id) { mutableStateOf(box.value) }
    var confidence by remember(id) { mutableIntStateOf(if (question.optBoolean("relearning")) 0 else saved?.optInt("confidence") ?: 0) }
    var result by remember(id, question.optBoolean("relearning")) { mutableStateOf<ReviewResult?>(null) }
    var busy by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val due = question.optString("due_date") <= today

    // An unsent answer survives leaving the screen or the app closing.
    LaunchedEffect(answer, confidence) {
        if (result != null) return@LaunchedEffect
        if (answer.isBlank() && confidence == 0) drafts.edit().remove(draftKey).apply()
        else drafts.edit().putString(draftKey, JSONObject().put("answer", answer).put("confidence", confidence).toString()).apply()
    }
    fun readPhotos(uris: List<Uri>) {
        if (uris.isEmpty()) return
        scope.launch {
            busy = true; error = ""; notice = "Reading your handwriting. This can take a minute…"
            try {
                val text = scanPhotos(base, token, id, uris, context)
                box.setText(if (box.text.text.isBlank()) text else box.text.text.trimEnd() + "\n" + text)
                notice = "Read by AI from your photo and may contain mistakes. Check it, then submit your answer."
            } catch (e: CancellationException) { throw e } catch (e: Exception) { notice = ""; error = e.message ?: "Could not read the photo" } finally { busy = false }
        }
    }
    val gallery = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(10)) { uris -> readPhotos(uris) }
    var shot by remember(id) { mutableStateOf<Uri?>(null) }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { taken -> shot?.let { if (taken) readPhotos(listOf(it)) }; shot = null }

    StudyCard(tone = CardTone.Container) {
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
            StudyChip(label, MaterialTheme.colorScheme.onSecondaryContainer, MaterialTheme.colorScheme.secondaryContainer)
            if (question.optBoolean("relearning")) StudyChip("Missed earlier", MaterialTheme.colorScheme.onErrorContainer, MaterialTheme.colorScheme.errorContainer)
            else if (!due) StudyChip("Not due until ${question.optString("due_date")}", MaterialTheme.colorScheme.onSurfaceVariant, LocalStudyColours.current.containerHighest)
            if (left != null) Text("$left left", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        question.optString("concept").takeIf { it.isNotBlank() }?.let { MathText("**$it**", fontSize = 18) }
        QuestionWording(question.optString("question"), hideTables = hasTableToComplete(forms), formulaStyle = true)
        if (question.optInt("answer_count") > 0 || question.optInt("reps") > 0) EarlierAnswers(api, id)
        val current = result
        if (current == null) {
            AnswerBox(box, enabled = !busy, onChange = { answer = it })
            // Working done on paper can be photographed and read into the box; not needed when the answer is picked from options.
            if (!box.hasChoice) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(enabled = !busy, shape = RoundedCornerShape(50), onClick = {
                    val folder = File(context.cacheDir, "review-photos").apply { mkdirs() }
                    val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", File.createTempFile("review-$id-", ".jpg", folder))
                    shot = uri; camera.launch(uri)
                }) { Text("Take photo") }
                OutlinedButton(enabled = !busy, shape = RoundedCornerShape(50), onClick = { gallery.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }) { Text("Upload photos") }
            }
            HintButton(base, token, "review", id.toString(), answer = { answer })
            Text("How confident are you?", style = MaterialTheme.typography.labelLarge)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (level in 1..5) {
                    val chosen = level == confidence
                    Surface(onClick = { confidence = level }, enabled = !busy, shape = RoundedCornerShape(12.dp),
                        color = if (chosen) MaterialTheme.colorScheme.primary else LocalStudyColours.current.containerHighest, modifier = Modifier.weight(1f)) {
                        Column(Modifier.padding(vertical = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("$level", style = MaterialTheme.typography.titleMedium, color = if (chosen) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }
            }
            Text(if (confidence == 0) "1 is not confident, 5 is very confident." else CONFIDENCE[confidence - 1], style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (notice.isNotEmpty()) Text(notice, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (error.isNotEmpty()) Text(error, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            if (busy) LoadingBar(Modifier.fillMaxWidth())
            Button(modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), shape = RoundedCornerShape(50),
                enabled = !busy && answer.isNotBlank() && confidence > 0 && answer.length <= 50000, onClick = {
                scope.launch {
                    busy = true; error = ""; notice = "Saving and checking your answer…"
                    try {
                        box.flush()     // a drawing still uploading is part of the answer
                        val sent = box.value.trim()
                        if (sent.isBlank()) throw IllegalStateException("Please enter an answer.")
                        val reply = JSONObject(api.post("/review-questions/$id/answers", JSONObject().put("answer", sent).put("confidence", confidence)))
                        drafts.edit().remove(draftKey).apply()
                        result = ReviewResult(reply, reply.optBoolean("relearn"))
                        notice = ""
                        onDone(reply)
                    } catch (e: CancellationException) { throw e } catch (e: Exception) {
                        notice = ""
                        error = "${e.message ?: "Could not save your answer."} Your draft is kept. If the connection failed, the answer may already be saved; Refresh checks the list before you retry."
                    } finally { busy = false }
                }
            }) { Text("Submit answer") }
            if (confidence == 0 && answer.isNotBlank()) Text("Choose how confident you are to submit.", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else ReviewOutcome(api, current, forms, inSession = left != null, nextLabel = nextLabel, onNext = { onNext(current.relearn) })
    }
}

@Composable
private fun ReviewOutcome(api: Api, result: ReviewResult, forms: List<AnswerForm>?, inSession: Boolean, nextLabel: String, onNext: () -> Unit) {
    val colours = LocalStudyColours.current
    val reply = result.reply
    val (label, fg, bg) = when (reply.optString("outcome")) {
        "correct" -> Triple("Correct", colours.achieved, colours.achieved.copy(alpha = 0.14f))
        "incorrect" -> Triple("Not quite", MaterialTheme.colorScheme.onErrorContainer, MaterialTheme.colorScheme.errorContainer)
        else -> Triple("Not independently marked", MaterialTheme.colorScheme.onSurfaceVariant, colours.containerHighest)
    }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        StudyChip(label, fg, bg)
        Text(if (reply.optJSONObject("choice_result")?.optString("marked_by") == "answer-key") "Marked from the answer key" else "AI judgement, advisory only", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    if (reply.optString("outcome") == "confidence-based") Text("Scheduled using your confidence.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    reply.optJSONObject("choice_result")?.let { ChoiceResultView(api, it, forms?.filterIsInstance<AnswerForm.Choice>()?.firstOrNull()?.options?.map { o -> o.key }) }
    reply.optString("feedback").takeIf { it.isNotBlank() }?.let {
        Surface(shape = RoundedCornerShape(12.dp), color = colours.containerHigh, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("FEEDBACK · AI", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                MathText(it)
            }
        }
    }
    if (result.relearn && inSession) Text("You will get this one again in a few questions, after the answer above has had a moment to settle.", style = MaterialTheme.typography.bodySmall)
    if (reply.optBoolean("confident_miss")) Text("You were confident about this one. Misses like this are worth a careful look at the answer: they are often the easiest to fix.", style = MaterialTheme.typography.bodySmall)
    Text("Next review ${reply.optString("next_due").ifBlank { "not given" }}, planned from how well you recalled it${if (result.relearn) "" else " and when your assessments are"}.",
        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Button(onClick = onNext, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text(nextLabel) }
}

/** What was written before for this question, with the verdict and feedback, newest first. */
@Composable
private fun EarlierAnswers(api: Api, questionId: Long) {
    var rows by remember(questionId) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var open by remember(questionId) { mutableStateOf(false) }
    LaunchedEffect(questionId) { rows = runCatching { api.getArray("/review-questions/$questionId/answers").objectList() }.getOrDefault(emptyList()) }
    if (rows.isEmpty()) return
    TextButton(onClick = { open = !open }, contentPadding = PaddingValues(horizontal = 0.dp)) {
        Text(if (open) "Hide earlier answers" else "Your earlier answer${if (rows.size == 1) "" else "s"} (${rows.size})")
    }
    AnimatedVisibility(open) {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            rows.takeLast(3).reversed().forEach { row ->
                Surface(shape = RoundedCornerShape(12.dp), color = LocalStudyColours.current.containerLow, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        val outcome = when (row.optString("outcome")) { "correct" -> "Correct"; "incorrect" -> "Not quite"; else -> "Not independently marked" }
                        Text("${row.optString("answered_at").take(10)} · $outcome · confidence ${row.optInt("confidence")}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        AnswerContent(api, row.optString("answer"))
                        row.optString("feedback").takeIf { it.isNotBlank() }?.let { MathText(it, fontSize = 14) }
                    }
                }
            }
        }
    }
}

/** Every saved question, filtered by topic, status and words, to answer early or revisit. */
@Composable
private fun AllQuestions(all: List<JSONObject>, today: String, labelOf: (JSONObject) -> String, onOpen: (JSONObject) -> Unit) {
    var topic by rememberSaveable { mutableLongStateOf(0L) }
    var status by rememberSaveable { mutableStateOf("all") }
    var words by rememberSaveable { mutableStateOf("") }
    var topicMenu by remember { mutableStateOf(false) }
    val topics = remember(all) { all.map { it.optLong("topic_id") }.distinct().sortedBy { id -> labelOf(all.first { it.optLong("topic_id") == id }).lowercase() } }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Box {
            OutlinedButton(onClick = { topicMenu = true }, shape = RoundedCornerShape(50)) {
                Text(if (topic == 0L) "All topics" else all.firstOrNull { it.optLong("topic_id") == topic }?.let(labelOf) ?: "All topics", maxLines = 1)
            }
            DropdownMenu(expanded = topicMenu, onDismissRequest = { topicMenu = false }) {
                DropdownMenuItem(text = { Text("All topics") }, onClick = { topic = 0; topicMenu = false })
                topics.forEach { id -> DropdownMenuItem(text = { Text(labelOf(all.first { it.optLong("topic_id") == id })) }, onClick = { topic = id; topicMenu = false }) }
            }
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf("all" to "Any status", "due" to "Due now", "upcoming" to "Coming up", "new" to "Never answered").forEach { (key, label) ->
                FilterChip(selected = status == key, onClick = { status = key }, label = { Text(label) })
            }
        }
        OutlinedTextField(words, { words = it }, Modifier.fillMaxWidth(), singleLine = true, label = { Text("Search questions") }, shape = RoundedCornerShape(12.dp))
        val needle = words.trim().lowercase()
        val rows = all.filter { q ->
            val due = q.optString("due_date") <= today
            (topic == 0L || q.optLong("topic_id") == topic) &&
                (status == "all" || (status == "due" && due) || (status == "upcoming" && !due) || (status == "new" && q.optInt("answer_count") == 0)) &&
                (needle.isEmpty() || "${q.optString("question")} ${q.optString("concept")}".lowercase().contains(needle))
        }
        if (rows.isEmpty()) Text(if (all.isEmpty()) "No review questions yet. They are made when you complete a lesson or get an exam answer wrong." else "No questions match these filters.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Surface(shape = RoundedCornerShape(16.dp), color = LocalStudyColours.current.container) {
            Column {
                rows.take(200).forEachIndexed { index, q ->
                    if (index > 0) HorizontalDivider(Modifier.padding(horizontal = 14.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    val due = q.optString("due_date") <= today
                    Row(Modifier.fillMaxWidth().clickable { onOpen(q) }.padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            val snippet = splitAnswer(q.optString("question")).text.replace(Regex("\\s+"), " ").replace("$", "")
                            Text(q.optString("concept").ifBlank { snippet.take(80) }.replace("$", ""), style = MaterialTheme.typography.titleSmall, maxLines = 2)
                            if (q.optString("concept").isNotBlank()) Text(snippet, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
                            Text("${if (due) "Due now" else "Due ${q.optString("due_date")}"} · ${labelOf(q)} · ${if (q.optInt("answer_count") > 0) "answered ${q.optInt("answer_count")}×" else "not answered yet"}",
                                style = MaterialTheme.typography.labelSmall, color = if (due) LocalStudyColours.current.amber else MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text(if (due) "Answer" else "Practise", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }
    }
}
