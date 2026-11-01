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
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import java.time.ZonedDateTime

internal fun nextReminder(now: ZonedDateTime): ZonedDateTime {
    val evening = now.withHour(19).withMinute(0).withSecond(0).withNano(0)
    return if (evening.isAfter(now)) evening else evening.plusDays(1)
}

private fun reminderEnabled(context: Context) = context.getSharedPreferences("reminders", Context.MODE_PRIVATE).getBoolean("enabled", false)

private fun notificationsAllowed(context: Context): Boolean {
    val manager = context.getSystemService(NotificationManager::class.java)
    return manager.areNotificationsEnabled() &&
        (manager.getNotificationChannel("daily-study")?.importance != NotificationManager.IMPORTANCE_NONE)
}

internal fun scheduleReminder(context: Context) {
    val intent = PendingIntent.getBroadcast(context, 0, Intent(context, StudyReminderReceiver::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    val alarms = context.getSystemService(AlarmManager::class.java)
    alarms.cancel(intent)
    if (reminderEnabled(context) && notificationsAllowed(context)) {
        // ponytail: inexact local-time alarm; add a time picker only if needed.
        alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, nextReminder(ZonedDateTime.now()).toInstant().toEpochMilli(), intent)
    }
}

class StudyReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != null) {
            scheduleReminder(context)
            return
        }
        if (!reminderEnabled(context)) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("daily-study", "Daily study reminder", NotificationManager.IMPORTANCE_DEFAULT))
        if (notificationsAllowed(context) && (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED)) {
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
    fun save(value: Boolean) {
        enabled = value
        context.getSharedPreferences("reminders", Context.MODE_PRIVATE).edit().putBoolean("enabled", value).apply()
        scheduleReminder(context)
        if (!value) context.getSystemService(NotificationManager::class.java).cancel(1900)
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        save(granted)
        notice = if (granted) "" else "Notifications are not permitted. Enable them in Android Settings to use reminders."
    }
    Column {
        Text("Daily study reminder — around 7 pm local time")
        Text("Optional; Android battery saving may delay delivery. No connection required.")
        Switch(modifier = Modifier.semantics { contentDescription = "Daily study reminder around 7 pm" }, checked = enabled, onCheckedChange = { value ->
            notice = ""
            if (value && Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                permission.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else if (value && !notificationsAllowed(context)) {
                notice = "Notifications are blocked. Enable them in Android Settings."
            } else save(value)
        })
        if (notice.isNotEmpty()) Text(notice)
    }
}
