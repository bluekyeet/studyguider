package nz.studyguider

import android.graphics.Bitmap
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.Modifier
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
                compose.setContent { MaterialTheme { Column(Modifier.verticalScroll(rememberScrollState())) { LessonScreen("http://127.0.0.1:${server.localPort}", "fake-token", 1) } } }
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
