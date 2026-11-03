package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate

private suspend fun postReviewDraft(base: String, token: String, path: String, body: JSONObject): JSONObject = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 200000
        connection.requestMethod = "POST"
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        JSONObject(text)
    } finally { connection.disconnect() }
}

/** Generates unsaved questions for review before adding them to the queue. */
@Composable
fun ReviewDraftScreen(base: String, token: String, topicId: Long) {
    var query by remember(base, token, topicId) { mutableStateOf("") }
    val drafts = remember(base, token, topicId) { mutableStateListOf<String>() }
    var sources by remember(base, token, topicId) { mutableStateOf<List<String>>(emptyList()) }
    var error by remember(base, token, topicId) { mutableStateOf("") }
    var busy by remember(base, token, topicId) { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(Modifier.fillMaxWidth().padding(top = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        StudyCard(tone = CardTone.Container) {
            SectionLabel("New review questions", "AI DRAFTS")
            Text("Generating sends your query and up to five matching source excerpts to the configured AI education provider. AI-generated questions may contain errors; check the original sources. Drafts are not saved until approved.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            MathField(query, { query = it }, label = "Topic or search", enabled = !busy, supportingText = "1–200 characters")
            Button(enabled = !busy && drafts.isEmpty() && topicId > 0 && query.isNotBlank() && query.length <= 200, shape = RoundedCornerShape(50), onClick = {
                val submittedQuery = query.trim()
                scope.launch {
                    busy = true; error = ""
                    try {
                        val result = postReviewDraft(base, token, "/topics/$topicId/review-questions/generate", JSONObject().put("query", submittedQuery))
                        val questions = result.getJSONArray("questions")
                        val foundSources = result.getJSONArray("sources")
                        sources = (0 until foundSources.length()).map { index ->
                            val source = foundSources.getJSONObject(index)
                            "${source.getString("filename")} · page ${source.get("page")} · resource ${source.getString("resource_id").take(8)}…"
                        }
                        for (index in 0 until questions.length()) drafts.add(questions.getString(index))
                    } catch (e: Exception) { error = e.message ?: "Generation failed" } finally { busy = false }
                }
            }) { Text("Generate drafts") }
            if (busy) LoadingBar(Modifier.fillMaxWidth())
            if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }
        if (drafts.isNotEmpty()) {
            StudyCard(tone = CardTone.High) {
                Text("Check these sources before approving", style = MaterialTheme.typography.titleMedium)
                sources.forEach { Text("§ $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            // ponytail: drafts live only on this screen; add persistence when draft recovery is needed.
            drafts.forEachIndexed { index, question ->
                StudyCard(tone = CardTone.Container) {
                    Text("DRAFT ${index + 1}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                    MathText(question)
                    Button(enabled = !busy && question.isNotBlank() && question.length <= 5000, shape = RoundedCornerShape(50), onClick = {
                        scope.launch {
                            busy = true; error = ""
                            try {
                                postReviewDraft(base, token, "/topics/$topicId/review-questions", JSONObject().put("question", question.trim()).put("due_date", LocalDate.now().toString()))
                                drafts.removeAt(index)
                            } catch (e: Exception) { error = e.message ?: "Could not approve question" } finally { busy = false }
                        }
                    }) { Text("Approve into queue (due today)") }
                }
            }
            OutlinedButton(enabled = !busy, shape = RoundedCornerShape(50), onClick = { drafts.clear(); sources = emptyList() }) { Text("Discard remaining drafts") }
        }
    }
}
