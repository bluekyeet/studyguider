package nz.studyguider

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.json.JSONObject

/** One topic with the level and subject it sits under. */
data class PickableTopic(val id: Long, val level: Int, val subject: String, val topic: String)

/** A topic from the `Pair(subjectName, topicJson)` list the app keeps, where the topic carries `subject_level`. */
fun Pair<String, JSONObject>.pickable() = PickableTopic(second.getLong("id"), second.optInt("subject_level"), first, second.optString("name"))

/**
 * Picks a topic in three short steps (level, then subject, then topic) so a long list of subjects never becomes one long menu.
 * A level or subject with only one choice is chosen for you; changing a step clears the ones after it.
 */
@Composable
fun TopicPicker(
    items: List<PickableTopic>,
    selected: Long?,
    onSelect: (Long?) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val current = items.firstOrNull { it.id == selected }
    var pickedLevel by remember { mutableStateOf(current?.level) }
    var pickedSubject by remember { mutableStateOf(current?.subject) }
    val levels = items.map { it.level }.distinct().sorted()
    val level = pickedLevel?.takeIf { it in levels } ?: levels.singleOrNull()
    val subjects = items.filter { it.level == level }.map { it.subject }.distinct().sortedBy { it.lowercase() }
    val subject = pickedSubject?.takeIf { it in subjects } ?: subjects.singleOrNull()
    val topics = items.filter { it.level == level && it.subject == subject }.sortedBy { it.topic.lowercase() }
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        PickerMenu("Choose a level", level?.let { "NCEA Level $it" }, levels.map { it to "NCEA Level $it" }, enabled) { pickedLevel = it; pickedSubject = null; onSelect(null) }
        PickerMenu("Choose a subject", subject, subjects.map { it to it }, enabled && level != null) { pickedSubject = it; onSelect(null) }
        PickerMenu("Choose a topic", items.firstOrNull { it.id == selected && it.level == level && it.subject == subject }?.topic, topics.map { it.id to it.topic }, enabled && subject != null) { onSelect(it) }
    }
}

/** A full-width button that opens a menu of [options]; a null key such as "All" is allowed. */
@Composable
fun <T> PickerMenu(placeholder: String, value: String?, options: List<Pair<T, String>>, enabled: Boolean = true, onPick: (T) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(enabled = enabled && options.isNotEmpty(), onClick = { open = true }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            Text((value ?: placeholder) + "  ▾", maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }, modifier = Modifier.heightIn(max = 360.dp)) {
            options.forEach { (key, label) -> DropdownMenuItem(text = { Text(label) }, onClick = { open = false; onPick(key) }) }
        }
    }
}
