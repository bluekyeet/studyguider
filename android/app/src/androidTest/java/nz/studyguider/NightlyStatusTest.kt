package nz.studyguider

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import java.net.ServerSocket
import java.util.concurrent.Executors

class NightlyStatusTest {
    @get:Rule val compose = createComposeRule()

    @Test fun failedNightlyRunShowsRecordedError() {
        ServerSocket(0).use { server ->
            val worker = Executors.newSingleThreadExecutor()
            try {
                worker.submit {
                    server.accept().use { socket ->
                        socket.soTimeout = 10000
                        val reader = socket.getInputStream().bufferedReader()
                        check(reader.readLine() == "GET /topics/2/schedule/runs HTTP/1.1")
                        while (reader.readLine().isNotEmpty()) { }
                        val body = """[{"run_date":"2026-11-02","status":"failed","error":"Model unavailable","lesson_id":null}]"""
                        socket.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${body.length}\r\nConnection: close\r\n\r\n$body".toByteArray())
                    }
                }
                compose.setContent { NightlyStatus("http://127.0.0.1:${server.localPort}", "test-token", JSONObject().put("topic_id", 2).put("topic", "Waves"), {}) }
                compose.waitUntil(10000) {
                    runCatching { compose.onNodeWithText("Model unavailable").assertExists() }.isSuccess
                }
                compose.onNodeWithText("2026-11-02 · failed").assertExists()
            } finally { worker.shutdownNow() }
        }
    }
}
