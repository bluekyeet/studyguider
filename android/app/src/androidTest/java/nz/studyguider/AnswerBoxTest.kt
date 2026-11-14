package nz.studyguider

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/** The answer box writes what the learner picks, types and fills into one answer text, in the web's format. */
class AnswerBoxTest {
    @get:Rule val compose = createComposeRule()

    // No network is used: nothing here uploads a drawing or loads a saved one.
    private val api = Api("http://127.0.0.1:9", "")

    private fun show(state: AnswerBoxState) = compose.setContent {
        StudyTheme(dark = false) { Column(Modifier.verticalScroll(rememberScrollState())) { AnswerBox(state) } }
    }

    @Test fun singleChoiceWritesTheChosenKeyNotTheShownLetter() {
        val forms = answerForms(JSONArray("""[{"kind":"choice","options":[{"key":"A","text":"One"},{"key":"B","text":"Two"},{"key":"C","text":"Three"}],
            "multiple":false,"display_order":["C","A","B"]},{"kind":"text","palette":"general"}]"""))
        val state = AnswerBoxState(api, forms, "")
        show(state)
        // Shown first, so lettered A, but its key is C.
        compose.onNodeWithContentDescription("Option A").performClick()
        compose.runOnIdle { assertEquals("Choice: C", state.value) }
        compose.onNodeWithContentDescription("Option C").performClick()
        compose.runOnIdle { assertEquals("Choice: B", state.value) }
    }

    @Test fun selectAllWritesKeysInOrderWithOptionalWorkingAfter() {
        val forms = answerForms(JSONArray("""[{"kind":"choice","options":[{"key":"A","text":"Momentum"},{"key":"B","text":"Kinetic energy"},{"key":"C","text":"Energy"}],
            "multiple":true,"display_order":["A","B","C"]},{"kind":"text","palette":"general"}]"""))
        val state = AnswerBoxState(api, forms, "")
        show(state)
        compose.onNodeWithContentDescription("Option C").performClick()
        compose.onNodeWithContentDescription("Option A").performClick()
        compose.onNodeWithText("Add working or a reason (optional)").performScrollTo().performClick()
        compose.onNodeWithText("Working or reason (optional)").performScrollTo().performTextInput("No external force.")
        compose.runOnIdle { assertEquals("Choice: A, C\n\nNo external force.", state.value) }
    }

    @Test fun savedChoiceIsSelectedAgain() {
        val forms = answerForms(JSONArray("""[{"kind":"choice","options":[{"key":"A","text":"One"},{"key":"B","text":"Two"}],"multiple":true}]"""))
        val state = AnswerBoxState(api, forms, "Choice: A, B")
        compose.runOnIdle { assertEquals(listOf("A", "B"), (state.blocks.single() as AnswerBlock.Choice).chosen.toList()) }
    }

    @Test fun completedTableIsWrittenAsMarkdownBeforeTheText() {
        val forms = answerForms(JSONArray("""[{"kind":"table","columns":["Molecule","Shape"],"rows":[["CH4",""]]},{"kind":"text","palette":"chemistry"}]"""))
        val state = AnswerBoxState(api, forms, "")
        state.setText("Both have four regions.")
        val table = state.blocks.single() as AnswerBlock.Table
        table.rows[0] = listOf("CH4", "tetrahedral")
        assertEquals("| Molecule | Shape |\n| --- | --- |\n| CH4 | tetrahedral |\n\nBoth have four regions.", state.value)
    }

    @Test fun savedDrawingReferenceIsKeptWhileItsStrokesLoad() {
        val saved = "![Drawing 1](/answer-images/42)\n\nNH3 is trigonal pyramidal."
        val state = AnswerBoxState(api, answerForms(JSONArray("""[{"kind":"drawing","background":"blank","purpose":"lewis"}]""")), saved)
        assertTrue(state.blocks.single() is AnswerBlock.Pending)
        assertEquals(saved, state.value)
    }
}
