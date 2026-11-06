package nz.studyguider

import android.net.Uri
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
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

/** Sends photos of handwritten working to the server and returns the text it read from them. */
private suspend fun scanPhotos(base: String, token: String, questionId: Long, uris: List<Uri>, context: android.content.Context): String = withContext(Dispatchers.IO) {
    val boundary = "scan-${java.util.UUID.randomUUID()}"
    val connection = URL(base.trimEnd('/') + "/review-questions/$questionId/scan").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 200000
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        connection.outputStream.use {
            var total = 0
            uris.forEachIndexed { index, uri ->
                val bytes = context.contentResolver.openInputStream(uri)?.use { stream -> stream.readNBytes(10 * 1024 * 1024 + 1) } ?: throw IllegalStateException("Cannot open image")
                total += bytes.size
                if (total > 10 * 1024 * 1024) throw IllegalStateException("The photos are over 10 MiB in total. Use fewer or smaller photos.")
                it.write("--$boundary\r\nContent-Disposition: form-data; name=\"files\"; filename=\"page-${index + 1}.jpg\"\r\nContent-Type: application/octet-stream\r\n\r\n".toByteArray())
                it.write(bytes); it.write("\r\n".toByteArray())
            }
            it.write("--$boundary--\r\n".toByteArray())
        }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException(runCatching { JSONObject(text).getString("detail") }.getOrNull() ?: "Could not read the photo ($status)")
        JSONObject(text).getString("transcription")
    } finally { connection.disconnect() }
}

/** Displays due reviews for the authenticated server session. */
@Composable
fun ReviewScreen(base: String, token: String) {
    var questions by remember(base, token) { mutableStateOf(JSONArray()) }
    var error by remember(base, token) { mutableStateOf("") }
    var busy by remember(base, token) { mutableStateOf(false) }
    var loaded by remember(base, token) { mutableStateOf(false) }
    var notice by remember(base, token) { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

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
        if (notice.isNotEmpty()) Text(notice, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
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
                // Working done on paper: photos are read into the answer box, to be checked before submitting.
                fun readPhotos(uris: List<Uri>) {
                    if (uris.isEmpty()) return
                    scope.launch {
                        busy = true; error = ""; notice = "Reading your handwriting. This can take a minute…"
                        try {
                            val text = scanPhotos(base, token, id, uris, context)
                            answer = if (answer.isBlank()) text else answer.trimEnd() + "\n" + text
                            notice = "Read by AI from your photo and may contain mistakes. Check it, then submit your answer."
                        } catch (e: Exception) { notice = ""; error = e.message ?: "Could not read the photo" } finally { busy = false }
                    }
                }
                val gallery = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(10)) { uris -> readPhotos(uris) }
                var shot by remember(id) { mutableStateOf<Uri?>(null) }
                val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { taken -> shot?.let { if (taken) readPhotos(listOf(it)) }; shot = null }
                StudyCard(tone = CardTone.Container) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("DUE ${question.getString("due_date")}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                        Text(question.optString("topic").ifBlank { "Topic ${question.getLong("topic_id")}" }.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    MathText(question.getString("question"), formulaStyle = true)
                    TableAnswer(question.getString("question"), answer, { answer = it }, enabled = !busy)
                    MathField(answer, { answer = it }, label = "Your working", enabled = !busy, minLines = 3, maxLines = 10)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(enabled = !busy, shape = RoundedCornerShape(50), onClick = {
                            val folder = File(context.cacheDir, "review-photos").apply { mkdirs() }
                            val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", File.createTempFile("review-$id-", ".jpg", folder))
                            shot = uri; camera.launch(uri)
                        }) { Text("Take photo") }
                        OutlinedButton(enabled = !busy, shape = RoundedCornerShape(50), onClick = { gallery.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }) { Text("Upload photos") }
                    }
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
