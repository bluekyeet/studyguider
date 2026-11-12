package nz.studyguider

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

// Exam revision: pick a topic and get a pack built from the mistakes you have made in it (rapid questions and their parts,
// marked exams and the daily review). A pack is a short re-teach plus questions per weak concept. Answers are marked straight
// away by the daily-review marking, and a wrong answer comes back through spaced repetition. All of it is AI-written and unofficial.

private fun JSONArray.items(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }
private fun JSONObject.str(key: String): String = if (isNull(key)) "" else optString(key)

@Composable
fun RevisionScreen(base: String, token: String) {
    var packId by rememberSaveable { mutableStateOf<Long?>(null) }
    AnimatedContent(targetState = packId, transitionSpec = { fadeIn(tween(220)) togetherWith fadeOut(tween(120)) }, label = "revision") { id ->
        if (id == null) RevisionTopics(base, token, onOpen = { packId = it }) else RevisionPack(base, token, id, onBack = { packId = null })
    }
}

@Composable
private fun RevisionTopics(base: String, token: String, onOpen: (Long) -> Unit) {
    var topics by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var packs by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var error by remember { mutableStateOf("") }
    var building by remember { mutableStateOf<Long?>(null) }
    var levelFilter by remember { mutableStateOf<Int?>(null) }
    var subjectFilter by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(base, token) {
        try {
            topics = JSONArray(rapidCall(base, token, "/revision/topics")).items().sortedWith(compareByDescending<JSONObject> { it.optInt("mistakes") }.thenBy { it.str("subject") }.thenBy { it.str("topic") })
            packs = JSONArray(rapidCall(base, token, "/revision/packs?limit=50")).items(); error = ""
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load" }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Exam revision", style = MaterialTheme.typography.headlineSmall)
        Text("Pick a topic. A revision pack is built from the mistakes you have made in it (rapid questions, marked exams and the daily review): a short re-teach and questions on each weak concept.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        // Level, then subject, narrow the list so many topics stay easy to scan.
        val levels = topics.map { it.optInt("level") }.distinct().sorted()
        val subjects = topics.filter { levelFilter == null || it.optInt("level") == levelFilter }.map { it.str("subject") }.distinct().sortedBy { it.lowercase() }
        if (topics.isNotEmpty()) {
            PickerMenu("All levels", levelFilter?.let { "NCEA Level $it" }, listOf<Pair<Int?, String>>(null to "All levels") + levels.map { it to "NCEA Level $it" }) { levelFilter = it; subjectFilter = null }
            PickerMenu("All subjects", subjectFilter?.takeIf { it in subjects }, listOf<Pair<String?, String>>(null to "All subjects") + subjects.map { it to it }) { subjectFilter = it }
        }
        val shown = topics.filter { (levelFilter == null || it.optInt("level") == levelFilter) && (subjectFilter == null || it.str("subject") == subjectFilter) }
        shown.forEachIndexed { index, t ->
            val topicId = t.getLong("topic_id")
            val latest = packs.firstOrNull { it.getLong("topic_id") == topicId }
            val mistakes = t.optInt("mistakes")
            Column(Modifier.fillMaxWidth().staggeredEnter(index, topicId).animateContentSize(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                HorizontalDivider()
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Column(Modifier.weight(1f)) {
                        Text(t.str("topic"), style = MaterialTheme.typography.titleMedium)
                        Text("Level ${t.optInt("level")} · ${t.str("subject")} · ${if (mistakes == 0) "no mistakes yet" else "$mistakes mistake${if (mistakes == 1) "" else "s"}"}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Button(enabled = mistakes > 0 && building == null, shape = RoundedCornerShape(50), onClick = {
                        building = topicId
                        scope.launch {
                            try { onOpen(JSONObject(rapidCall(base, token, "/revision/packs", "POST", JSONObject().put("topic_id", topicId))).getLong("id")) }
                            catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not start" }
                            building = null
                        }
                    }) { Text("Build pack") }
                }
                if (latest != null) {
                    val status = latest.str("status")
                    TextButton(onClick = { onOpen(latest.getLong("id")) }, contentPadding = PaddingValues(0.dp)) {
                        Text(when (status) { "ready" -> "Latest pack: ${latest.optInt("answered")} of ${latest.optInt("total")} answered"; "generating" -> "Latest pack is being built"; else -> "Latest pack could not be built" })
                    }
                }
            }
        }
    }
}

@Composable
private fun RevisionPack(base: String, token: String, id: Long, onBack: () -> Unit) {
    var pack by remember { mutableStateOf<JSONObject?>(null) }
    var error by remember { mutableStateOf("") }
    LaunchedEffect(base, token, id) {
        // Poll while it is being written; a ready or failed pack is fetched once.
        while (true) {
            try {
                val next = JSONObject(rapidCall(base, token, "/revision/packs/$id")); error = ""
                if (pack == null || next.str("status") != "ready" || pack?.str("status") != "ready") pack = next
                if (next.str("status") != "generating") break
            } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load" }
            delay(3000)
        }
    }
    val data = pack
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        TextButton(onClick = onBack, contentPadding = PaddingValues(0.dp)) { Text("← All topics") }
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        if (data == null) return@Column
        Text("${data.str("topic")} revision", style = MaterialTheme.typography.headlineSmall)
        when (data.str("status")) {
            "generating" -> Text("Reading your mistakes and writing questions. This takes about a minute; you can leave this screen and come back.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            "failed" -> Text(data.str("error").ifBlank { "The pack could not be built." }, color = MaterialTheme.colorScheme.error)
            else -> PackBody(base, token, data)
        }
    }
}

@Composable
private fun PackBody(base: String, token: String, data: JSONObject) {
    val sections = (data.optJSONArray("sections") ?: JSONArray()).items()
    val results = remember(data.getLong("id")) { mutableStateMapOf<Long, JSONObject>() }
    LaunchedEffect(data) {
        sections.flatMap { (it.optJSONArray("questions") ?: JSONArray()).items() }.forEach { q -> q.optJSONObject("result")?.let { results[q.getLong("id")] = it } }
    }
    val total = sections.sumOf { it.optJSONArray("questions")?.length() ?: 0 }
    Text("Built from ${data.optInt("mistake_count")} mistake${if (data.optInt("mistake_count") == 1) "" else "s"}. AI-written from your resources and your answers; unofficial, so check it against your resources.",
        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text("${results.size} of $total answered · ${results.values.count { it.optBoolean("correct") }} correct", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary)
    var basis by remember { mutableStateOf(false) }
    TextButton(onClick = { basis = !basis }, contentPadding = PaddingValues(0.dp)) { Text(if (basis) "Hide what it was built from" else "What it was built from") }
    if (basis) (data.optJSONArray("mistakes") ?: JSONArray()).items().forEach { m ->
        Text("• ${m.str("from")}${m.str("label").let { if (it.isEmpty()) "" else " $it" }}: ${m.str("question")}", style = MaterialTheme.typography.bodySmall)
    }
    sections.forEachIndexed { index, section ->
        Column(Modifier.fillMaxWidth().staggeredEnter(index, data.getLong("id")), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            HorizontalDivider()
            Text(section.str("concept"), style = MaterialTheme.typography.titleLarge)
            if (section.str("why").isNotEmpty()) Text(section.str("why"), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            MathText(section.str("teaching"))
            (section.optJSONArray("questions") ?: JSONArray()).items().forEachIndexed { n, q -> PackQuestion(base, token, data.getLong("id"), n + 1, q, results) }
        }
    }
}

@Composable
private fun PackQuestion(base: String, token: String, packId: Long, number: Int, q: JSONObject, results: MutableMap<Long, JSONObject>) {
    val qid = q.getLong("id")
    val saved = results[qid]
    var answer by remember(qid) { mutableStateOf(q.optJSONObject("result")?.str("your_answer").orEmpty()) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    StudyCard(modifier = Modifier.animateContentSize()) {
        Text("Question $number", style = MaterialTheme.typography.labelLarge)
        MathText(q.str("question"))
        TableAnswer(q.str("question"), answer, { answer = it }, enabled = !busy)
        MathField(answer, { answer = it }, label = "Your answer", enabled = !busy, minLines = 3, maxLines = 12)
        HintButton(base, token, "review", qid.toString(), answer = { answer })
        Button(enabled = !busy && answer.isNotBlank(), shape = RoundedCornerShape(50), onClick = {
            busy = true
            scope.launch {
                try {
                    rapidCall(base, token, "/review-questions/$qid/answers", "POST", JSONObject().put("answer", answer).put("confidence", 3))
                    // The pack view carries the marked result with the worked answer.
                    val latest = JSONObject(rapidCall(base, token, "/revision/packs/$packId"))
                    latest.optJSONArray("sections")?.items()?.flatMap { (it.optJSONArray("questions") ?: JSONArray()).items() }?.firstOrNull { it.getLong("id") == qid }?.optJSONObject("result")?.let { results[qid] = it }
                    error = ""
                } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not check" }
                busy = false
            }
        }) { Text(if (saved != null) "Try again" else "Check answer") }
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        if (saved != null) {
            val correct = saved.optBoolean("correct")
            Text(if (correct) "Correct · it will come back later to keep it fresh." else "Not quite · it comes back tomorrow.",
                color = if (correct) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelLarge)
            if (saved.str("feedback").isNotEmpty()) MathText(saved.str("feedback"))
            if (saved.str("expected_answer").isNotEmpty()) {
                var open by remember(qid) { mutableStateOf(false) }
                TextButton(onClick = { open = !open }, contentPadding = PaddingValues(0.dp)) { Text(if (open) "Hide worked answer" else "Worked answer") }
                if (open) MathText(saved.str("expected_answer"))
            }
        }
    }
}
