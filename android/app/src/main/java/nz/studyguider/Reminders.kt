package nz.studyguider

import android.Manifest
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.Spacer
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.dp
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import java.time.ZonedDateTime

internal fun nextReminder(now: ZonedDateTime, hour: Int = 19, minute: Int = 0): ZonedDateTime {
    val evening = now.withHour(hour).withMinute(minute).withSecond(0).withNano(0)
    return if (evening.isAfter(now)) evening else evening.plusDays(1)
}

private fun reminderEnabled(context: Context) = context.getSharedPreferences("reminders", Context.MODE_PRIVATE).getBoolean("enabled", false)

private fun reminderTime(context: Context): Pair<Int, Int> =
    context.getSharedPreferences("reminders", Context.MODE_PRIVATE).let { it.getInt("hour", 19).coerceIn(0, 23) to it.getInt("minute", 0).coerceIn(0, 59) }

private fun timeLabel(hour: Int, minute: Int) = "%d:%02d %s".format(if (hour % 12 == 0) 12 else hour % 12, minute, if (hour < 12) "am" else "pm")

private fun notificationsAllowed(context: Context): Boolean {
    val manager = context.getSystemService(NotificationManager::class.java)
    return (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) &&
        manager.areNotificationsEnabled() &&
        (manager.getNotificationChannel("daily-study")?.importance != NotificationManager.IMPORTANCE_NONE)
}

internal fun scheduleReminder(context: Context) {
    val intent = PendingIntent.getBroadcast(context, 0, Intent(context, StudyReminderReceiver::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    val alarms = context.getSystemService(AlarmManager::class.java)
    alarms.cancel(intent)
    if (reminderEnabled(context) && notificationsAllowed(context)) {
        // Inexact local-time alarm at the chosen time (default 7 pm).
        val (hour, minute) = reminderTime(context)
        alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, nextReminder(ZonedDateTime.now(), hour, minute).toInstant().toEpochMilli(), intent)
    } else {
        intent.cancel()
        context.getSystemService(NotificationManager::class.java).cancel(1900)
    }
}

class StudyReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != null) {
            scheduleReminder(context)
            return
        }
        if (!reminderEnabled(context)) {
            scheduleReminder(context)
            return
        }
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("daily-study", "Daily study reminder", NotificationManager.IMPORTANCE_DEFAULT))
        if (notificationsAllowed(context)) {
            val open = PendingIntent.getActivity(context, 0, Intent(context, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            manager.notify(1900, Notification.Builder(context, "daily-study")
                .setSmallIcon(android.R.drawable.ic_menu_edit)
                .setContentTitle("Time for a little study")
                .setContentText("Open StudyGuider for your lessons and daily review.")
                .setContentIntent(open).setAutoCancel(true).build())
        }
        scheduleReminder(context)
    }
}

@Composable
fun DailyReminderSetting() {
    val context = LocalContext.current
    var enabled by remember { mutableStateOf(reminderEnabled(context)) }
    var notice by remember { mutableStateOf("") }
    var time by remember { mutableStateOf(reminderTime(context)) }
    fun save(value: Boolean) {
        enabled = value
        context.getSharedPreferences("reminders", Context.MODE_PRIVATE).edit().putBoolean("enabled", value).apply()
        scheduleReminder(context)
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        save(granted)
        notice = if (granted) "" else "Notifications are not permitted. Enable them in Android Settings to use reminders."
    }
    StudyCard {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
            Column(Modifier.weight(1f)) {
                Text("Daily reminder", style = MaterialTheme.typography.titleMedium)
                Text("Around ${timeLabel(time.first, time.second)} · local time", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.width(12.dp))
        Switch(modifier = Modifier.semantics { contentDescription = "Daily study reminder around ${timeLabel(time.first, time.second)}" }, checked = enabled, onCheckedChange = { value ->
            notice = ""
            if (value && Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                permission.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else if (value && !notificationsAllowed(context)) {
                notice = "Notifications are blocked. Enable them in Android Settings."
            } else save(value)
        })
        }
        androidx.compose.material3.TextButton(onClick = {
            android.app.TimePickerDialog(context, { _, hour, minute ->
                context.getSharedPreferences("reminders", Context.MODE_PRIVATE).edit().putInt("hour", hour).putInt("minute", minute).apply()
                time = hour to minute
                scheduleReminder(context)
            }, time.first, time.second, false).show()
        }) { Text("Change time") }
        Text("Works offline. Battery saving may delay delivery.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (notice.isNotEmpty()) Text(notice, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
    }
}
