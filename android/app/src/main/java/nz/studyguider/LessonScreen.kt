package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

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

/** Generates and saves an experimental lesson for the selected topic. */
@Composable
fun LessonScreen(base: String, token: String, topicId: Long) {
    var query by remember(base, token, topicId) { mutableStateOf("") }
    var result by remember(base, token, topicId) { mutableStateOf<JSONObject?>(null) }
    var error by remember(base, token, topicId) { mutableStateOf("") }
    var busy by remember(base, token, topicId) { mutableStateOf(false) }
    var history by remember(base, token, topicId) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var historyError by remember(base, token, topicId) { mutableStateOf("") }
    var historyLoading by remember(base, token, topicId) { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

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

    Column(Modifier.fillMaxWidth().padding(vertical = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Experimental lesson draft", style = MaterialTheme.typography.headlineMedium)
        Text("Generating sends your query, up to five matching source excerpts and linked standards to the configured education and education-reviewer model providers.")
        Text("This lesson is saved as a draft. AI review is not verification; check claims and citations against the original sources.", color = MaterialTheme.colorScheme.error)
        OutlinedTextField(query, { query = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Lesson topic or search") }, enabled = !busy, supportingText = { Text("1–200 characters") })
        Button(enabled = !busy && !historyLoading && query.isNotBlank() && query.length <= 200 && topicId > 0, onClick = {
            val submittedQuery = query.trim()
            scope.launch {
                busy = true; error = ""; result = null
                try {
                    val draft = requestLesson(base, token, topicId, submittedQuery)
                    result = draft
                    history = listOf(draft) + history
                }
                catch (e: Exception) { error = e.message ?: "Request failed" }
                finally { busy = false }
            }
        }) { Text("Generate lesson draft") }
        if (busy) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
            Text("Generating and reviewing the draft may take several minutes.")
        }
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        Text("Saved lessons", style = MaterialTheme.typography.titleLarge)
        // ponytail: The API defaults to the latest 50; add pagination when older drafts are needed.
        Text("Showing up to the 50 most recent saved lessons.")
        if (historyLoading) Text("Loading lesson history…")
        else if (historyError.isNotEmpty()) Text("Could not load lesson history: $historyError", color = MaterialTheme.colorScheme.error)
        else if (history.isEmpty()) Text("No saved lessons yet.")
        history.take(50).forEach { draft ->
            TextButton(onClick = { result = draft }, enabled = !busy) {
                Text("${draft.optString("query")} · ${draft.optString("created_at")}")
            }
        }
        result?.let { draft ->
            Text("Draft lesson", style = MaterialTheme.typography.titleLarge)
            Text(draft.optString("lesson"))
            Text("AI review", style = MaterialTheme.typography.titleLarge)
            Text(if (draft.isNull("review")) "Review unavailable" else draft.optString("review"))
            Text(draft.optString("warning"), color = MaterialTheme.colorScheme.error)
            Text("Sources", style = MaterialTheme.typography.titleLarge)
            val sources = draft.optJSONArray("sources")
            if (sources != null) for (i in 0 until sources.length()) {
                val source = sources.getJSONObject(i)
                Text("${source.optString("filename")} · Resource ${source.optString("resource_id")} · Page/slide/section ${source.optInt("page")}")
            }
        }
    }
}
