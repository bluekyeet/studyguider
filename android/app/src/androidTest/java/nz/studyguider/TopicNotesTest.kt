package nz.studyguider

import androidx.compose.foundation.layout.Column
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Rule
import org.junit.Test
import java.net.ServerSocket
import java.util.concurrent.Executors

class TopicNotesTest {
    @get:Rule val compose = createComposeRule()

    @Test fun chooseTopicLoadsAndDeletesNoteAfterConfirmation() {
        ServerSocket(0).use { server ->
            val worker = Executors.newSingleThreadExecutor()
            try {
                worker.submit {
                    repeat(4) {
                        server.accept().use { socket ->
                            socket.soTimeout = 10000
                            val reader = socket.getInputStream().bufferedReader()
                            val request = reader.readLine().split(' ')
                            val path = request[1]
                            while (reader.readLine().isNotEmpty()) { }
                            val body = when (path) {
                                "/subjects" -> """[{"id":1,"name":"Physics"}]"""
                                "/subjects/1/topics" -> """[{"id":2,"name":"Waves"}]"""
                                "/topics/2/notes" -> """[{"id":42,"content":"# Saved explanation","created_at":"2026-11-02"}]"""
                                "/topics/2/notes/42" -> {
                                    check(request[0] == "DELETE")
                                    ""
                                }
                                else -> error("Unexpected path $path")
                            }
                            socket.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${body.length}\r\nConnection: close\r\n\r\n$body".toByteArray())
                        }
                    }
                }
                compose.setContent { Column { TopicNotes("http://127.0.0.1:${server.localPort}", "test-token") } }
                compose.waitForIdle()
                compose.onNodeWithText("Choose a topic").performClick()
                compose.waitUntil(10000) {
                    runCatching { compose.onNodeWithText("Physics · Waves").assertExists() }.isSuccess
                }
                compose.onNodeWithText("Physics · Waves").performClick()
                compose.waitUntil(10000) {
                    runCatching { compose.onNodeWithText("Saved explanation").assertExists() }.isSuccess
                }
                compose.onNodeWithText("Delete").performClick()
                compose.onNodeWithText("Cancel").performClick()
                compose.onNodeWithText("Saved explanation").assertExists()
                compose.onNodeWithText("Delete").performClick()
                compose.onNodeWithText("Delete note").performClick()
                compose.waitUntil(10000) {
                    runCatching { compose.onNodeWithText("No notes saved for this topic yet.").assertExists() }.isSuccess
                }
            } finally { worker.shutdownNow() }
        }
    }
}
