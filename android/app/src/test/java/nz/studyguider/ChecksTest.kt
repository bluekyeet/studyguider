package nz.studyguider

import org.junit.Test

/** Runs the plain main() checks in this folder under Gradle, so testDebugUnitTest exercises them. */
class ChecksTest {
    private fun run(file: String) {
        try { Class.forName("nz.studyguider.$file").getMethod("main").invoke(null) }
        catch (e: java.lang.reflect.InvocationTargetException) { throw e.targetException }
    }

    @Test fun answerText() = run("AnswerTextCheckKt")
    @Test fun examParts() = run("ExamPartsCheckKt")
}
