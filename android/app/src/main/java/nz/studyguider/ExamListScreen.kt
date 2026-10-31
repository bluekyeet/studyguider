package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL

private data class ExamSummary(val id: Long, val createdAt: String, val questionCount: Int)

private suspend fun loadExamList(base: String, token: String): List<ExamSummary> = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + "/exams").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 20000
        connection.setRequestProperty("Authorization", "Bearer $token")
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)
            ?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        val data = JSONArray(text)
        List(data.length()) { index ->
            val exam = data.getJSONObject(index)
            ExamSummary(exam.getLong("id"), exam.getString("created_at"), exam.getInt("question_count"))
        }
    } finally { connection.disconnect() }
}

/** Displays exams for an authenticated session. The caller supplies scrolling. */
@Composable
fun ExamListScreen(base: String, token: String, onChooseExam: (Long) -> Unit) {
    var exams by remember(base, token) { mutableStateOf<List<ExamSummary>?>(null) }
    var error by remember(base, token) { mutableStateOf("") }
    var busy by remember(base, token) { mutableStateOf(true) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        busy = true; error = ""
        try { exams = loadExamList(base, token) }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Unable to load exams" }
        finally { busy = false }
    }

    LaunchedEffect(base, token) { load() }

    Column(Modifier.fillMaxWidth().padding(vertical = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Exams", style = MaterialTheme.typography.headlineMedium)
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        Button(enabled = !busy, onClick = { scope.launch { load() } }) { Text(if (exams == null && error.isNotEmpty()) "Retry" else "Refresh") }
        if (exams?.isEmpty() == true) Text("No exams yet.")
        exams?.forEach { exam ->
            key(exam.id) {
                HorizontalDivider()
                Text("Exam ${exam.id}", style = MaterialTheme.typography.titleMedium)
                Text("Created ${exam.createdAt} · ${exam.questionCount} ${if (exam.questionCount == 1) "question" else "questions"}")
                Button(onClick = { onChooseExam(exam.id) }) { Text("Choose exam ${exam.id}") }
            }
        }
    }
}
