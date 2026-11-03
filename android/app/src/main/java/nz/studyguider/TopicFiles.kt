package nz.studyguider

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject

private class Folder(val key: String, val label: String, val matches: (JSONObject) -> Boolean)

// The same folders and categories as the website's file manager.
private val folders = listOf(
    Folder("all", "All files") { true },
    Folder("exams", "Exams") { it.optString("category") in setOf("exam_paper", "exam_answers") },
    Folder("slides", "Slides") { it.optString("category") == "slides" },
    Folder("extra", "Extra") { it.optString("category") == "extra" },
    Folder("pending", "Sorting") { it.optString("category") == "auto" },
)
private val categories = listOf(
    "auto" to "Detect automatically", "exam_paper" to "Exam paper", "exam_answers" to "Exam answers or schedule",
    "slides" to "Slides", "extra" to "Extra resource",
)

private fun sizeText(bytes: Long) = if (bytes >= 1048576) "%.1f MB".format(bytes / 1048576.0) else "${maxOf(1, (bytes + 1023) / 1024)} KB"

/**
 * The files of one topic: folders with counts, a name filter, status and size for each file, retry or re-extract,
 * delete (one or several, after a confirmation) and an upload that can name the category. Mirrors the website's Files tab.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TopicFiles(
    resources: JSONArray, busy: Boolean, uploadNotice: String,
    onUpload: (String) -> Unit, onRefresh: () -> Unit, onExtract: (String, Boolean) -> Unit,
    onOpen: (String) -> Unit, onDelete: (List<JSONObject>) -> Unit,
) {
    var folder by rememberSaveable { mutableStateOf("all") }
    var filter by rememberSaveable { mutableStateOf("") }
    var category by rememberSaveable { mutableStateOf("auto") }
    var menu by remember { mutableStateOf(false) }
    var selected by remember { mutableStateOf(setOf<String>()) }
    var confirm by remember { mutableStateOf<List<JSONObject>?>(null) }
    val items = remember(resources) {
        (0 until resources.length()).map { resources.getJSONObject(it) }.filter { it.optString("status") != "deleting" }
            .sortedBy { it.optString("filename").lowercase() }
    }
    LaunchedEffect(items) { selected = selected.intersect(items.map { it.optString("id") }.toSet()) }
    val current = folders.first { it.key == folder }
    val shown = items.filter(current.matches).filter { it.optString("filename").lowercase().contains(filter.trim().lowercase()) }
    val shownIds = shown.map { it.optString("id") }
    val colours = LocalStudyColours.current

    StudyCard(tone = CardTone.Low) {
        Text("Add files", style = MaterialTheme.typography.titleMedium)
        Text("Choose files or a ZIP. Up to 50 MiB per upload; duplicates are kept once.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Box {
            OutlinedButton(onClick = { menu = true }, enabled = !busy, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth()) {
                Text("Category: ${categories.first { it.first == category }.second}  ▾", maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                categories.forEach { (key, label) -> DropdownMenuItem(text = { Text(label) }, onClick = { category = key; menu = false }) }
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(enabled = !busy, onClick = { onUpload(category) }, shape = RoundedCornerShape(50), modifier = Modifier.weight(1f)) { Text("Upload files") }
            OutlinedButton(enabled = !busy, onClick = onRefresh, shape = RoundedCornerShape(50), modifier = Modifier.weight(1f)) { Text("Refresh") }
        }
        if (uploadNotice.isNotEmpty()) StudyChip(uploadNotice, MaterialTheme.colorScheme.onSecondaryContainer, MaterialTheme.colorScheme.secondaryContainer)
    }

    Column(Modifier.fillMaxWidth().animateContentSize(spring(stiffness = 500f)), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            folders.forEach { entry ->
                FilterChip(selected = entry.key == folder, onClick = { folder = entry.key },
                    label = { Text("${entry.label} · ${items.count(entry.matches)}") })
            }
        }
        OutlinedTextField(filter, { filter = it }, label = { Text("Filter by file name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        if (shown.isNotEmpty()) Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = shownIds.isNotEmpty() && shownIds.all { it in selected },
                onCheckedChange = { all -> selected = if (all) selected + shownIds else selected - shownIds.toSet() })
            Text(if (selected.isEmpty()) "Select all" else "${selected.size} selected", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            AnimatedVisibility(selected.isNotEmpty()) {
                TextButton(enabled = !busy, onClick = { confirm = items.filter { it.optString("id") in selected } }) {
                    Text("Delete selected", color = MaterialTheme.colorScheme.error)
                }
            }
        }
        if (shown.isEmpty()) StudyCard(tone = CardTone.Low) {
            Text(if (items.isEmpty()) "No files yet. Upload a PDF, slide deck or photo to begin." else if (filter.isNotBlank()) "No files match." else "This folder is empty.", style = MaterialTheme.typography.bodyMedium)
        }
        shown.forEach { item ->
            val id = item.optString("id")
            val name = item.optString("filename")
            val status = item.optString("status")
            val extension = name.substringAfterLast('.', "").lowercase()
            Surface(shape = RoundedCornerShape(14.dp), color = colours.container, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(start = 4.dp, end = 12.dp, top = 8.dp, bottom = 4.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = id in selected, onCheckedChange = { selected = if (it) selected + id else selected - id })
                        Box(Modifier.size(40.dp).background(MaterialTheme.colorScheme.secondaryContainer, RoundedCornerShape(10.dp)), contentAlignment = Alignment.Center) {
                            Text(extension.take(4).uppercase().ifEmpty { "FILE" }, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSecondaryContainer)
                        }
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(name, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            StatusDot(when (status) {
                                "extracted" -> colours.achieved
                                "failed" -> MaterialTheme.colorScheme.error
                                "pending", "extracting" -> colours.amber
                                else -> colours.outline
                            }, "${item.optString("display_status", status)} · ${item.optInt("page_count")} pages · ${sizeText(item.optLong("size"))}")
                        }
                    }
                    item.optString("error").takeIf { it.isNotBlank() }?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(start = 12.dp)) }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End, verticalAlignment = Alignment.CenterVertically) {
                        if (extension in listOf("pdf", "png", "jpg", "jpeg")) TextButton(onClick = { onOpen(id) }) { Text("Open") }
                        if (status == "failed") TextButton(enabled = !busy, onClick = { onExtract(id, true) }) { Text("Retry") }
                        else if (status == "extracted") TextButton(enabled = !busy, onClick = { onExtract(id, false) }) { Text("Re-extract") }
                        TextButton(enabled = !busy, onClick = { confirm = listOf(item) }) { Text("Delete", color = MaterialTheme.colorScheme.error) }
                    }
                }
            }
        }
    }

    confirm?.let { doomed ->
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text("Delete ${if (doomed.size == 1) doomed[0].optString("filename") else "${doomed.size} files"}?") },
            text = { Text("This also deletes the extracted text. Lessons that cite a file must be deleted first.") },
            confirmButton = { TextButton(onClick = { confirm = null; onDelete(doomed) }) { Text("Delete", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(onClick = { confirm = null }) { Text("Cancel") } },
        )
    }
}
