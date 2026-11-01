package nz.studyguider

import android.os.Bundle
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.BackHandler
import androidx.activity.compose.LocalActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.Alignment
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.spec.GCMParameterSpec

private fun sessionCipher(): javax.crypto.SecretKey {
    val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    (store.getKey("studyguider-session", null) as? javax.crypto.SecretKey)?.let { return it }
    return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
        init(KeyGenParameterSpec.Builder("studyguider-session", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
    }.generateKey()
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        scheduleReminder(this)
        // Transparent system bars with icons that follow the theme, so the status bar never shows as a white strip.
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.auto(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.auto(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
        )
        setContent {
            val dark = isSystemInDarkTheme()
            StudyTheme(dark) { Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { StudyApp() } }
        }
    }
}

private suspend fun request(base: String, path: String, token: String = "", body: JSONObject? = null, method: String = "POST"): String = withContext(Dispatchers.IO) {
    val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 10000
        connection.readTimeout = if (path.endsWith("/analyse")) 200000 else 20000
        if (token.isNotEmpty()) connection.setRequestProperty("Authorization", "Bearer $token")
        if (body != null) {
            connection.requestMethod = method
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

/**
 * Uploads one file or several at once. Several files are wrapped in a zip on
 * the device and sent to the batch endpoint, so one request covers the lot.
 */
private suspend fun uploadMany(context: android.content.Context, base: String, token: String, topic: Long, uris: List<Uri>, category: String = "extra"): String = withContext(Dispatchers.IO) {
    fun read(uri: Uri): Triple<String, ByteArray, String?> {
        val name = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
            if (!it.moveToFirst()) throw IllegalStateException("Cannot read file details")
            it.getString(it.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME))
        } ?: throw IllegalStateException("Cannot read file details")
        val bytes = context.contentResolver.openInputStream(uri)?.use { stream ->
            val buffer = java.io.ByteArrayOutputStream()
            val chunk = ByteArray(65536)
            while (true) {
                val count = stream.read(chunk)
                if (count < 0) break
                if (buffer.size() + count > 50 * 1024 * 1024) throw IllegalStateException("$name exceeds 50 MiB")
                buffer.write(chunk, 0, count)
            }
            buffer.toByteArray()
        } ?: throw IllegalStateException("Cannot open $name")
        val mime = context.contentResolver.getType(uri)
        return Triple(name, bytes, mime)
    }

    val parts = mutableListOf<Triple<String, ByteArray, String?>>()
    if (uris.size == 1) parts.add(read(uris.first()))
    else {
        // Several files: one zip, written to memory only, then replaced by its contents server-side.
        val zip = java.io.ByteArrayOutputStream()
        java.util.zip.ZipOutputStream(zip).use { out ->
            uris.forEach { uri ->
                val (name, bytes, _) = read(uri)
                out.putNextEntry(java.util.zip.ZipEntry(name.replace("\\", "_").replace("/", "_")))
                out.write(bytes)
                out.closeEntry()
            }
        }
        val archive = zip.toByteArray()
        if (archive.size > 50 * 1024 * 1024) throw IllegalStateException("The batch is larger than 50 MiB; upload it in smaller groups")
        parts.add(Triple("batch-${uris.size}-files.zip", archive, "application/zip"))
    }

    val boundary = "studyguider-" + java.util.UUID.randomUUID()
    val body = java.io.ByteArrayOutputStream()
    body.write("--$boundary\r\nContent-Disposition: form-data; name=\"category\"\r\n\r\n$category\r\n".toByteArray())
    parts.forEach { (name, bytes, mime) ->
        val safeName = name.replace("\"", "_").replace("\r", "_").replace("\n", "_")
        body.write("--$boundary\r\nContent-Disposition: form-data; name=\"files\"; filename=\"$safeName\"\r\nContent-Type: ${mime ?: "application/octet-stream"}\r\n\r\n".toByteArray(Charsets.UTF_8))
        body.write(bytes)
        body.write("\r\n".toByteArray())
    }
    body.write("--$boundary--\r\n".toByteArray())
    val payload = body.toByteArray()
    val connection = URL(base.trimEnd('/') + "/topics/$topic/resources/batch").openConnection() as HttpURLConnection
    try {
        connection.connectTimeout = 15000; connection.readTimeout = 120000
        connection.requestMethod = "POST"; connection.doOutput = true
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        connection.setFixedLengthStreamingMode(payload.size)
        connection.outputStream.use { it.write(payload) }
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("Upload failed ($status): $text")
        text
    } finally { connection.disconnect() }
}

private val tabOrder = listOf(1 to "Today's Lesson", 2 to "Daily Review", 3 to "Monthly Exam", 0 to "Resources")

@Composable
private fun StudyApp() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("session", android.content.Context.MODE_PRIVATE) }
    val activity = androidx.activity.compose.LocalActivity.current as? android.app.Activity
    val leaveApp: () -> Unit = { activity?.finish() }
    var base by remember { mutableStateOf("https://") }
    var password by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }
    var subjects by remember { mutableStateOf(JSONArray()) }
    var topics by remember { mutableStateOf(JSONArray()) }
    var selected by remember { mutableStateOf(0L) }
    var selectedTopic by remember { mutableStateOf(0L) }
    var selectedLesson by remember { mutableLongStateOf(0L) }
    var resources by remember { mutableStateOf(JSONArray()) }
    var resourceRefreshError by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var subjectName by remember { mutableStateOf("") }
    var subjectLevel by remember { mutableStateOf("2") }
    var topicName by remember { mutableStateOf("") }
    var examId by remember { mutableStateOf("") }
    var examDirty by remember { mutableStateOf(false) }
    var lessonPending by remember { mutableStateOf(false) }
    val examScroll = rememberScrollState()
    var sourceId by rememberSaveable { mutableStateOf("") }
    var sourcePage by remember { mutableIntStateOf(1) }
    var topicSourceId by remember { mutableStateOf("") }
    var pendingTab by remember { mutableStateOf<Int?>(null) }
    var confirmExamExit by remember { mutableStateOf(false) }
    var tab by remember { mutableIntStateOf(1) }
    var subjectTitle by remember { mutableStateOf("") }
    var topicTitle by remember { mutableStateOf("") }
    var showAddSubject by remember { mutableStateOf(false) }
    var signOutConfirm by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(false) }
    // Every topic across subjects, so the Lessons and Review tabs list them straight away.
    var allTopics by remember { mutableStateOf<List<Pair<String, JSONObject>>>(emptyList()) }
    var allTopicsLoading by remember { mutableStateOf(false) }
    var allTopicsError by remember { mutableStateOf("") }
    var topicsReload by remember { mutableIntStateOf(0) }
    // Picking the topics to study, opened from Lessons and from Settings.
    var showTopicPicker by remember { mutableStateOf(false) }
    // True until the saved session has been checked, so the sign-in form never flashes.
    var restoring by remember { mutableStateOf(true) }
    val scope = rememberCoroutineScope()
    val openTopic = { id: Long, title: String ->
        if (examDirty) { confirmExamExit = true } else scope.launch {
            selectedTopic = id; topicTitle = title
            try {
                resources = JSONArray(request(base, "/topics/$id/resources", token))
                resourceRefreshError = ""
            } catch (e: CancellationException) { throw e } catch (e: Exception) {
                resourceRefreshError = "Could not load resources: ${e.message ?: "request failed"}"
            }
        }
        Unit
    }
    val findSubject = { topicId: Long -> allTopics.firstOrNull { it.second.optLong("id") == topicId }?.first ?: subjectTitle }

    /**
     * One level up in the app, used by both the visible back control and the
     * Android back key. Returns true when it handled the press.
     */
    fun goBack(): Boolean {
        if (topicSourceId.isNotEmpty()) { topicSourceId = ""; return true }
        if (selectedTopic != 0L) { selectedTopic = 0; selectedLesson = 0; topicTitle = ""; resources = JSONArray(); return true }
        if (selected != 0L) { selected = 0; subjectTitle = ""; topics = JSONArray(); return true }
        if (tab != 0) { tab = 0; return true }
        return false
    }
    BackHandler(enabled = token.isNotEmpty()) {
        if (examDirty) { pendingTab = null; confirmExamExit = true } else if (!goBack()) leaveApp()
    }
    LaunchedEffect(Unit) {
        val saved = prefs.getString("token", null)
        if (saved == null) { restoring = false; return@LaunchedEffect }
        try {
            val bytes = Base64.decode(saved, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, sessionCipher(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
            val restored = String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), Charsets.UTF_8)
            val savedBase = prefs.getString("base", null) ?: run { restoring = false; return@LaunchedEffect }
            base = savedBase; token = restored
            val loaded = JSONArray(request(savedBase, "/subjects", restored))
            subjects = loaded
        } catch (e: Exception) {
            error = "Could not restore your session. Sign in again."
        } finally { restoring = false }
    }
    val processing = (0 until resources.length()).any { resources.getJSONObject(it).optString("status") in setOf("pending", "extracting") }
    LaunchedEffect(token, base, subjects.length(), topicsReload) {
        if (token.isEmpty()) { allTopics = emptyList(); return@LaunchedEffect }
        allTopicsLoading = true; allTopicsError = ""
        try {
            val found = mutableListOf<Pair<String, JSONObject>>()
            val list = JSONArray(request(base, "/subjects", token))
            subjects = list
            for (i in 0 until list.length()) {
                val subject = list.getJSONObject(i)
                val name = subject.optString("name")
                val topicsForSubject = JSONArray(request(base, "/subjects/${subject.getLong("id")}/topics", token))
                for (j in 0 until topicsForSubject.length()) found.add(name to topicsForSubject.getJSONObject(j))
            }
            allTopics = found
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { allTopicsError = e.message ?: "Could not load topics" }
        finally { allTopicsLoading = false }
    }
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
    var uploadNotice by remember { mutableStateOf("") }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        if (uris.isNotEmpty() && selectedTopic != 0L) run {
            val reply = uploadMany(context, base, token, selectedTopic, uris)
            resources = JSONArray(request(base, "/topics/$selectedTopic/resources", token))
            val result = JSONObject(reply)
            uploadNotice = buildString {
                append("Queued ${result.optInt("queued")} file(s)")
                if (result.optInt("duplicates") > 0) append(" · ${result.optInt("duplicates")} already in this topic")
                val skipped = result.optJSONArray("skipped")
                if (skipped != null && skipped.length() > 0) append(" · ${skipped.length()} skipped")
            }
        }
    }
    val scopeLabel = if (selectedTopic != 0L) "$subjectTitle · $topicTitle" else null
    LaunchedEffect(Unit) {
        // Debug builds expose the bundled KaTeX page on 127.0.0.1:8787 so its rendering can be checked in a browser.
        val debugBuild = (context.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0
        if (debugBuild) {
            try {
                val socket = java.net.ServerSocket(8787, 4, java.net.InetAddress.getByName("127.0.0.1"))
                while (true) {
                    val client = withContext(Dispatchers.IO) { socket.accept() }
                    withContext(Dispatchers.IO) {
                        client.use {
                            val reader = it.getInputStream().bufferedReader()
                            val request = reader.readLine().orEmpty()
                            while (true) { val line = reader.readLine() ?: break; if (line.isEmpty()) break }
                            // Serve the bundled assets as well as the page, so the real KaTeX files are exercised.
                            val path = request.split(' ').getOrNull(1)?.substringBefore('?')?.trimStart('/')
                            val asset = path?.takeIf { it.startsWith("katex/") }?.let { name ->
                                runCatching { context.assets.open(name).use { stream -> stream.readBytes() } }.getOrNull()
                            }
                            val body = if (asset != null) asset else debugKaTeXPage(KaTeXProbe, dark = request.contains("dark")).toByteArray(Charsets.UTF_8)
                            val type = when {
                                path == null -> "text/html; charset=utf-8"
                                path.endsWith(".js") -> "application/javascript; charset=utf-8"
                                path.endsWith(".css") -> "text/css; charset=utf-8"
                                path.endsWith(".woff2") -> "font/woff2"
                                else -> "text/html; charset=utf-8"
                            }
                            val header = "HTTP/1.1 200 OK\r\nContent-Type: $type\r\nCache-Control: no-store\r\nContent-Length: ${body.size}\r\nConnection: close\r\n\r\n"
                            it.getOutputStream().write(header.toByteArray(Charsets.UTF_8)); it.getOutputStream().write(body); it.getOutputStream().flush()
                        }
                    }
                }
            } catch (e: CancellationException) { throw e } catch (e: Exception) { }
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            if (!(token.isNotEmpty() && tab == 1 && selectedLesson > 0)) {
            // One compact row: the screen title plus settings. Account actions live in Settings.
            Surface(color = MaterialTheme.colorScheme.surface) {
                Column(Modifier.fillMaxWidth().statusBarsPadding()) {
                    val kicker = when (tab) {
                        1 -> scopeLabel
                        2 -> if (selectedTopic != 0L) "$subjectTitle · $topicTitle" else "Daily review"
                        3 -> null
                        4 -> null
                        else -> if (selectedTopic != 0L) "$subjectTitle · $topicTitle" else "Resources"
                    }
                    Row(
                        Modifier.fillMaxWidth().heightIn(min = 52.dp).padding(start = 20.dp, end = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(
                                when (tab) { 1 -> "Your lessons"; 2 -> "Daily review"; 3 -> "Exam"; 4 -> "Learning"; else -> "Resources" },
                                style = MaterialTheme.typography.titleMedium,
                                color = MaterialTheme.colorScheme.onSurface,
                            )
                            if (token.isNotEmpty() && kicker != null) Text(kicker, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, maxLines = 1)
                        }
                        if (error.isNotEmpty()) Text("!", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(end = 8.dp))
                        if (token.isNotEmpty()) {
                            val tint = if (showSettings) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant
                            Box(
                                Modifier.size(40.dp).clip(RoundedCornerShape(50))
                                    .background(if (showSettings) MaterialTheme.colorScheme.primaryContainer else Color.Transparent)
                                    .clickable(role = androidx.compose.ui.semantics.Role.Button) { showSettings = true },
                                contentAlignment = Alignment.Center,
                            ) { SettingsIcon(tint, Modifier.size(22.dp)) }
                        }
                    }
                    if (busy) LinearProgressIndicator(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.secondary)
                }
            }
            }
        },
        bottomBar = {
            if (token.isNotEmpty()) StudyNavBar(current = tab) { destination ->
                if (lessonPending && destination != tab) error = "Your lesson answer is not saved yet. Wait for saving or resolve the save error before changing tabs."
                else if (examDirty && destination != tab) { pendingTab = destination; confirmExamExit = true } else {
                    if (error == "Your lesson answer is not saved yet. Wait for saving or resolve the save error before changing tabs." && !lessonPending) error = ""
                    tab = destination
                }
            }
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if (restoring) {
                Column(Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
                    Spacer(Modifier.height(40.dp))
                    Text("STUDYGUIDER", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                    Text("Opening your\ntopics…", style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.primary)
                    LinearProgressIndicator(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.secondary)
                }
            } else if (token.isEmpty()) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Spacer(Modifier.height(24.dp))
                    Text("YOUR STUDY COMPANION", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
                    Text("Make progress,\none topic at a time.", style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.primary)
                    Text("Sign in to pick up your lessons, reviews and exams.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(base, { base = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Server URL") }, singleLine = true, shape = RoundedCornerShape(12.dp))
                    OutlinedTextField(password, { password = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Password") }, visualTransformation = PasswordVisualTransformation(), singleLine = true, shape = RoundedCornerShape(12.dp))
                    Button(modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp), shape = RoundedCornerShape(50), enabled = !busy, onClick = { run {
                        val result = JSONObject(request(base, "/login", body = JSONObject().put("password", password)))
                        val newToken = result.getString("token")
                        val loaded = JSONArray(request(base, "/subjects", newToken))
                        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
                        cipher.init(Cipher.ENCRYPT_MODE, sessionCipher())
                        prefs.edit().putString("base", base).putString("token", Base64.encodeToString(cipher.iv + cipher.doFinal(newToken.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)).apply()
                        token = newToken; password = ""; subjects = loaded
                    } }) { Text("Sign in") }
                }
            } else when (tab) {
                0 -> ResourceHub(
                    base, token, subjects, topics, resources, selected, selectedTopic,
                    subjectTitle, topicTitle, topicSourceId, resourceRefreshError, busy,
                    subjectName = subjectName, onSubjectName = { subjectName = it },
                    subjectLevel = subjectLevel, onSubjectLevel = { subjectLevel = it },
                    topicName = topicName, onTopicName = { topicName = it },
                    showAddSubject = showAddSubject, onToggleAddSubject = { showAddSubject = !showAddSubject },
                    onOpenSubject = { id, title -> run { topics = JSONArray(request(base, "/subjects/$id/topics", token)); selected = id; subjectTitle = title; selectedTopic = 0; topicTitle = "" } },
                    onOpenTopic = { id, title -> run { resources = JSONArray(request(base, "/topics/$id/resources", token)); selectedTopic = id; topicTitle = title } },
                    onBack = {
                        if (topicSourceId.isNotEmpty()) topicSourceId = ""
                        else if (selectedTopic != 0L) { selectedTopic = 0; topicTitle = ""; resources = JSONArray() }
                        else { selected = 0; subjectTitle = ""; topics = JSONArray() }
                    },
                    onAddSubject = { run {
                        val level = subjectLevel.toIntOrNull()?.takeIf { it in 1..3 } ?: throw IllegalArgumentException("Enter a level from 1 to 3")
                        request(base, "/subjects", token, JSONObject().put("name", subjectName).put("level", level))
                        subjectName = ""; subjects = JSONArray(request(base, "/subjects", token)); showAddSubject = false
                    } },
                    onAddTopic = { run {
                        request(base, "/subjects/$selected/topics", token, JSONObject().put("name", topicName))
                        topicName = ""; topics = JSONArray(request(base, "/subjects/$selected/topics", token))
                    } },
                    onUpload = { uploadNotice = ""; picker.launch(arrayOf("application/pdf", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "text/*", "image/*")) },
                    uploadNotice = uploadNotice,
                    onRefresh = { run { resources = JSONArray(request(base, "/topics/$selectedTopic/resources", token)); resourceRefreshError = "" } },
                    onExtract = { id, retry -> run {
                        request(base, "/resources/$id/${if (retry) "retry" else "extract"}", token, JSONObject())
                        resources = JSONArray(request(base, "/topics/$selectedTopic/resources", token))
                    } },
                    onOpenPdf = { topicSourceId = it }, onClosePdf = { topicSourceId = "" },
                )
                1 -> when {
                    selectedTopic != 0L -> Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
                        LessonScreen(
                            base = base, token = token, topicId = selectedTopic,
                            topicName = topicTitle, subjectName = subjectTitle,
                            allTopics = allTopics,
                            onSwitchTopic = { id, title -> openTopic(id, title); subjectTitle = findSubject(id) },
                            onOpenResources = { tab = 0 },
                            lessonId = selectedLesson,
                            onPendingChange = { lessonPending = it },
                            onExit = { selectedTopic = 0; selectedLesson = 0; topicTitle = "" },
                        )
                    }
                    else -> LessonsHome(
                        base = base, token = token,
                        onOpenLesson = { id, title, lessonId -> selectedLesson = lessonId; openTopic(id, title); subjectTitle = findSubject(id) },
                    )
                }
                2 -> Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
                    ReviewScreen(base, token)
                }
                4 -> LearningScreen(base, token, topicsReload, onManageCourses = { showTopicPicker = true }, onOpenLesson = { topic, title, lesson ->
                    selectedLesson = lesson; openTopic(topic, title); subjectTitle = findSubject(topic); tab = 1
                })
                else -> Column(Modifier.fillMaxSize().verticalScroll(examScroll).padding(horizontal = 16.dp)) {
                    if (examId.isEmpty()) ExamListScreen(base, token) { examId = it.toString(); sourceId = "" }
                    else {
                        Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                            TextButton(onClick = { if (examDirty) { pendingTab = null; confirmExamExit = true } else { examId = ""; sourceId = "" } }) { Text("‹ All exams") }
                            Spacer(Modifier.weight(1f))
                            if (sourceId.isNotEmpty()) TextButton(onClick = { sourceId = "" }) { Text("Close source") }
                        }
                        if (sourceId.isNotEmpty()) SourceScreen(base, token, sourceId, sourcePage)
                        ExamScreen(base, token, examId.toLong(), onOpenSource = { id, page -> sourceId = id; sourcePage = page }, onDirtyChange = { examDirty = it }, onPageChange = { scope.launch { examScroll.scrollTo(0) } })
                    }
                }
            }
        }
    }
    // App-wide errors stay visible in a single line under the header.
    if (token.isNotEmpty() && error.isNotEmpty()) {
        Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 4.dp))
    }
    if (showTopicPicker) TopicPickerSheet(
        base = base,
        token = token,
        allTopics = allTopics,
        loading = allTopicsLoading,
        onDismiss = { showTopicPicker = false },
        onChanged = { topicsReload++ },
    )
    if (showSettings) SettingsSheet(
        base = base,
        token = token,
        signedIn = token.isNotEmpty(),
        busy = busy,
        dark = isSystemInDarkTheme(),
        onDismiss = { showSettings = false },
        onSignOut = { if (!busy && !examDirty) { showSettings = false; signOutConfirm = true } },
        canSignOut = !busy && !examDirty,
        subjectCount = subjects.length(),
        topicCount = topics.length(),
    )
    if (signOutConfirm) AlertDialog(
        onDismissRequest = { signOutConfirm = false },
        title = { Text("Sign out?") },
        text = { Text("You will need the password to sign in again on this device.") },
        confirmButton = { TextButton(onClick = {
            signOutConfirm = false
            run { request(base, "/logout", token, JSONObject()); prefs.edit().clear().apply(); token = ""; subjects = JSONArray(); topics = JSONArray(); resources = JSONArray(); selected = 0; selectedTopic = 0; subjectTitle = ""; topicTitle = ""; examId = ""; sourceId = ""; tab = 1 }
        }) { Text("Sign out") } },
        dismissButton = { TextButton(onClick = { signOutConfirm = false }) { Text("Cancel") } },
    )
    if (confirmExamExit) AlertDialog(
        onDismissRequest = { confirmExamExit = false },
        title = { Text("Discard unsaved answers?") },
        text = { Text("Changes not saved to the server will be lost.") },
        confirmButton = { TextButton(onClick = { examDirty = false; examId = ""; sourceId = ""; pendingTab?.let { tab = it }; pendingTab = null; confirmExamExit = false }) { Text("Discard") } },
        dismissButton = { TextButton(onClick = { confirmExamExit = false }) { Text("Keep editing") } }
    )
}

