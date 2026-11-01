package nz.studyguider

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LessonDeletionTest {
    @get:Rule val compose = createComposeRule()

    @Test fun deletesOnlyAfterConfirmation() {
        ServerSocket(0).use { server ->
            server.soTimeout = 15000
            val executor = Executors.newSingleThreadExecutor()
            try {
                val requests = executor.submit<List<String>> {
                    val seen = mutableListOf<String>()
                    repeat(2) { index ->
                        server.accept().use { socket ->
                            socket.soTimeout = 15000
                            val input = socket.getInputStream().bufferedReader()
                            val first = input.readLine(); seen.add(first)
                            var authenticated = false
                            while (true) {
                                val line = input.readLine() ?: break
                                if (line.isEmpty()) break
                                if (line.equals("Authorization: Bearer fake-token", ignoreCase = true)) authenticated = true
                            }
                            check(authenticated)
                            val body = if (index == 0) """[{"id":7,"query":"Waves","created_at":"today","lesson":"Example lesson","review":"Check","review_status":"completed","warning":"Not verified","sources":[]}]""" else """{"status":"ok"}"""
                            val bytes = body.toByteArray()
                            socket.getOutputStream().apply { write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray()); write(bytes); flush() }
                        }
                    }
                    seen
                }
                compose.setContent { Column(Modifier.verticalScroll(rememberScrollState())) { LessonScreen("http://127.0.0.1:${server.localPort}", "fake-token", 1, "Waves", "Physics", emptyList(), { _, _ -> }, {}) } }
                compose.waitUntil(15000) { compose.onAllNodesWithText("Waves · today").fetchSemanticsNodes().isNotEmpty() }
                compose.onNodeWithText("Waves · today").performScrollTo().performClick()
                compose.onNodeWithText("Delete lesson").performScrollTo().performClick()
                compose.onNodeWithText("Cancel").performClick()
                compose.onNodeWithText("Delete lesson").performScrollTo().performClick()
                compose.onNodeWithText("Delete", useUnmergedTree = true).performClick()
                compose.waitUntil(15000) { compose.onAllNodesWithText("No saved lessons yet.").fetchSemanticsNodes().isNotEmpty() }
                compose.onNodeWithText("Example lesson").assertDoesNotExist()
                val seen = requests.get(5, TimeUnit.SECONDS)
                assertTrue(seen[0].startsWith("GET /topics/1/lessons"))
                assertTrue(seen[1].startsWith("DELETE /lessons/7"))
            } finally { server.close(); executor.shutdownNow() }
        }
    }
}
