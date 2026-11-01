package nz.studyguider

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test

class LessonSourcesTest {
    @get:Rule val compose = createComposeRule()

    @Test fun sourcePanelShowsFilenameAndPageWithoutInlineMarkers() {
        val draft = JSONObject().put("sources", JSONArray().put(JSONObject()
            .put("filename", "teacher-notes.pdf").put("page", 6).put("content", "")))
        compose.setContent { LessonSourcesDialog(draft, {}) }
        compose.onNodeWithText("teacher-notes.pdf").assertExists()
        compose.onNodeWithText("Page 6").assertExists()
        compose.onNodeWithText("Close").assertExists()
    }
}