/**
 * Chooses which topics to learn. Selected topics become courses, so their
 * lessons appear on the Lessons home. Opened from the floating button, the
 * empty state, or Settings.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TopicPickerSheet(
    base: String,
    token: String,
    allTopics: List<Pair<String, JSONObject>>,
    loading: Boolean,
    onDismiss: () -> Unit,
    onChanged: () -> Unit,
) {
    var enrolledTopicIds by remember { mutableStateOf<Set<Long>>(emptySet()) }
    var busyTopic by remember { mutableStateOf<Long?>(null) }
    var error by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val colours = LocalStudyColours.current
    suspend fun loadCourses(): Set<Long> = withContext(Dispatchers.IO) {
        val list = JSONArray(request(base, "/courses", token))
        (0 until list.length()).map { list.getJSONObject(it).getLong("topic_id") }.toSet()
    }
    LaunchedEffect(base, token) {
        try { enrolledTopicIds = loadCourses() } catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = "Could not load your courses: ${e.message ?: "request failed"}" }
    }
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Topics you're learning", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
            Text("Tick the topics you want lessons for. They appear on your Lessons page, starting from the basics.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            if (loading && allTopics.isEmpty()) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text("Loading topics…", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            allTopics.groupBy({ it.first }, { it.second }).forEach { (subject, list) ->
                Text(subject, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                list.forEach { topic ->
                    val id = topic.getLong("id")
                    val on = id in enrolledTopicIds
                    Row(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(if (on) colours.containerLow else colours.container)
                            .clickable(enabled = busyTopic == null) {
                                scope.launch {
                                    busyTopic = id; error = ""
                                    try {
                                        if (on) {
                                            // Removing a course stops it appearing; lessons stay saved on the server.
                                            val list2 = JSONArray(request(base, "/courses", token))
                                            for (i in 0 until list2.length()) {
                                                val c = list2.getJSONObject(i)
                                                if (c.getLong("topic_id") == id) {
                                                    request(base, "/courses/${c.getLong("id")}", token, JSONObject(), "DELETE")
                                                    break
                                                }
                                            }
                                        } else request(base, "/courses", token, JSONObject().put("topic_id", id))
                                        enrolledTopicIds = loadCourses()
                                        onChanged()
                                    } catch (e: CancellationException) { throw e } catch (e: Exception) {
                                        error = "Could not save: ${e.message ?: "request failed"}"
                                    } finally { busyTopic = null }
                                }
                            }
                            .padding(horizontal = 14.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text(topic.optString("name"), style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                        if (busyTopic == id) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                        else Text(if (on) "✓ Learning" else "Add", style = MaterialTheme.typography.labelMedium, color = if (on) colours.teal else MaterialTheme.colorScheme.primary)
                    }
                }
            }
            if (allTopics.isEmpty() && !loading) StudyCard(tone = CardTone.Low) {
                Text("No topics yet. Add a subject and topic in Resources first.", style = MaterialTheme.typography.bodySmall)
            }
            Button(onClick = onDismiss, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Done") }
        }
    }
}

@Composable
private fun LessonChooseTopic(
    onChoose: () -> Unit,
    subjectsCount: Int,
    title: String = "Today's lesson",
    detail: String = "Select a subject and topic to open saved lessons or create a new one.",
) {
    Column(Modifier.fillMaxWidth().padding(top = 20.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Column {
            Text(if (title == "Today's lesson") "YOUR LEARNING" else "SPACED REPETITION", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
            Text(title, style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.primary)
        }
        StudyCard(tone = CardTone.Container) {
            Text("Choose what to learn", style = MaterialTheme.typography.titleLarge)
            Text(detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (subjectsCount == 0) Text("No subjects yet. Add one in Resources.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = onChoose, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 50.dp)) { Text("Open Resources") }
        }
    }
}

/**
 * Lists every subject and its topics directly on the Lessons tab, so picking a
 * topic is one tap rather than a trip through Resources.
 */
