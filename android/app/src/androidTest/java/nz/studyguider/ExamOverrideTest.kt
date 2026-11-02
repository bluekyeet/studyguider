package nz.studyguider

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.StateRestorationTester
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextReplacement
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class ExamOverrideTest {
    @get:Rule val compose = createComposeRule()

    private fun awaitText(text: String) = compose.waitUntil(10000) {
        runCatching { compose.onNodeWithText(text).assertExists() }.isSuccess
    }

    @Test fun failedSaveRetainsDraftAcrossRestorationThenSavesAndReloads() {
        var stored = JSONObject().put("outcome", "merit").put("note", "Saved reason")
        val failSave = AtomicBoolean(true)
        val restoration = StateRestorationTester(compose)
        val visible = mutableStateOf(true)
        OverrideStub { request, _, body ->
            when (request.substringBefore(' ')) {
                "GET" -> 200 to JSONObject().put("override", stored).toString()
                "PUT" -> if (failSave.get()) 503 to "unavailable" else {
                    stored = JSONObject(body)
                    200 to "{}"
                }
                else -> error(request)
            }
        }.use { server ->
            restoration.setContent {
                if (visible.value) Column { ExamOverride(server.base, "account-a", 1, 2, null) }
            }
            compose.onNodeWithText("Your judgement / override").performClick()
            awaitText("Saved reason")
            compose.onNodeWithText("Reason for your judgement").performTextReplacement("Unsaved reason")
            compose.onNodeWithText("Save your judgement").performClick()
            awaitText("Override save failed (503). Your note is retained.")
            restoration.emulateSavedInstanceStateRestore()
            compose.onNodeWithText("Your judgement / override").performClick()
            awaitText("Unsaved reason")
            // The input remains disabled until GET completes; wait for that request too.
            compose.waitUntil(10000) {
                runCatching { compose.onNodeWithText("Load / retry saved judgement").assertDoesNotExist() }.isSuccess
            }
            compose.onNodeWithText("Unsaved reason").assertExists()
            failSave.set(false)
            compose.onNodeWithText("Save your judgement").performClick()
            awaitText("Your judgement saved separately from the AI mark.")
            compose.runOnIdle { visible.value = false }
            compose.runOnIdle { visible.value = true }
            compose.onNodeWithText("Your judgement / override").performClick()
            awaitText("Unsaved reason")
            compose.onNodeWithText("merit").assertExists()
            server.assertHealthy()
        }
    }

    @Test fun accountSwitchDoesNotReuseDraftOrLoadedState() {
        val token = mutableStateOf("account-a")
        OverrideStub { _, headers, _ ->
            val account = headers.first { it.startsWith("Authorization:", ignoreCase = true) }.substringAfter("Bearer ")
            200 to JSONObject().put("override", JSONObject().put("outcome", "achieved").put("note", "$account reason")).toString()
        }.use { server ->
            compose.setContent { Column { ExamOverride(server.base, token.value, 1, 2, null) } }
            compose.onNodeWithText("Your judgement / override").performClick()
            awaitText("account-a reason")
            compose.onNodeWithText("Reason for your judgement").performTextReplacement("Private draft")
            compose.runOnIdle { token.value = "account-b" }
            compose.onNodeWithText("Private draft").assertDoesNotExist()
            compose.onNodeWithText("Your judgement / override").performClick()
            awaitText("account-b reason")
            compose.onNodeWithText("Private draft").assertDoesNotExist()
            server.assertHealthy()
        }
    }

    @Test fun failedLoadDisablesSaveAndCanRetry() {
        val failLoad = AtomicBoolean(true)
        OverrideStub { _, _, _ ->
            if (failLoad.get()) 503 to "unavailable" else 200 to "{\"override\":null}"
        }.use { server ->
            compose.setContent { Column { ExamOverride(server.base, "test", 1, 2, null) } }
            compose.onNodeWithText("Your judgement / override").performClick()
            awaitText("Request failed (503): unavailable")
            compose.onNodeWithText("Save your judgement").assertIsNotEnabled()
            compose.onNodeWithText("Your judgement is saved separately. It does not change the AI mark or official-schedule result.").assertExists()
            failLoad.set(false)
            compose.onNodeWithText("Load / retry saved judgement").performClick()
            compose.waitUntil(10000) {
                runCatching { compose.onNodeWithText("Load / retry saved judgement").assertDoesNotExist() }.isSuccess
            }
            compose.onNodeWithText("Save your judgement").assertIsNotEnabled()
            server.assertHealthy()
        }
    }
}

private class OverrideStub(private val respond: (String, List<String>, String) -> Pair<Int, String>) : AutoCloseable {
    private val server = ServerSocket(0)
    private val worker = Executors.newSingleThreadExecutor()
    val base = "http://127.0.0.1:${server.localPort}"
    private val task = worker.submit {
        while (!server.isClosed) {
            val socket = try { server.accept() } catch (e: java.net.SocketException) {
                if (server.isClosed) break else throw e
            }
            socket.use {
                it.soTimeout = 10000
                val input = it.getInputStream()
                fun line(): String = buildString {
                    while (true) {
                        val byte = input.read()
                        check(byte >= 0) { "Unexpected end of HTTP headers" }
                        if (byte == 10) break
                        if (byte != 13) append(byte.toChar())
                    }
                }
                val request = line()
                assertEquals("/exams/1/answers/2/override", request.split(' ')[1])
                val headers = generateSequence { line().takeIf(String::isNotEmpty) }.toList()
                val length = headers.firstOrNull { header -> header.startsWith("Content-Length:", true) }?.substringAfter(':')?.trim()?.toInt() ?: 0
                val bytes = ByteArray(length)
                var offset = 0
                while (offset < length) {
                    val read = input.read(bytes, offset, length - offset)
                    check(read > 0)
                    offset += read
                }
                val (status, body) = respond(request, headers, bytes.toString(Charsets.UTF_8))
                val response = body.toByteArray(Charsets.UTF_8)
                it.getOutputStream().write("HTTP/1.1 $status Stub\r\nContent-Type: application/json\r\nContent-Length: ${response.size}\r\nConnection: close\r\n\r\n".toByteArray() + response)
            }
        }
    }
    fun assertHealthy() { if (task.isDone) task.get(1, TimeUnit.SECONDS) }
    override fun close() {
        server.close()
        worker.shutdown()
        try { task.get(10, TimeUnit.SECONDS) } finally { worker.shutdownNow() }
    }
}
