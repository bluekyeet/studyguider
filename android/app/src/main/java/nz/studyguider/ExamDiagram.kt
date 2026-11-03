package nz.studyguider

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL

fun requestsDiagram(text: String): Boolean = Regex("\\b(draw|sketch|plot|label|complete the diagram|Lewis structure|force diagram)\\b", RegexOption.IGNORE_CASE).containsMatchIn(text)

@Composable
fun ExamDiagram(base: String, token: String, examId: Long, questionId: Long, enabled: Boolean, onAttached: (String, Int) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var drawing by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    suspend fun attach(bytes: ByteArray) {
        if (bytes.size > 10 * 1024 * 1024) throw IllegalStateException("Image exceeds 10 MiB")
        val response = withContext(Dispatchers.IO) {
            val boundary = "diagram-${java.util.UUID.randomUUID()}"
            val c = URL(base.trimEnd('/') + "/exams/$examId/answers/$questionId/scan").openConnection() as HttpURLConnection
            try {
                c.connectTimeout = 10000; c.readTimeout = 200000; c.requestMethod = "POST"; c.doOutput = true
                c.setRequestProperty("Authorization", "Bearer $token")
                c.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
                c.outputStream.use {
                    it.write("--$boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"diagram.png\"\r\nContent-Type: application/octet-stream\r\n\r\n".toByteArray())
                    it.write(bytes); it.write("\r\n--$boundary--\r\n".toByteArray())
                }
                if (c.responseCode !in 200..299) throw IllegalStateException("Diagram upload failed (${c.responseCode})")
                JSONObject(c.inputStream.bufferedReader().use { it.readText() })
            } finally { c.disconnect() }
        }
        onAttached(response.getString("transcription"), response.getInt("scan_revision"))
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) scope.launch {
            busy = true; error = ""
            try {
                val bytes = withContext(Dispatchers.IO) { context.contentResolver.openInputStream(uri)?.use { it.readNBytes(10 * 1024 * 1024 + 1) } ?: throw IllegalStateException("Cannot open image") }
                attach(bytes)
            } catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { error = e.message ?: "Could not attach diagram" }
            finally { busy = false }
        }
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(enabled = enabled && !busy, onClick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }) { Text("Insert image") }
        OutlinedButton(enabled = enabled && !busy, onClick = { drawing = true }) { Text("Draw diagram") }
    }
    Text("One image per question. A new image replaces the previous one. Check the recognition, then Save & mark.", style = MaterialTheme.typography.bodySmall)
    if (busy) LoadingBar(Modifier.fillMaxWidth())
    if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
    if (drawing) {
        val bitmap = remember { Bitmap.createBitmap(1000, 1000, Bitmap.Config.ARGB_8888).apply { eraseColor(android.graphics.Color.WHITE) } }
        val canvas = remember { Canvas(bitmap) }
        val paint = remember { Paint(Paint.ANTI_ALIAS_FLAG).apply { color = android.graphics.Color.BLACK; strokeWidth = 4f; strokeCap = Paint.Cap.ROUND } }
        var revision by remember { mutableIntStateOf(0) }
        var hasInk by remember { mutableStateOf(false) }
        AlertDialog(onDismissRequest = { if (!busy) drawing = false }, title = { Text("Draw your answer") }, text = {
            Column {
                Text("Draw labels and question-part numbers too. This canvas is a draft until uploaded.", style = MaterialTheme.typography.bodySmall)
                AndroidView(factory = { android.widget.ImageView(it).apply { setImageBitmap(bitmap) } }, update = { revision; it.invalidate() }, modifier = Modifier.fillMaxWidth().aspectRatio(1f).background(Color.White).pointerInput(Unit) {
                    detectDragGestures { change, amount ->
                        change.consume()
                        val x = change.position.x * 1000 / size.width
                        val y = change.position.y * 1000 / size.height
                        canvas.drawLine(x - amount.x * 1000 / size.width, y - amount.y * 1000 / size.height, x, y, paint)
                        hasInk = true; revision++
                    }
                })
                TextButton(enabled = !busy, onClick = { bitmap.eraseColor(android.graphics.Color.WHITE); revision++; hasInk = false }) { Text("Clear") }
            }
        }, confirmButton = { TextButton(enabled = hasInk && !busy, onClick = {
            scope.launch {
                busy = true; error = ""
                try { val out = ByteArrayOutputStream(); bitmap.compress(Bitmap.CompressFormat.PNG, 100, out); attach(out.toByteArray()); drawing = false }
                catch (e: kotlinx.coroutines.CancellationException) { throw e }
                catch (e: Exception) { error = e.message ?: "Could not upload drawing" }
                finally { busy = false }
            }
        }) { Text(if (busy) "Uploading…" else "Attach drawing") } }, dismissButton = { TextButton(enabled = !busy, onClick = { drawing = false }) { Text("Cancel") } })
    }
}
