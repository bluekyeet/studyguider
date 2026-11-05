package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
        connection.readTimeout = 200000
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

    val colours = LocalStudyColours.current
    Column(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        StudyCard(tone = CardTone.Container) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("DAILY REVIEW", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                    Text(if (loaded) "${questions.length()} due today" else "Loading…", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
                }
                StudyChip(if (questions.length() == 0 && loaded) "All clear" else "${questions.length()} due",
                    if (questions.length() == 0 && loaded) MaterialTheme.colorScheme.onSecondaryContainer else MaterialTheme.colorScheme.onErrorContainer,
                    if (questions.length() == 0 && loaded) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.errorContainer)
            }
            Text("Answer from memory, then rate how confident you felt.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(enabled = !busy, onClick = { refresh() }, shape = RoundedCornerShape(50)) { Text("Refresh") }
            }
        }
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        if (busy) LoadingBar(Modifier.fillMaxWidth())
        if (loaded && questions.length() == 0 && !busy) StudyCard(tone = CardTone.Low) {
            Text("Nothing due right now", style = MaterialTheme.typography.titleMedium)
            Text("Generate review questions for a topic, or come back tomorrow.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        for (i in 0 until questions.length()) {
            val question = questions.getJSONObject(i)
            val id = question.getLong("id")
            key(id) {
                var answer by remember(base, token, id) { mutableStateOf("") }
                var confidence by remember(base, token, id) { mutableIntStateOf(3) }
                StudyCard(tone = CardTone.Container) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("DUE ${question.getString("due_date")}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                        Text(question.optString("topic").ifBlank { "Topic ${question.getLong("topic_id")}" }.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    MathText(question.getString("question"), formulaStyle = true)
                    TableAnswer(question.getString("question"), answer, { answer = it }, enabled = !busy)
                    MathField(answer, { answer = it }, label = "Your working", enabled = !busy, minLines = 3, maxLines = 10)
                    HintButton(base, token, "review", id.toString(), answer = { answer })
                    Text("How confident are you? $confidence / 5", style = MaterialTheme.typography.labelMedium)
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        for (level in 1..5) {
                            val selectedLevel = level <= confidence
                            Surface(
                                onClick = { confidence = level },
                                enabled = !busy,
                                shape = RoundedCornerShape(50),
                                color = if (selectedLevel) MaterialTheme.colorScheme.primary else colours.containerHighest,
                                modifier = Modifier.weight(1f),
                            ) {
                                Box(Modifier.padding(vertical = 10.dp), contentAlignment = Alignment.Center) {
                                    Text("$level", style = MaterialTheme.typography.labelLarge, color = if (selectedLevel) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                    }
                    Button(modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), shape = RoundedCornerShape(50), enabled = !busy && answer.isNotBlank() && answer.length <= 50000, onClick = {
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
