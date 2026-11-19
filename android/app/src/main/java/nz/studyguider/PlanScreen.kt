package nz.studyguider

import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

// Plan: what you study (an NCEA programme or university papers), when each assessment is, and what the planner does with it
// (the Android counterpart of server/web-plan.js). A paper comes in from an AUT course code, a pasted or uploaded outline, or
// by hand; every import is a draft to check and edit before it is saved.

private val INSTITUTIONS = listOf("nzqa" to "NCEA (school)", "aut" to "AUT", "uoa" to "University of Auckland", "other" to "Somewhere else")
private val KINDS = listOf("exam" to "Exam", "test" to "Test", "assignment" to "Assignment", "lab" to "Lab", "project" to "Project", "presentation" to "Presentation",
    "portfolio" to "Portfolio", "practical" to "Practical", "quiz" to "Quiz", "internal" to "NCEA internal", "external_exam" to "NCEA external exam", "other" to "Other")
private val GOALS = listOf("long_term" to "Keep it long term", "foundation" to "Later papers build on it", "assessment" to "Only for its assessments")
private val SCALES = listOf("ncea" to "NCEA (N/A/M/E)", "aut9" to "AUT (A+ to D)", "uoa9" to "University of Auckland (A+ to D-)", "percent" to "Percentage")

/** Everything the Plan page shows, fetched together. */
class PlanData(val token: String, val curriculum: JSONObject, val calendars: JSONObject, val plan: JSONObject, val estimates: List<JSONObject>) {
    val subjects get() = curriculum.optJSONArray("subjects")?.objectList().orEmpty()
    val programmes get() = curriculum.optJSONArray("programmes")?.objectList().orEmpty()
    val today: String get() = curriculum.optString("today")
}
private var planCache: PlanData? = null

suspend fun loadPlan(api: Api): PlanData = PlanData(api.token, api.getObject("/curriculum"), api.getObject("/calendars"), api.getObject("/review-plan"),
    api.getArray("/grade-estimates").objectList()).also { planCache = it }

/** The subject's details as the server takes them, with [change] applied. */
private fun details(subject: JSONObject, change: JSONObject.() -> Unit = {}): JSONObject = JSONObject().apply {
    put("programme_id", subject.opt("programme_id") ?: JSONObject.NULL)
    put("code", subject.optString("code"))
    put("points", subject.opt("points") ?: JSONObject.NULL)
    put("term", subject.optString("term"))
    put("start_date", subject.opt("start_date") ?: JSONObject.NULL)
    put("end_date", subject.opt("end_date") ?: JSONObject.NULL)
    put("grade_scale", subject.optString("grade_scale").ifBlank { "ncea" })
    put("pass_rule", subject.optString("pass_rule"))
    put("retention_goal", subject.optString("retention_goal").ifBlank { "long_term" })
    put("outline_url", subject.optString("outline_url"))
    put("source", subject.optString("source").ifBlank { "manual" })
    change()
}

private fun orNull(value: String): Any = value.trim().toDoubleOrNull() ?: JSONObject.NULL
private fun dateOrNull(value: String): Any = value.ifBlank { null } ?: JSONObject.NULL

/** How an estimate is toned: university by passing or not, NCEA by grade. */
fun estimateTone(estimate: JSONObject): String {
    val grade = estimate.optString("estimate")
    return if (estimate.optString("kind") == "university") (if (estimate.optBoolean("passing")) "ok" else "bad")
    else if (grade == "Merit" || grade == "Excellence") "ok" else if (grade == "Not achieved") "warn" else ""
}

/**
 * The Plan page's own cards, placed in the caller's column. [onStartReviews] opens Review; [onOpenResources] opens the library.
 */
