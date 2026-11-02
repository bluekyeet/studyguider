package nz.studyguider

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LessonHeadingTest {
    @Test fun deeperMarkdownHeadingsBecomeSeparateReaderSections() {
        val chunks = lessonChunks("## Lesson\nIntro\n#### Learning Goal\nExplain equilibrium.\n#### Worked Example\nCalculate a change.\n###### Summary ###\nTemperature matters.")
        assertEquals(listOf("Lesson", "Learning Goal", "Worked Example", "Summary"), chunks.map { it.title })
        assertTrue(chunks.flatMap { it.blocks }.none { it.second.startsWith("####") })
    }
}
