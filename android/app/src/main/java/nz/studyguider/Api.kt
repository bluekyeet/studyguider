package nz.studyguider

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Calls to the StudyGuider server for the screens added with the plan, review and answer-input work. The older screens keep
 * their own request functions. Errors carry the server's "detail" message, so a screen can show it as it is.
 */
class Api(val base: String, val token: String) {
    suspend fun get(path: String): String = call("GET", path, null)
    suspend fun post(path: String, body: JSONObject = JSONObject()): String = call("POST", path, body)
    suspend fun put(path: String, body: JSONObject): String = call("PUT", path, body)
    suspend fun delete(path: String): String = call("DELETE", path, null)

    suspend fun getObject(path: String) = JSONObject(get(path))
    suspend fun getArray(path: String) = JSONArray(get(path))

    /** A multipart form: text fields, then files as (field name, file name, content type, bytes). */
    suspend fun multipart(path: String, fields: Map<String, String>, files: List<Part>, readTimeout: Int = 120000): String = withContext(Dispatchers.IO) {
        val boundary = "studyguider-" + java.util.UUID.randomUUID()
        val body = java.io.ByteArrayOutputStream()
        fields.forEach { (name, value) ->
            body.write("--$boundary\r\nContent-Disposition: form-data; name=\"$name\"\r\n\r\n".toByteArray())
            body.write(value.toByteArray(Charsets.UTF_8)); body.write("\r\n".toByteArray())
        }
        files.forEach { part ->
            val safe = part.filename.replace("\"", "_").replace("\r", "_").replace("\n", "_")
            body.write("--$boundary\r\nContent-Disposition: form-data; name=\"${part.field}\"; filename=\"$safe\"\r\nContent-Type: ${part.type}\r\n\r\n".toByteArray(Charsets.UTF_8))
            body.write(part.bytes); body.write("\r\n".toByteArray())
        }
        body.write("--$boundary--\r\n".toByteArray())
        val payload = body.toByteArray()
        val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 15000; connection.readTimeout = readTimeout
            connection.requestMethod = "POST"; connection.doOutput = true
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            connection.setFixedLengthStreamingMode(payload.size)
            connection.outputStream.use { it.write(payload) }
            read(connection)
        } finally { connection.disconnect() }
    }

    class Part(val field: String, val filename: String, val type: String, val bytes: ByteArray)

    private suspend fun call(method: String, path: String, body: JSONObject?): String = withContext(Dispatchers.IO) {
        val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 10000
            // Marking and outline reading call the model, which can take a while.
            connection.readTimeout = if (method == "GET") 30000 else 200000
            connection.requestMethod = method
            if (token.isNotEmpty()) connection.setRequestProperty("Authorization", "Bearer $token")
            if (body != null) {
                connection.setRequestProperty("Content-Type", "application/json")
                connection.doOutput = true
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            read(connection)
        } finally { connection.disconnect() }
    }

    private fun read(connection: HttpURLConnection): String {
        val status = connection.responseCode
        val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw ApiError(status, errorDetail(text) ?: "Request failed ($status)")
        return text
    }

    /** Fetches raw bytes, such as a drawing's PNG. */
    suspend fun bytes(path: String): ByteArray = withContext(Dispatchers.IO) {
        val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 10000; connection.readTimeout = 30000
            connection.setRequestProperty("Authorization", "Bearer $token")
            val status = connection.responseCode
            if (status !in 200..299) throw ApiError(status, "Request failed ($status)")
            connection.inputStream.use { it.readBytes() }
        } finally { connection.disconnect() }
    }
}

class ApiError(val status: Int, message: String) : IllegalStateException(message)

/** FastAPI's "detail" as one readable line: a string, or the first validation message. */
fun errorDetail(text: String): String? = runCatching {
    when (val detail = JSONObject(text).opt("detail")) {
        is String -> detail
        is JSONArray -> (0 until detail.length()).mapNotNull { detail.optJSONObject(it)?.optString("msg")?.takeIf { m -> m.isNotBlank() } }.joinToString("; ")
        else -> null
    }
}.getOrNull()?.takeIf { it.isNotBlank() }

fun JSONArray.objectList(): List<JSONObject> = (0 until length()).mapNotNull { optJSONObject(it) }
fun JSONArray.stringList(): List<String> = (0 until length()).map { optString(it) }

/** A JSON value that may be null, as a Kotlin nullable. */
fun JSONObject.doubleOrNull(key: String): Double? = if (isNull(key) || !has(key)) null else optDouble(key).takeIf { !it.isNaN() }
fun JSONObject.stringOrNull(key: String): String? = if (isNull(key) || !has(key)) null else optString(key)