@Composable
private fun TopicBrowser(
    allTopics: List<Pair<String, JSONObject>>,
    loading: Boolean,
    error: String,
    selectedTopicId: Long,
    onRetry: () -> Unit,
    onOpen: (Long, String) -> Unit,
    onBrowseResources: () -> Unit,
) {
    val colours = LocalStudyColours.current
    val grouped = remember(allTopics) { allTopics.groupBy({ it.first }, { it.second }) }
    Column(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("YOUR LEARNING", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
        Text("Pick a topic", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
        Text("Your topics are ready — tap one to read, add files and practise.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        when {
            loading && allTopics.isEmpty() -> {
                StudyCard(tone = CardTone.Low) {
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                    Text("Loading your topics…", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            error.isNotEmpty() && allTopics.isEmpty() -> StudyCard(tone = CardTone.Low) {
                Text("Could not load your topics.", style = MaterialTheme.typography.titleSmall)
                Text(error, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                OutlinedButton(onClick = onRetry, shape = RoundedCornerShape(50)) { Text("Try again") }
            }
            allTopics.isEmpty() -> StudyCard(tone = CardTone.Low) {
                Text("No topics yet.", style = MaterialTheme.typography.titleSmall)
                Text("Add a subject and topic in Resources, then upload a file to start learning.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedButton(onClick = onBrowseResources, shape = RoundedCornerShape(50)) { Text("Open Resources") }
            }
            else -> grouped.forEach { (subject, list) ->
                Text(subject, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                list.forEach { topic ->
                    val id = topic.getLong("id")
                    val selected = id == selectedTopicId
                    Surface(
                        onClick = { onOpen(id, topic.optString("name")) },
                        shape = RoundedCornerShape(14.dp),
                        color = if (selected) MaterialTheme.colorScheme.primaryContainer else colours.container,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(Modifier.padding(horizontal = 16.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Text(topic.optString("name"), style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                            Text(if (selected) "Reading" else "Open →", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
        }
    }
}

/**
 * Teaching style per subject. The saved profile is included in every lesson
 * generated for that subject, so the learner can shape how lessons read.
 */
@Composable
private fun LearningScreen(base: String, token: String, revision: Int, onManageCourses: () -> Unit, onOpenLesson: (Long, String, Long) -> Unit) {
    var courses by remember(base, token) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf("") }
    var retry by remember { mutableIntStateOf(0) }
    var page by remember { mutableStateOf("") }
    var managerDay by remember { mutableStateOf<String?>(null) }
    var lessons by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var deleting by remember { mutableStateOf(false) }
    var deleteTarget by remember { mutableStateOf<JSONObject?>(null) }
    var scheduleTopic by remember { mutableStateOf<JSONObject?>(null) }
    val scope = rememberCoroutineScope()
    val pageScroll = rememberScrollState()
    scheduleTopic?.let { selected -> NightlyStatus(base, token, selected, onDismiss = { scheduleTopic = null }) }
    LaunchedEffect(page, managerDay) { pageScroll.scrollTo(0) }
    BackHandler(enabled = page.isNotEmpty()) { if (managerDay != null) managerDay = null else page = "" }
    LaunchedEffect(base, token, revision, retry) {
        loading = true; error = ""
        try {
            val list = JSONArray(request(base, "/courses", token))
            courses = (0 until list.length()).map { list.getJSONObject(it) }
            val saved = JSONArray(request(base, "/lessons", token))
            lessons = (0 until saved.length()).map { saved.getJSONObject(it) }
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Could not load your topics" }
        finally { loading = false }
    }
    Column(Modifier.fillMaxSize().verticalScroll(pageScroll).padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        if (page.isNotEmpty()) Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { if (managerDay != null) managerDay = null else page = "" }) { Text(if (managerDay != null) "‹ All days" else "‹ Learning") }
            Spacer(Modifier.weight(1f))
            if (managerDay != null) Text(managerDay.orEmpty(), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (page.isEmpty()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("What I'm learning", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
            TextButton(onClick = onManageCourses) { Text("Edit topics") }
        }
        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (error.isNotEmpty()) {
            Text(error, color = MaterialTheme.colorScheme.error)
            TextButton(onClick = { retry++ }) { Text("Try again") }
        }
        if (!loading && error.isEmpty() && courses.isEmpty()) Text("Choose topics to include in your lessons.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (courses.isNotEmpty()) Surface(shape = RoundedCornerShape(16.dp), color = LocalStudyColours.current.container) {
            Column {
                courses.forEachIndexed { index, course ->
                    if (index > 0) HorizontalDivider(Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    ListItem(headlineContent = { Text(course.optString("topic")) }, supportingContent = { Text(course.optString("subject")) }, trailingContent = {
                        TextButton(onClick = { scheduleTopic = course }) { Text("Nightly status") }
                    }, colors = ListItemDefaults.colors(containerColor = Color.Transparent))
                }
            }
        }
        TeachingStyleEditor(base, token)
        DailyReminderSetting()
        AiUsageCard(base, token)
        LearnerSummaryCard(base, token)
        Surface(shape = RoundedCornerShape(16.dp), color = LocalStudyColours.current.container) {
            Column {
                ListItem(headlineContent = { Text("Lesson manager") }, supportingContent = { Text("Open or delete saved lessons") }, trailingContent = { Text("›") }, modifier = Modifier.clickable { page = "Lesson manager" }, colors = ListItemDefaults.colors(containerColor = Color.Transparent))
                HorizontalDivider(Modifier.padding(horizontal = 16.dp))
                ListItem(headlineContent = { Text("Lesson history") }, supportingContent = { Text("Completed lessons used for your reviews") }, trailingContent = { Text("›") }, modifier = Modifier.clickable { page = "Lesson history" }, colors = ListItemDefaults.colors(containerColor = Color.Transparent))
                HorizontalDivider(Modifier.padding(horizontal = 16.dp))
                ListItem(headlineContent = { Text("Topic notes") }, supportingContent = { Text("Read your saved explanations and notes") }, trailingContent = { Text("›") }, modifier = Modifier.clickable { page = "Topic notes" }, colors = ListItemDefaults.colors(containerColor = Color.Transparent))
            }
        }
        } else if (page == "Topic notes") {
            TopicNotes(base, token)
        } else {
            if (managerDay == null) Text(page, style = MaterialTheme.typography.titleLarge)
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (error.isNotEmpty()) { Text(error, color = MaterialTheme.colorScheme.error); TextButton(onClick = { retry++ }) { Text("Try again") } }
            val visible = if (page == "Lesson history") lessons.filter { !it.isNull("completed_at") } else lessons
            val days = visible.groupBy { lesson ->
                runCatching {
                    java.time.Instant.parse(lesson.getString("created_at"))
                        .atZone(java.time.ZoneId.of("Pacific/Auckland")).toLocalDate().toString()
                }.getOrDefault("Unknown date")
            }.toSortedMap(compareByDescending { it })
            if (!loading && visible.isEmpty()) Text(if (page == "Lesson history") "Finish a lesson to build your review history." else "No saved lessons yet.")
            if (page == "Lesson manager" && managerDay == null) {
                days.forEach { (day, items) ->
                    Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp), color = LocalStudyColours.current.container) {
                        ListItem(
                            headlineContent = { Text(day) },
                            supportingContent = { Text("${items.size} lesson${if (items.size == 1) "" else "s"} · ${items.count { !it.isNull("completed_at") }} completed") },
                            trailingContent = { Text("›", style = MaterialTheme.typography.titleLarge) },
                            modifier = Modifier.clickable { managerDay = day },
                            colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                        )
                    }
                }
            }
            val dayLessons = if (page == "Lesson manager") days[managerDay].orEmpty() else visible
            if (managerDay != null && dayLessons.isEmpty()) Text("No lessons left for this day.")
            if (dayLessons.isNotEmpty()) Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp), color = LocalStudyColours.current.container) {
                Column {
                    dayLessons.forEachIndexed { index, lesson ->
                        key(lesson.getLong("id")) {
                        var menu by remember { mutableStateOf(false) }
                        if (index > 0) HorizontalDivider(Modifier.padding(horizontal = 14.dp), color = MaterialTheme.colorScheme.outlineVariant)
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f).clickable(role = androidx.compose.ui.semantics.Role.Button, onClickLabel = "Open lesson") {
                                onOpenLesson(lesson.getLong("topic_id"), lesson.optString("topic"), lesson.getLong("id"))
                            }.padding(14.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Text(lesson.optString("query"), style = MaterialTheme.typography.titleMedium)
                                val topic = lesson.optString("topic")
                                Text(lesson.optString("subject") + if (topic.equals(lesson.optString("query"), true)) "" else " · $topic", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text(if (lesson.isNull("completed_at")) "Not finished" else "Completed", style = MaterialTheme.typography.labelMedium, color = if (lesson.isNull("completed_at")) MaterialTheme.colorScheme.onSurfaceVariant else LocalStudyColours.current.teal)
                            }
                            if (page == "Lesson manager") Box {
                                IconButton(enabled = !deleting, onClick = { menu = true }) {
                                    Text("⋮", style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { contentDescription = "Lesson actions" })
                                }
                                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                                    DropdownMenuItem(text = { Text("Delete lesson", color = MaterialTheme.colorScheme.error) }, onClick = { menu = false; deleteTarget = lesson })
                                }
                            }
                        }
                        }
                    }
                }
            }
        }
    }
    deleteTarget?.let { lesson -> AlertDialog(
        onDismissRequest = { if (!deleting) deleteTarget = null }, title = { Text("Delete this lesson?") },
        text = { Text("This permanently removes the lesson and its completion history. Existing review questions are kept.") },
        confirmButton = { TextButton(enabled = !deleting, onClick = {
            scope.launch {
                deleting = true; error = ""
                try {
                    request(base, "/lessons/${lesson.getLong("id")}", token, JSONObject(), "DELETE")
                    lessons = lessons.filterNot { it.getLong("id") == lesson.getLong("id") }; deleteTarget = null
                } catch (e: CancellationException) { throw e }
                catch (e: Exception) { error = e.message ?: "Could not delete lesson"; deleteTarget = null }
                finally { deleting = false }
            }
        }) { Text("Delete") } }, dismissButton = { TextButton(enabled = !deleting, onClick = { deleteTarget = null }) { Text("Cancel") } },
    ) }
}

@Composable
internal fun NightlyStatus(base: String, token: String, topic: JSONObject, onDismiss: () -> Unit) {
    var runs by remember(base, token, topic) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf("") }
    var retry by remember { mutableIntStateOf(0) }
    LaunchedEffect(base, token, topic, retry) {
        loading = true; error = ""
        try {
            val rows = JSONArray(request(base, "/topics/${topic.getLong("topic_id")}/schedule/runs", token))
            runs = (0 until minOf(rows.length(), 7)).map { rows.getJSONObject(it) }
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Could not load nightly runs" }
        finally { loading = false }
    }
    AlertDialog(onDismissRequest = onDismiss,
        title = { Text("Nightly lessons · ${topic.optString("topic")}") },
        text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Latest seven runs. Completed means generation finished, not that AI review passed.", style = MaterialTheme.typography.bodySmall)
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
            if (!loading && error.isEmpty() && runs.isEmpty()) Text("No scheduled runs recorded yet.")
            runs.forEach { run ->
                Text("${run.optString("run_date")} · ${run.optString("status")}", style = MaterialTheme.typography.titleSmall)
                if (!run.isNull("review_status")) {
                    val review = run.optString("review_status")
                    Text("AI review: $review — not factual verification", style = MaterialTheme.typography.bodySmall,
                        color = if (review == "passed") MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error)
                }
                if (!run.isNull("error") && run.optString("error").isNotBlank()) Text(run.optString("error"), color = MaterialTheme.colorScheme.error)
                if (!run.isNull("lesson_id")) Text("Lesson ${run.optLong("lesson_id")}", style = MaterialTheme.typography.bodySmall)
                HorizontalDivider()
            }
        } },
        confirmButton = { TextButton(enabled = !loading, onClick = { retry++ }) { Text("Refresh") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

@Composable
internal fun TopicNotes(base: String, token: String) {
    var topics by remember(base, token) { mutableStateOf<List<Pair<String, Long>>>(emptyList()) }
    var topic by remember(base, token) { mutableStateOf<Pair<String, Long>?>(null) }
    var notes by remember(base, token) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var menu by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf("") }
    var reload by remember { mutableIntStateOf(0) }
    var deleteNote by remember(base, token, topic) { mutableStateOf<JSONObject?>(null) }
    var deletingNote by remember { mutableStateOf(false) }
    val noteScope = rememberCoroutineScope()
    LaunchedEffect(base, token) {
        busy = true; error = ""
        try {
            val subjects = JSONArray(request(base, "/subjects", token))
            val found = mutableListOf<Pair<String, Long>>()
            for (i in 0 until subjects.length()) {
                val subject = subjects.getJSONObject(i)
                val rows = JSONArray(request(base, "/subjects/${subject.getLong("id")}/topics", token))
                for (j in 0 until rows.length()) {
                    val item = rows.getJSONObject(j)
                    found.add("${subject.optString("name")} · ${item.optString("name")}" to item.getLong("id"))
                }
            }
            topics = found
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Could not load topics" }
        finally { busy = false }
    }
    LaunchedEffect(base, token, topic, reload) {
        notes = emptyList()
        val selected = topic ?: return@LaunchedEffect
        busy = true; error = ""
        try {
            val rows = JSONArray(request(base, "/topics/${selected.second}/notes", token))
            notes = (0 until rows.length()).map { rows.getJSONObject(it) }
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Could not load notes" }
        finally { busy = false }
    }
    Text("Topic notes", style = MaterialTheme.typography.titleLarge)
    Box {
        OutlinedButton(enabled = !deletingNote, onClick = { menu = true }, modifier = Modifier.fillMaxWidth()) { Text(topic?.first ?: "Choose a topic") }
        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
            topics.forEach { item -> DropdownMenuItem(text = { Text(item.first) }, onClick = { topic = item; menu = false }) }
        }
    }
    TextButton(enabled = !busy && !deletingNote, onClick = { reload++ }) { Text("Refresh") }
    if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
    if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
    if (!busy && error.isEmpty() && topic != null && notes.isEmpty()) Text("No notes saved for this topic yet.")
    notes.forEach { note ->
        StudyCard {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(note.optString("created_at").take(10), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                TextButton(enabled = !deletingNote, onClick = { deleteNote = note }) { Text("Delete", color = MaterialTheme.colorScheme.error) }
            }
            val text = withoutSourceMarkers(shortCitations(note.optString("content"), emptyList()))
            markdownBlocks(text).forEach { (kind, runs) ->
                val content = runs.joinToString("") { it.text }
                if (kind == "heading") Text(content, style = MaterialTheme.typography.titleSmall)
                else MathText(content)
            }
        }
    }
    deleteNote?.let { note ->
        AlertDialog(
            onDismissRequest = { if (!deletingNote) deleteNote = null },
            title = { Text("Delete note?") },
            text = { Text("This permanently deletes this saved note. The original lesson and its sources are kept.") },
            confirmButton = { TextButton(enabled = !deletingNote, onClick = {
                val topicId = topic?.second ?: return@TextButton
                noteScope.launch {
                    deletingNote = true; error = ""
                    try {
                        request(base, "/topics/$topicId/notes/${note.getLong("id")}", token, method = "DELETE")
                        notes = notes.filterNot { it.getLong("id") == note.getLong("id") }
                        deleteNote = null
                    } catch (e: CancellationException) { throw e }
                    catch (e: Exception) { error = e.message ?: "Could not delete note"; deleteNote = null }
                    finally { deletingNote = false }
                }
            }) { Text(if (deletingNote) "Deleting…" else "Delete note", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(enabled = !deletingNote, onClick = { deleteNote = null }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun AiUsageCard(base: String, token: String) {
    var usage by remember(base, token) { mutableStateOf<JSONObject?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    StudyCard {
            Text("AI usage", style = MaterialTheme.typography.titleMedium)
            Text("Last 30 days", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            TextButton(enabled = !busy, onClick = {
                scope.launch {
                    busy = true; error = ""
                    try { usage = JSONObject(request(base, "/usage?days=30", token)) }
                    catch (e: CancellationException) { throw e }
                    catch (e: Exception) { error = e.message ?: "Could not load AI usage" }
                    finally { busy = false }
                }
            }) { Text(if (busy) "Loading…" else if (usage == null) "View usage" else "Refresh usage") }
            usage?.let { data ->
                Text("${data.optLong("calls")} calls · ${data.optLong("errors")} errors")
                if (!data.isNull("failure_warning")) Text(data.optString("failure_warning"), color = MaterialTheme.colorScheme.error)
                Text("Reported tokens: ${data.optLong("prompt_tokens")} input · ${data.optLong("completion_tokens")} output")
                Text("${data.optLong("calls_without_token_counts")} calls without complete token counts", style = MaterialTheme.typography.bodySmall)
                Text(data.optString("warning"), style = MaterialTheme.typography.bodySmall)
                Text(data.optString("cost_notice", "Cost unavailable; gateway pricing is not configured."), style = MaterialTheme.typography.bodySmall)
            }
            if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
    }
}

/** Cross-topic learner summary: repeated mistakes, strengths, review activity. */
@Composable
private fun LearnerSummaryCard(base: String, token: String) {
    var summary by remember(base, token) { mutableStateOf<JSONObject?>(null) }
    var error by remember { mutableStateOf("") }
    LaunchedEffect(base, token) {
        try { summary = JSONObject(request(base, "/learner/summary", token)) }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Could not load your summary" }
    }
    val data = summary ?: return
    val mistakes = data.optJSONArray("repeated_mistakes") ?: JSONArray()
    val strengths = data.optJSONArray("strengths") ?: JSONArray()
    if (mistakes.length() == 0 && strengths.length() == 0 && error.isEmpty()) return
    Surface(shape = RoundedCornerShape(16.dp), color = LocalStudyColours.current.container) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Your progress", style = MaterialTheme.typography.titleMedium)
            if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            Text("Reviews completed today: ${data.optInt("reviews_today")}", style = MaterialTheme.typography.bodySmall)
            if (mistakes.length() > 0) {
                Text("Keeps coming up", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.error)
                for (i in 0 until minOf(mistakes.length(), 5)) {
                    val item = mistakes.getJSONObject(i)
                    Text("• ${item.optString("concept")} (${item.optInt("times_wrong")}×)", style = MaterialTheme.typography.bodySmall)
                }
            }
            if (strengths.length() > 0) {
                Text("You've got this", style = MaterialTheme.typography.labelLarge, color = LocalStudyColours.current.teal)
                for (i in 0 until minOf(strengths.length(), 5)) {
                    val item = strengths.getJSONObject(i)
                    Text("• ${item.optString("concept")} (${item.optInt("times_correct")}×)", style = MaterialTheme.typography.bodySmall)
                }
            }
            Text(data.optString("notice"), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun TeachingStyleEditor(base: String, token: String) {
    var subjects by remember { mutableStateOf(JSONArray()) }
    var draft by remember { mutableStateOf("") }
    var saved by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var savedNotice by remember { mutableStateOf("") }
    var expanded by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var uploadTopics by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var chooseUploadTopic by remember { mutableStateOf(false) }
    var uploadTopic by remember { mutableStateOf(0L) }
    val slidesPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        if (uris.isNotEmpty()) scope.launch {
            busy = true; error = ""; savedNotice = "Uploading teacher slides…"
            try {
                val result = JSONObject(uploadMany(context, base, token, uploadTopic, uris, category = "slides"))
                val accepted = result.optJSONArray("accepted") ?: JSONArray()
                val ids = (0 until accepted.length()).map { accepted.getJSONObject(it) }
                    .filter { it.optString("category") == "slides" }.map { it.getString("id") }.toSet()
                if (ids.isEmpty()) throw IllegalStateException("No teacher slides accepted. Duplicate files filed as other resource types were not changed; unsupported files may have been skipped.")
                savedNotice = "Slides uploaded. Waiting for text extraction…"
                var ready = false
                for (attempt in 0 until 60) {
                    val resources = JSONArray(request(base, "/topics/$uploadTopic/resources", token))
                    val slides = (0 until resources.length()).map { resources.getJSONObject(it) }
                        .filter { it.optString("id") in ids }
                    if (slides.any { it.optString("status") == "failed" }) throw IllegalStateException("A slide file could not be processed. Check Resources before analysing.")
                    if (slides.size == ids.size && slides.all { it.optString("status") == "extracted" }) { ready = true; break }
                    delay(2000)
                }
                if (!ready) throw IllegalStateException("Slides are still processing. Use Analyse teaching method once they are Ready in Resources.")
                savedNotice = "Analysing how your teacher teaches…"
                val analysis = JSONObject(request(base, "/style-profile/analyse", token, JSONObject()))
                draft = analysis.getString("profile")
                savedNotice = "Teaching method extracted. Read and edit it below, then Save style."
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { savedNotice = ""; error = e.message ?: "Could not process teacher slides" }
            finally { busy = false }
        }
    }

    if (chooseUploadTopic) AlertDialog(
        onDismissRequest = { chooseUploadTopic = false },
        title = { Text("File slides under a topic") },
        text = { Column(Modifier.verticalScroll(rememberScrollState())) {
            Text("This only organises your uploaded files. The teaching method applies across the whole app.")
            uploadTopics.forEach { topic ->
                TextButton(onClick = {
                    uploadTopic = topic.getLong("id"); chooseUploadTopic = false
                    slidesPicker.launch(arrayOf("application/pdf", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/*", "image/*", "application/zip"))
                }) { Text(topic.optString("name")) }
            }
        } },
        confirmButton = { TextButton(onClick = { chooseUploadTopic = false }) { Text("Cancel") } },
    )

    suspend fun load() = withContext(Dispatchers.IO) {
        val list = JSONArray(request(base, "/subjects", token))
        subjects = list
        val body = JSONObject(request(base, "/style-profile", token))
        draft = body.optString("content"); saved = draft
    }

    LaunchedEffect(base, token) {
        try { load() } catch (e: CancellationException) { throw e } catch (e: Exception) {
            error = "Could not load teaching style: ${e.message ?: "request failed"}"
        }
    }

    StudyCard(tone = CardTone.Low) {
        Row(Modifier.fillMaxWidth().clickable { expanded = !expanded }, verticalAlignment = Alignment.CenterVertically) {
            Text("Teaching method", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
            Text(if (expanded) "Hide" else "Edit", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
        }
        Text(
            "One teaching method for the whole app. Analyse your teacher's slides or write your preferences for all subjects.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        AnimatedVisibility(visible = expanded) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(
                    value = draft,
                    onValueChange = { draft = it; savedNotice = "" },
                    label = { Text("How should lessons teach you?") },
                    placeholder = { Text("e.g. Short sections, one worked example each, then a question. Use bullet points and show every algebra step.") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 4, maxLines = 12,
                    enabled = !busy,
                    shape = RoundedCornerShape(12.dp),
                )
                Text("${draft.length}/50000 characters", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                if (savedNotice.isNotEmpty()) Text(savedNotice, style = MaterialTheme.typography.bodySmall, color = LocalStudyColours.current.teal)
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = !busy && subjects.length() > 0, onClick = {
                        scope.launch {
                            busy = true; error = ""
                            try {
                                val found = mutableListOf<JSONObject>()
                                for (i in 0 until subjects.length()) {
                                    val subject = subjects.getJSONObject(i)
                                    val topics = JSONArray(request(base, "/subjects/${subject.getLong("id")}/topics", token))
                                    for (j in 0 until topics.length()) found.add(topics.getJSONObject(j).apply { put("name", "${subject.optString("name")} · ${optString("name")}") })
                                }
                                uploadTopics = found
                                if (uploadTopics.isEmpty()) error = "Add a topic in Resources to store your slide files first."
                                else chooseUploadTopic = true
                            } catch (e: CancellationException) { throw e }
                            catch (e: Exception) { error = e.message ?: "Could not load topics" }
                            finally { busy = false }
                        }
                    }) { Text("Upload teacher slides") }
                    OutlinedButton(enabled = !busy, onClick = {
                        scope.launch {
                            busy = true; error = ""
                            try {
                                val result = JSONObject(request(base, "/style-profile/analyse", token, JSONObject()))
                                draft = result.getString("profile")
                                savedNotice = "Teaching method written from your slides. Read how your teacher teaches below, then Save to use it in lessons."
                            } catch (e: CancellationException) { throw e }
                            catch (e: Exception) { error = e.message ?: "Could not analyse slides" }
                            finally { busy = false }
                        }
                    }) { Text("Analyse teaching method") }
                    Button(
                        enabled = !busy && draft != saved && draft.length <= 50000,
                        shape = RoundedCornerShape(50),
                        onClick = {
                            scope.launch {
                                busy = true; error = ""; savedNotice = ""
                                try {
                                    withContext(Dispatchers.IO) {
                                        request(base, "/style-profile", token, JSONObject().put("content", draft), method = "PUT")
                                    }
                                    saved = draft
                                    savedNotice = "Saved for the whole app. All subjects will use this teaching method."
                                } catch (e: CancellationException) { throw e } catch (e: Exception) {
                                    error = "Could not save: ${e.message ?: "request failed"}"
                                } finally { busy = false }
                            }
                        },
                    ) { Text("Save style") }
                    if (draft != saved) OutlinedButton(shape = RoundedCornerShape(50), enabled = !busy, onClick = { draft = saved; savedNotice = "" }) { Text("Revert") }
                }
            }
        }
    }
}

@Composable
private fun SettingsIcon(tint: Color, modifier: Modifier = Modifier) {
    androidx.compose.foundation.Canvas(modifier) {
        val w = size.width; val h = size.height
        val stroke = androidx.compose.ui.graphics.drawscope.Stroke(width = w * 0.1f, cap = androidx.compose.ui.graphics.StrokeCap.Round)
        val centre = androidx.compose.ui.geometry.Offset(w / 2f, h / 2f)
        val outer = w * 0.3f; val inner = w * 0.13f
        // Six spokes plus two rings read as a settings gear at this size.
        repeat(6) { index ->
            val angle = Math.toRadians(index * 60.0)
            val dx = Math.cos(angle).toFloat(); val dy = Math.sin(angle).toFloat()
            drawLine(tint, androidx.compose.ui.geometry.Offset(centre.x + dx * outer, centre.y + dy * outer), androidx.compose.ui.geometry.Offset(centre.x + dx * (outer + w * 0.12f), centre.y + dy * (outer + w * 0.12f)), strokeWidth = w * 0.1f, cap = androidx.compose.ui.graphics.StrokeCap.Round)
        }
        drawCircle(tint, radius = outer, center = centre, style = stroke)
        drawCircle(tint, radius = inner, center = centre, style = stroke)
    }
}

/** Account and app information, kept out of the main screen. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsSheet(
    base: String,
    token: String,
    signedIn: Boolean,
    busy: Boolean,
    dark: Boolean,
    onDismiss: () -> Unit,
    onSignOut: () -> Unit,
    canSignOut: Boolean,
    subjectCount: Int,
    topicCount: Int,
) {
    var page by remember { mutableStateOf("") }
    androidx.compose.ui.window.Dialog(onDismissRequest = { if (page.isNotEmpty()) page = "" else onDismiss() }, properties = androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { if (page.isNotEmpty()) page = "" else onDismiss() }) { Text("‹ Back") }
                Text(page.ifEmpty { "Settings" }, style = MaterialTheme.typography.titleLarge)
            }
            if (page.isEmpty()) {
                Text("App", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary, modifier = Modifier.padding(top = 8.dp, start = 16.dp))
                Surface(shape = RoundedCornerShape(16.dp), color = LocalStudyColours.current.container) {
                    Column {
                        listOf("Account" to "Sign-in and server", "Appearance & library" to "System theme and your resources", "About" to "About StudyGuider").forEachIndexed { index, (title, detail) ->
                            if (index > 0) HorizontalDivider(Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
                            ListItem(headlineContent = { Text(title) }, supportingContent = { Text(detail) }, trailingContent = { Text("›", style = MaterialTheme.typography.titleLarge) }, modifier = Modifier.clickable { page = title }, colors = ListItemDefaults.colors(containerColor = Color.Transparent))
                        }
                    }
                }
            }
            if (page == "Account") {
            StudyCard(tone = CardTone.Container) {
                SectionLabel("Account", if (signedIn) "SIGNED IN" else "SIGNED OUT")
                Text(if (signedIn) "You are signed in to this server." else "Sign in to load your own resources.", style = MaterialTheme.typography.bodyMedium)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (signedIn) StatusDot(LocalStudyColours.current.teal, "Session encrypted on this device")
                }
                Text(base, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
            }
            }
            if (page == "Appearance & library") {
            StudyCard(tone = CardTone.Low) {
                SectionLabel("Library", "YOUR CONTENT")
                Text("$subjectCount subject(s) · $topicCount topic(s) loaded", style = MaterialTheme.typography.bodyMedium)
                Text(if (dark) "Appearance: dark (follows the system)" else "Appearance: light (follows the system)", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            }
            if (page == "About") {
            StudyCard(tone = CardTone.Low) {
                SectionLabel("About", "STUDYGUIDER")
                Text("NCEA study companion. Lessons are drafts: check them against the cited sources.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            }
            if (page == "Account") {
            OutlinedButton(
                onClick = onSignOut,
                enabled = canSignOut,
                shape = RoundedCornerShape(50),
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
            ) { Text("Sign out") }
            if (signedIn && !canSignOut) Text("Finish or discard your exam answers before signing out.", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        }
    }
}

@Composable
private fun ResourceHub(
    base: String, token: String, subjects: JSONArray, topics: JSONArray, resources: JSONArray,
    selected: Long, selectedTopic: Long, subjectTitle: String, topicTitle: String, topicSourceId: String,
    refreshError: String, busy: Boolean,
    subjectName: String, onSubjectName: (String) -> Unit, subjectLevel: String, onSubjectLevel: (String) -> Unit,
    topicName: String, onTopicName: (String) -> Unit, showAddSubject: Boolean, onToggleAddSubject: () -> Unit,
    onOpenSubject: (Long, String) -> Unit, onOpenTopic: (Long, String) -> Unit, onBack: () -> Unit,
    onAddSubject: () -> Unit, onAddTopic: () -> Unit, onUpload: () -> Unit, uploadNotice: String, onRefresh: () -> Unit,
    onExtract: (String, Boolean) -> Unit, onOpenPdf: (String) -> Unit, onClosePdf: () -> Unit,
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (selected != 0L) TextButton(enabled = !busy, onClick = onBack) { Text(if (selectedTopic != 0L) "‹ $subjectTitle" else "‹ Subjects") }
        when {
            selected == 0L -> {
                Text("Resource Hub", style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.primary)
                Text("Choose a subject to explore its topics and resources.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (subjects.length() == 0) StudyCard(tone = CardTone.Low) { Text("No subjects yet. Add one below to get started.") }
                for (i in 0 until subjects.length()) {
                    val subject = subjects.getJSONObject(i)
                    Surface(shape = RoundedCornerShape(16.dp), color = LocalStudyColours.current.container, modifier = Modifier.fillMaxWidth().clickable(enabled = !busy, onClickLabel = "Open ${subject.getString("name")}") { onOpenSubject(subject.getLong("id"), subject.getString("name")) }) {
                        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("NCEA LEVEL ${subject.getInt("level")}", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.secondary)
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                Text(subject.getString("name"), style = MaterialTheme.typography.headlineSmall)
                                Text("↗", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
                            }
                            Text("Explore topics & resources", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                OutlinedButton(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(50), onClick = onToggleAddSubject) { Text(if (showAddSubject) "Cancel" else "+  Add a subject") }
                if (showAddSubject) StudyCard(tone = CardTone.Low) {
                    OutlinedTextField(subjectName, onSubjectName, label = { Text("New subject") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(subjectLevel, onSubjectLevel, label = { Text("NCEA level (1–3)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Button(enabled = !busy && subjectName.isNotBlank(), onClick = onAddSubject, shape = RoundedCornerShape(50)) { Text("Add subject") }
                }
            }
            selectedTopic == 0L -> {
                Text("$subjectTitle · Topics", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
                Text("Choose a topic to open its resources and lessons.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                for (i in 0 until topics.length()) {
                    val topic = topics.getJSONObject(i)
                    Surface(shape = RoundedCornerShape(16.dp), color = LocalStudyColours.current.container, modifier = Modifier.fillMaxWidth().clickable(enabled = !busy, onClickLabel = "Open ${topic.getString("name")}") { onOpenTopic(topic.getLong("id"), topic.getString("name")) }) {
                        Column(Modifier.padding(16.dp)) {
                            Text(topic.getString("name"), style = MaterialTheme.typography.titleMedium)
                            Text("View resources →", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.secondary)
                        }
                    }
                }
                StudyCard(tone = CardTone.Low) {
                    OutlinedTextField(topicName, onTopicName, label = { Text("New topic") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Button(enabled = !busy && topicName.isNotBlank(), onClick = onAddTopic, shape = RoundedCornerShape(50)) { Text("Add topic") }
                }
            }
            else -> {
                Text("$topicTitle · Resources", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
                if (topicSourceId.isNotEmpty()) {
                    TextButton(onClick = onClosePdf) { Text("‹ Close PDF") }
                    SourceScreen(base, token, topicSourceId)
                }
                if (refreshError.isNotEmpty()) Text(refreshError, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                if (uploadNotice.isNotEmpty()) StudyChip(uploadNotice, MaterialTheme.colorScheme.onSecondaryContainer, MaterialTheme.colorScheme.secondaryContainer)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = !busy, onClick = onUpload, shape = RoundedCornerShape(50), modifier = Modifier.weight(1f)) { Text("Upload files") }
                    OutlinedButton(enabled = !busy, onClick = onRefresh, shape = RoundedCornerShape(50), modifier = Modifier.weight(1f)) { Text("Refresh") }
                }
                if (resources.length() == 0) StudyCard(tone = CardTone.Low) { Text("No resources yet. Upload a PDF, slide deck or photo to begin.", style = MaterialTheme.typography.bodyMedium) }
                for (i in 0 until resources.length()) {
                    val item = resources.getJSONObject(i)
                    val status = item.optString("display_status", item.getString("status"))
                    StudyCard(tone = CardTone.Container) {
                        Text(item.getString("filename"), style = MaterialTheme.typography.titleMedium, maxLines = 2)
                        StatusDot(when (item.optString("status")) {
                            "extracted" -> LocalStudyColours.current.achieved
                            "failed" -> MaterialTheme.colorScheme.error
                            "pending", "extracting" -> LocalStudyColours.current.amber
                            else -> LocalStudyColours.current.outline
                        }, status)
                        if (item.getString("filename").endsWith(".pdf", ignoreCase = true)) OutlinedButton(shape = RoundedCornerShape(50), onClick = { onOpenPdf(item.getString("id")) }) { Text("Open PDF") }
                        if (item.optString("status") == "failed") Text("Extraction failed. Retry to see the error.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        TextButton(enabled = !busy, onClick = { onExtract(item.getString("id"), item.optString("status") == "failed") }) { Text(if (item.optString("status") == "failed") "Retry extraction" else "Extract text") }
                    }
                }
            }
        }
    }
}
