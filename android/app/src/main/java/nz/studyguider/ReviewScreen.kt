package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
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

    val navy = Color(0xFF001F6B)
    val lavender = Color(0xFFF2F0FC)
    Column(Modifier.fillMaxWidth().padding(vertical = 20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Surface(color = lavender, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("DAILY REVIEW", color = navy, style = MaterialTheme.typography.labelMedium)
                Text("Due reviews", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
                OutlinedButton(enabled = !busy, onClick = { refresh() }) { Text("Refresh") }
            }
        }
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (loaded && questions.length() == 0) Text("No reviews due.")
        for (i in 0 until questions.length()) {
            val question = questions.getJSONObject(i)
            val id = question.getLong("id")
            key(id) {
                var answer by remember(base, token, id) { mutableStateOf("") }
                var confidence by remember(base, token, id) { mutableIntStateOf(3) }
                Surface(color = Color.White, shape = RoundedCornerShape(16.dp), tonalElevation = 1.dp, modifier = Modifier.fillMaxWidth()) {
                  Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Due ${question.getString("due_date")} · Topic ${question.getLong("topic_id")}", color = navy, style = MaterialTheme.typography.labelMedium)
                Text(question.getString("question"), style = MaterialTheme.typography.titleMedium)
                HorizontalDivider()
                Text("Your working", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                OutlinedTextField(answer, { answer = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Your answer") }, enabled = !busy, minLines = 3)
                Text("Self-assessment confidence: $confidence / 5", style = MaterialTheme.typography.labelLarge)
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    for (level in 1..5) {
                        if (level == confidence) {
                            Button(enabled = !busy, onClick = { confidence = level }, modifier = Modifier.weight(1f), colors = ButtonDefaults.buttonColors(containerColor = navy), contentPadding = PaddingValues(0.dp)) { Text("$level") }
                        } else {
                            OutlinedButton(enabled = !busy, onClick = { confidence = level }, modifier = Modifier.weight(1f), contentPadding = PaddingValues(0.dp)) { Text("$level") }
                        }
                    }
                }
                Button(modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = navy), enabled = !busy && answer.isNotBlank() && answer.length <= 50000, onClick = {
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
    }
}
