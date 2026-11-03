package nz.studyguider

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

// Rapid exam questions and the Exam revision list.
// A rapid session is one-way: questions flash up, you answer or skip and move on, and you see nothing about
// how you are doing until you end the session. The server enforces that; this screen never asks for results early.

private suspend fun rapidCall(base: String, token: String, path: String, method: String = "GET", body: JSONObject? = null): String = withContext(Dispatchers.IO) {
    val c = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        c.connectTimeout = 10000; c.readTimeout = 60000
        c.requestMethod = method
        c.setRequestProperty("Authorization", "Bearer $token")
        if (body != null) {
            c.doOutput = true; c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val status = c.responseCode
        val text = (if (status in 200..299) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrDefault("").ifBlank { "Request failed ($status)" })
        text
    } finally { c.disconnect() }
}

private fun JSONArray.objects(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }
private fun JSONObject.text(key: String): String = if (isNull(key)) "" else optString(key)
private fun plural(n: Int, word: String) = "$n $word${if (n == 1) "" else "s"}"
private fun minutes(seconds: Int) = if (seconds >= 90) "${Math.round(seconds / 60f)} min" else "$seconds s"

/** Misses waiting in Exam revision, shown on its chip. */
suspend fun fetchRevisionCount(base: String, token: String): Int =
    JSONObject(rapidCall(base, token, "/exam-revision/summary")).optInt("total")

private val gradeNames = mapOf("not_achieved" to "Not achieved", "achieved" to "Achieved", "merit" to "Merit", "excellence" to "Excellence")

@Composable
private fun GradeChip(outcome: String?) {
    val colours = MaterialTheme.colorScheme
    val (background, foreground) = when (outcome) {
        "not_achieved" -> colours.errorContainer to colours.onErrorContainer
        "achieved" -> colours.primaryContainer to colours.onPrimaryContainer
        "merit" -> colours.secondaryContainer to colours.onSecondaryContainer
        "excellence" -> colours.tertiaryContainer to colours.onTertiaryContainer
        else -> colours.surfaceVariant to colours.onSurfaceVariant
    }
    Surface(shape = RoundedCornerShape(50), color = background) {
        Text(gradeNames[outcome] ?: "Unclear", Modifier.padding(horizontal = 10.dp, vertical = 3.dp), color = foreground, style = MaterialTheme.typography.labelMedium)
    }
}

private fun sourceLine(q: JSONObject) =
    if (q.optString("source") == "ai") "AI-written question · unofficial" else "Past paper · AS ${q.optInt("standard_number")} · ${q.text("year")}"

private fun displayLabel(label: String): String = when {
    label.isEmpty() || label == "context" -> ""
    label.startsWith("(") -> label
    else -> "(" + label.replace("(", ")(") + (if (label.endsWith(")")) "" else ")")
}

private fun reflow(text: String) = text.replace(Regex("[ \\t]*\\n(?!\\s*\\n)(?!\\s*(?:Source|\\([a-hivx]+\\)))", RegexOption.IGNORE_CASE), " ").trim()

/** The question as the learner reads it: labelled parts with the paper's figures under them. */
@Composable
private fun QuestionView(base: String, token: String, q: JSONObject) {
    val parts = (q.optJSONArray("parts") ?: JSONArray()).objects().filter { it.has("text") }
    val paper = q.text("paper_resource_id")
    val shown = remember(q.optInt("question_id")) { mutableSetOf<String>() }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (parts.isEmpty()) MathText(reflow(q.text("question_text").ifBlank { "Question text unavailable." }))
        parts.forEach { part ->
            val label = displayLabel(part.text("label"))
            var text = part.text("text")
            var heading = ""
            if (label.isNotEmpty()) text = text.replace(Regex("^\\s*\\([a-hivx]+\\)\\s*", RegexOption.IGNORE_CASE), "")
            else Regex("^\\s*QUESTION\\s+(?:ONE|TWO|THREE|\\d+)\\s*:?\\s*([^\\n]*)\\n?([\\s\\S]*)$", RegexOption.IGNORE_CASE).find(text)?.let { heading = it.groupValues[1].trim(); text = it.groupValues[2] }
            if (text.isBlank() && heading.isBlank()) return@forEach
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                if (label.isNotEmpty()) Text(label, color = MaterialTheme.colorScheme.secondary, fontFamily = FontFamily.Monospace, fontSize = 13.sp, modifier = Modifier.width(44.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (heading.isNotEmpty()) Text(heading, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    if (text.isNotBlank()) MathText(reflow(text))
                    val diagrams = part.optJSONArray("diagrams") ?: JSONArray()
                    if (paper.isNotEmpty()) (0 until diagrams.length()).map { diagrams.getJSONObject(it) }.forEach { diagram ->
                        val box = diagram.optJSONArray("bbox")
                        if (box != null && box.length() == 4 && shown.add("${diagram.optInt("page")}:$box")) {
                            val query = listOf("x0", "y0", "x1", "y1").mapIndexed { n, name -> "$name=${box.getDouble(n)}" }.joinToString("&")
                            AuthorisedImage(base, token, "/resources/$paper/pages/${diagram.getInt("page")}/diagram-image?$query")
                        }
                    }
                }
            }
        }
    }
}

