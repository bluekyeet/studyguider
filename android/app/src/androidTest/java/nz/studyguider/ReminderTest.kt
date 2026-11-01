package nz.studyguider

import org.junit.Test
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import java.time.ZonedDateTime

class ReminderTest {
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
}
