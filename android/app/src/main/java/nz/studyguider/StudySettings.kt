package nz.studyguider

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.json.JSONObject

private val PREFERENCE_LABELS = listOf("tone" to "Tone", "reading_level" to "Reading level", "pace" to "Pace")
private val PREFERENCE_NAMES = mapOf("warm" to "Warm", "neutral" to "Neutral", "direct" to "Direct", "plain" to "Plain words", "standard" to "Standard",
    "technical" to "Technical", "small" to "Small steps", "brisk" to "Brisk")

/**
 * How explanations read: tone, reading level and pace. Not a "learning style": matching lessons to a preferred modality has no
 * experimental support, so these choices never change what is taught or how it is practised. Notes written before these choices
 * existed (the old free-text teaching style) are kept and still used, for tone, language and pace only.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ExplanationSettings(base: String, token: String) {
    val api = remember(base, token) { Api(base, token) }
    var chosen by remember { mutableStateOf<JSONObject?>(null) }
    var notes by remember { mutableStateOf("") }
    var savedNotes by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("") }
    var bad by remember { mutableStateOf(false) }
    var showNotes by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(base, token) {
        try {
            chosen = api.getObject("/teaching-preferences")
            notes = api.getObject("/style-profile").optString("content"); savedNotes = notes; showNotes = notes.isNotBlank()
        } catch (e: CancellationException) { throw e } catch (e: Exception) { status = e.message ?: "Could not load these settings"; bad = true }
    }
    fun save(work: suspend () -> Unit) {
        scope.launch {
            status = "Saving…"; bad = false
            try { work(); status = "Saved" } catch (e: CancellationException) { throw e } catch (e: Exception) { status = e.message ?: "Could not save"; bad = true }
        }
    }
    StudyCard(tone = CardTone.Container) {
        SectionLabel("How explanations read", "LESSONS AND FEEDBACK")
        Text("Choose the tone, reading level and pace of lessons and explanations. Every lesson still uses what helps everyone remember: questions before and after reading, worked examples that fade, and spaced review.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        val current = chosen
        if (current == null && !bad) LoadingBar(Modifier.fillMaxWidth())
        if (current != null) PREFERENCE_LABELS.forEach { (key, label) ->
            val options = current.optJSONObject("options")?.optJSONObject(key) ?: JSONObject()
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(label, style = MaterialTheme.typography.titleSmall)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    options.keys().asSequence().toList().forEach { value ->
                        FilterChip(selected = current.optString(key) == value, label = { Text(PREFERENCE_NAMES[value] ?: value) }, onClick = {
                            val next = JSONObject(current.toString()).put(key, value)
                            chosen = next
                            save { api.put("/teaching-preferences", JSONObject().put("tone", next.optString("tone")).put("reading_level", next.optString("reading_level")).put("pace", next.optString("pace"))) }
                        })
                    }
                }
                // What the chosen option means, in the server's own words.
                options.optString(current.optString(key)).takeIf { it.isNotBlank() }?.let {
                    Text(it.replaceFirstChar { c -> c.uppercase() } + ".", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        Row(Modifier.fillMaxWidth().clickable { showNotes = !showNotes }, verticalAlignment = Alignment.CenterVertically) {
            Text("Other notes (language, examples you relate to)", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
            Text(if (showNotes) "Hide" else "Edit", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        }
        AnimatedVisibility(showNotes) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(notes, { notes = it.take(50000) }, Modifier.fillMaxWidth(), minLines = 3, maxLines = 10, shape = RoundedCornerShape(12.dp),
                    placeholder = { Text("For example: use rugby and cooking examples; spell out every algebra step.") })
                Button(enabled = notes != savedNotes, shape = RoundedCornerShape(50), onClick = { val sent = notes; save { api.put("/style-profile", JSONObject().put("content", sent)); savedNotes = sent } }) { Text("Save notes") }
            }
        }
        // The line is always there, so the card does not jump when "Saved" appears.
        Text(status.ifEmpty { " " }, style = MaterialTheme.typography.bodySmall, color = if (bad) MaterialTheme.colorScheme.error else LocalStudyColours.current.teal)
    }
}
