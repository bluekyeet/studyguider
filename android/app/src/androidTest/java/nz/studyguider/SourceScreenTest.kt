package nz.studyguider

import android.graphics.pdf.PdfDocument
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.io.ByteArrayOutputStream
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class SourceScreenTest {
    @get:Rule val compose = createComposeRule()

    @Test fun downloadsAndNavigatesPdf() {
        val document = PdfDocument()
        val pdf = try {
            repeat(2) { index ->
                val page = document.startPage(PdfDocument.PageInfo.Builder(200, 200, index + 1).create())
                document.finishPage(page)
            }
            ByteArrayOutputStream().also { document.writeTo(it) }.toByteArray()
        } finally { document.close() }
        val id = "123e4567-e89b-12d3-a456-426614174000"
        ServerSocket(0).use { server ->
            server.soTimeout = 15000
            val executor = Executors.newSingleThreadExecutor()
            try {
                val request = executor.submit<List<String>> {
                    server.accept().use { socket ->
                        socket.soTimeout = 15000
                        val input = socket.getInputStream().bufferedReader()
                        val lines = mutableListOf<String>()
                        while (true) {
                            val line = input.readLine() ?: break
                            if (line.isEmpty()) break
                            lines.add(line)
                        }
                        socket.getOutputStream().apply {
                            write("HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\nContent-Length: ${pdf.size}\r\nConnection: close\r\n\r\n".toByteArray())
                            write(pdf)
                            flush()
                        }
                        lines
                    }
                }
                compose.setContent { SourceScreen("http://127.0.0.1:${server.localPort}", "fake-token", id) }
                compose.waitUntil(20000) { compose.onAllNodesWithContentDescription("PDF page 1").fetchSemanticsNodes().isNotEmpty() }
                val headers = request.get(5, TimeUnit.SECONDS)
                assertEquals("GET /resources/$id/download HTTP/1.1", headers.first())
                assertEquals(true, headers.any { it.equals("Authorization: Bearer fake-token", ignoreCase = true) })
                compose.onNodeWithText("Page 1 of 2").assertIsDisplayed()
                compose.onNodeWithText("Previous page").assertIsNotEnabled()
                compose.onNodeWithText("Next page").performClick()
                compose.waitUntil(10000) { compose.onAllNodesWithContentDescription("PDF page 2").fetchSemanticsNodes().isNotEmpty() }
                compose.onNodeWithText("Page 2 of 2").assertIsDisplayed()
                compose.onNodeWithText("Next page").assertIsNotEnabled()
            } finally {
                server.close()
                executor.shutdownNow()
            }
        }
    }
}
