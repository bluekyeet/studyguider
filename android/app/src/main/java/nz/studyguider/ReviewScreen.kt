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
import java.time.LocalDate

private suspend fun reviewRequest(base: String, path: String, token: String, body: JSONObject? = null): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 20000
        connection.setRequestProperty("Authorization", "Bearer $token")
        if (body != null) {
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.doOutput = true
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        text
    } finally { connection.disconnect() }
}

/** Displays due reviews for the authenticated server session. */
@Composable
fun ReviewScreen(base: String, token: String) {
    var questions by remember(base, token) { mutableStateOf(JSONArray()) }
    var error by remember(base, token) { mutableStateOf("") }
    var busy by remember(base, token) { mutableStateOf(false) }
    var loaded by remember(base, token) { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        questions = JSONArray(reviewRequest(base, "/review-questions/due?as_of=${LocalDate.now()}", token))
        loaded = true
    }
    fun refresh() {
        scope.launch {
            busy = true; error = ""
            try { load() } catch (e: Exception) { error = e.message ?: "Request failed" } finally { busy = false }
        }
    }
    LaunchedEffect(base, token) {
        busy = true; error = ""
        try { load() } catch (e: Exception) { error = e.message ?: "Request failed" } finally { busy = false }
    }

    Column(Modifier.fillMaxWidth().padding(vertical = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Due reviews", style = MaterialTheme.typography.headlineMedium)
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        Button(enabled = !busy, onClick = { refresh() }) { Text("Refresh") }
        if (loaded && questions.length() == 0) Text("No reviews due.")
        for (i in 0 until questions.length()) {
            val question = questions.getJSONObject(i)
            val id = question.getLong("id")
            key(id) {
                var answer by remember(base, token, id) { mutableStateOf("") }
                var confidence by remember(base, token, id) { mutableIntStateOf(3) }
                Text(question.getString("question"), style = MaterialTheme.typography.titleMedium)
                Text("Due ${question.getString("due_date")} · Topic ${question.getLong("topic_id")}")
                OutlinedTextField(answer, { answer = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Your answer") }, enabled = !busy)
                Text("Confidence: $confidence / 5")
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    for (level in 1..5) {
                        if (level == confidence) {
                            Button(enabled = !busy, onClick = { confidence = level }, contentPadding = PaddingValues(horizontal = 8.dp)) { Text("$level") }
                        } else {
                            OutlinedButton(enabled = !busy, onClick = { confidence = level }, contentPadding = PaddingValues(horizontal = 8.dp)) { Text("$level") }
                        }
                    }
                }
                Button(enabled = !busy && answer.isNotBlank() && answer.length <= 50000, onClick = {
                    scope.launch {
                        busy = true; error = ""
                        try {
                            reviewRequest(base, "/review-questions/$id/answers", token, JSONObject().put("answer", answer.trim()).put("confidence", confidence))
                            // Remove the submitted question immediately, even if a later refresh fails.
                            val remaining = JSONArray()
                            for (index in 0 until questions.length()) {
                                val item = questions.getJSONObject(index)
                                if (item.getLong("id") != id) remaining.put(item)
                            }
                            questions = remaining
                        } catch (e: Exception) { error = e.message ?: "Request failed" } finally { busy = false }
                    }
                }) { Text("Submit answer") }
            }
        }
    }
}
