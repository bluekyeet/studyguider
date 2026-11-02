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
        assertTrue(!stored.getJSONArray("marks").getJSONObject(1).has("disclaimer"))
    }
}
