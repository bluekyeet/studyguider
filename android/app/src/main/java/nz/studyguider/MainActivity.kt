package nz.studyguider

import android.os.Bundle
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.graphics.Color
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(primary = Color(0xFF355C4D), secondary = Color(0xFF816044), surface = Color(0xFFFAF9F4), background = Color(0xFFFAF9F4))) {
                Surface(Modifier.fillMaxSize()) { StudyApp() }
            }
        }
    }
}

private suspend fun request(base: String, path: String, token: String = "", body: JSONObject? = null): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = 20000
        if (token.isNotEmpty()) connection.setRequestProperty("Authorization", "Bearer $token")
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

private suspend fun upload(context: android.content.Context, base: String, token: String, topic: Long, uri: Uri) = withContext(Dispatchers.IO) {
    val name = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use {
        if (!it.moveToFirst()) throw IllegalStateException("Cannot read file details")
        val sizeIndex = it.getColumnIndex(OpenableColumns.SIZE)
        if (sizeIndex >= 0 && !it.isNull(sizeIndex) && it.getLong(sizeIndex) > 50L * 1024 * 1024) throw IllegalStateException("File exceeds 50 MiB")
        it.getString(it.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME))
    } ?: throw IllegalStateException("Cannot read file details")
    val bytes = context.contentResolver.openInputStream(uri)?.use { stream ->
        val buffer = java.io.ByteArrayOutputStream()
        val chunk = ByteArray(65536)
        while (true) {
            val count = stream.read(chunk)
            if (count < 0) break
            if (buffer.size() + count > 50 * 1024 * 1024) throw IllegalStateException("File exceeds 50 MiB")
            buffer.write(chunk, 0, count)
        }
        buffer.toByteArray()
    } ?: throw IllegalStateException("Cannot open file")
    val boundary = "studyguider-" + java.util.UUID.randomUUID()
    val safeName = name.replace("\"", "_").replace("\r", "_").replace("\n", "_")
    val prefix = "--$boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"$safeName\"\r\nContent-Type: application/octet-stream\r\n\r\n".toByteArray(Charsets.UTF_8)
    val suffix = "\r\n--$boundary--\r\n".toByteArray()
    val connection = URL(base.trimEnd('/') + "/topics/$topic/resources").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000; connection.readTimeout = 30000
        connection.requestMethod = "POST"; connection.doOutput = true
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        connection.setFixedLengthStreamingMode(prefix.size + bytes.size + suffix.size)
        connection.outputStream.use { it.write(prefix); it.write(bytes); it.write(suffix) }
        val status = connection.responseCode
        if (status !in 200..299) throw IllegalStateException("Upload failed ($status): " + connection.errorStream?.bufferedReader()?.use { it.readText() })
    } finally { connection.disconnect() }
}

