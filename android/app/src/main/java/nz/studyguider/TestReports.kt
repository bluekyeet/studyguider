package nz.studyguider

import android.app.Activity
import android.graphics.Bitmap
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.PixelCopy
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import kotlin.coroutines.resume
import kotlin.math.roundToInt

/**
 * "Report a problem" in the test build (BuildConfig.TEST_SYSTEM; docs/test-system.md, server/reports.py). A small bubble, which can
 * be dragged out of the way, sends what the tester wrote with the screen they were on, the phone and app version, recent failed
 * requests, the app's own recent log and a screenshot taken just before the form opened. If the app crashed, the next start
 * offers to report the crash with its stack trace. In the normal build none of this appears.
 */
object TestReports {
    // State, so the bubble appears once someone signs in.
    var base by mutableStateOf("")
    var token by mutableStateOf("")
    var screen by mutableStateOf("")
    private val recent = ArrayDeque<JSONObject>()

    fun recordError(method: String, path: String, status: Int, detail: String) {
        if (!BuildConfig.TEST_SYSTEM || path.startsWith("/reports")) return
        synchronized(recent) {
            recent.addLast(JSONObject().put("at", java.time.Instant.now().toString()).put("method", method).put("path", path)
                .put("status", status).put("detail", detail.take(500)))
            while (recent.size > 30) recent.removeFirst()
        }
    }

    fun recentErrors(): JSONArray = synchronized(recent) { JSONArray(recent.toList()) }

    private fun crashFile(activity: Activity) = File(activity.filesDir, "last-crash.txt")

    /** Keeps the stack trace of a crash for the next start, then lets Android handle the crash as usual. */
    fun watchForCrashes(activity: Activity) {
        if (!BuildConfig.TEST_SYSTEM) return
        val file = crashFile(activity)
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching { file.writeText("Screen: $screen\n" + error.stackTraceToString().take(20000)) }
            previous?.uncaughtException(thread, error)
        }
    }

    fun takeCrash(activity: Activity): String? = crashFile(activity).takeIf { it.exists() }?.let { file ->
        runCatching { file.readText() }.getOrNull().also { file.delete() }
    }

    fun deviceText(activity: Activity): String {
        val metrics = activity.resources.configuration
        return "${Build.MANUFACTURER} ${Build.MODEL}, Android ${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT}), " +
            "${metrics.screenWidthDp}×${metrics.screenHeightDp} dp, font ×${metrics.fontScale}, theme ${Appearance.mode}"
    }

    /** The app's own recent log lines (an app can always read its own). */
    fun ownLog(): String = runCatching {
        val process = Runtime.getRuntime().exec(arrayOf("logcat", "-d", "-t", "300", "--pid", android.os.Process.myPid().toString()))
        process.inputStream.bufferedReader().use { it.readText() }.takeLast(60000)
    }.getOrDefault("")

    suspend fun screenshot(activity: Activity): Bitmap? = suspendCancellableCoroutine { done ->
        val view = activity.window.decorView
        if (view.width == 0 || view.height == 0) { done.resume(null); return@suspendCancellableCoroutine }
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        runCatching {
            PixelCopy.request(activity.window, bitmap, { result -> done.resume(if (result == PixelCopy.SUCCESS) bitmap else null) }, Handler(Looper.getMainLooper()))
        }.onFailure { done.resume(null) }
    }
}

