package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.ZoneId
import java.time.LocalDate

private suspend fun api(base: String, token: String, path: String, post: Boolean = false): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = if (post) 200000 else 20000
        connection.requestMethod = if (post) "POST" else "GET"
        connection.setRequestProperty("Authorization", "Bearer $token")
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrDefault("").ifBlank { "Request failed ($status)" })
        text
    } finally { connection.disconnect() }
}

/** Reads stage names only; the lesson arrives in the final event, after review. */
private suspend fun generateLesson(base: String, token: String, topicId: Long, requestKey: String, onStage: (String) -> Unit): JSONObject = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + "/topics/$topicId/lessons/automatic/stream").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 60000 // the server sends a keepalive every 15 seconds
        connection.requestMethod = "POST"
        connection.setRequestProperty("Authorization", "Bearer $token")
        // Retrying the same attempt returns the lesson already saved instead of making a second one.
        connection.setRequestProperty("Idempotency-Key", requestKey)
        val status = connection.responseCode
        if (status !in 200..299) {
            val text = connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
            throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrDefault("").ifBlank { "Request failed ($status)" })
        }
        connection.inputStream.bufferedReader(Charsets.UTF_8).use { reader ->
            while (true) {
                val line = reader.readLine() ?: break
                if (!line.startsWith("data:")) continue
                val event = JSONObject(line.substringAfter("data:").trim())
                if (event.has("error")) throw IllegalStateException(event.getString("error"))
                if (event.has("lesson")) return@withContext event.getJSONObject("lesson")
                event.optString("message").takeIf { it.isNotBlank() }?.let { withContext(Dispatchers.Main) { onStage(it) } }
            }
        }
        throw IllegalStateException("Lesson generation was interrupted. Check Lessons before trying again.")
    } finally { connection.disconnect() }
}

