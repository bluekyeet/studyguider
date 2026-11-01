package nz.studyguider

import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class ExplanationNoteTest {
    @Test fun hidesOnlySourceMarkersWithoutChangingMaths() {
        assertEquals("Rate increases. Next.", withoutSourceMarkers("Rate increases [S1]. Next [S2 p. 6; S3 p. 1]."))
        assertEquals("[Na+] and [0, 1] with \$x_{1}$", withoutSourceMarkers("[Na+] and [0, 1] with \$x_{1}$"))
    }
    @Test fun savesExactDisplayedExplanationWithoutModelRequest() = runBlocking {
        val content = "Lesson 18 - Why?\n\nFrequency is constant: $ f = 0.4 $ Hz.\n\nAI-generated; not verified."
        ServerSocket(0).use { server ->
            val worker = Executors.newSingleThreadExecutor()
            try {
                val received = worker.submit<String> {
                    server.accept().use { socket ->
                        socket.soTimeout = 10000
                        val reader = socket.getInputStream().bufferedReader()
                        assertEquals("POST /topics/2/notes HTTP/1.1", reader.readLine())
                        val headers = mutableListOf<String>()
                        while (true) {
                            val line = reader.readLine()
                            if (line.isEmpty()) break
                            headers.add(line)
                        }
                        assertTrue(headers.any { it.equals("Authorization: Bearer test-token", ignoreCase = true) })
                        val length = headers.first { it.startsWith("Content-Length:", true) }.substringAfter(':').trim().toInt()
                        val body = CharArray(length)
                        var read = 0
                        while (read < length) read += reader.read(body, read, length - read)
                        val response = "{\"id\":42}"
                        socket.getOutputStream().write("HTTP/1.1 201 Created\r\nContent-Length: ${response.length}\r\nConnection: close\r\n\r\n$response".toByteArray())
                        JSONObject(String(body)).getString("content")
                    }
                }
                assertEquals(42L, saveExplanationNote("http://127.0.0.1:${server.localPort}", "test-token", 2, content))
                assertEquals(content, received.get(10, TimeUnit.SECONDS))
            } finally { worker.shutdownNow() }
        }
    }
}
