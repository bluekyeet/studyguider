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
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

private suspend fun examRequest(base: String, token: String, path: String, answer: String? = null, feedback: Boolean = false): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 20000
        connection.setRequestProperty("Authorization", "Bearer $token")
        if (answer != null || feedback) {
            connection.requestMethod = if (feedback) "POST" else "PUT"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.doOutput = true
            connection.outputStream.use { it.write((if (feedback) JSONObject() else JSONObject().put("answer", answer)).toString().toByteArray(Charsets.UTF_8)) }
        }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)
            ?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Request failed ($status): $text")
        text
    } finally { connection.disconnect() }
}

/** Displays an existing exam. The caller supplies scrolling and an authenticated server session. */
@Composable
fun ExamScreen(base: String, token: String, examId: Long) {
    var exam by remember(base, token, examId) { mutableStateOf<JSONObject?>(null) }
    var error by remember(base, token, examId) { mutableStateOf("") }
    var busy by remember(base, token, examId) { mutableStateOf(false) }
    val answers = remember(base, token, examId) { mutableStateMapOf<Long, String>() }
    val saved = remember(base, token, examId) { mutableStateMapOf<Long, String>() }
    val feedback = remember(base, token, examId) { mutableStateMapOf<Long, JSONObject>() }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        val result = JSONObject(examRequest(base, token, "/exams/$examId"))
        val questions = result.getJSONArray("questions")
        answers.clear()
        saved.clear()
        feedback.clear()
        for (i in 0 until questions.length()) {
            val question = questions.getJSONObject(i)
            val id = question.getLong("id")
            val answer = if (question.isNull("answer")) "" else question.getString("answer")
            answers[id] = answer
            saved[id] = answer
        }
        exam = result
    }

    LaunchedEffect(base, token, examId) {
        busy = true
        error = ""
        try { load() } catch (e: CancellationException) { throw e } catch (e: Exception) {
            error = e.message ?: "Unable to load exam"
        } finally { busy = false }
    }

    Column(Modifier.fillMaxWidth().padding(vertical = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Exam $examId", style = MaterialTheme.typography.headlineMedium)
        Text("Questions and marking schedules are not included here. Consult the original paper and schedule using the references below. Feedback is experimental AI-generated study feedback, not an official or verified grade.")
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (exam == null && !busy) {
            Button(onClick = {
                scope.launch {
                    busy = true; error = ""
                    try { load() } catch (e: CancellationException) { throw e } catch (e: Exception) {
                        error = e.message ?: "Unable to load exam"
                    } finally { busy = false }
                }
            }) { Text("Retry") }
        }
        exam?.let { data ->
            val questions = data.getJSONArray("questions")
            if (questions.length() == 0) Text("This exam has no questions.")
            for (i in 0 until questions.length()) {
                val question = questions.getJSONObject(i)
                val id = question.getLong("id")
                key(id) {
                    HorizontalDivider()
                    Text("${question.getInt("position")}. Question ${question.getString("question_number")}", style = MaterialTheme.typography.titleMedium)
                    Text("Standard ${question.getInt("standard_number")} · ${question.getInt("year")} · Topic ${question.getLong("topic_id")}")
                    Text("Paper resource ${question.getString("paper_resource_id")}, page ${question.getInt("paper_page")}")
                    Text("Schedule resource ${question.getString("schedule_resource_id")}, page ${question.getInt("schedule_page")}")
                    OutlinedTextField(answers[id].orEmpty(), { answers[id] = it; feedback.remove(id) }, modifier = Modifier.fillMaxWidth(), label = { Text("Your answer") }, enabled = !busy, supportingText = { Text("Maximum 100,000 characters") })
                    if (answers[id] != saved[id]) Text("Unsaved changes")
                    Button(enabled = !busy && answers[id].orEmpty().length <= 100000, onClick = {
                        val answer = answers[id].orEmpty()
                        scope.launch {
                            busy = true; error = ""
                            try {
                                examRequest(base, token, "/exams/$examId/answers/$id", answer)
                                saved[id] = answer
                            } catch (e: CancellationException) { throw e } catch (e: Exception) {
                                error = e.message ?: "Unable to save answer"
                            } finally { busy = false }
                        }
                    }) { Text("Save answer") }
                    Button(enabled = !busy && answers[id].orEmpty().isNotBlank() && answers[id].orEmpty().length <= 100000, onClick = {
                        val answer = answers[id].orEmpty()
                        scope.launch {
                            busy = true; error = ""; feedback.remove(id)
                            try {
                                examRequest(base, token, "/exams/$examId/answers/$id", answer)
                                saved[id] = answer
                                feedback[id] = JSONObject(examRequest(base, token, "/exams/$examId/answers/$id/feedback", feedback = true))
                            } catch (e: CancellationException) { throw e } catch (e: Exception) {
                                error = e.message ?: "Unable to get feedback"
                            } finally { busy = false }
                        }
                    }) { Text("Save and get experimental feedback") }
                    feedback[id]?.let { result ->
                        Text(result.getString("disclaimer"))
                        Text("AI suggestion (not a grade): ${result.getString("outcome").replace('_', ' ')}")
                        Text(result.getString("feedback"))
                        val evidence = result.getJSONArray("evidence")
                        for (j in 0 until evidence.length()) {
                            val item = evidence.getJSONObject(j)
                            Text("Schedule quotation: “${item.getString("quote")}”")
                            Text(item.getString("explanation"))
                        }
                        Text("Feedback is not saved. Check the original schedule using the reference above.")
                    }
                }
            }
        }
    }
}