private class LessonsSnapshot(val token: String, val courses: List<JSONObject>, val lessons: List<JSONObject>)
private var lessonsCache: LessonsSnapshot? = null

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LessonsHome(base: String, token: String, onOpenLesson: (Long, String, Long) -> Unit) {
    // The last list appears at once and is refreshed quietly, so switching back to Lessons never starts from empty.
    val cached = lessonsCache?.takeIf { it.token == token }
    var courses by remember { mutableStateOf<List<JSONObject>>(cached?.courses ?: emptyList()) }
    var lessons by remember { mutableStateOf<List<JSONObject>>(cached?.lessons ?: emptyList()) }
    var loading by remember { mutableStateOf(cached == null) }
    var generating by remember { mutableStateOf(false) }
    var stage by remember { mutableStateOf("") }
    var picker by remember { mutableStateOf(false) }
    val attemptKeys = remember { mutableMapOf<Long, String>() }
    var error by remember { mutableStateOf("") }
    var reload by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(base, token, reload) {
        if (cached == null && lessons.isEmpty()) loading = true
        error = ""
        try {
            val c = JSONArray(api(base, token, "/courses"))
            val l = JSONArray(api(base, token, "/lessons"))
            courses = (0 until c.length()).map { c.getJSONObject(it) }
            lessons = (0 until l.length()).map { l.getJSONObject(it) }
            lessonsCache = LessonsSnapshot(token, courses, lessons)
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load lessons" }
        finally { loading = false }
    }
    fun date(item: JSONObject): LocalDate? = runCatching { Instant.parse(item.getString("created_at")).atZone(ZoneId.of("Pacific/Auckland")).toLocalDate() }.getOrNull()
    val today = LocalDate.now(ZoneId.of("Pacific/Auckland"))
    // Same rule as the website: today's lessons, plus the newest lesson nobody opened from an earlier day for each topic that
    // has none today. A lesson that was started but not finished is not carried; its topic gets a fresh lesson instead.
    val fresh = lessons.filter { date(it) == today }
    val carried = lessons.filter { it.isNull("completed_at") && !it.optBoolean("started") && date(it)?.isBefore(today) == true }
        .filter { lesson -> fresh.none { it.optLong("topic_id") == lesson.optLong("topic_id") } }
        .distinctBy { it.optLong("topic_id") }
    val toDo = fresh.filter { it.isNull("completed_at") } + carried
    val earlier = lessons.filter { it !in fresh && it !in carried }
    var showEarlier by remember { mutableStateOf(false) }
    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(top = 16.dp, bottom = 100.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (generating) { LinearProgressIndicator(Modifier.fillMaxWidth()); Text(stage.ifBlank { "Generating your lesson…" }) }
            else if (loading) DelayedLoading { Column { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("Loading lessons…") } }
            if (error.isNotEmpty()) { Text(error, color = MaterialTheme.colorScheme.error); OutlinedButton(onClick = { reload++ }) { Text("Try again") } }
            if (!loading && lessons.isEmpty() && error.isEmpty()) StudyCard(tone = CardTone.Low) {
                Text("No lessons available yet.", style = MaterialTheme.typography.titleMedium)
                Text(if (courses.isEmpty()) "Choose your topics in Settings to get started." else "Use New lesson to create one from your resources.")
            }
            if (toDo.isNotEmpty()) {
                Text("Today · ${toDo.size} to do", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                toDo.forEachIndexed { index, item ->
                    LessonRow(item, onOpenLesson, Modifier.staggeredEnter(index, item.optLong("id")),
                        note = if (item.optBoolean("started")) "In progress" else "To do")
                }
            }
            if (lessons.isNotEmpty() && toDo.isEmpty()) Text(if (fresh.isNotEmpty()) "All of today’s lessons are done. Well done." else "No lessons to do right now.")
            if (earlier.isNotEmpty()) {
                TextButton(onClick = { showEarlier = !showEarlier }) { Text(if (showEarlier) "Hide earlier lessons" else "Earlier lessons (${earlier.size})") }
                if (showEarlier) earlier.forEach { item -> LessonRow(item, onOpenLesson, note = if (item.isNull("completed_at")) "Not finished" else "Completed") }
            }
        }
        if (courses.isNotEmpty()) ExtendedFloatingActionButton(onClick = { picker = true }, modifier = Modifier.align(Alignment.BottomEnd).padding(20.dp), text = { Text("New lesson") }, icon = { Text("+") })
    }
    if (picker) ModalBottomSheet(onDismissRequest = { if (!generating) picker = false }) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Choose a topic", style = MaterialTheme.typography.headlineSmall)
            courses.forEach { course ->
                val id = course.getLong("topic_id")
                Button(enabled = !generating, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(50), onClick = {
                    picker = false
                    scope.launch {
                        generating = true; error = ""; stage = ""
                        try {
                            val key = attemptKeys.getOrPut(id) { "android-" + java.util.UUID.randomUUID() }
                            val lesson = generateLesson(base, token, id, key) { stage = it }
                            attemptKeys.remove(id)
                            onOpenLesson(id, course.optString("topic"), lesson.getLong("id"))
                        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not generate lesson" }
                        finally { generating = false }
                    }
                }) { Text("${course.optString("subject")} · ${course.optString("topic")}") }
            }
        }
    }
}

@Composable
private fun LessonRow(item: JSONObject, open: (Long, String, Long) -> Unit, modifier: Modifier = Modifier, note: String = "") {
    val source = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    Surface(onClick = { open(item.getLong("topic_id"), item.optString("topic"), item.getLong("id")) }, interactionSource = source, shape = RoundedCornerShape(14.dp), color = LocalStudyColours.current.container, modifier = modifier.fillMaxWidth().pressScale(source)) {
        Column(Modifier.padding(16.dp)) {
            Text("${item.optString("subject")} · ${item.optString("topic")}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
            Text(item.optString("query"), style = MaterialTheme.typography.titleMedium)
            val created = runCatching { Instant.parse(item.getString("created_at")).atZone(ZoneId.of("Pacific/Auckland")).toLocalDate().toString() }.getOrDefault("")
            Text(listOf(created, note).filter { it.isNotBlank() }.joinToString(" · "), style = MaterialTheme.typography.bodySmall)
        }
    }
}
