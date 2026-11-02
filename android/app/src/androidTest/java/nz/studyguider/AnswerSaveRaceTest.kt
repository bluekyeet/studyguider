package nz.studyguider

import androidx.compose.foundation.layout.Column
import androidx.compose.material3.OutlinedTextField
import androidx.compose.runtime.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performTextReplacement
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import java.net.ServerSocket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class AnswerSaveRaceTest {
    @get:Rule val compose = createComposeRule()

    @Test fun typingWhilePutInFlightUsesAcknowledgedRevisionForNextPut() {
        val started = CountDownLatch(1)
        val release = CountDownLatch(1)
        val writes = mutableListOf<JSONObject>()
        ServerSocket(0).use { server ->
            val worker = Executors.newSingleThreadExecutor()
            try {
                val served = worker.submit {
                    repeat(3) { index ->
                        server.accept().use { socket ->
                            socket.soTimeout = 15000
                            val input = socket.getInputStream()
                            fun line(): String {
                                val bytes = mutableListOf<Byte>()
                                while (true) { val b = input.read(); check(b >= 0); if (b == 10) break; if (b != 13) bytes.add(b.toByte()) }
                                return bytes.toByteArray().toString(Charsets.UTF_8)
                            }
                            val method = line().substringBefore(' ')
                            var length = 0
                            while (true) {
                                val header = line(); if (header.isEmpty()) break
                                if (header.startsWith("Content-Length:", true)) length = header.substringAfter(':').trim().toInt()
                            }
                            val body = if (method == "GET") "[]" else {
                                val json = JSONObject(input.readNBytes(length).toString(Charsets.UTF_8))
                                writes.add(json)
                                if (index == 1) { started.countDown(); check(release.await(15, TimeUnit.SECONDS)) }
                                "{\"revision\":$index}"
                            }
                            socket.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Length: ${body.toByteArray().size}\r\nConnection: close\r\n\r\n$body".toByteArray())
                        }
                    }
                }
                compose.setContent {
                    var answer by remember { mutableStateOf("") }
                    Column {
                        val loaded = SavedAnswer("http://127.0.0.1:${server.localPort}", "test-token", 987654321, "Synthetic race question", answer, "", { answer = it }, {})
                        OutlinedTextField(answer, { answer = it }, enabled = loaded, label = { androidx.compose.material3.Text("Race answer") })
                    }
                }
                compose.waitForIdle()
                compose.onNodeWithText("Race answer").performTextReplacement("First draft")
                compose.mainClock.advanceTimeBy(1000)
                compose.waitUntil(15000) { started.count == 0L }
                compose.onNodeWithText("Race answer").performTextReplacement("Latest draft typed during save")
                release.countDown()
                compose.mainClock.advanceTimeBy(2000)
                served.get(20, TimeUnit.SECONDS)
                compose.waitUntil(10000) { runCatching { compose.onNodeWithText("Saved to server").assertExists() }.isSuccess }
                assertEquals(2, writes.size)
                assertEquals(0, writes[0].getInt("revision"))
                assertEquals(1, writes[1].getInt("revision"))
                assertEquals("Latest draft typed during save", writes[1].getString("answer"))
            } finally { release.countDown(); worker.shutdownNow() }
        }
    }
}
