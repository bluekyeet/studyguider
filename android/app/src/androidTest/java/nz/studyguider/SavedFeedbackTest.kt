package nz.studyguider

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SavedFeedbackTest {
    @Test fun restoresFirstMarkAndSeparateOverrideWithoutMutatingStoredJson() {
        val stored = JSONObject("""{"marks":[{"kind":"second","marks_awarded":2},{"kind":"first","marks_awarded":1}],"override":{"outcome":"merit","note":"My judgement"}}""")
        val restored = savedExamFeedback(stored)
        assertEquals(1, restored.getInt("marks_awarded"))
        assertEquals("merit", restored.getJSONObject("override").getString("outcome"))
        assertTrue(restored.getString("disclaimer").contains("not an official"))
        assertEquals(2, restored.getJSONObject("second_review").getInt("marks_awarded"))
        assertTrue(restored.getBoolean("disagreement"))
        assertTrue(!stored.getJSONArray("marks").getJSONObject(1).has("disclaimer"))
    }

    @Test fun matchingSecondMarkIsNotFlaggedAsDisagreement() {
        val stored = JSONObject("""{"marks":[{"kind":"first","marks_awarded":1,"outcome":"achieved"},{"kind":"second","marks_awarded":1,"outcome":"achieved"}]}""")
        assertTrue(!savedExamFeedback(stored).getBoolean("disagreement"))
    }

    @Test fun matchingScoreDoesNotHideDifferentOutcomes() {
        val stored = JSONObject("""{"marks":[{"kind":"first","marks_awarded":1,"outcome":"achieved"},{"kind":"second","marks_awarded":1,"outcome":"uncertain"}]}""")
        assertTrue(savedExamFeedback(stored).getBoolean("disagreement"))
    }

    @Test fun explicitDisagreementIsNotOverwrittenByMatchingScores() {
        val stored = JSONObject("""{"marks":[{"kind":"first","marks_awarded":1,"outcome":"achieved","disagreement":true},{"kind":"second","marks_awarded":1,"outcome":"achieved"}]}""")
        assertTrue(savedExamFeedback(stored).getBoolean("disagreement"))
    }

    @Test(expected = IllegalStateException::class)
    fun secondMarkAloneCannotMasqueradeAsFirstMark() {
        savedExamFeedback(JSONObject("""{"marks":[{"kind":"second","marks_awarded":1}]}"""))
    }
}
