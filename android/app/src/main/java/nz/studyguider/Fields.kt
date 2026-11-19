package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

// Form fields shared by the Plan and Settings screens: a date, a pick-one list, a number, and how dates are worded.

private val dayFormat = DateTimeFormatter.ofPattern("d MMM yyyy", Locale("en", "NZ"))
private val shortDayFormat = DateTimeFormatter.ofPattern("EEE d MMM", Locale("en", "NZ"))

/** "24 Nov 2026" for an ISO date, or "No date". */
fun niceDate(iso: String?): String = runCatching { LocalDate.parse(iso).format(dayFormat) }.getOrDefault("No date")
fun shortDate(iso: String?): String = runCatching { LocalDate.parse(iso).format(shortDayFormat) }.getOrDefault("No date")

/** Whole days from [today] to [iso]; null when either is not a date. */
fun daysUntil(iso: String?, today: String?): Int? = runCatching { ChronoUnit.DAYS.between(LocalDate.parse(today), LocalDate.parse(iso)).toInt() }.getOrNull()

fun inDays(days: Int): String = when { days == 0 -> "today"; days == 1 -> "tomorrow"; days < 0 -> "${-days} days ago"; else -> "in $days days" }

/** A whole percentage, or a dash when there is none. */
fun percentOrDash(value: Double?): String = if (value == null) "—" else "${Math.round(value * 100)}%"

/** A number without a trailing ".0". */
fun trimNumber(value: Double?): String = value?.toBigDecimal()?.stripTrailingZeros()?.toPlainString().orEmpty()

/** A date chosen from the calendar; [value] is an ISO date or empty. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DateField(label: String, value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    var open by remember { mutableStateOf(false) }
    OutlinedButton(onClick = { open = true }, enabled = enabled, shape = RoundedCornerShape(12.dp), modifier = modifier.heightIn(min = 56.dp),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp)) {
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(if (value.isBlank()) "Choose a date" else niceDate(value), style = MaterialTheme.typography.bodyLarge,
                color = if (value.isBlank()) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface)
        }
    }
    if (open) {
        val initial = runCatching { LocalDate.parse(value).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli() }.getOrNull()
        val state = rememberDatePickerState(initialSelectedDateMillis = initial)
        DatePickerDialog(onDismissRequest = { open = false },
            confirmButton = { TextButton(onClick = {
                state.selectedDateMillis?.let { onChange(Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate().toString()) }
                open = false
            }) { Text("OK") } },
            dismissButton = { Row {
                if (value.isNotBlank()) TextButton(onClick = { onChange(""); open = false }) { Text("No date") }
                TextButton(onClick = { open = false }) { Text("Cancel") }
            } }) { DatePicker(state) }
    }
}

/** Pick one of a short list; [options] are (value, label). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PickField(label: String, options: List<Pair<String, String>>, value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    var open by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = open, onExpandedChange = { if (enabled) open = it }, modifier = modifier) {
        OutlinedTextField(
            value = options.firstOrNull { it.first == value }?.second ?: "Choose…", onValueChange = {}, readOnly = true, enabled = enabled, singleLine = true,
            label = { Text(label) }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = open) }, shape = RoundedCornerShape(12.dp),
            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            options.forEach { (key, text) -> DropdownMenuItem(text = { Text(text) }, onClick = { onChange(key); open = false }) }
        }
    }
}

/** A number typed as text, so it can be empty. */
@Composable
fun NumberField(label: String, value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, placeholder: String = "", whole: Boolean = false) {
    OutlinedTextField(value, { text -> onChange(text.filter { it.isDigit() || (!whole && it == '.') }.take(8)) }, modifier, enabled = enabled, singleLine = true,
        label = { Text(label) }, placeholder = if (placeholder.isEmpty()) null else ({ Text(placeholder) }), shape = RoundedCornerShape(12.dp),
        keyboardOptions = KeyboardOptions(keyboardType = if (whole) KeyboardType.Number else KeyboardType.Decimal))
}

/** A chip in one of the app's tones: good, bad, warning or plain. */
@Composable
fun ToneChip(text: String, tone: String = "") {
    val colours = LocalStudyColours.current
    val (fg, bg) = when (tone) {
        "ok" -> colours.achieved to colours.achieved.copy(alpha = 0.14f)
        "bad" -> MaterialTheme.colorScheme.onErrorContainer to MaterialTheme.colorScheme.errorContainer
        "warn" -> colours.amber to colours.amber.copy(alpha = 0.16f)
        else -> MaterialTheme.colorScheme.onSurfaceVariant to colours.containerHighest
    }
    StudyChip(text, fg, bg)
}

/** One figure with its label, for the rows of headline numbers. */
@Composable
fun StatTile(value: String, label: String, modifier: Modifier = Modifier, tone: CardTone = CardTone.Low, accent: Color? = null) {
    StudyCard(modifier = modifier, tone = tone) {
        Text(value, style = MaterialTheme.typography.headlineSmall, color = accent ?: MaterialTheme.colorScheme.onSurface)
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
