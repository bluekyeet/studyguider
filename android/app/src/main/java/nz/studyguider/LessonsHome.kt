package nz.studyguider

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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

/**
 * The Lessons home: the courses the learner chose, each with its lessons in
 * order from basics to exam level. Creating a lesson is the floating button, so
 * it is never hidden in the navigation bar.
 */

private suspend fun api(base: String, token: String, path: String, body: JSONObject? = null, method: String = "GET"): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = if (method == "POST") 200000 else 20000
        connection.requestMethod = method
        connection.setRequestProperty("Authorization", "Bearer $token")
        if (body != null) {
            connection.setRequestProperty("Content-Type", "application/json")
            connection.doOutput = true
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException(friendly(status, text))
        text
    } finally { connection.disconnect() }
}

/** Turns a server error body into something a learner can act on. */
private fun friendly(status: Int, text: String): String {
    val detail = runCatching { JSONObject(text).optString("detail") }.getOrDefault("")
    return when {
        status == 422 && detail.contains("No matching extracted sources", true) ->
            "There are no readable resources for this topic yet. Add files in Resources, then try again."
        detail.isNotBlank() -> detail
        else -> "Request failed ($status)"
    }
}

data class Course(val id: Long, val topicId: Long, val topic: String, val subject: String, val lessonCount: Int)
data class LessonSummary(val id: Long, val title: String, val stage: Int, val createdAt: String)

@Composable
fun LessonsHome(
    base: String,
    token: String,
    onOpenCourse: (Long, String) -> Unit,
    onAddCourse: () -> Unit,
) {
    var courses by remember { mutableStateOf<List<Course>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf("") }
    var reload by remember { mutableIntStateOf(0) }
    val colours = LocalStudyColours.current

    LaunchedEffect(base, token, reload) {
        loading = true; error = ""
        try {
            val list = JSONArray(api(base, token, "/courses"))
            courses = (0 until list.length()).map {
                val c = list.getJSONObject(it)
                Course(c.getLong("id"), c.getLong("topic_id"), c.optString("topic"), c.optString("subject"), c.optInt("lesson_count"))
            }
        } catch (e: Exception) { error = e.message ?: "Could not load your courses" }
        finally { loading = false }
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 96.dp)) {
            Column(Modifier.padding(top = 16.dp, bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("YOUR LEARNING", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                Text("Keep going", style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.primary)
                Text("Each course starts from the basics and builds to exam standard.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            when {
                loading && courses.isEmpty() -> StudyCard(tone = CardTone.Low) {
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                    Text("Loading your courses…", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                error.isNotEmpty() && courses.isEmpty() -> StudyCard(tone = CardTone.Low) {
                    Text("Could not load your courses.", style = MaterialTheme.typography.titleSmall)
                    Text(error, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    OutlinedButton(onClick = { reload++ }, shape = RoundedCornerShape(50)) { Text("Try again") }
                }
                courses.isEmpty() -> StudyCard(tone = CardTone.Container) {
                    SectionLabel("No courses yet", "START HERE")
                    Text("Choose the topics you want to learn. Lessons for those topics appear here, starting from the basics.", style = MaterialTheme.typography.bodyMedium)
                    Button(onClick = onAddCourse, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 50.dp)) { Text("Choose topics") }
                }
                else -> Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
                    courses.forEach { course -> CourseBlock(base, token, course, onOpenCourse, colours) }
                    OutlinedButton(onClick = onAddCourse, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("+  Add another topic") }
                }
            }
        }
        // Create lesson: a floating action button, clear of the navigation bar.
        if (courses.isNotEmpty()) {
            ExtendedFloatingActionButton(
                onClick = { onOpenCourse(courses.first().topicId, courses.first().topic) },
                containerColor = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier.align(Alignment.BottomEnd).padding(end = 20.dp, bottom = 20.dp),
            ) {
                Text("+", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(8.dp))
                Text("New lesson", style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}

@Composable
private fun CourseBlock(
    base: String,
    token: String,
    course: Course,
    onOpenCourse: (Long, String) -> Unit,
    colours: StudyColours,
) {
    var lessons by remember(course.id) { mutableStateOf<List<LessonSummary>>(emptyList()) }
    var loading by remember(course.id) { mutableStateOf(true) }
    var error by remember(course.id) { mutableStateOf("") }
    var expanded by remember(course.id) { mutableStateOf(true) }

    LaunchedEffect(base, token, course.id) {
        loading = true
        try {
            val items = JSONArray(api(base, token, "/topics/${course.topicId}/lessons"))
            lessons = (0 until items.length()).map {
                val l = items.getJSONObject(it)
                LessonSummary(l.getLong("id"), l.optString("query"), l.optInt("stage", 1), l.optString("created_at"))
            }.sortedWith(compareBy({ it.stage }, { it.id }))
        } catch (e: Exception) { error = e.message ?: "Could not load lessons" }
        finally { loading = false }
    }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(course.subject.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                Text(course.topic, style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onSurface)
            }
            Text("${lessons.size} lesson(s)", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (loading) StudyCard(tone = CardTone.Low) { LinearProgressIndicator(Modifier.fillMaxWidth()) }
        else if (error.isNotEmpty()) StudyCard(tone = CardTone.Low) { Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        else if (lessons.isEmpty()) StudyCard(tone = CardTone.Low) {
            Text("No lessons yet for ${course.topic}.", style = MaterialTheme.typography.titleSmall)
            Text("Start with the basics — the first lesson covers the ideas you need before exam questions.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = { onOpenCourse(course.topicId, course.topic) }, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth()) { Text("Start the first lesson") }
        }
        else {
            lessons.forEachIndexed { index, lesson ->
                val isNext = index == lessons.size - 1
                Surface(
                    onClick = { onOpenCourse(course.topicId, course.topic) },
                    shape = RoundedCornerShape(14.dp),
                    color = if (isNext) colours.containerLow else colours.container,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Row(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        // A numbered spine makes the basics-to-exam order obvious.
                        Surface(shape = RoundedCornerShape(50), color = if (isNext) MaterialTheme.colorScheme.primary else colours.containerHigh) {
                            Box(Modifier.size(28.dp), contentAlignment = Alignment.Center) {
                                Text("${index + 1}", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold,
                                    color = if (isNext) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        Column(Modifier.weight(1f)) {
                            Text(lesson.title.ifBlank { "Lesson ${index + 1}" }, style = MaterialTheme.typography.titleSmall, maxLines = 2)
                            Text(if (index == 0) "Basics" else if (isNext) "Next up" else "Completed", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text("Open →", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }
    }
}
