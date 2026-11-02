package nz.studyguider

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import android.util.TypedValue
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/**
 * Renders the app's own KaTeX runtime offline. Every asset (KaTeX, mhchem, fonts)
 * is bundled in the APK, so lesson text never leaves the device and rendering
 * works with no network.
 */
object KaTeX {
    const val AVAILABLE = true

    /** Text colour comes from Compose so dark mode does not need a page reload. */
    fun head(): String = """
        <style>
          html, body { margin:0; padding:0; background:transparent; max-width:100%; }
          #content { position:absolute; top:0; left:0; width:100%; }
          #content > div { display:flow-root; }
          body { color:#1A1B22; font-family:system-ui, sans-serif; font-size:16px; line-height:1.55;
                 overflow-wrap:anywhere; word-break:normal; }
          b { font-weight:600; }
          i { font-style:italic; }
          code { font-family:monospace; font-size:0.85em; background:rgba(120,130,150,0.14); padding:0 3px; border-radius:4px; }
          .katex { font-size:1.05em; overflow-wrap:normal; word-break:normal; }
          .katex-display { margin:8px 0; overflow-x:auto; overflow-y:hidden; }
          .katex-display > .katex, .katex .katex-html, .katex .base, .katex .text { white-space:nowrap; overflow-wrap:normal; word-break:normal; }
        </style>
        <link rel="stylesheet" href="katex/katex.min.css">
        <script src="katex/katex.min.js"></script>
        <script src="katex/contrib/mhchem.min.js"></script>
    """

    /**
     * Splits text into styled Markdown runs, then renders `$...$` and `$$...$$`
     * with KaTeX. Invalid formulas fall back to the literal source so nothing is
     * silently lost.
     */
    fun toHtml(text: String): String {
        val builder = StringBuilder()
        fun escape(value: String) = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        var seenText = false
        inlineRuns(text).map { run ->
            if (!seenText && run.text.isNotBlank()) { seenText = true; run.copy(text = run.text.trimStart()) } else run
        }.forEachIndexed { position, run ->
            if (run.bold) builder.append("<b>")
            if (run.italic) builder.append("<i>")
            if (run.code) builder.append("<code>")
            appendMath(builder, run.text, ::escape)
            if (run.code) builder.append("</code>")
            if (run.italic) builder.append("</i>")
            if (run.bold) builder.append("</b>")
        }
        return builder.toString()
    }

    private fun appendMath(builder: StringBuilder, text: String, escape: (String) -> String) {
        var index = 0
        while (index < text.length) {
            val dollar = text.indexOf('$', index)
            if (dollar < 0) { builder.append(escape(text.substring(index))); break }
            builder.append(escape(text.substring(index, dollar)))
            val display = dollar + 1 < text.length && text[dollar + 1] == '$'
            val start = if (display) dollar + 2 else dollar + 1
            val closing = text.indexOf(if (display) "$$" else "$", start)
            if (closing < 0) { builder.append(escape(text.substring(dollar))); break }
            val formula = text.substring(start, closing)
            // Emit the formula as plain text; the script reads it back and never runs it as JavaScript.
            builder.append("<span data-tex=\"").append(escape(formula)).append("\" data-display=\"").append(if (display) "1" else "0").append("\"></span>")
            index = closing + if (display) 2 else 1
        }
    }

    /**
     * Renders every formula, then reports the rendered height to the native
     * [Bridge] so the WebView can size itself instead of clipping the text.
     */
    fun script(): String = """
        (function(){
          function report(){
            var height = Math.ceil(document.getElementById('content').getBoundingClientRect().height);
            if (window.Native && window.Native.onHeight) { window.Native.onHeight(height); }
          }
          document.querySelectorAll('span[data-tex]').forEach(function(node){
            var tex = node.getAttribute('data-tex');
            var display = node.getAttribute('data-display') === '1';
            // A provider may wrap a whole prose sentence in maths. Plain text
            // needs normal browser wrapping, not KaTeX's unbreakable math base.
            var prose = /^\\text\{([^{}]*)\}$/.exec(tex.trim());
            if (prose) { node.textContent = prose[1]; return; }
            try {
              katex.render(tex, node, { displayMode: display, throwOnError: true,
                  strict: 'ignore', trust: false, output: 'html' });
            } catch (error) {
              var fallback = document.createElement('span');
              fallback.textContent = tex;
              fallback.style.fontFamily = 'monospace';
              fallback.style.color = '#BA1A1A';
              node.replaceWith(fallback);
            }
          });
          if (window.ResizeObserver) { new ResizeObserver(report).observe(document.getElementById('content')); }
          if (document.fonts && document.fonts.ready) { document.fonts.ready.then(report); }
          report();
          setTimeout(report, 120);
          setTimeout(report, 500);
        })();
    """

