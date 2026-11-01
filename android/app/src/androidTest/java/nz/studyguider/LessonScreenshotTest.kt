package nz.studyguider

import android.graphics.Bitmap
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.Tab
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.net.InetAddress
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LessonScreenshotTest {
    @get:Rule val compose = createComposeRule()

    @Test fun capturesSyntheticLesson() {
        ServerSocket(0, 1, InetAddress.getByName("127.0.0.1")).use { server ->
            server.soTimeout = 15000
            val executor = Executors.newSingleThreadExecutor()
            try {
                val request = executor.submit {
                    server.accept().use { socket ->
                        socket.soTimeout = 15000
                        val input = socket.getInputStream().bufferedReader()
                        check(input.readLine().startsWith("GET /topics/1/lessons "))
                        while (!input.readLine().isNullOrEmpty()) { }
                        val body = """[{"id":7,"query":"Synthetic waves","created_at":"today","lesson":"A wave transfers energy from one place to another.","review":"Synthetic review","warning":"Example only","sources":[]}]""".toByteArray(Charsets.UTF_8)
                        socket.getOutputStream().apply {
                            write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${body.size}\r\nConnection: close\r\n\r\n".toByteArray())
                            write(body)
                            flush()
                        }
                    }
                }
                compose.setContent {
                    MaterialTheme(colorScheme = lightColorScheme(primary = Color(0xFF1E3A8A), surface = Color(0xFFFBF8FF))) {
                        Surface(Modifier.fillMaxSize()) {
                            Column(Modifier.padding(top = 32.dp)) {
                                Text("STUDYGUIDER", Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                                Text("Your study space", Modifier.padding(horizontal = 20.dp, vertical = 8.dp), style = MaterialTheme.typography.headlineMedium)
                                ScrollableTabRow(selectedTabIndex = 1) {
                                    listOf("Study", "Lessons", "Reviews", "Exams").forEachIndexed { index, title ->
                                        Tab(selected = index == 1, onClick = {}, text = { Text(title) })
                                    }
                                }
                                Column(Modifier.fillMaxWidth().weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)) {
                                    LessonScreen("http://127.0.0.1:${server.localPort}", "fake-token", 1, "Waves", "Physics", emptyList(), { _, _ -> }, {})
                                }
                            }
                        }
                    }
                }
                compose.waitUntil(15000) { compose.onAllNodesWithText("Synthetic waves · today").fetchSemanticsNodes().isNotEmpty() }
                compose.onNodeWithText("Synthetic waves · today").performScrollTo().performClick()
                compose.onNodeWithText("A wave transfers energy from one place to another.").performScrollTo().assertExists()
                compose.waitForIdle()
                val instrumentation = InstrumentationRegistry.getInstrumentation()
                val directory = checkNotNull(instrumentation.targetContext.getExternalFilesDir(null))
                val bitmap = checkNotNull(instrumentation.uiAutomation.takeScreenshot())
                File(directory, "synthetic-lesson.png").outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) }
                bitmap.recycle()
                request.get(5, TimeUnit.SECONDS)
            } finally {
                server.close()
                executor.shutdownNow()
            }
        }
    }
}
