package nz.studyguider

import android.graphics.Bitmap
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LoginHomeTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun signInLoadsSubjects() {
        ServerSocket(0).use { server ->
            server.soTimeout = 15000
            val executor = Executors.newSingleThreadExecutor()
            try {
                val requests = executor.submit<List<Pair<String, String>>> {
                    listOf("{\"token\":\"fake-token\"}", "[{\"id\":1,\"name\":\"Physics\",\"level\":2}]").map { response ->
                        server.accept().use { socket ->
                            socket.soTimeout = 15000
                            val input = socket.getInputStream().buffered()
                            val headers = StringBuilder()
                            while (!headers.endsWith("\r\n\r\n")) {
                                val byte = input.read()
                                check(byte >= 0) { "Incomplete request headers" }
                                headers.append(byte.toChar())
                            }
                            val length = Regex("(?im)^Content-Length: (\\d+)\\r?$").find(headers)?.groupValues?.get(1)?.toInt() ?: 0
                            val body = ByteArray(length)
                            var offset = 0
                            while (offset < length) {
                                val count = input.read(body, offset, length - offset)
                                check(count > 0) { "Incomplete request body" }
                                offset += count
                            }
                            val bytes = response.toByteArray(Charsets.UTF_8)
                            socket.getOutputStream().apply {
                                write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray())
                                write(bytes)
                                flush()
                            }
                            headers.toString() to body.toString(Charsets.UTF_8)
                        }
                    }
                }
                compose.onNodeWithText("Make progress, one topic at a time.").assertIsDisplayed()
                compose.onNodeWithText("Server URL").performTextClearance()
                compose.onNodeWithText("Server URL").performTextInput("http://127.0.0.1:${server.localPort}")
                compose.onNodeWithText("Password").performTextInput("secret")
                compose.onNodeWithText("Sign in").performClick()
                compose.waitUntil(20000) { compose.onAllNodesWithText("Physics — Level 2").fetchSemanticsNodes().isNotEmpty() }
                compose.onNodeWithText("Your study space").assertIsDisplayed()
                compose.onNodeWithText("Subjects").assertIsDisplayed()
                compose.onNodeWithText("Physics — Level 2").assertIsDisplayed()
                compose.waitForIdle()
                val instrumentation = InstrumentationRegistry.getInstrumentation()
                val directory = checkNotNull(instrumentation.targetContext.getExternalFilesDir(null))
                val screenshot = checkNotNull(instrumentation.uiAutomation.takeScreenshot())
                File(directory, "synthetic-home.png").outputStream().use { check(screenshot.compress(Bitmap.CompressFormat.PNG, 100, it)) }
                screenshot.recycle()
                val received = requests.get(5, TimeUnit.SECONDS)
                assertTrue(received[0].first.startsWith("POST /login HTTP/1.1\r\n"))
                assertEquals("secret", JSONObject(received[0].second).getString("password"))
                assertTrue(received[1].first.startsWith("GET /subjects HTTP/1.1\r\n"))
                assertTrue(received[1].first.contains("Authorization: Bearer fake-token", ignoreCase = true))
            } finally {
                server.close()
                executor.shutdownNow()
            }
        }
    }
}