/** The app with the report bubble over it in the test build; just the app otherwise. */
@Composable
fun TestSystemOverlay(content: @Composable () -> Unit) {
    if (!BuildConfig.TEST_SYSTEM) { content(); return }
    val activity = LocalContext.current as? Activity
    val scope = rememberCoroutineScope()
    var open by remember { mutableStateOf(false) }
    var shot by remember { mutableStateOf<Bitmap?>(null) }
    var crash by remember { mutableStateOf<String?>(null) }
    var offset by remember { mutableStateOf(IntOffset(0, 0)) }
    LaunchedEffect(Unit) { activity?.let { a -> TestReports.takeCrash(a)?.let { crash = it; open = true } } }
    val height = LocalConfiguration.current.screenHeightDp
    Box(Modifier.fillMaxSize()) {
        content()
        if (TestReports.token.isNotEmpty()) {
            Surface(
                shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.tertiaryContainer, shadowElevation = 6.dp,
                modifier = Modifier.align(Alignment.CenterStart).offset { offset }.padding(start = 4.dp, top = (height / 6).dp)
                    .pointerInput(Unit) { detectDragGestures { change, drag -> change.consume(); offset = IntOffset(offset.x + drag.x.roundToInt(), offset.y + drag.y.roundToInt()) } },
                onClick = { scope.launch { shot = activity?.let { TestReports.screenshot(it) }; open = true } },
            ) { Text("Report", Modifier.padding(horizontal = 12.dp, vertical = 8.dp), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onTertiaryContainer) }
        }
    }
    if (open && activity != null) ReportDialog(activity, shot, crash) { open = false; shot = null; crash = null }
}

@Composable
private fun ReportDialog(activity: Activity, shot: Bitmap?, crash: String?, close: () -> Unit) {
    val scope = rememberCoroutineScope()
    var text by remember { mutableStateOf(if (crash != null) "The app closed unexpectedly. I was doing: " else "") }
    var withShot by remember { mutableStateOf(shot != null) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("") }
    var sent by remember { mutableStateOf<Long?>(null) }
    val screen = remember { TestReports.screen }
    AlertDialog(
        onDismissRequest = { if (!busy) close() },
        title = { Text(if (sent != null) "Thank you" else if (crash != null) "Report the crash" else "Report a problem") },
        text = {
            if (sent != null) Text("Report #$sent is saved. It will be looked at with the others.")
            else Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (TestReports.token.isEmpty()) Text("Sign in first, then send the report.", color = MaterialTheme.colorScheme.error)
                OutlinedTextField(text, { text = it.take(5000) }, Modifier.fillMaxWidth().heightIn(min = 120.dp), enabled = !busy,
                    label = { Text("What went wrong") }, placeholder = { Text("What did you do, what happened, and what did you expect instead?") })
                if (shot != null) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(withShot, { withShot = it }, enabled = !busy); Text("Include this screenshot")
                    }
                    if (withShot) Image(shot.asImageBitmap(), "Screenshot to send", Modifier.fillMaxWidth().heightIn(max = 220.dp).background(MaterialTheme.colorScheme.surfaceVariant))
                }
                Text("Also sent: the screen ($screen), your phone and app version, recent errors and the app's recent log${if (crash != null) ", and the crash details" else ""}.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (message.isNotEmpty()) Text(message, color = MaterialTheme.colorScheme.error)
            }
        },
        confirmButton = {
            if (sent != null) TextButton(onClick = close) { Text("Close") }
            else TextButton(enabled = !busy && text.isNotBlank() && TestReports.token.isNotEmpty(), onClick = {
                busy = true; message = ""
                scope.launch {
                    try {
                        val context = JSONObject().put("errors", TestReports.recentErrors()).put("log", withContext(Dispatchers.IO) { TestReports.ownLog() })
                        if (crash != null) context.put("crash", crash)
                        val png = if (withShot && shot != null) withContext(Dispatchers.Default) {
                            java.io.ByteArrayOutputStream().also { shot.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray()
                        } else null
                        val result = JSONObject(Api(TestReports.base, TestReports.token).multipart("/reports", mapOf(
                            "description" to text, "client" to "android", "screen" to screen, "app_version" to BuildConfig.VERSION_NAME,
                            "device" to TestReports.deviceText(activity), "context" to context.toString()),
                            listOfNotNull(png?.let { Api.Part("screenshot", "screenshot.png", "image/png", it) })))
                        sent = result.getLong("id")
                    } catch (e: CancellationException) { throw e } catch (e: Exception) { message = "Could not send: ${e.message ?: "request failed"}" }
                    finally { busy = false }
                }
            }) { Text(if (busy) "Sending…" else "Send") }
        },
        dismissButton = { if (sent == null) TextButton(enabled = !busy, onClick = close) { Text("Cancel") } },
    )
}