@Composable
fun PlanContent(base: String, token: String, onStartReviews: () -> Unit, onOpenResources: () -> Unit) {
    val api = remember(base, token) { Api(base, token) }
    var data by remember { mutableStateOf(planCache?.takeIf { it.token == token }) }
    var loading by remember { mutableStateOf(data == null) }
    var error by remember { mutableStateOf("") }
    var failure by remember { mutableStateOf("") }      // a save that did not go through
    var busy by remember { mutableStateOf(false) }
    var reload by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(base, token, reload) {
        error = ""
        try { data = loadPlan(api) } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load your plan" }
        finally { loading = false }
    }
    // Every change is saved straight away, then the page is read again so the planner's numbers follow.
    val act: (suspend () -> Unit) -> Unit = { work ->
        scope.launch {
            busy = true
            try { work(); reload++ } catch (e: CancellationException) { throw e } catch (e: Exception) { failure = e.message ?: "Could not save" }
            finally { busy = false }
        }
    }
    if (failure.isNotEmpty()) AlertDialog(onDismissRequest = { failure = "" }, title = { Text("Not saved") }, text = { Text(failure) },
        confirmButton = { TextButton(onClick = { failure = "" }) { Text("OK") } })

    Text("Your programme, its assessment dates, and how reviews and lessons are planned around them.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    if (loading) DelayedLoading { LoadingBar(Modifier.fillMaxWidth()) }
    if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
    if (error.isNotEmpty()) { Text(error, color = MaterialTheme.colorScheme.error); OutlinedButton(onClick = { reload++ }) { Text("Try again") } }
    val plan = data ?: return
    val curriculum = plan.curriculum

    if (!curriculum.optBoolean("set_up")) {
        StudyCard(tone = CardTone.Container) {
            SectionLabel("Set up your study plan", "GET STARTED")
            Text("Tell StudyGuider where you study and when your assessments are. Reviews then come back on a schedule that keeps what you learn, and lessons shift to exam practice as an assessment gets close.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            val existing = plan.subjects.count { it.optBoolean("studying") }
            if (existing > 0) Text("Everything you already have stays as it is: your ${if (existing == 1) "subject" else "subjects"}, lessons, review history and files. Setting up only adds dates and details.",
                style = MaterialTheme.typography.bodyMedium)
            ProgrammeForm(api, plan, first = true, enabled = !busy, act = act)
        }
        return
    }

    TodayCard(api, plan, busy, act, onStartReviews)
    ComingAssessments(plan)
    val estimateOf = plan.estimates.associateBy { it.optLong("subject_id") }
    plan.programmes.forEach { programme -> ProgrammeSection(api, plan, programme, estimateOf, busy, act, onOpenResources) }

    val loose = plan.subjects.filter { it.isNull("programme_id") && it.optBoolean("studying") }
    if (loose.isNotEmpty()) StudyCard(tone = CardTone.Low) {
        Text("Subjects not in a programme", style = MaterialTheme.typography.titleMedium)
        Text("These still get lessons and reviews as before. Add them to a programme to plan around their assessment dates.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        loose.forEach { Text("• ${it.optString("name")}", style = MaterialTheme.typography.bodyMedium) }
    }
    var another by rememberSaveable { mutableStateOf(false) }
    StudyCard(tone = CardTone.Low) {
        Row(Modifier.fillMaxWidth().clickable { another = !another }, verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Another programme", style = MaterialTheme.typography.titleMedium)
                Text("For example, the university you start next year while you finish NCEA: its papers get a refresher before they begin.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(if (another) "Hide" else "Add", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(start = 8.dp))
        }
        AnimatedVisibility(another) { Column(verticalArrangement = Arrangement.spacedBy(10.dp)) { ProgrammeForm(api, plan, first = false, enabled = !busy, act = { work -> act { work(); another = false } }) } }
    }
}

// ---- setting up a programme ---------------------------------------------------------------------------------------------------

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ProgrammeForm(api: Api, plan: PlanData, first: Boolean, enabled: Boolean, act: (suspend () -> Unit) -> Unit) {
    var institution by rememberSaveable { mutableStateOf(if (first) "nzqa" else "aut") }
    var level by rememberSaveable { mutableStateOf("Level 2") }
    var year by rememberSaveable { mutableStateOf(java.time.LocalDate.now().year.toString()) }
    var name by rememberSaveable { mutableStateOf("") }
    var stage by rememberSaveable { mutableStateOf("Year 1") }
    var hours by rememberSaveable { mutableStateOf(trimNumber(plan.curriculum.doubleOrNull("hours_per_week") ?: 10.0)) }
    if (first) Text("Where do you study?", style = MaterialTheme.typography.titleSmall)
    // Two by two, each choice the same size, so the four read as one set.
    INSTITUTIONS.chunked(2).forEach { pair ->
        Row(Modifier.fillMaxWidth().height(IntrinsicSize.Max), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            pair.forEach { (key, label) ->
                val chosen = institution == key
                Surface(onClick = { institution = key }, enabled = enabled, shape = RoundedCornerShape(14.dp), modifier = Modifier.weight(1f).fillMaxHeight(),
                    color = if (chosen) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
                    border = androidx.compose.foundation.BorderStroke(if (chosen) 2.dp else 1.dp, if (chosen) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)) {
                    Box(Modifier.heightIn(min = 52.dp).padding(horizontal = 12.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
                        Text(label, style = MaterialTheme.typography.labelLarge, textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            color = if (chosen) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurface)
                    }
                }
            }
        }
    }
    if (institution == "nzqa") Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        PickField("Level", listOf("Level 1" to "NCEA Level 1", "Level 2" to "NCEA Level 2", "Level 3" to "NCEA Level 3"), level, { level = it }, Modifier.weight(1.4f), enabled)
        NumberField("Year", year, { year = it }, Modifier.weight(1f), enabled, whole = true)
    } else {
        OutlinedTextField(name, { name = it.take(200) }, Modifier.fillMaxWidth(), enabled = enabled, singleLine = true, label = { Text("Programme") },
            placeholder = { Text("Bachelor of Computer and Information Sciences") }, shape = RoundedCornerShape(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(stage, { stage = it.take(100) }, Modifier.weight(1.4f), enabled = enabled, singleLine = true, label = { Text("Year of study") }, shape = RoundedCornerShape(12.dp))
            NumberField("Starting year", year, { year = it }, Modifier.weight(1f), enabled, whole = true)
        }
    }
    if (first) {
        NumberField("Hours a week you can study", hours, { hours = it }, Modifier.fillMaxWidth(), enabled)
        Text("Time available sets how many reviews a day you get (about a third of your study time). You can change it later.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    Button(enabled = enabled && (institution == "nzqa" || name.isNotBlank()), shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), onClick = {
        act {
            val ncea = institution == "nzqa"
            val programme = JSONObject(api.post("/programmes", JSONObject()
                .put("kind", if (ncea) "ncea" else if (institution == "other") "other" else "university").put("institution", institution)
                .put("name", if (ncea) "NCEA" else name.trim()).put("level", if (ncea) level else stage.trim()).put("year", year.toIntOrNull() ?: JSONObject.NULL)))
            if (first) api.put("/study-time", JSONObject().put("hours_per_week", (hours.toDoubleOrNull() ?: 10.0).coerceIn(0.5, 80.0)))
            // The NCEA subjects already being studied join the programme, keeping everything they hold.
            if (ncea) plan.subjects.filter { it.optBoolean("studying") && it.isNull("programme_id") && it.optString("grade_scale") == "ncea" }.forEach { subject ->
                api.put("/subjects/${subject.getLong("subject_id")}/details", details(subject) { put("programme_id", programme.getLong("id")) })
            }
        }
    }) { Text(if (first) "Save and continue" else "Add programme") }
}

// ---- today and the coming assessments ------------------------------------------------------------------------------------------

@Composable
private fun TodayCard(api: Api, plan: PlanData, busy: Boolean, act: (suspend () -> Unit) -> Unit, onStartReviews: () -> Unit) {
    val items = plan.plan.optJSONArray("items")?.length() ?: 0
    val leftOut = plan.plan.optInt("left_out")
    var editHours by remember { mutableStateOf(false) }
    val hours = plan.curriculum.doubleOrNull("hours_per_week")
    StudyCard(tone = CardTone.Container) {
        SectionLabel("Today", "REVIEW PLAN")
        Row(Modifier.fillMaxWidth().height(IntrinsicSize.Max), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatTile("$items", "Reviews in today’s list", Modifier.weight(1f).fillMaxHeight())
            StatTile("$leftOut", "Left for another day", Modifier.weight(1f).fillMaxHeight())
            StatTile("${plan.plan.optInt("cap")}", "Daily review limit", Modifier.weight(1f).fillMaxHeight())
        }
        if (leftOut > 0) Text("More is due than fits today. The most important come first: questions for heavily weighted, close assessments that you are most likely to have forgotten.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(if (hours == null) "Study time not set" else "${trimNumber(hours)} hours a week to study", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            TextButton(enabled = !busy, onClick = { editHours = true }) { Text("Change") }
        }
        if (items > 0) Button(onClick = onStartReviews, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Start $items review${if (items == 1) "" else "s"}") }
    }
    if (editHours) {
        var draft by remember { mutableStateOf(trimNumber(hours)) }
        val value = draft.toDoubleOrNull()
        AlertDialog(onDismissRequest = { editHours = false }, title = { Text("Hours a week you can study") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                NumberField("Hours a week", draft, { draft = it })
                Text("About a third of this time goes to reviews, which sets the daily limit.", style = MaterialTheme.typography.bodySmall)
            } },
            confirmButton = { TextButton(enabled = value != null && value in 0.5..80.0, onClick = { editHours = false; act { api.put("/study-time", JSONObject().put("hours_per_week", value)) } }) { Text("Save") } },
            dismissButton = { TextButton(onClick = { editHours = false }) { Text("Cancel") } })
    }
}

@Composable
private fun ComingAssessments(plan: PlanData) {
    val today = plan.today
    val dated = plan.subjects.flatMap { subject ->
        subject.optJSONArray("assessments")?.objectList().orEmpty()
            .filter { !it.isNull("due_date") && it.optString("due_date") >= today && it.optString("status") != "done" }
            .map { subject.optString("name") to it }
    }.sortedBy { it.second.optString("due_date") }.take(12)
    val ready = plan.plan.optJSONArray("assessments")?.objectList().orEmpty().associateBy { it.optLong("assessment_id") }
    StudyCard(tone = CardTone.Container) {
        SectionLabel("Coming assessments", "WHAT IS NEXT")
        if (dated.isEmpty()) { Text("No dated assessments yet. Add their dates below and the planner will work back from them.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant); return@StudyCard }
        dated.forEachIndexed { index, (subject, a) ->
            if (index > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            AssessmentReadiness(subject, a, ready[a.optLong("id")], daysUntil(a.optString("due_date"), today) ?: 0)
        }
        Text("Predicted recall: the chance you would remember the reviewed questions on the day if you did no more reviews, from your review history. In the last three weeks lessons turn into mixed exam-style practice; in the last two, reviews aim higher.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** One coming assessment: when, what, how much it counts, and how ready the reviewed questions are. Also used on Home. */
@Composable
fun AssessmentReadiness(subject: String, assessment: JSONObject, readiness: JSONObject?, days: Int) {
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("${shortDate(assessment.optString("due_date"))} · ${inDays(days)}", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary, modifier = Modifier.weight(1f))
            if (days <= 21) ToneChip(if (days <= 14) "Final review" else "Exam practice", "warn")
        }
        Text(listOf(subject, assessment.optString("title")).filter { it.isNotBlank() }.joinToString(" · "), style = MaterialTheme.typography.titleSmall)
        val recall = readiness?.doubleOrNull("predicted_recall")
        val unanswered = readiness?.optInt("unanswered") ?: 0
        val weight = assessment.doubleOrNull("weight_pct")?.let { "${trimNumber(it)}% of the grade" } ?: assessment.doubleOrNull("credits")?.let { "${trimNumber(it)} credits" }
        val facts = listOfNotNull(weight,
            if (recall == null) (if (unanswered > 0) "$unanswered questions not answered yet" else "No reviews yet") else "Predicted recall ${percentOrDash(recall)}",
            readiness?.optInt("at_risk")?.takeIf { it > 0 && recall != null }?.let { "$it at risk" },
            unanswered.takeIf { it > 0 && recall != null }?.let { "$it not answered yet" })
        Text(facts.joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (recall != null) LinearProgressIndicator(progress = { recall.toFloat().coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(50)),
            color = if (recall >= 0.85) LocalStudyColours.current.achieved else LocalStudyColours.current.amber, trackColor = LocalStudyColours.current.containerHighest)
    }
}

// ---- a programme and its subjects or papers ---------------------------------------------------------------------------------------

@Composable
private fun ProgrammeSection(api: Api, plan: PlanData, programme: JSONObject, estimateOf: Map<Long, JSONObject>, busy: Boolean,
                             act: (suspend () -> Unit) -> Unit, onOpenResources: () -> Unit) {
    val ncea = programme.optString("kind") == "ncea"
    val title = if (ncea) "NCEA ${programme.optString("level")} ${programme.opt("year")?.takeIf { it != JSONObject.NULL } ?: ""}".trim()
        else programme.optString("name").ifBlank { "Programme" }
    val place = if (ncea) "" else listOf(mapOf("aut" to "AUT", "uoa" to "University of Auckland")[programme.optString("institution")] ?: "Other", programme.optString("level")).filter { it.isNotBlank() }.joinToString(" · ")
    var menu by remember { mutableStateOf(false) }
    var confirm by remember { mutableStateOf(false) }
    var addPaper by remember { mutableStateOf(false) }
    val subjects = plan.subjects.filter { !it.isNull("programme_id") && it.optLong("programme_id") == programme.optLong("id") }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                if (place.isNotEmpty()) Text(place.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                Text(title, style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
            }
            Box {
                IconButton(onClick = { menu = true }) { Text("⋮", style = MaterialTheme.typography.titleLarge) }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("Remove programme", color = MaterialTheme.colorScheme.error) }, onClick = { menu = false; confirm = true })
                }
            }
        }
        if (subjects.isEmpty()) Text(if (ncea) "No subjects yet. Add one below." else "No papers yet. Add one below.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        subjects.forEach { subject -> key(subject.optLong("subject_id")) { SubjectCard(api, subject, ncea, estimateOf[subject.optLong("subject_id")], plan.today, busy, act) } }
        if (ncea) AddNceaSubject(api, plan, programme, busy, act, onOpenResources)
        else OutlinedButton(enabled = !busy, onClick = { addPaper = true }, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("+  Add a paper") }
    }
    if (confirm) AlertDialog(onDismissRequest = { confirm = false }, title = { Text("Remove this programme?") },
        text = { Text("Its subjects, lessons and reviews stay; only the grouping goes.") },
        confirmButton = { TextButton(onClick = { confirm = false; act { api.delete("/programmes/${programme.getLong("id")}") } }) { Text("Remove", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirm = false }) { Text("Cancel") } })
    if (addPaper) PaperDialog(api, programme, plan.calendars, onDismiss = { addPaper = false }, onSaved = { addPaper = false; act { } })
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SubjectCard(api: Api, subject: JSONObject, ncea: Boolean, estimate: JSONObject?, today: String, busy: Boolean, act: (suspend () -> Unit) -> Unit) {
    val id = subject.getLong("subject_id")
    var open by rememberSaveable(id) { mutableStateOf(false) }
    var editing by remember { mutableStateOf<JSONObject?>(null) }       // an assessment being edited; an empty object is a new one
    var standard by remember { mutableStateOf(false) }
    val assessments = subject.optJSONArray("assessments")?.objectList().orEmpty()
    val outcomes = subject.optJSONArray("outcomes")?.objectList().orEmpty()
    val topics = subject.optJSONArray("topics")?.objectList().orEmpty()
    val next = assessments.filter { !it.isNull("due_date") && it.optString("due_date") >= today && it.optString("status") != "done" }.minByOrNull { it.optString("due_date") }
    Surface(shape = RoundedCornerShape(16.dp), color = LocalStudyColours.current.container, modifier = Modifier.fillMaxWidth()) {
        Column {
            Row(Modifier.fillMaxWidth().clickable(onClickLabel = if (open) "Close ${subject.optString("name")}" else "Open ${subject.optString("name")}") { open = !open }.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(subject.optString("name"), style = MaterialTheme.typography.titleMedium)
                    val facts = listOfNotNull(subject.doubleOrNull("points")?.let { "${trimNumber(it)} points" }, subject.optInt("level").takeIf { it > 0 }?.let { "Level $it" },
                        subject.optString("term").takeIf { it.isNotBlank() },
                        when (subject.optString("source")) { "aut_descriptor" -> "From AUT descriptor"; "outline" -> "From your outline"; else -> null })
                    if (facts.isNotEmpty()) Text(facts.joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (estimate != null && !estimate.isNull("estimate")) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ToneChip(estimate.optString("estimate"), estimateTone(estimate))
                        Text(estimate.optString("summary"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Text(if (next != null) "Next: ${next.optString("title")} · ${shortDate(next.optString("due_date"))} (${inDays(daysUntil(next.optString("due_date"), today) ?: 0)})"
                        else if (assessments.isEmpty()) "No assessments yet" else "${assessments.size} assessment${if (assessments.size == 1) "" else "s"}, none coming with a date",
                        style = MaterialTheme.typography.bodySmall, color = if (next != null) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text(if (open) "▴" else "▾", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            AnimatedVisibility(open) {
                Column(Modifier.padding(start = 16.dp, end = 16.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (estimate != null) {
                        if (estimate.isNull("estimate")) Text(estimate.optString("reason"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        estimate.optJSONArray("must_pass_failed")?.stringList()?.takeIf { it.isNotEmpty() }?.let { ToneChip("Below the pass mark on: ${it.joinToString(", ")}", "bad") }
                        estimate.optString("notice").takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                    if (subject.optString("pass_rule").isNotBlank()) Text("To pass: ${subject.optString("pass_rule")}", style = MaterialTheme.typography.bodySmall)
                    // How long the knowledge must last sets the maintenance target after the assessments.
                    PickField("After its assessments", GOALS, subject.optString("retention_goal").ifBlank { "long_term" }, { goal ->
                        act { api.put("/subjects/$id/details", details(subject) { put("retention_goal", goal) }) }
                    }, Modifier.fillMaxWidth(), enabled = !busy)

                    Text("Assessments", style = MaterialTheme.typography.titleSmall)
                    if (assessments.isEmpty()) Text("No assessments yet.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    assessments.forEach { a ->
                        Surface(onClick = { editing = a }, enabled = !busy, shape = RoundedCornerShape(12.dp), color = LocalStudyColours.current.containerHigh, modifier = Modifier.fillMaxWidth()) {
                            Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(a.optString("title"), style = MaterialTheme.typography.titleSmall)
                                    val tags = listOfNotNull(KINDS.firstOrNull { it.first == a.optString("kind") }?.second, a.doubleOrNull("weight_pct")?.let { "${trimNumber(it)}%" },
                                        a.doubleOrNull("credits")?.let { "${trimNumber(it)} credits" }, if (a.optBoolean("must_pass")) "Must pass" else null,
                                        a.optJSONArray("outcome_codes")?.stringList()?.takeIf { it.isNotEmpty() }?.joinToString(", "))
                                    Text(tags.joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Text(if (a.isNull("due_date")) "No date" else niceDate(a.optString("due_date")), style = MaterialTheme.typography.labelLarge)
                                    Text(a.doubleOrNull("result_pct")?.let { "Mark ${trimNumber(it)}%" } ?: "Not back yet", style = MaterialTheme.typography.bodySmall,
                                        color = if (a.isNull("result_pct")) MaterialTheme.colorScheme.onSurfaceVariant else LocalStudyColours.current.achieved)
                                }
                            }
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(enabled = !busy, onClick = { editing = JSONObject() }, shape = RoundedCornerShape(50)) { Text("Add assessment") }
                        if (ncea) OutlinedButton(enabled = !busy, onClick = { standard = true }, shape = RoundedCornerShape(50)) { Text("Add a standard") }
                    }

                    if (outcomes.isNotEmpty()) {
                        Text(if (ncea) "Standards" else "Learning outcomes", style = MaterialTheme.typography.titleSmall)
                        outcomes.forEach { o ->
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text(o.optString("code"), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                                Text(o.optString("title") + (o.doubleOrNull("credits")?.let { " (${trimNumber(it)} credits)" } ?: ""), style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                            }
                        }
                    }
                    if (topics.isNotEmpty()) {
                        Text("Topics", style = MaterialTheme.typography.titleSmall)
                        topics.forEach { topic ->
                            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text(topic.optString("name"), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                                    ToneChip(if (topic.optBoolean("active")) "Learning" else "Off", if (topic.optBoolean("active")) "ok" else "")
                                }
                                // Which outcomes the topic covers: this is how the planner knows which assessments its reviews are for.
                                if (outcomes.isNotEmpty()) {
                                    val linked = topic.optJSONArray("outcome_ids")?.let { ids -> (0 until ids.length()).map { ids.optLong(it) } }.orEmpty()
                                    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        outcomes.forEach { o ->
                                            val oid = o.optLong("id")
                                            FilterChip(selected = oid in linked, enabled = !busy, label = { Text(o.optString("code")) }, onClick = {
                                                val next = if (oid in linked) linked - oid else linked + oid
                                                act { api.put("/topics/${topic.getLong("id")}/outcomes", JSONObject().put("outcome_ids", JSONArray(next))) }
                                            })
                                        }
                                    }
                                }
                            }
                        }
                        Text("Upload slides and readings for each topic in Resources, and switch topics on in Settings to get a lesson each night.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
    editing?.let { a -> AssessmentSheet(api, id, a, ncea, onDismiss = { editing = null }, act = act) }
    if (standard) StandardSheet(api, id, onDismiss = { standard = false }, act = act)
}

/** Add or change one assessment: what it is, when, how much it counts, and the mark once it is back. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AssessmentSheet(api: Api, subjectId: Long, existing: JSONObject, ncea: Boolean, onDismiss: () -> Unit, act: (suspend () -> Unit) -> Unit) {
    val isNew = !existing.has("id")
    var title by remember { mutableStateOf(existing.optString("title")) }
    var kind by remember { mutableStateOf(existing.optString("kind").ifBlank { if (ncea) "external_exam" else "exam" }) }
    var date by remember { mutableStateOf(existing.stringOrNull("due_date").orEmpty()) }
    var weight by remember { mutableStateOf(trimNumber(existing.doubleOrNull("weight_pct"))) }
    var mark by remember { mutableStateOf(trimNumber(existing.doubleOrNull("result_pct"))) }
    var mustPass by remember { mutableStateOf(existing.optBoolean("must_pass")) }
    var confirmRemove by remember { mutableStateOf(false) }
    val valid = title.isNotBlank() && (weight.isBlank() || (weight.toDoubleOrNull() ?: -1.0) in 0.0..100.0) && (mark.isBlank() || (mark.toDoubleOrNull() ?: -1.0) in 0.0..100.0)
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = MaterialTheme.colorScheme.surface, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 24.dp).imePadding(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(if (isNew) "New assessment" else "Assessment", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
            OutlinedTextField(title, { title = it.take(300) }, Modifier.fillMaxWidth(), singleLine = true, label = { Text("Name") }, placeholder = { Text("Final exam") }, shape = RoundedCornerShape(12.dp))
            PickField("Kind", KINDS, kind, { kind = it }, Modifier.fillMaxWidth())
            DateField("Date", date, { date = it }, Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                NumberField("Weight %", weight, { weight = it }, Modifier.weight(1f))
                NumberField("Your mark %", mark, { mark = it }, Modifier.weight(1f), placeholder = "Not back yet")
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Must pass", style = MaterialTheme.typography.bodyLarge)
                    Text("You have to pass this one to pass the paper.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(mustPass, { mustPass = it })
            }
            if (!isNew && mark.isBlank()) Text("Enter your mark when it comes back: the grade estimate is the weighted marks so far.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(enabled = valid, shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), onClick = {
                val body = JSONObject().put("title", title.trim()).put("kind", kind).put("due_date", dateOrNull(date)).put("weight_pct", orNull(weight))
                    .put("credits", existing.opt("credits") ?: JSONObject.NULL).put("must_pass", mustPass)
                    .put("standard_number", existing.opt("standard_number") ?: JSONObject.NULL).put("outcome_codes", existing.optJSONArray("outcome_codes") ?: JSONArray())
                    .put("status", if (mark.isBlank()) "planned" else "done").put("result_pct", orNull(mark))
                onDismiss()
                act { if (isNew) api.post("/subjects/$subjectId/assessments", body) else api.put("/assessments/${existing.getLong("id")}", body) }
            }) { Text(if (isNew) "Add assessment" else "Save") }
            if (!isNew) TextButton(onClick = { confirmRemove = true }, modifier = Modifier.fillMaxWidth()) { Text("Remove assessment", color = MaterialTheme.colorScheme.error) }
        }
    }
    if (confirmRemove) AlertDialog(onDismissRequest = { confirmRemove = false }, title = { Text("Remove ${existing.optString("title")}?") },
        confirmButton = { TextButton(onClick = { confirmRemove = false; onDismiss(); act { api.delete("/assessments/${existing.getLong("id")}") } }) { Text("Remove", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirmRemove = false }) { Text("Cancel") } })
}

/** An NCEA standard and the date it is assessed: saved as an outcome plus its assessment. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StandardSheet(api: Api, subjectId: Long, onDismiss: () -> Unit, act: (suspend () -> Unit) -> Unit) {
    var number by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var credits by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("external_exam") }
    var date by remember { mutableStateOf("") }
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = MaterialTheme.colorScheme.surface, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 24.dp).imePadding(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Add a standard", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                NumberField("Standard number", number, { number = it }, Modifier.weight(1.4f), placeholder = "91171", whole = true)
                NumberField("Credits", credits, { credits = it }, Modifier.weight(1f), whole = true)
            }
            OutlinedTextField(title, { title = it.take(200) }, Modifier.fillMaxWidth(), label = { Text("Title") }, placeholder = { Text("Demonstrate understanding of mechanics") }, shape = RoundedCornerShape(12.dp))
            PickField("Assessed", listOf("external_exam" to "External exam", "internal" to "Internal"), kind, { kind = it }, Modifier.fillMaxWidth())
            DateField("Date (exam or due date)", date, { date = it }, Modifier.fillMaxWidth())
            Text("NCEA 2026 external exams run 10 November to 4 December; check your own timetable for each exam’s date.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(enabled = (number.toIntOrNull() ?: 0) > 0 && title.isNotBlank(), shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), onClick = {
                val n = number.toInt(); val code = "AS$n"
                onDismiss()
                act {
                    api.post("/subjects/$subjectId/outcomes", JSONObject().put("code", code).put("title", title.trim()).put("credits", orNull(credits)).put("standard_number", n))
                    api.post("/subjects/$subjectId/assessments", JSONObject().put("title", "$code ${if (kind == "internal") "internal" else "external exam"}").put("kind", kind)
                        .put("due_date", dateOrNull(date)).put("credits", orNull(credits)).put("standard_number", n).put("outcome_codes", JSONArray().put(code)))
                }
            }) { Text("Add standard") }
        }
    }
}

@Composable
private fun AddNceaSubject(api: Api, plan: PlanData, programme: JSONObject, busy: Boolean, act: (suspend () -> Unit) -> Unit, onOpenResources: () -> Unit) {
    val free = plan.subjects.filter { it.isNull("programme_id") && it.optString("grade_scale") == "ncea" }
    var pick by remember(free.size) { mutableStateOf(free.firstOrNull()?.optLong("subject_id")?.toString().orEmpty()) }
    StudyCard(tone = CardTone.Low) {
        Text("Add a subject", style = MaterialTheme.typography.titleMedium)
        if (free.isEmpty()) {
            Text("Every NCEA subject is in a programme. Add new subjects in Resources.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedButton(onClick = onOpenResources, shape = RoundedCornerShape(50)) { Text("Open Resources") }
        } else {
            PickField("Subject", free.map { it.optLong("subject_id").toString() to "${it.optString("name")} (Level ${it.optInt("level")})" }, pick, { pick = it }, Modifier.fillMaxWidth(), enabled = !busy)
            Button(enabled = !busy && pick.isNotEmpty(), shape = RoundedCornerShape(50), onClick = {
                val subject = free.first { it.optLong("subject_id").toString() == pick }
                act { api.put("/subjects/$pick/details", details(subject) { put("programme_id", programme.getLong("id")); put("grade_scale", "ncea") }) }
            }) { Text("Add to programme") }
        }
    }
}

// ---- university: adding a paper -------------------------------------------------------------------------------------------------

private class DraftOutcome(code: String, title: String) { var code by mutableStateOf(code); var title by mutableStateOf(title) }
private class DraftAssessment(json: JSONObject) {
    var title by mutableStateOf(json.optString("title"))
    var kind by mutableStateOf(json.optString("kind").ifBlank { "other" })
    var weight by mutableStateOf(trimNumber(json.doubleOrNull("weight_pct")))
    var date by mutableStateOf(json.stringOrNull("due_date").orEmpty())
    var outcomes by mutableStateOf(json.optJSONArray("outcome_codes")?.stringList().orEmpty().joinToString(", "))
    var mustPass by mutableStateOf(json.optBoolean("must_pass"))
}

/** A paper read from a descriptor or outline (or empty, to type in), editable before it is saved. */
private class PaperDraft(val json: JSONObject) {
    var code by mutableStateOf(json.optString("code"))
    var title by mutableStateOf(json.optString("title"))
    var points by mutableStateOf(trimNumber(json.doubleOrNull("points")))
    var level by mutableStateOf(json.optInt("level").takeIf { it > 0 }?.toString().orEmpty())
    var term by mutableStateOf("")
    var start by mutableStateOf("")
    var end by mutableStateOf("")
    var scale by mutableStateOf(json.optString("grade_scale").ifBlank { "percent" })
    val outcomes = mutableStateListOf<DraftOutcome>().apply { json.optJSONArray("outcomes")?.objectList()?.forEach { add(DraftOutcome(it.optString("code"), it.optString("title"))) } }
    val assessments = mutableStateListOf<DraftAssessment>().apply { json.optJSONArray("assessments")?.objectList()?.forEach { add(DraftAssessment(it)) } }
    var rule by mutableStateOf(json.optString("pass_rule"))
    var goal by mutableStateOf("long_term")
    var topics by mutableStateOf(true)
    val weightTotal get() = assessments.sumOf { it.weight.toDoubleOrNull() ?: 0.0 }
}

@Composable
private fun PaperDialog(api: Api, programme: JSONObject, calendars: JSONObject, onDismiss: () -> Unit, onSaved: () -> Unit) {
    val institution = programme.optString("institution")
    var way by rememberSaveable { mutableStateOf(if (institution == "aut") "aut" else "outline") }
    var draft by remember { mutableStateOf<PaperDraft?>(null) }
    var busy by remember { mutableStateOf(false) }
    var note by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var code by rememberSaveable { mutableStateOf("") }
    var outline by rememberSaveable { mutableStateOf("") }
    var file by remember { mutableStateOf<Uri?>(null) }
    var fileName by remember { mutableStateOf("") }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            file = uri
            fileName = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { if (it.moveToFirst()) it.getString(0) else null } ?: "outline"
        }
    }
    fun read(work: suspend () -> JSONObject) {
        scope.launch {
            busy = true; error = ""; note = ""
            try { val found = work(); draft = PaperDraft(found); note = found.optString("notice").ifBlank { "Read. Check it below." } }
            catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not read that" }
            finally { busy = false }
        }
    }
    val manual = { PaperDraft(JSONObject().put("points", 15).put("source", "manual").put("grade_scale", if (institution == "aut") "aut9" else if (institution == "uoa") "uoa9" else "percent")) }
    FullScreenDialog(onDismissRequest = onDismiss) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().systemBarsPadding().imePadding().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(Modifier.fillMaxWidth().heightIn(min = 64.dp), contentAlignment = Alignment.Center) {
                    TextButton(modifier = Modifier.align(Alignment.CenterStart), onClick = onDismiss) { Text("‹ Back") }
                    Text("Add a paper", style = MaterialTheme.typography.titleLarge)
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("aut" to "AUT code", "outline" to "Outline", "manual" to "Type it in").forEach { (key, label) ->
                        FilterChip(selected = way == key, enabled = !busy, modifier = Modifier.weight(1f), onClick = { way = key; error = ""; note = ""; draft = if (key == "manual") manual() else null },
                            label = { Text(label, Modifier.fillMaxWidth(), textAlign = androidx.compose.ui.text.style.TextAlign.Center, maxLines = 1) })
                    }
                }
                when (way) {
                    "aut" -> StudyCard(tone = CardTone.Low) {
                        Text("AUT publishes every paper’s descriptor. The points, learning outcomes, assessments and pass rule are read from it for you to check; dates come from your course’s Canvas page.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        OutlinedTextField(code, { code = it.take(10).uppercase() }, Modifier.fillMaxWidth(), enabled = !busy, singleLine = true, label = { Text("Course code") }, placeholder = { Text("COMP500") }, shape = RoundedCornerShape(12.dp),
                            keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(capitalization = androidx.compose.ui.text.input.KeyboardCapitalization.Characters, autoCorrectEnabled = false))
                        Button(enabled = !busy && code.isNotBlank(), shape = RoundedCornerShape(50), onClick = { read { api.getObject("/papers/aut/${Uri.encode(code.trim())}") } }) { Text("Fetch descriptor") }
                    }
                    "outline" -> StudyCard(tone = CardTone.Low) {
                        Text("University of Auckland outlines need your sign-in, so open yours, then paste its text here or upload the PDF.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        OutlinedTextField(outline, { outline = it }, Modifier.fillMaxWidth(), enabled = !busy && file == null, minLines = 4, maxLines = 8, label = { Text("Outline text") },
                            placeholder = { Text("Paste the learning outcomes and the assessment table") }, shape = RoundedCornerShape(12.dp))
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(enabled = !busy, shape = RoundedCornerShape(50), onClick = {
                                picker.launch(arrayOf("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/*"))
                            }) { Text(if (file == null) "Upload a file" else "Change file") }
                            if (file != null) {
                                Text(fileName, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f), maxLines = 1)
                                TextButton(onClick = { file = null; fileName = "" }) { Text("Remove") }
                            }
                        }
                        Button(enabled = !busy && (file != null || outline.trim().length >= 20), shape = RoundedCornerShape(50), onClick = {
                            read {
                                val chosen = file
                                val parts = if (chosen == null) emptyList() else {
                                    val bytes = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                                        context.contentResolver.openInputStream(chosen)?.use { it.readNBytes(20 * 1024 * 1024 + 1) } ?: throw IllegalStateException("Cannot open the file")
                                    }
                                    if (bytes.size > 20 * 1024 * 1024) throw IllegalStateException("Outline files are limited to 20 MiB")
                                    listOf(Api.Part("file", fileName, context.contentResolver.getType(chosen) ?: "application/octet-stream", bytes))
                                }
                                JSONObject(api.multipart("/papers/outline", mapOf("institution" to institution) + if (chosen == null) mapOf("text" to outline) else emptyMap(), parts, readTimeout = 200000))
                            }
                        }) { Text("Read outline") }
                    }
                }
                if (busy) { LoadingBar(Modifier.fillMaxWidth()); Text("Reading. This can take a minute.", style = MaterialTheme.typography.bodySmall) }
                if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                draft?.let { current -> key(current) { DraftEditor(api, programme, calendars, current, note, onSaved) } }
            }
        }
    }
}

@Composable
private fun DraftEditor(api: Api, programme: JSONObject, calendars: JSONObject, draft: PaperDraft, note: String, onSaved: () -> Unit) {
    val terms = calendars.optJSONObject("calendars")?.optJSONObject(programme.optString("institution"))?.optJSONArray("terms")?.objectList().orEmpty()
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    Text("Check and save", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
    if (note.isNotBlank()) Text(note, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    StudyCard(tone = CardTone.Container) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(draft.code, { draft.code = it.take(40) }, Modifier.weight(1f), singleLine = true, label = { Text("Code") }, shape = RoundedCornerShape(12.dp))
            NumberField("Points", draft.points, { draft.points = it }, Modifier.weight(1f))
            NumberField("Level", draft.level, { draft.level = it.take(2) }, Modifier.weight(1f), whole = true)
        }
        OutlinedTextField(draft.title, { draft.title = it.take(200) }, Modifier.fillMaxWidth(), label = { Text("Title") }, shape = RoundedCornerShape(12.dp))
        if (terms.isNotEmpty()) PickField("Semester", listOf("" to "Choose…") + terms.map { it.optString("code") to it.optString("name") }, draft.term, { chosen ->
            draft.term = chosen
            terms.firstOrNull { it.optString("code") == chosen }?.let { draft.start = it.optString("start"); draft.end = it.optString("end") }
        }, Modifier.fillMaxWidth())
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            DateField("Starts", draft.start, { draft.start = it }, Modifier.weight(1f))
            DateField("Ends", draft.end, { draft.end = it }, Modifier.weight(1f))
        }
        PickField("Grade scale", SCALES, draft.scale, { draft.scale = it }, Modifier.fillMaxWidth())
        if (terms.isNotEmpty()) Text(calendars.optString("note"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    Text("Learning outcomes", style = MaterialTheme.typography.titleMedium)
    draft.outcomes.forEachIndexed { index, outcome ->
        Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            OutlinedTextField(outcome.code, { outcome.code = it.take(40) }, Modifier.width(84.dp), singleLine = true, label = { Text("Code") }, shape = RoundedCornerShape(12.dp))
            OutlinedTextField(outcome.title, { outcome.title = it.take(2000) }, Modifier.weight(1f), label = { Text("Outcome") }, maxLines = 4, shape = RoundedCornerShape(12.dp))
            IconButton(onClick = { draft.outcomes.removeAt(index) }) { Text("✕", color = MaterialTheme.colorScheme.error) }
        }
    }
    OutlinedButton(onClick = { draft.outcomes.add(DraftOutcome("LO${draft.outcomes.size + 1}", "")) }, shape = RoundedCornerShape(50)) { Text("Add outcome") }

    Text("Assessments", style = MaterialTheme.typography.titleMedium)
    draft.assessments.forEachIndexed { index, a ->
        StudyCard(tone = CardTone.Container) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(a.title, { a.title = it.take(300) }, Modifier.weight(1f), singleLine = true, label = { Text("Assessment") }, shape = RoundedCornerShape(12.dp))
                IconButton(onClick = { draft.assessments.removeAt(index) }) { Text("✕", color = MaterialTheme.colorScheme.error) }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PickField("Kind", KINDS, a.kind, { a.kind = it }, Modifier.weight(1.5f))
                NumberField("Weight %", a.weight, { a.weight = it }, Modifier.weight(1f))
            }
            DateField("Date", a.date, { a.date = it }, Modifier.fillMaxWidth())
            OutlinedTextField(a.outcomes, { a.outcomes = it }, Modifier.fillMaxWidth(), singleLine = true, label = { Text("Outcomes it assesses") }, placeholder = { Text("LO1, LO2") }, shape = RoundedCornerShape(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) { Text("Must pass", Modifier.weight(1f)); Switch(a.mustPass, { a.mustPass = it }) }
        }
    }
    OutlinedButton(onClick = { draft.assessments.add(DraftAssessment(JSONObject())) }, shape = RoundedCornerShape(50)) { Text("Add assessment") }
    val total = draft.weightTotal
    Text("Weights add up to ${trimNumber(total)}%${if (Math.abs(total - 100) > 0.01) " (check: usually 100%)" else ""}.", style = MaterialTheme.typography.bodySmall,
        color = if (Math.abs(total - 100) > 0.01) LocalStudyColours.current.amber else MaterialTheme.colorScheme.onSurfaceVariant)

    OutlinedTextField(draft.rule, { draft.rule = it.take(2000) }, Modifier.fillMaxWidth(), label = { Text("What you need to pass") }, minLines = 2, shape = RoundedCornerShape(12.dp))
    PickField("After its assessments", GOALS, draft.goal, { draft.goal = it }, Modifier.fillMaxWidth())
    Row(verticalAlignment = Alignment.CenterVertically) { Text("Make a topic for each learning outcome", Modifier.weight(1f)); Switch(draft.topics, { draft.topics = it }) }
    if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    Button(enabled = !saving && draft.title.isNotBlank(), shape = RoundedCornerShape(50), modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp), onClick = {
        scope.launch {
            saving = true; error = ""
            try {
                val term = terms.firstOrNull { it.optString("code") == draft.term }
                api.post("/papers", JSONObject().put("programme_id", programme.getLong("id")).put("code", draft.code.trim()).put("title", draft.title.trim())
                    .put("points", orNull(draft.points)).put("level", (draft.level.toIntOrNull() ?: 0).coerceIn(0, 10)).put("term", term?.optString("name").orEmpty())
                    .put("start_date", dateOrNull(draft.start)).put("end_date", dateOrNull(draft.end)).put("grade_scale", draft.scale).put("pass_rule", draft.rule.trim())
                    .put("retention_goal", draft.goal).put("outline_url", draft.json.optString("outline_url")).put("source", draft.json.optString("source").ifBlank { "manual" })
                    .put("outcomes", JSONArray(draft.outcomes.filter { it.code.isNotBlank() && it.title.isNotBlank() }.map { JSONObject().put("code", it.code.trim()).put("title", it.title.trim()) }))
                    .put("assessments", JSONArray(draft.assessments.filter { it.title.isNotBlank() }.map { a ->
                        JSONObject().put("title", a.title.trim()).put("kind", a.kind).put("weight_pct", orNull(a.weight)).put("due_date", dateOrNull(a.date))
                            .put("outcome_codes", JSONArray(a.outcomes.split(Regex("[,\\s]+")).filter { it.isNotBlank() })).put("must_pass", a.mustPass)
                    }))
                    .put("topics_from_outcomes", draft.topics))
                onSaved()
            } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not save the paper" }
            finally { saving = false }
        }
    }) { Text(if (saving) "Saving…" else "Save paper") }
}
