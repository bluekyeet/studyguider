package nz.studyguider

import android.os.SystemClock
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay

internal fun examSecondsLeft(deadline: Long, now: Long): Long = ((deadline - now).coerceAtLeast(0) + 999) / 1000

@Composable
fun ExamTimer(examId: Long, server: String) {
    val context = LocalContext.current
    val prefs = remember(examId, server) { context.getSharedPreferences("exam-timer-${server.hashCode()}-$examId", 0) }
    val boot = android.provider.Settings.Global.getInt(context.contentResolver, android.provider.Settings.Global.BOOT_COUNT, -1)
    // ponytail: local-device timer, not a synchronised exam deadline. Pause after
    // reboot because elapsedRealtime resets; a server deadline is the upgrade path.
    var deadline by remember(prefs) { mutableLongStateOf(if (prefs.getInt("boot", -2) == boot) prefs.getLong("deadline", 0) else 0) }
    var seconds by remember(prefs) { mutableLongStateOf(prefs.getLong("remaining", 0)) }
    var minutes by remember(prefs) { mutableStateOf(prefs.getString("minutes", "60").orEmpty()) }
    var expanded by remember(prefs) { mutableStateOf(deadline > 0 || seconds > 0) }
    fun persist() {
        prefs.edit().putLong("deadline", deadline).putLong("remaining", seconds).putInt("boot", boot).putString("minutes", minutes).apply()
    }
    LaunchedEffect(deadline) {
        if (deadline == 0L) return@LaunchedEffect
        while (true) {
            seconds = examSecondsLeft(deadline, SystemClock.elapsedRealtime())
            if (seconds == 0L) { deadline = 0; persist(); break }
            delay(250)
        }
    }
    TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "Hide timer" else "Optional timer") }
    if (expanded) {
        Text("Time left: ${seconds / 60}:${(seconds % 60).toString().padStart(2, '0')}", style = MaterialTheme.typography.titleMedium)
        Text("Local timer only. Time running out never submits or locks your answers. After a device reboot it is paused.", style = MaterialTheme.typography.bodySmall)
        if (deadline == 0L && seconds == 0L) OutlinedTextField(minutes, { minutes = it.filter(Char::isDigit).take(3) }, label = { Text("Minutes (1–360)") }, singleLine = true)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            val duration = minutes.toLongOrNull()
            TextButton(enabled = deadline > 0 || seconds > 0 || (duration != null && duration in 1L..360L), onClick = {
                if (deadline > 0) { seconds = examSecondsLeft(deadline, SystemClock.elapsedRealtime()); deadline = 0 }
                else { if (seconds == 0L) seconds = (duration ?: 60) * 60; deadline = SystemClock.elapsedRealtime() + seconds * 1000 }
                persist()
            }) { Text(if (deadline > 0) "Pause" else if (seconds > 0) "Resume" else "Start") }
            TextButton(onClick = { deadline = 0; seconds = 0; persist() }) { Text("Reset") }
        }
    }
}
