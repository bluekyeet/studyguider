package nz.studyguider

import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

private suspend fun homeGet(base: String, token: String, path: String): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 20000
        connection.setRequestProperty("Authorization", "Bearer $token")
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrDefault("").ifBlank { "Request failed ($status)" })
        text
    } finally { connection.disconnect() }
}

private fun JSONArray.objects(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }
private fun percent(value: Double) = "${Math.round(value * 100)}%"

/** Counts of saved records plus one labelled rough estimate; the same figures as the website Home. */
private class HomeSnapshot(val token: String, val summary: JSONObject, val todayCount: Int, val todo: List<Pair<JSONObject, Boolean>>)
private var homeCache: HomeSnapshot? = null

@Composable
fun HomeScreen(base: String, token: String, onOpenLesson: (Long, String, Long) -> Unit, onGoTo: (Int) -> Unit, onOpenRewards: () -> Unit = {}) {
    // What Home showed last time appears at once and is refreshed quietly, so switching back to it never starts from empty.
    val cached = homeCache?.takeIf { it.token == token }
    var summary by remember { mutableStateOf<JSONObject?>(cached?.summary) }
    var todo by remember { mutableStateOf<List<Pair<JSONObject, Boolean>>>(cached?.todo ?: emptyList()) } // lesson, started
    var todayCount by remember { mutableIntStateOf(cached?.todayCount ?: 0) }
    var loading by remember { mutableStateOf(cached == null) }
    var error by remember { mutableStateOf("") }
    var reload by remember { mutableIntStateOf(0) }
    LaunchedEffect(base, token, reload) {
        if (summary == null) loading = true
        error = ""
        try {
            val data = JSONObject(homeGet(base, token, "/study-summary"))
            val lessons = JSONArray(homeGet(base, token, "/lessons")).objects()
            val zone = ZoneId.of("Pacific/Auckland")
            val today = LocalDate.now(zone)
            val todays = lessons.filter { runCatching { Instant.parse(it.getString("created_at")).atZone(zone).toLocalDate() == today }.getOrDefault(false) }
            val open = todays.filter { it.isNull("completed_at") }
            // A saved reading position past the first section means the lesson was started, perhaps on another device.
            val started = open.map { lesson ->
                runCatching { JSONObject(homeGet(base, token, "/lessons/${lesson.getLong("id")}/progress")).optInt("section", 0) > 0 }.getOrDefault(false)
            }
            summary = data; todayCount = todays.size; todo = open.zip(started)
            homeCache = HomeSnapshot(token, data, todays.size, todo)
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load Home" }
        finally { loading = false }
    }
    val data = summary
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        if (loading) DelayedLoading { Column { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("Loading…") } }
        if (error.isNotEmpty()) { Text(error, color = MaterialTheme.colorScheme.error); OutlinedButton(onClick = { reload++ }) { Text("Try again") } }
        if (data == null) return@Column
        val reviews = data.getJSONObject("reviews")
        val topics = data.getJSONArray("topics").objects()
        val due = reviews.optInt("due")

        // Headline numbers
        val estimated = topics.count { !it.isNull("estimated_grade") }
        Row(Modifier.fillMaxWidth().height(IntrinsicSize.Max), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Stat((data.optDouble("overall_mastery") * 100).toFloat(), { "${Math.round(it)}%" }, "Overall mastery", Modifier.weight(1f).fillMaxHeight().staggeredEnter(0, data))
            Stat((todayCount - todo.size).toFloat(), { "${Math.round(it)}/$todayCount" }, "Lessons done today", Modifier.weight(1f).fillMaxHeight().staggeredEnter(1, data))
            Stat(due.toFloat(), { "${Math.round(it)}" }, "Reviews due", Modifier.weight(1f).fillMaxHeight().staggeredEnter(2, data))
        }

        // Lessons to do: a plain list, not cards
        Section("Lessons to do", Modifier.staggeredEnter(3, data)) {
            if (todo.isEmpty()) Text(if (todayCount > 0) "All of today’s lessons are done. Well done." else "No lessons were prepared today. A new one is made overnight for each topic you are learning.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            todo.forEachIndexed { index, (lesson, started) ->
                if (index > 0) HorizontalDivider()
                val source = remember { MutableInteractionSource() }
                Row(
                    Modifier.fillMaxWidth().pressScale(source, 0.985f)
                        .clickable(interactionSource = source, indication = LocalIndication.current) { onOpenLesson(lesson.getLong("topic_id"), lesson.optString("topic"), lesson.getLong("id")) }
                        .padding(vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("${lesson.optString("subject")} · ${lesson.optString("topic")}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                        Text(lesson.optString("query"), style = MaterialTheme.typography.bodyLarge)
                    }
                    Text(if (started) "Continue" else "Start", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
                }
            }
            if (due > 0) FilledTonalButton(onClick = { onGoTo(2) }, modifier = Modifier.padding(top = 4.dp)) { Text("Start $due review${if (due == 1) "" else "s"}") }
        }

        // Topics, progress and estimated grade
        Section("Topics", Modifier.staggeredEnter(4, data)) {
            if (topics.isEmpty()) Text("Choose topics in Settings to see them here.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            topics.forEachIndexed { index, topic ->
                if (index > 0) HorizontalDivider()
                val mastery = topic.optDouble("mastery")
                val fill = animatedFill(mastery.toFloat().coerceIn(0f, 1f))
                Column(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("${topic.optString("subject")} · ${topic.optString("topic")}", Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                        Text(percent(mastery), style = MaterialTheme.typography.bodyMedium)
                    }
                    LinearProgressIndicator(progress = { fill }, modifier = Modifier.fillMaxWidth())
                    val grade = if (topic.isNull("estimated_grade")) null else topic.getString("estimated_grade")
                    Text(
                        grade?.let { "Estimated: $it" } ?: "Needs ${5 - minOf(topic.optInt("review_answers"), 5)} more review answers for an estimate",
                        style = MaterialTheme.typography.labelMedium,
                        color = if (grade == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.secondary,
                    )
                }
            }
            if (topics.isNotEmpty()) Text("$estimated of ${topics.size} topics have an estimate. ${data.optString("estimate_rule")}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        // Weak concepts
        val weak = data.getJSONArray("weak_concepts").objects()
        Section("Weak concepts", Modifier.staggeredEnter(5, data)) {
            Text("Tomorrow’s lesson will revisit these.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (weak.isEmpty()) Text("None yet. These appear after review answers.", style = MaterialTheme.typography.bodyMedium)
            weak.forEach { Text("• ${it.optString("concept")} (${it.optString("topic")})", style = MaterialTheme.typography.bodyMedium) }
        }

        // Reviews
        Section("Reviews", Modifier.staggeredEnter(6, data)) {
            val answers = reviews.optJSONObject("answers_last_30_days") ?: JSONObject()
            val correct = answers.optInt("correct"); val incorrect = answers.optInt("incorrect")
            var total = 0; answers.keys().forEach { total += answers.optInt(it) }
            val other = total - correct - incorrect
            Text(if (total == 0) "No review answers yet." else "Last 30 days: $correct correct, $incorrect incorrect" + (if (other > 0) ", $other not independently marked." else "."))
            Text("$due due now, ${reviews.optInt("upcoming")} coming up, ${reviews.optInt("total")} in total.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        // Recent exams, with the unfinished one first as a way back in
        val exams = data.getJSONArray("exams").objects()
        Section("Recent exams", Modifier.staggeredEnter(7, data)) {
            Text("Marks are AI-marked practice, unofficial, and not an NZQA grade.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (exams.isEmpty()) Text("No exams yet.")
            exams.forEachIndexed { index, exam ->
                if (index > 0) HorizontalDivider()
                val kind = when (exam.optString("kind")) { "ai_practice" -> "AI practice (unofficial)"; "mixed" -> "Mixed practice"; else -> "Past paper" }
                val marked = exam.optInt("marked_questions")
                val questions = exam.optInt("questions")
                val result = if (marked > 0) "${exam.optDouble("marks_awarded").toInt()} / ${exam.optDouble("marks_available").toInt()} marks ($marked of $questions marked)"
                    else "${exam.optInt("answered")} of $questions answered, not marked"
                Column(Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
                    Text("$kind · ${exam.optString("created_at").take(10)}", style = MaterialTheme.typography.bodyMedium)
                    Text(result, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            val unfinished = exams.firstOrNull { it.optBoolean("unfinished") && it.optInt("answered") > 0 }
            if (unfinished != null) FilledTonalButton(onClick = { onGoTo(3) }) { Text("Resume exam (${unfinished.optInt("answered")} of ${unfinished.optInt("questions")} answered)") }
        }

        Section("Rewards", Modifier.staggeredEnter(5, data)) {
            Text("Earn points for correct work, then spend them on collectables for your character.", style = MaterialTheme.typography.bodyMedium)
            FilledTonalButton(onClick = onOpenRewards) { Text("Open Rewards") }
        }
    }
}

@Composable
private fun Stat(target: Float, format: (Float) -> String, label: String, modifier: Modifier) {
    val shown = animatedCount(target)
    StudyCard(modifier = modifier, tone = CardTone.Low) {
        Text(format(shown), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun Section(title: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        content()
    }
}