/** What you were asked, what you wrote and what the marker said. Shared by results and revision. */
@Composable
private fun ReviewBody(base: String, token: String, item: JSONObject, answer: String, feedback: String) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        QuestionView(base, token, item)
        Text("Your answer", style = MaterialTheme.typography.titleSmall)
        if (answer.isBlank()) Text("You skipped this question.", color = MaterialTheme.colorScheme.onSurfaceVariant) else MathText(answer)
        if (feedback.isNotBlank()) StudyCard(tone = CardTone.Low) {
            Text("AI generated · verify with sources", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
            MathText(feedback)
            val evidence = item.optJSONArray("evidence") ?: JSONArray()
            (0 until evidence.length()).map { evidence.getJSONObject(it) }.forEach {
                Text("“${it.optString("quote")}”", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                MathText("${it.optInt("marks")} marks: ${it.optString("explanation")}")
            }
            val missing = item.optJSONArray("missing") ?: JSONArray()
            if (missing.length() > 0) { Text("Missing evidence / next steps", style = MaterialTheme.typography.titleSmall); (0 until missing.length()).forEach { MathText(missing.getString(it)) } }
        }
        if (item.optBoolean("second_review_disagrees")) Text("A second marker disagreed. Check the original schedule; marks are advisory.", style = MaterialTheme.typography.bodySmall)
        val schedule = item.text("schedule_text")
        if (schedule.isNotBlank()) {
            var open by remember { mutableStateOf(false) }
            TextButton(onClick = { open = !open }) { Text(if (open) "Hide ${if (item.optString("source") == "ai") "rubric" else "schedule excerpt"}" else if (item.optString("source") == "ai") "Show AI-written rubric (unofficial)" else "Show schedule excerpt") }
            if (open) {
                if (item.optString("source") != "ai") Text("Extracted text; table layout is lost. Check the original schedule page.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(schedule, fontFamily = FontFamily.Monospace, fontSize = 12.sp, modifier = Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp)).padding(10.dp))
            }
        }
        Text(item.text("rubric_type"), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

private sealed interface RapidPhase {
    data object Loading : RapidPhase
    data object Setup : RapidPhase
    data class Resume(val active: JSONObject) : RapidPhase
    data class Play(val id: Long, val target: Int?, val question: JSONObject, val answered: Int) : RapidPhase
    data class Results(val id: Long, val note: String) : RapidPhase
}

/** [startWith] is a session just started from Exam revision (its id, target_count and first question). */
@Composable
fun RapidScreen(base: String, token: String, startWith: JSONObject?, onStartedWith: () -> Unit) {
    var phase by remember { mutableStateOf<RapidPhase>(RapidPhase.Loading) }
    var error by remember { mutableStateOf("") }
    LaunchedEffect(base, token, startWith) {
        try {
            if (startWith != null) {
                phase = RapidPhase.Play(startWith.getLong("id"), if (startWith.isNull("target_count")) null else startWith.getInt("target_count"), startWith.getJSONObject("question"), 0)
                onStartedWith()
                return@LaunchedEffect
            }
            val active = JSONObject(rapidCall(base, token, "/rapid/active")).optJSONObject("active")
            phase = if (active != null) RapidPhase.Resume(active) else RapidPhase.Setup
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load"; phase = RapidPhase.Setup }
    }
    Column(Modifier.fillMaxSize()) {
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
        when (val current = phase) {
            RapidPhase.Loading -> Spacer(Modifier.fillMaxSize())
            RapidPhase.Setup -> RapidSetup(base, token) { id, target, question -> error = ""; phase = RapidPhase.Play(id, target, question, 0) }
            is RapidPhase.Resume -> {
                val active = current.active
                val scope = rememberCoroutineScope()
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    StudyCard {
                        Text("You have a session in progress", style = MaterialTheme.typography.titleMedium)
                        Text("${active.optString("topic")} · ${plural(active.optInt("answered"), "question")} answered so far.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        val question = active.optJSONObject("question")
                        Button(onClick = {
                            if (question != null) phase = RapidPhase.Play(active.getLong("id"), if (active.isNull("target_count")) null else active.getInt("target_count"), question, active.optInt("answered"))
                            else scope.launch { runCatching { rapidCall(base, token, "/rapid/${active.getLong("id")}/end", "POST", JSONObject()) }; phase = RapidPhase.Results(active.getLong("id"), "") }
                        }) { Text("Continue session") }
                        OutlinedButton(onClick = {
                            scope.launch {
                                try { rapidCall(base, token, "/rapid/${active.getLong("id")}/end", "POST", JSONObject()); phase = RapidPhase.Results(active.getLong("id"), "") }
                                catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not end the session" }
                            }
                        }) { Text("End it and see results") }
                    }
                }
            }
            is RapidPhase.Play -> RapidPlayer(base, token, current, onEnd = { id, note -> phase = RapidPhase.Results(id, note) })
            is RapidPhase.Results -> RapidResults(base, token, current.id, current.note, onNew = { phase = RapidPhase.Setup })
        }
    }
}

@Composable
private fun RapidSetup(base: String, token: String, onStarted: (Long, Int?, JSONObject) -> Unit) {
    var topics by remember { mutableStateOf<List<Pair<Long, String>>>(emptyList()) }
    var topic by remember { mutableLongStateOf(0L) }
    var source by remember { mutableStateOf("mix") }
    var length by remember { mutableStateOf<Int?>(10) }
    var history by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var results by remember { mutableStateOf<Long?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    LaunchedEffect(base, token) {
        try {
            val found = mutableListOf<Pair<Long, String>>()
            JSONArray(rapidCall(base, token, "/subjects")).objects().forEach { subject ->
                JSONArray(rapidCall(base, token, "/subjects/${subject.getLong("id")}/topics")).objects().forEach { found += it.getLong("id") to "${subject.optString("name")} · ${it.optString("name")}" }
            }
            topics = found; if (topic == 0L && found.isNotEmpty()) topic = found.first().first
            history = JSONArray(rapidCall(base, token, "/rapid")).objects()
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load topics" }
    }
    if (results != null) { RapidResults(base, token, results!!, "", onNew = { results = null }); return }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        StudyCard {
            Text("Start a rapid session", style = MaterialTheme.typography.titleMedium)
            Text("Questions flash up one after another and you cannot go back. You will not see any marks or feedback until you end the session; answers are marked quietly as you go. AI-written questions are unofficial practice.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("Topic", style = MaterialTheme.typography.titleSmall)
        topics.forEachIndexed { index, (id, label) ->
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).clickable { topic = id }.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = topic == id, onClick = { topic = id })
                Text(label, style = MaterialTheme.typography.bodyLarge)
            }
        }
        Text("Questions from", style = MaterialTheme.typography.titleSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("mix" to "Mix", "past" to "Past papers", "ai" to "AI").forEach { (value, label) -> FilterChip(selected = source == value, onClick = { source = value }, label = { Text(label) }) }
        }
        Text("Session length", style = MaterialTheme.typography.titleSmall)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf<Int?>(10, 20, 30, 50, null).forEach { value -> FilterChip(selected = length == value, onClick = { length = value }, label = { Text(value?.toString() ?: "Unlimited") }) }
        }
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        Button(enabled = !busy && topic != 0L, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(50), onClick = {
            scope.launch {
                busy = true; error = ""
                try {
                    val body = JSONObject().put("topic_id", topic).put("source", source).put("count", length ?: JSONObject.NULL)
                    val session = JSONObject(rapidCall(base, token, "/rapid", "POST", body))
                    onStarted(session.getLong("id"), if (session.isNull("target_count")) null else session.getInt("target_count"), session.getJSONObject("question"))
                } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not start the session" }
                finally { busy = false }
            }
        }) { Text("Start session") }
        if (history.isNotEmpty()) {
            Text("Earlier sessions", style = MaterialTheme.typography.titleSmall)
            history.forEach { session ->
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).clickable { results = session.getLong("id") }.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(session.optString("topic"), style = MaterialTheme.typography.bodyLarge)
                        Text("${session.optString("ended_at").take(10)} · ${plural(session.optInt("answered"), "answer")}, ${session.optInt("skipped")} skipped", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Text("Results", color = MaterialTheme.colorScheme.primary)
                }
            }
        }
    }
}

@Composable
private fun RapidPlayer(base: String, token: String, start: RapidPhase.Play, onEnd: (Long, String) -> Unit) {
    var question by remember(start) { mutableStateOf(start.question) }
    var answer by remember(start.id, question.optLong("question_id")) { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var confirmEnd by remember { mutableStateOf(false) }
    val startedAt = remember(question.optLong("question_id")) { System.currentTimeMillis() }
    val scope = rememberCoroutineScope()
    val position = question.optInt("position")

    fun move(skip: Boolean) {
        if (busy) return
        scope.launch {
            busy = true; error = ""
            try {
                val body = JSONObject().put("question_id", question.getLong("question_id")).put("answer", if (skip) "" else answer)
                    .put("seconds", ((System.currentTimeMillis() - startedAt) / 1000).toInt()).put("skip", skip)
                val reply = JSONObject(rapidCall(base, token, "/rapid/${start.id}/next", "POST", body))
                val next = reply.optJSONObject("question")
                if (next != null) question = next
                else {
                    rapidCall(base, token, "/rapid/${start.id}/end", "POST", JSONObject())
                    onEnd(start.id, if (reply.optBoolean("finished")) "You reached the end of your session." else "You have used every question available for this topic.")
                }
            } catch (e: CancellationException) { throw e } catch (e: Exception) { error = "${e.message ?: "Could not continue"} Your answer is kept; press Next to try again." }
            finally { busy = false }
        }
    }

    Column(Modifier.fillMaxSize()) {
    Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Rapid session · no going back · results appear when you end it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        // The whole card slides in from the side whenever the next question arrives.
        Column(Modifier.sectionTransition(position), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            StudyCard {
                Text("Question $position${start.target?.let { " of $it" } ?: ""}", style = MaterialTheme.typography.titleLarge)
                Text(sourceLine(question), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                QuestionView(base, token, question)
            }
            MathField(answer, { answer = it }, label = "Your answer", enabled = !busy, minLines = 5, maxLines = 16)
        }
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    }
    // The controls stay in reach however long the question is.
    Surface(color = MaterialTheme.colorScheme.surface, tonalElevation = 2.dp) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Button(enabled = !busy, shape = RoundedCornerShape(50), onClick = { move(false) }) { Text("Next") }
            OutlinedButton(enabled = !busy, shape = RoundedCornerShape(50), onClick = { move(true) }) { Text("Skip") }
            Spacer(Modifier.weight(1f))
            TextButton(enabled = !busy, onClick = { confirmEnd = true }) { Text("End session") }
        }
    }
    }
    if (confirmEnd) AlertDialog(
        onDismissRequest = { confirmEnd = false },
        title = { Text("End the session?") },
        text = { Text("Your results appear straight away. A question you have not touched is not counted.") },
        confirmButton = { TextButton(onClick = {
            confirmEnd = false
            scope.launch {
                busy = true; error = ""
                try {
                    val body = JSONObject().put("question_id", question.getLong("question_id")).put("answer", answer).put("seconds", ((System.currentTimeMillis() - startedAt) / 1000).toInt())
                    rapidCall(base, token, "/rapid/${start.id}/end", "POST", body)
                    onEnd(start.id, "")
                } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not end the session"; busy = false }
            }
        }) { Text("End session") } },
        dismissButton = { TextButton(onClick = { confirmEnd = false }) { Text("Keep going") } },
    )
}

@Composable
private fun GradeTile(count: Int, label: String, modifier: Modifier) {
    val shown = animatedCount(count.toFloat())
    StudyCard(modifier = modifier, tone = CardTone.Low) {
        Text("${Math.round(shown)}", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun RapidResults(base: String, token: String, id: Long, note: String, onNew: () -> Unit) {
    var data by remember(id) { mutableStateOf<JSONObject?>(null) }
    var error by remember(id) { mutableStateOf("") }
    var retry by remember(id) { mutableIntStateOf(0) }
    val open = remember(id) { mutableStateListOf<Long>() }
    val scope = rememberCoroutineScope()
    LaunchedEffect(id, retry) {
        // Grades arrive as marking finishes; keep looking until nothing is pending.
        while (true) {
            try {
                val latest = JSONObject(rapidCall(base, token, "/rapid/$id/results"))
                data = latest; error = ""
                if (latest.optInt("pending") == 0) break
            } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load results"; break }
            delay(2500)
        }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("Session results", style = MaterialTheme.typography.headlineSmall)
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        val result = data ?: return@Column
        val b = result.getJSONObject("breakdown")
        Text("${result.optString("topic")} · ${plural(result.optInt("answered"), "question")} answered, ${b.optInt("skipped")} skipped · ${minutes(result.optInt("seconds"))} in total", color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (note.isNotEmpty()) Text(note, style = MaterialTheme.typography.bodySmall)
        if (result.optInt("pending") > 0) Text("Marking is finishing: ${plural(result.optInt("pending"), "answer")} still being marked. Grades appear below as they arrive.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        // Grade breakdown
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            GradeTile(b.optInt("not_achieved"), "Not achieved", Modifier.weight(1f))
            GradeTile(b.optInt("achieved"), "Achieved", Modifier.weight(1f))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            GradeTile(b.optInt("merit"), "Merit", Modifier.weight(1f))
            GradeTile(b.optInt("excellence"), "Excellence", Modifier.weight(1f))
        }
        if (b.optInt("skipped") > 0 || b.optInt("unclear") > 0 || b.optInt("failed") > 0) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (b.optInt("skipped") > 0) GradeTile(b.optInt("skipped"), "Skipped", Modifier.weight(1f))
            if (b.optInt("unclear") > 0) GradeTile(b.optInt("unclear"), "Unclear", Modifier.weight(1f))
            if (b.optInt("failed") > 0) GradeTile(b.optInt("failed"), "Could not mark", Modifier.weight(1f))
        }
        val total = listOf("not_achieved", "skipped", "achieved", "merit", "excellence", "unclear").sumOf { b.optInt(it) }
        if (total > 0) Row(Modifier.fillMaxWidth().height(12.dp).clip(RoundedCornerShape(50)), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
            val colours = MaterialTheme.colorScheme
            listOf("not_achieved" to colours.error, "skipped" to colours.outline, "achieved" to colours.primary, "merit" to colours.secondary, "excellence" to colours.tertiary, "unclear" to colours.outlineVariant).forEach { (key, colour) ->
                val n = b.optInt(key)
                if (n > 0) Box(Modifier.weight(n.toFloat()).fillMaxHeight().background(colour))
            }
        }
        if (b.optInt("failed") > 0) OutlinedButton(onClick = { scope.launch { runCatching { rapidCall(base, token, "/rapid/$id/remark", "POST", JSONObject()) }; retry++ } }) { Text("Try marking again") }
        val missed = b.optInt("not_achieved") + b.optInt("skipped")
        if (missed > 0) Text("${plural(result.optInt("revision_added"), "missed question")} added to Exam revision and sent to your lessons, so your next lessons revisit them.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        else if (result.optInt("pending") == 0) Text("No misses in this session.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Button(onClick = onNew, shape = RoundedCornerShape(50)) { Text("New session") }
        Text("Question by question", style = MaterialTheme.typography.titleMedium)
        Text(result.optString("notice"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        result.getJSONArray("items").objects().forEachIndexed { index, item ->
            val qid = item.getLong("question_id")
            val expanded = qid in open
            StudyCard(modifier = Modifier.staggeredEnter(index, id).animateContentSize()) {
                Row(Modifier.fillMaxWidth().clickable { if (expanded) open.remove(qid) else open.add(qid) }, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Question ${item.optInt("position")}", style = MaterialTheme.typography.titleSmall)
                    when (item.optString("status")) {
                        "pending" -> Text("Marking…", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelMedium)
                        "failed" -> Text("Could not mark", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelMedium)
                        "skipped" -> Text("Skipped", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelMedium)
                        else -> GradeChip(item.text("outcome"))
                    }
                    Spacer(Modifier.weight(1f))
                    Text(if (expanded) "Hide" else "View", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
                }
                Text(sourceLine(item), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (expanded) ReviewBody(base, token, item, item.text("answer"), item.text("feedback"))
            }
        }
    }
}

/** Questions missed or skipped in rapid sessions. Redo starts a session of just those. */
@Composable
fun RevisionScreen(base: String, token: String, onRedo: (JSONObject) -> Unit) {
    var summary by remember { mutableStateOf<JSONObject?>(null) }
    var items by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var topic by remember { mutableStateOf<Long?>(null) }
    var cleared by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    val open = remember { mutableStateListOf<Long>() }
    val scope = rememberCoroutineScope()
    LaunchedEffect(base, token) {
        try { summary = JSONObject(rapidCall(base, token, "/exam-revision/summary")) } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load" }
    }
    LaunchedEffect(base, token, topic, cleared) {
        try {
            val query = (topic?.let { "topic_id=$it&" } ?: "") + "include_resolved=$cleared"
            items = JSONArray(rapidCall(base, token, "/exam-revision?$query")).objects(); error = ""
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load" }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Exam revision", style = MaterialTheme.typography.headlineSmall)
        Text("Questions you have missed or skipped in rapid sessions. Look at the schedule, then redo them; a question clears when you next get it Achieved or better. Misses also feed your next lessons.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        val topics = summary?.optJSONArray("topics")?.objects().orEmpty()
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = topic == null, onClick = { topic = null }, label = { Text("All (${summary?.optInt("total") ?: 0})") })
            topics.forEach { t -> FilterChip(selected = topic == t.getLong("topic_id"), onClick = { topic = t.getLong("topic_id") }, label = { Text("${t.optString("topic")} (${t.optInt("outstanding")})") }) }
        }
        Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(checked = cleared, onCheckedChange = { cleared = it }); Text("Show cleared") }
        if (items.isEmpty() && error.isEmpty()) Text(if ((summary?.optInt("total") ?: 0) == 0) "Nothing to revise. Questions you miss in rapid sessions will appear here." else "Nothing in this view.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        items.groupBy { it.getLong("topic_id") }.forEach { (topicId, group) ->
            Text("${group.first().optString("subject")} · ${group.first().optString("topic")}", style = MaterialTheme.typography.titleMedium)
            val outstanding = group.count { it.isNull("resolved_at") }
            if (outstanding > 0) Button(shape = RoundedCornerShape(50), onClick = {
                scope.launch {
                    try { onRedo(JSONObject(rapidCall(base, token, "/rapid", "POST", JSONObject().put("topic_id", topicId).put("source", "revision").put("count", JSONObject.NULL)))) }
                    catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not start" }
                }
            }) { Text("Redo ${plural(outstanding, "question")}") }
            group.forEachIndexed { index, item ->
                val qid = item.getLong("question_id")
                val expanded = qid in open
                StudyCard(modifier = Modifier.staggeredEnter(index, topicId).animateContentSize()) {
                    Row(Modifier.fillMaxWidth().clickable { if (expanded) open.remove(qid) else open.add(qid) }, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(if (item.isNull("resolved_at")) "Tried ${item.optInt("attempts")}×" else "Cleared", style = MaterialTheme.typography.labelMedium, color = if (item.isNull("resolved_at")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.tertiary)
                        Text(item.text("question_text").replace(Regex("\\s+"), " ").take(70), Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, maxLines = 2)
                        Text(if (expanded) "Hide" else "View", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
                    }
                    Text(sourceLine(item), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (expanded) ReviewBody(base, token, item, item.text("your_answer"), item.text("feedback"))
                }
            }
        }
    }
}
