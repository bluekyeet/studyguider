package nz.studyguider

import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** Opens an authenticated PDF resource without sharing its URL or credentials with another app. Page numbers are one-based. */
@Composable
fun SourceScreen(base: String, token: String, resourceId: String, initialPage: Int = 1) {
    val cacheDir = LocalContext.current.cacheDir
    var file by remember(base, token, resourceId) { mutableStateOf<File?>(null) }
    var error by remember(base, token, resourceId) { mutableStateOf("") }
    var page by remember(base, token, resourceId, initialPage) { mutableIntStateOf(initialPage.coerceAtLeast(1)) }
    var pageCount by remember(base, token, resourceId) { mutableIntStateOf(0) }
    var image by remember(base, token, resourceId) { mutableStateOf<Bitmap?>(null) }

    LaunchedEffect(base, token, resourceId) {
        try {
            withContext(Dispatchers.IO) {
                val temporary = File.createTempFile("source-", ".pdf", cacheDir)
                try {
                    require(runCatching { java.util.UUID.fromString(resourceId) }.isSuccess) { "Invalid resource ID" }
                    val connection = URL(base.trimEnd('/') + "/resources/$resourceId/download").openConnection() as HttpURLConnection
                    try {
                        connection.instanceFollowRedirects = false
                        connection.connectTimeout = 10000
                        connection.readTimeout = 60000
                        connection.setRequestProperty("Authorization", "Bearer $token")
                        val status = connection.responseCode
                        if (status !in 200..299) throw IllegalStateException("Download failed ($status)")
                        connection.inputStream.use { input -> temporary.outputStream().use { output ->
                            val buffer = ByteArray(65536); var total = 0L
                            while (true) {
                                val read = input.read(buffer); if (read < 0) break
                                total += read; require(total <= 50L * 1024 * 1024) { "Source exceeds 50 MiB" }
                                output.write(buffer, 0, read)
                            }
                        } }
                    } finally { connection.disconnect() }
                    withContext(Dispatchers.Main) { file = temporary }
                    awaitCancellation()
                } finally { temporary.delete() }
            }
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Could not load source" }
    }

    LaunchedEffect(file, page) {
        val source = file ?: return@LaunchedEffect
        image = null
        error = ""
        try {
            val result = withContext(Dispatchers.IO) {
                ParcelFileDescriptor.open(source, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
                    PdfRenderer(descriptor).use { renderer ->
                        require(renderer.pageCount > 0) { "PDF has no pages" }
                        val selected = page.coerceIn(1, renderer.pageCount)
                        renderer.openPage(selected - 1).use { pdfPage ->
                            // ponytail: fixed-width rendering limits memory; add zoom when detailed inspection is needed.
                            val width = 1200
                            val height = (width.toLong() * pdfPage.height / pdfPage.width).coerceIn(1, 4096).toInt()
                            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                            bitmap.eraseColor(Color.WHITE)
                            pdfPage.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                            Triple(renderer.pageCount, selected, bitmap)
                        }
                    }
                }
            }
            pageCount = result.first
            page = result.second
            image = result.third
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message ?: "Could not open PDF" }
    }

    Column(Modifier.fillMaxWidth().padding(vertical = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Source PDF", style = MaterialTheme.typography.headlineMedium)
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
        else if (image == null) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (pageCount > 0) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { page-- }, enabled = page > 1) { Text("Previous page") }
                Text("Page $page of $pageCount", modifier = Modifier.padding(top = 12.dp))
                Button(onClick = { page++ }, enabled = page < pageCount) { Text("Next page") }
            }
        }
        image?.let { Image(it.asImageBitmap(), contentDescription = "PDF page $page", modifier = Modifier.fillMaxWidth()) }
    }
}
