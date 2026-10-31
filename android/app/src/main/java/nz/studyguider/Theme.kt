package nz.studyguider

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Palette and type scale from the supplied Tātai STEM M3 design system, so every
 * screen uses one set of colours instead of ad-hoc hex values.
 */
data class StudyColours(
    val formulaBackground: Color,
    val formulaBorder: Color,
    val containerLow: Color,
    val container: Color,
    val containerHigh: Color,
    val containerHighest: Color,
    val achieved: Color,
    val merit: Color,
    val excellence: Color,
    val amber: Color,
    val teal: Color,
    val outline: Color,
)

val LightStudyColours = StudyColours(
    formulaBackground = Color(0xFFF1F5F9),
    formulaBorder = Color(0xFFCBD5E1),
    containerLow = Color(0xFFF4F2FD),
    container = Color(0xFFEEEDF7),
    containerHigh = Color(0xFFE8E7F1),
    containerHighest = Color(0xFFE3E1EC),
    achieved = Color(0xFF059669),
    merit = Color(0xFF2563EB),
    excellence = Color(0xFF7C3AED),
    amber = Color(0xFFD97706),
    teal = Color(0xFF0D9488),
    outline = Color(0xFF757682),
)

val DarkStudyColours = StudyColours(
    formulaBackground = Color(0xFF1B2534),
    formulaBorder = Color(0xFF334155),
    containerLow = Color(0xFF171B25),
    container = Color(0xFF1C212C),
    containerHigh = Color(0xFF232A37),
    containerHighest = Color(0xFF2A323F),
    achieved = Color(0xFF34D399),
    merit = Color(0xFF8AB4FF),
    excellence = Color(0xFFC4A6FF),
    amber = Color(0xFFFBBF24),
    teal = Color(0xFF2DD4BF),
    outline = Color(0xFF9AA0AE),
)

val LocalStudyColours = staticCompositionLocalOf { LightStudyColours }

private val Mono = FontFamily.Monospace

private val StudyTypography = Typography(
    headlineLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 30.sp, lineHeight = 38.sp, fontWeight = FontWeight.Bold),
    headlineMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 26.sp, lineHeight = 32.sp, fontWeight = FontWeight.Bold),
    headlineSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 22.sp, lineHeight = 28.sp, fontWeight = FontWeight.SemiBold),
    titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 19.sp, lineHeight = 26.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 16.sp, lineHeight = 26.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 14.sp, lineHeight = 22.sp),
    bodySmall = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 12.sp, lineHeight = 18.sp),
    labelLarge = TextStyle(fontFamily = Mono, fontSize = 13.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium),
    labelMedium = TextStyle(fontFamily = Mono, fontSize = 11.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, letterSpacing = 0.4.sp),
    labelSmall = TextStyle(fontFamily = Mono, fontSize = 10.sp, lineHeight = 14.sp, fontWeight = FontWeight.Medium, letterSpacing = 0.6.sp),
)

private val LightColours = lightColorScheme(
    primary = Color(0xFF1E3A8A),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE1FF),
    onPrimaryContainer = Color(0xFF00164E),
    secondary = Color(0xFF006A61),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFF86F2E4),
    onSecondaryContainer = Color(0xFF006F66),
    tertiary = Color(0xFF92400E),
    tertiaryContainer = Color(0xFFFFDCC3),
    background = Color(0xFFFBF8FF),
    onBackground = Color(0xFF1A1B22),
    surface = Color(0xFFFBF8FF),
    onSurface = Color(0xFF1A1B22),
    surfaceVariant = Color(0xFFEEEDF7),
    onSurfaceVariant = Color(0xFF444651),
    outline = Color(0xFF757682),
    outlineVariant = Color(0xFFC5C5D3),
    error = Color(0xFFBA1A1A),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF93000A),
)

private val DarkColours = darkColorScheme(
    primary = Color(0xFFB6C4FF),
    onPrimary = Color(0xFF00164E),
    primaryContainer = Color(0xFF264191),
    onPrimaryContainer = Color(0xFFDCE1FF),
    secondary = Color(0xFF6BD8CB),
    onSecondary = Color(0xFF00312C),
    secondaryContainer = Color(0xFF005049),
    onSecondaryContainer = Color(0xFF86F2E4),
    tertiary = Color(0xFFFFB77D),
    tertiaryContainer = Color(0xFF653400),
    background = Color(0xFF11151D),
    onBackground = Color(0xFFE3E1EC),
    surface = Color(0xFF151922),
    onSurface = Color(0xFFE3E1EC),
    surfaceVariant = Color(0xFF232A37),
    onSurfaceVariant = Color(0xFFC5C5D3),
    outline = Color(0xFF8F909C),
    outlineVariant = Color(0xFF444651),
    error = Color(0xFFFFB4AB),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
)

@Composable
fun StudyTheme(dark: Boolean, content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalStudyColours provides if (dark) DarkStudyColours else LightStudyColours) {
        MaterialTheme(colorScheme = if (dark) DarkColours else LightColours, typography = StudyTypography, content = content)
    }
}

/** Small uppercase chip used for statuses and NCEA grade tags. */
@Composable
fun StudyChip(text: String, foreground: Color, background: Color, modifier: Modifier = Modifier) {
    Surface(modifier = modifier, shape = RoundedCornerShape(50), color = background) {
        Box(Modifier.padding(horizontal = 8.dp, vertical = 3.dp)) {
            Text(text.uppercase(), style = MaterialTheme.typography.labelMedium, color = foreground, maxLines = 1)
        }
    }
}
