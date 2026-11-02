package nz.studyguider

import android.Manifest
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import java.time.ZonedDateTime

class ReminderTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val preferences = context.getSharedPreferences("reminders", Context.MODE_PRIVATE)
    private val notifications = context.getSystemService(NotificationManager::class.java)
    private var originalEnabled: Boolean? = null
    private var restore = false

    @Before fun preserveSetting() {
        // Do not overwrite an existing reminder notification on a user's device.
        assumeTrue(notifications.activeNotifications.none { it.id == 1900 })
        originalEnabled = if (preferences.contains("enabled")) preferences.getBoolean("enabled", false) else null
        restore = true
    }

    @After fun restoreSetting() {
        if (!restore) return
        val edit = preferences.edit()
        originalEnabled?.let { edit.putBoolean("enabled", it) } ?: edit.remove("enabled")
        assertTrue(edit.commit())
        notifications.cancel(1900)
        scheduleReminder(context)
    }

    private fun enabled(value: Boolean) {
        assertTrue(preferences.edit().putBoolean("enabled", value).commit())
    }

    private fun operation(): PendingIntent? = PendingIntent.getBroadcast(
        context, 0, Intent(context, StudyReminderReceiver::class.java),
        PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE
    )

    private fun requireNotificationsAllowed() {
        assumeTrue(Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED)
        assumeTrue(notifications.areNotificationsEnabled())
        assumeTrue(notifications.getNotificationChannel("daily-study")?.importance != NotificationManager.IMPORTANCE_NONE)
    }

    @Test fun enabledSchedulingReusesOperationAndDisableCancelsIt() {
        requireNotificationsAllowed()
        enabled(true)
        scheduleReminder(context)
        val first = operation()
        assertNotNull(first)
        scheduleReminder(context)
        assertEquals(first, operation())
        enabled(false)
        scheduleReminder(context)
        assertNull(operation())
        assertFalse(notifications.activeNotifications.any { it.id == 1900 })
    }

    @Test fun deniedPermissionCancelsExistingOperationWithoutPosting() {
        assumeTrue(Build.VERSION.SDK_INT >= 33)
        enabled(true)
        // Seed a stale operation without changing the device's actual permission.
        PendingIntent.getBroadcast(context, 0, Intent(context, StudyReminderReceiver::class.java), PendingIntent.FLAG_IMMUTABLE)
        val denied = object : ContextWrapper(context) {
            override fun checkSelfPermission(permission: String): Int =
                if (permission == Manifest.permission.POST_NOTIFICATIONS) PackageManager.PERMISSION_DENIED
                else super.checkSelfPermission(permission)
        }
        StudyReminderReceiver().onReceive(denied, Intent())
        assertNull(operation())
        assertFalse(notifications.activeNotifications.any { it.id == 1900 })
        assertTrue(preferences.getBoolean("enabled", false))
    }

    @Test fun disabledReceiverCancelsStaleOperationWithoutPosting() {
        enabled(false)
        PendingIntent.getBroadcast(context, 0, Intent(context, StudyReminderReceiver::class.java), PendingIntent.FLAG_IMMUTABLE)
        StudyReminderReceiver().onReceive(context, Intent())
        assertNull(operation())
        assertFalse(notifications.activeNotifications.any { it.id == 1900 })
    }

    @Test fun missingPreferenceDefaultsToOff() {
        assertTrue(preferences.edit().remove("enabled").commit())
        scheduleReminder(context)
        assertNull(operation())
        StudyReminderReceiver().onReceive(context, Intent())
        assertFalse(notifications.activeNotifications.any { it.id == 1900 })
    }

    @Test fun reschedulingBroadcastsRespectOptInWithoutPosting() {
        requireNotificationsAllowed()
        for (action in listOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_TIME_CHANGED, Intent.ACTION_TIMEZONE_CHANGED, Intent.ACTION_MY_PACKAGE_REPLACED)) {
            enabled(true)
            StudyReminderReceiver().onReceive(context, Intent(action))
            assertNotNull(operation())
            assertFalse(notifications.activeNotifications.any { it.id == 1900 })
            enabled(false)
            StudyReminderReceiver().onReceive(context, Intent(action))
            assertNull(operation())
        }
    }

    @Test fun nextEveningUsesLocalCalendarAcrossDst() {
        val before = ZonedDateTime.parse("2026-09-26T18:00:00+12:00[Pacific/Auckland]")
        assertEquals(19, nextReminder(before).hour)
        val at = before.withHour(19)
        val next = nextReminder(at)
        assertEquals(27, next.dayOfMonth)
        assertEquals(19, next.hour)
        assertEquals(23L, java.time.Duration.between(at, next).toHours())
        assertTrue(next.isAfter(at))
    }

    @Test fun nextEveningUsesLocalCalendarAcrossDstEnd() {
        val at = ZonedDateTime.parse("2026-04-04T19:00:00+13:00[Pacific/Auckland]")
        val next = nextReminder(at)
        assertEquals(5, next.dayOfMonth)
        assertEquals(19, next.hour)
        assertEquals(25L, java.time.Duration.between(at, next).toHours())
        assertEquals(0, next.minute)
        assertEquals(0, next.second)
        assertEquals(0, next.nano)
    }
}