    fun fullPage(body: String, colour: String): String =
        "<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width, initial-scale=1, maximum-scale=1\">${head()}</head><body style=\"color:$colour\"><div id=\"content\">$body</div><script>${script()}</script></body></html>"
}

/** Receives the measured content height from the KaTeX page. */
class KaTeXBridge(private val updateHeight: (Int) -> Unit) {
    @JavascriptInterface
    fun onHeight(px: Int) {
        updateHeight(px)
    }
}

/**
 * Shows mixed prose and LaTeX. The WebView measures its own content and grows to
 * fit, so long passages are never cut off and no inner scrolling is needed.
 */
@Composable
fun MathText(
    text: String,
    modifier: Modifier = Modifier,
    formulaStyle: Boolean = false,
    fontSize: Int = 16,
) {
    val html = remember(text) { KaTeX.toHtml(text) }
    val onSurface = MaterialTheme.colorScheme.onSurface
    val colour = remember(onSurface) {
        val argb = android.graphics.Color.argb(
            (onSurface.alpha * 255).toInt(), (onSurface.red * 255).toInt(),
            (onSurface.green * 255).toInt(), (onSurface.blue * 255).toInt())
        String.format("#%06X", 0xFFFFFF and argb)
    }
    // Start with a small estimate, then use the measured height; the estimate only avoids a jump.
    var height by remember(text) { mutableIntStateOf(estimateMathHeight(text)) }
    val colours = LocalStudyColours.current
    Box(
        modifier
            .fillMaxWidth()
            .then(if (formulaStyle) Modifier.clip(RoundedCornerShape(8.dp)).background(colours.formulaBackground).border(1.dp, colours.formulaBorder, RoundedCornerShape(8.dp)).padding(10.dp).fillMaxWidth() else Modifier)
            .heightIn(min = 20.dp)
    ) {
        key(text) { AndroidView(
            modifier = Modifier.fillMaxWidth().height(height.dp),
            factory = { context ->
                WebView(context).apply {
                    setBackgroundColor(android.graphics.Color.TRANSPARENT)
                    settings.javaScriptEnabled = true
                    // Only the bundled KaTeX assets load; no network, no file or content access.
                    settings.allowFileAccess = true
                    settings.allowContentAccess = false
                    settings.setAllowFileAccessFromFileURLs(false)
                    settings.setAllowUniversalAccessFromFileURLs(false)
                    settings.domStorageEnabled = false
                    settings.cacheMode = android.webkit.WebSettings.LOAD_NO_CACHE
                    settings.mediaPlaybackRequiresUserGesture = true
                    isVerticalScrollBarEnabled = false
                    isHorizontalScrollBarEnabled = false
                    isNestedScrollingEnabled = false
                    addJavascriptInterface(KaTeXBridge { px ->
                        post {
                            val measured = px
                            if (measured > 0) height = measured.coerceIn(20, 20000)
                        }
                    }, "Native")
                    webViewClient = object : WebViewClient() {
                        override fun onReceivedError(view: WebView, request: android.webkit.WebResourceRequest, error: android.webkit.WebResourceError) {
                            if (request.isForMainFrame) android.util.Log.e("KaTeX", "Load failed: ${error.description}")
                        }
                    }
                }
            },
            update = { view ->
                // Font size comes from the page itself, so reload only when the text or colour changes.
                val page = KaTeX.fullPage("<div>${html}</div>", colour).replace("font-size:16px", "font-size:${fontSize}px")
                if (view.tag != page) {
                    view.tag = page
                    view.settings.textZoom = 100
                    view.loadDataWithBaseURL("file:///android_asset/", page, "text/html", "utf-8", null)
                }
            }
        ) }
    }
}

/** Rough starting height; the page reports the real height once rendered. */
fun estimateMathHeight(text: String): Int {
    val charactersPerLine = 42
    val lines = text.split('\n').sumOf { (it.length / charactersPerLine) + 1 } + text.count { it == '$' } / 2
    return (lines * 26 + 12).coerceIn(24, 20000)
}

/** Compact formula preview used above inputs and in the LaTeX helper. */
@Composable
fun FormulaPreview(latex: String) {
    val colours = LocalStudyColours.current
    if (latex.isBlank()) return
    Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).background(colours.formulaBackground).border(1.dp, colours.formulaBorder, RoundedCornerShape(8.dp)).padding(8.dp)) {
        MathText(if (latex.trim().startsWith("$")) latex else "$" + latex.trim() + "$", fontSize = 18)
    }
}

