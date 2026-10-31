package nz.studyguider

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/** Tonal level for [StudyCard], mirroring the design system's surface containers. */
enum class CardTone { Container, Low, High }

/** Rounded card with a tonal background, used as the base for every content chunk. */
@Composable
fun StudyCard(
    tone: CardTone = CardTone.Container,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    val colours = LocalStudyColours.current
    val background = when (tone) {
        CardTone.Container -> colours.container
        CardTone.Low -> colours.containerLow
        CardTone.High -> colours.containerHigh
    }
    Surface(shape = RoundedCornerShape(16.dp), color = background, modifier = modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

/** Upper-case mono label with an optional second line, matching the design's chunk tags. */
@Composable
fun SectionLabel(title: String, kicker: String? = null, modifier: Modifier = Modifier) {
    Column(modifier) {
        if (kicker != null) Text(kicker, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
        Text(title, style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface)
    }
}

/** Small coloured dot plus label, used for statuses such as "Ready". */
@Composable
fun StatusDot(colour: androidx.compose.ui.graphics.Color, label: String) {
    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(Modifier.size(6.dp).background(colour, RoundedCornerShape(50)))
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
