package nz.studyguider

import org.junit.Assert.assertTrue
import org.junit.Test

class MathWrappingTest {
    @Test fun rendererAllowsTextWrappingAndHandlesProseOnlyMath() {
        assertTrue(KaTeX.head().contains(".katex .text { white-space:normal"))
        assertTrue(KaTeX.script().contains("node.textContent = prose[1]"))
    }
}
