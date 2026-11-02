package nz.studyguider

import androidx.compose.foundation.layout.Column
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.assertIsNotEnabled
import org.junit.Rule
import org.junit.Test

class ExamOverrideTest {
    @get:Rule val compose = createComposeRule()

    @Test fun overrideRequiresReasonAndExplainsSeparation() {
        compose.setContent { Column { ExamOverride("http://127.0.0.1", "test", 1, 2, null) } }
        compose.onNodeWithText("Your judgement / override").performClick()
        compose.onNodeWithText("Save your judgement").assertIsNotEnabled()
        compose.onNodeWithText("Your judgement is saved separately. It does not change the AI mark or official-schedule result.").assertExists()
    }
}