@Composable
private fun StudyApp() {
    var base by remember { mutableStateOf("https://") }
    var password by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }
    var subjects by remember { mutableStateOf(JSONArray()) }
    var topics by remember { mutableStateOf(JSONArray()) }
    var selected by remember { mutableStateOf(0L) }
    var selectedTopic by remember { mutableStateOf(0L) }
    var resources by remember { mutableStateOf(JSONArray()) }
    var resourceRefreshError by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var subjectName by remember { mutableStateOf("") }
    var subjectLevel by remember { mutableStateOf("2") }
    var topicName by remember { mutableStateOf("") }
    var examId by remember { mutableStateOf("") }
    var examDirty by remember { mutableStateOf(false) }
    var pendingTab by remember { mutableStateOf<Int?>(null) }
    var confirmExamExit by remember { mutableStateOf(false) }
    var tab by remember { mutableIntStateOf(0) }
    var subjectTitle by remember { mutableStateOf("") }
    var topicTitle by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val processing = (0 until resources.length()).any { resources.getJSONObject(it).optString("status") in setOf("pending", "extracting") }
    LaunchedEffect(selectedTopic, token, base, tab, processing) {
        if (selectedTopic != 0L && token.isNotEmpty() && tab == 0 && processing) {
            while (true) {
                delay(5000)
                try {
                    resources = JSONArray(request(base, "/topics/$selectedTopic/resources", token))
                    resourceRefreshError = ""
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    resourceRefreshError = "Resource refresh failed: ${e.message ?: "Request failed"}"
                }
            }
        }
    }
    fun run(block: suspend () -> Unit) {
        scope.launch { busy = true; error = ""; try { block() } catch (e: Exception) { error = e.message ?: "Request failed" } finally { busy = false } }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null && selectedTopic != 0L) run {
            upload(context, base, token, selectedTopic, uri)
            resources = JSONArray(request(base, "/topics/$selectedTopic/resources", token))
        }
    }
    Column(Modifier.fillMaxSize()) {
      Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("STUDYGUIDER", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        Text(if (token.isEmpty()) "Make progress, one topic at a time." else "Your study space", style = MaterialTheme.typography.headlineMedium)
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (token.isEmpty()) {
            OutlinedTextField(base, { base = it }, label = { Text("Server URL") }, singleLine = true)
            OutlinedTextField(password, { password = it }, label = { Text("Password") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
            Button(enabled = !busy, onClick = { run {
                val result = JSONObject(request(base, "/login", body = JSONObject().put("password", password)))
                token = result.getString("token"); password = ""
                subjects = JSONArray(request(base, "/subjects", token))
            } }) { Text("Sign in") }
        } else {
            TextButton(enabled = !busy && !examDirty, onClick = { run { request(base, "/logout", token, JSONObject()); token = ""; subjects = JSONArray(); topics = JSONArray(); resources = JSONArray(); selected = 0; selectedTopic = 0; subjectTitle = ""; topicTitle = ""; examId = ""; tab = 0 } }) { Text("Sign out") }
        }
      }
      if (token.isNotEmpty()) {
        val tabs = listOf("Study", "Lessons", "Reviews", "Exams")
        ScrollableTabRow(selectedTabIndex = tab) {
            tabs.forEachIndexed { index, title -> Tab(selected = tab == index, onClick = { if (examDirty && index != tab) { pendingTab = index; confirmExamExit = true } else tab = index }, text = { Text(title) }) }
        }
        when (tab) {
          0 -> Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (selected != 0L) {
                TextButton(enabled = !busy, onClick = {
                    if (selectedTopic != 0L) { selectedTopic = 0; topicTitle = ""; resources = JSONArray() }
                    else { selected = 0; subjectTitle = ""; topics = JSONArray() }
                }) { Text(if (selectedTopic != 0L) "‹ $subjectTitle" else "‹ Subjects") }
            }
            if (selected == 0L) {
            Text("Subjects", style = MaterialTheme.typography.titleLarge)
            OutlinedTextField(subjectName, { subjectName = it }, label = { Text("New subject") }, singleLine = true)
            OutlinedTextField(subjectLevel, { subjectLevel = it }, label = { Text("NCEA level (1–3)") }, singleLine = true)
            OutlinedButton(enabled = !busy && subjectName.isNotBlank(), onClick = { run {
                val level = subjectLevel.toIntOrNull()?.takeIf { it in 1..3 } ?: throw IllegalArgumentException("Enter a level from 1 to 3")
                request(base, "/subjects", token, JSONObject().put("name", subjectName).put("level", level))
                subjectName = ""; subjects = JSONArray(request(base, "/subjects", token))
            } }) { Text("Add subject") }
            for (i in 0 until subjects.length()) {
                val subject = subjects.getJSONObject(i)
                TextButton(enabled = !busy, onClick = { run { val id = subject.getLong("id"); val loaded = JSONArray(request(base, "/subjects/$id/topics", token)); selected = id; subjectTitle = subject.getString("name"); topics = loaded } }) {
                    Text("${subject.getString("name")} — Level ${subject.getInt("level")}")
                }
            }
            } else if (selectedTopic == 0L) {
                Text("$subjectTitle · Topics", style = MaterialTheme.typography.titleLarge)
                OutlinedTextField(topicName, { topicName = it }, label = { Text("New topic") }, singleLine = true)
                OutlinedButton(enabled = !busy && topicName.isNotBlank(), onClick = { run {
                    request(base, "/subjects/$selected/topics", token, JSONObject().put("name", topicName))
                    topicName = ""; topics = JSONArray(request(base, "/subjects/$selected/topics", token))
                } }) { Text("Add topic") }
                for (i in 0 until topics.length()) {
                    val topic = topics.getJSONObject(i)
                    TextButton(enabled = !busy, onClick = { run { val id = topic.getLong("id"); val loaded = JSONArray(request(base, "/topics/$id/resources", token)); selectedTopic = id; topicTitle = topic.getString("name"); resources = loaded } }) { Text(topic.getString("name")) }
                }
            } else {
                Text("$topicTitle · Resources", style = MaterialTheme.typography.titleLarge)
                if (resourceRefreshError.isNotEmpty()) Text(resourceRefreshError, color = MaterialTheme.colorScheme.error)
                OutlinedButton(enabled = !busy, onClick = { run {
                    resources = JSONArray(request(base, "/topics/$selectedTopic/resources", token))
                    resourceRefreshError = ""
                } }) { Text("Refresh resources") }
                Button(enabled = !busy, onClick = { picker.launch(arrayOf("*/*")) }) { Text("Upload file") }
                for (i in 0 until resources.length()) {
                    val item = resources.getJSONObject(i)
                    Text("${item.getString("filename")} — ${item.getString("status")}")
                    if (item.optString("status") == "failed") Text("Extraction failed. Retry to see the error.", color = MaterialTheme.colorScheme.error)
                    OutlinedButton(enabled = !busy, onClick = { run {
                        request(base, "/resources/${item.getString("id")}/extract", token, JSONObject())
                        resources = JSONArray(request(base, "/topics/$selectedTopic/resources", token))
                    } }) { Text(if (item.optString("status") == "failed") "Retry extraction" else "Extract text") }
                }
            }
          }
          1 -> Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)) {
              if (selectedTopic != 0L) LessonScreen(base, token, selectedTopic) else Text("Choose a topic in Study to create a lesson.", Modifier.padding(vertical = 20.dp))
          }
          2 -> Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(20.dp)) {
              if (selectedTopic != 0L) ReviewDraftScreen(base, token, selectedTopic)
              else Text("Choose a topic in Study to generate review questions.")
              ReviewScreen(base, token)
          }
          3 -> Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)) {
            if (examId.isEmpty()) ExamListScreen(base, token) { examId = it.toString() }
            else {
                TextButton(onClick = { if (examDirty) { pendingTab = null; confirmExamExit = true } else examId = "" }) { Text("‹ All exams") }
                ExamScreen(base, token, examId.toLong()) { examDirty = it }
            }
          }
        }
        }
    }
    if (confirmExamExit) AlertDialog(
        onDismissRequest = { confirmExamExit = false },
        title = { Text("Discard unsaved answers?") },
        text = { Text("Changes not saved to the server will be lost.") },
        confirmButton = { TextButton(onClick = { examDirty = false; examId = ""; pendingTab?.let { tab = it }; pendingTab = null; confirmExamExit = false }) { Text("Discard") } },
        dismissButton = { TextButton(onClick = { confirmExamExit = false }) { Text("Keep editing") } }
    )
}