/**
 * Live maths editor: preview on top, raw LaTeX below, and a symbol toolbar.
 * The result is inserted into the host field as display maths.
 */
@Composable
fun LatexSheet(onDismiss: () -> Unit, onInsert: (String) -> Unit, initial: String = "") {
    var draft by remember { mutableStateOf(initial) }
    val symbols = listOf("a⁄b" to "\\frac{a}{b}", "x²" to "x^{2}", "√x" to "\\sqrt{x}", "∫" to "\\int", "∑" to "\\sum", "Δ" to "\\Delta", "θ" to "\\theta", "π" to "\\pi", "v⃗" to "\\vec{v}", "H₂O" to "\\ce{H2O}", "×" to "\\times", "≈" to "\\approx", "→" to "\\rightarrow")
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Type maths") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Preview", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)
                if (draft.isBlank()) Text("Start typing LaTeX below.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                FormulaPreview(draft)
                Text("LaTeX", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)
                OutlinedTextField(draft, { draft = it }, modifier = Modifier.fillMaxWidth(), minLines = 2, textStyle = MaterialTheme.typography.bodyMedium)
                @OptIn(ExperimentalLayoutApi::class)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    symbols.forEach { (label, latex) -> AssistChip(onClick = { draft += latex }, label = { Text(label, style = MaterialTheme.typography.titleMedium) }) }
                }
                Text("Inserted as display maths with double dollar signs.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        },
        confirmButton = {
            TextButton(enabled = draft.isNotBlank(), onClick = {
                val trimmed = draft.trim()
                onInsert(if (trimmed.startsWith("$$") || trimmed.startsWith("$")) trimmed else "$$$trimmed$$")
                onDismiss()
            }) { Text("Insert") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } }
    )
}

/**
 * Answer or chat field with a maths helper. Typing `/latex` (or tapping the
 * toolbar button) opens the editor, and the field grows with the answer instead
 * of hiding it.
 */
@Composable
fun MathField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    minLines: Int = 1,
    maxLines: Int = 20,
    supportingText: String? = null,
) {
    var showSheet by remember { mutableStateOf(false) }
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        OutlinedTextField(
            value = value,
            onValueChange = { next ->
                if (next.endsWith("/latex")) { showSheet = true; onValueChange(next.removeSuffix("/latex")) } else onValueChange(next)
            },
            label = { Text(label) },
            modifier = Modifier.fillMaxWidth(),
            enabled = enabled,
            minLines = minLines,
            maxLines = maxLines,
            shape = RoundedCornerShape(12.dp),
        )
        if (supportingText != null) Text(supportingText, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { showSheet = true }, shape = RoundedCornerShape(50), contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp), modifier = Modifier.heightIn(min = 36.dp)) {
                Text("Σ  Maths")
            }
            Text("Type /latex or tap Σ", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
    if (showSheet) LatexSheet(onDismiss = { showSheet = false }, onInsert = { onValueChange(value + (if (value.isEmpty() || value.endsWith(" ")) "" else " ") + it) }, initial = "")
}

/** Loads an authenticated server image (page scan or diagram) as a bitmap. */
@Composable
fun AuthorisedImage(base: String, token: String, path: String, modifier: Modifier = Modifier, contentDescription: String = "Page image") {
    var bitmap by remember(path, token) { mutableStateOf<Bitmap?>(null) }
    var failed by remember(path, token) { mutableStateOf(false) }
    LaunchedEffect(path, token) {
        try {
            bitmap = withContext(Dispatchers.IO) {
                val connection = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
                try {
                    connection.setRequestProperty("Authorization", "Bearer $token")
                    val status = connection.responseCode
                    if (status !in 200..299) throw IllegalStateException("Image request failed ($status)")
                    connection.inputStream.use { BitmapFactory.decodeStream(it) }
                } finally { connection.disconnect() }
            }
        } catch (e: Exception) { failed = true }
    }
    when {
        bitmap != null -> ZoomableImage(bitmap!!, contentDescription, modifier)
        failed -> Text("Image could not be loaded.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        else -> Box(modifier.height(120.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
    }
}

/** Renders a standalone page for debugging the bundled KaTeX runtime. */
fun debugKaTeXPage(text: String, dark: Boolean = false): String = KaTeX.fullPage("<div>" + KaTeX.toHtml(text) + "</div>", if (dark) "#E3E1EC" else "#1A1B22")

/** Short sample used only by the debug KaTeX page. */
const val KaTeXProbe = "Momentum is \$p = mv\$. Then \$\$p_{before} = p_{after}\$\$ and \$\$\\ce{H2O + CO2 -> H2CO3}\$\$ with \$\$E_k = \\tfrac{1}{2}mv^2\$\$"
