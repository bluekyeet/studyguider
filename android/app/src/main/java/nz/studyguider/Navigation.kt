package nz.studyguider

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** The bottom-bar destinations, Home first, then the supplied Stitch navigation order. */
enum class Destination(val label: String, val tab: Int) {
    Home("Home", 5),
    Lesson("Lesson", 1),
    Review("Review", 2),
    Exam("Exam", 3),
    Resources("Resources", 0),
    Learning("Learning", 4),
}

/**
 * Bottom navigation with vector icons and a highlighted pill around the active
 * destination. The pill and its icon animate, so the current tab reads clearly
 * without changing position.
 */
@Composable
fun StudyNavBar(current: Int, onSelect: (Int) -> Unit) {
    val index = Destination.entries.indexOfFirst { it.tab == current }.coerceAtLeast(0)
    // One pill glides, with a little spring, to the selected destination instead of each tab lighting up alone.
    val position by animateFloatAsState(index.toFloat(), spring(dampingRatio = 0.7f, stiffness = 380f), label = "nav pill")
    val pillColour = MaterialTheme.colorScheme.primaryContainer
    Column(Modifier.fillMaxWidth()) {
        androidx.compose.material3.HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))
        Row(
            Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface).navigationBarsPadding()
                .drawBehind {
                    val item = (size.width - 8.dp.toPx()) / Destination.entries.size
                    drawRoundRect(
                        pillColour,
                        topLeft = Offset(4.dp.toPx() + position * item + 2.dp.toPx(), 6.dp.toPx()),
                        size = Size(item - 4.dp.toPx(), size.height - 12.dp.toPx()),
                        cornerRadius = CornerRadius(size.height / 2),
                    )
                }
                .heightIn(min = 64.dp).padding(horizontal = 4.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Destination.entries.forEach { destination ->
                val selected = destination.tab == current
                val tint by animateColorAsState(if (selected) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant, label = "nav tint")
                val lift by animateFloatAsState(if (selected) 1.14f else 1f, spring(dampingRatio = 0.45f, stiffness = 520f), label = "nav icon")
                // Each destination takes an equal share of the bar so the row spans the full width.
                Box(Modifier.weight(1f).padding(horizontal = 2.dp), contentAlignment = Alignment.Center) {
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(50))
                            .clickable(role = Role.Tab) { onSelect(destination.tab) }
                            .padding(vertical = 6.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(2.dp),
                    ) {
                        DestinationIcon(destination, tint, Modifier.size(22.dp).graphicsLayer { scaleX = lift; scaleY = lift })
                        Text(
                            destination.label,
                            color = tint,
                            fontSize = 10.sp,
                            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                            maxLines = 1,
                        )
                    }
                }
            }
        }
    }
}

/** Small vector icons drawn with Compose paths: book, refresh arrows, page and folder. */
@Composable
fun DestinationIcon(destination: Destination, tint: Color, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        val w = size.width
        val h = size.height
        val stroke = Stroke(width = w * 0.09f, cap = StrokeCap.Round)
        when (destination) {
            Destination.Home -> {
                // House: roof and walls with a door.
                val house = Path().apply {
                    moveTo(w * 0.08f, h * 0.48f)
                    lineTo(w * 0.5f, h * 0.12f)
                    lineTo(w * 0.92f, h * 0.48f)
                    moveTo(w * 0.18f, h * 0.42f)
                    lineTo(w * 0.18f, h * 0.88f)
                    lineTo(w * 0.82f, h * 0.88f)
                    lineTo(w * 0.82f, h * 0.42f)
                }
                drawPath(house, tint, style = stroke)
                drawLine(tint, Offset(w * 0.44f, h * 0.88f), Offset(w * 0.44f, h * 0.6f), strokeWidth = w * 0.09f, cap = StrokeCap.Round)
                drawLine(tint, Offset(w * 0.44f, h * 0.6f), Offset(w * 0.62f, h * 0.6f), strokeWidth = w * 0.09f, cap = StrokeCap.Round)
                drawLine(tint, Offset(w * 0.62f, h * 0.6f), Offset(w * 0.62f, h * 0.88f), strokeWidth = w * 0.09f, cap = StrokeCap.Round)
            }
            Destination.Learning -> {
                drawCircle(tint, radius = w * 0.14f, center = Offset(w * 0.5f, h * 0.25f), style = stroke)
                drawArc(tint, 180f, 180f, false, Offset(w * 0.18f, h * 0.5f), Size(w * 0.64f, h * 0.55f), style = stroke)
            }
            Destination.Lesson -> {
                // Open book: two pages meeting at a spine.
                val left = Path().apply {
                    moveTo(w * 0.5f, h * 0.3f)
                    cubicTo(w * 0.38f, h * 0.18f, w * 0.18f, h * 0.18f, w * 0.08f, h * 0.24f)
                    lineTo(w * 0.08f, h * 0.82f)
                    cubicTo(w * 0.24f, h * 0.76f, w * 0.38f, h * 0.78f, w * 0.5f, h * 0.9f)
                }
                val right = Path().apply {
                    moveTo(w * 0.5f, h * 0.3f)
                    cubicTo(w * 0.62f, h * 0.18f, w * 0.82f, h * 0.18f, w * 0.92f, h * 0.24f)
                    lineTo(w * 0.92f, h * 0.82f)
                    cubicTo(w * 0.76f, h * 0.76f, w * 0.62f, h * 0.78f, w * 0.5f, h * 0.9f)
                }
                drawPath(left, tint, style = stroke)
                drawPath(right, tint, style = stroke)
                drawLine(tint, Offset(w * 0.5f, h * 0.3f), Offset(w * 0.5f, h * 0.9f), strokeWidth = w * 0.09f, cap = StrokeCap.Round)
            }
            Destination.Review -> {
                // Circular arrows for spaced repetition.
                drawArc(tint, startAngle = 40f, sweepAngle = 240f, useCenter = false, topLeft = Offset(w * 0.14f, h * 0.14f), size = Size(w * 0.72f, h * 0.72f), style = stroke)
                val arrow = Path().apply {
                    moveTo(w * 0.74f, h * 0.06f)
                    lineTo(w * 0.96f, h * 0.2f)
                    lineTo(w * 0.72f, h * 0.28f)
                }
                drawPath(arrow, tint)
            }
            Destination.Exam -> {
                // Page with a tick.
                drawRoundRect(tint, topLeft = Offset(w * 0.2f, h * 0.08f), size = Size(w * 0.6f, h * 0.84f), cornerRadius = androidx.compose.ui.geometry.CornerRadius(w * 0.1f), style = stroke)
                val tick = Path().apply {
                    moveTo(w * 0.34f, h * 0.52f)
                    lineTo(w * 0.46f, h * 0.65f)
                    lineTo(w * 0.68f, h * 0.36f)
                }
                drawPath(tick, tint, style = Stroke(width = w * 0.1f, cap = StrokeCap.Round))
            }
            Destination.Resources -> {
                // Folder.
                val folder = Path().apply {
                    moveTo(w * 0.1f, h * 0.26f)
                    lineTo(w * 0.42f, h * 0.26f)
                    lineTo(w * 0.5f, h * 0.38f)
                    lineTo(w * 0.9f, h * 0.38f)
                    lineTo(w * 0.9f, h * 0.82f)
                    lineTo(w * 0.1f, h * 0.82f)
                    close()
                }
                drawPath(folder, tint, style = stroke)
            }
        }
    }
}
