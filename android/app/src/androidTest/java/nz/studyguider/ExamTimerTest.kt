package nz.studyguider

import org.junit.Assert.assertEquals
import org.junit.Test

class ExamTimerTest {
    @Test fun remainingTimeRoundsUpAndNeverGoesNegative() {
        assertEquals(60L, examSecondsLeft(61000, 1000))
        assertEquals(1L, examSecondsLeft(61000, 60999))
        assertEquals(0L, examSecondsLeft(61000, 61000))
        assertEquals(0L, examSecondsLeft(61000, 62000))
    }
}
