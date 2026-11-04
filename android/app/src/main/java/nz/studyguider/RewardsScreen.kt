package nz.studyguider

import android.annotation.SuppressLint
import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView

/**
 * Rewards (points, gacha, shop, character, leaderboards) is the website's own Rewards page shown full screen, so the character art,
 * odds and boards are exactly what the website shows. The page is the server's; the web view is signed in with the app's session and may
 * only visit that server.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun RewardsScreen(base: String, token: String, onDismiss: () -> Unit) {
    val root = base.trimEnd('/')
    val host = android.net.Uri.parse(root).host
    var view by remember { mutableStateOf<WebView?>(null) }
    BackHandler { val v = view; if (v != null && v.canGoBack()) v.goBack() else onDismiss() }
    androidx.compose.ui.window.Dialog(onDismissRequest = onDismiss, properties = androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
                Box(Modifier.fillMaxWidth().heightIn(min = 56.dp), contentAlignment = Alignment.CenterStart) {
                    TextButton(onClick = onDismiss) { Text("‹ Back") }
                }
                AndroidView(modifier = Modifier.fillMaxWidth().weight(1f), factory = { context ->
                    WebView(context).apply {
                        setBackgroundColor(android.graphics.Color.TRANSPARENT)
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        settings.allowFileAccess = false
                        settings.allowContentAccess = false
                        CookieManager.getInstance().setCookie(root, "studyguider_session=$token; Secure; SameSite=Lax")
                        webViewClient = object : WebViewClient() {
                            override fun shouldOverrideUrlLoading(v: WebView, request: WebResourceRequest) = request.url.host != host
                        }
                        loadUrl("$root/?embedded=1#rewards")
                        view = this
                    }
                })
            }
        }
    }
}
