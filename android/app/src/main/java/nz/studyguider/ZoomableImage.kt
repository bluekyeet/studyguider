package nz.studyguider

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties

internal fun boundedImageZoom(value: Float): Float = value.coerceIn(1f, 8f)

@Composable
fun ZoomableImage(bitmap: Bitmap, description: String, modifier: Modifier = Modifier) {
    var expanded by remember(bitmap) { mutableStateOf(false) }
    Image(bitmap.asImageBitmap(), contentDescription = description,
        modifier = modifier.clickable(onClickLabel = "Enlarge image") { expanded = true })
    if (expanded) Dialog(onDismissRequest = { expanded = false }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        var zoom by remember(bitmap) { mutableFloatStateOf(1f) }
        var offset by remember(bitmap) { mutableStateOf(Offset.Zero) }
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().systemBarsPadding()) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = { expanded = false }) { Text("Close") }
                    Spacer(Modifier.weight(1f))
                    TextButton(enabled = zoom > 1f, onClick = { zoom = boundedImageZoom(zoom / 1.5f); if (zoom == 1f) offset = Offset.Zero }) { Text("Zoom out") }
                    TextButton(onClick = { zoom = boundedImageZoom(zoom * 1.5f) }) { Text("Zoom in") }
                    TextButton(onClick = { zoom = 1f; offset = Offset.Zero }) { Text("Reset") }
                }
                Box(Modifier.weight(1f).fillMaxWidth().clipToBounds().pointerInput(bitmap) {
                    detectTransformGestures { _, pan, change, _ ->
                        zoom = boundedImageZoom(zoom * change)
                        offset = if (zoom == 1f) Offset.Zero else Offset(
                            (offset.x + pan.x).coerceIn(-size.width * (zoom - 1) / 2, size.width * (zoom - 1) / 2),
                            (offset.y + pan.y).coerceIn(-size.height * (zoom - 1) / 2, size.height * (zoom - 1) / 2))
                    }
                }, contentAlignment = Alignment.Center) {
                    // ponytail: zoom existing bounded bitmap; higher-resolution PDF
                    // tile rendering can follow if source detail is insufficient.
                    Image(bitmap.asImageBitmap(), contentDescription = description,
                        modifier = Modifier.fillMaxSize().graphicsLayer {
                            scaleX = zoom; scaleY = zoom; translationX = offset.x; translationY = offset.y
                        })
                }
                Text("Pinch to zoom · drag to pan", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(12.dp))
            }
        }
    }
}
