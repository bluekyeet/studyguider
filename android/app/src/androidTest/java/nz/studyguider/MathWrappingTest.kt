package nz.studyguider

import org.junit.Assert.assertTrue
import org.junit.Test

class MathWrappingTest {
    @Test fun rendererAllowsTextWrappingAndHandlesProseOnlyMath() {
        assertTrue(KaTeX.head().contains("white-space:nowrap; overflow-wrap:normal; word-break:normal"))
        assertTrue(!KaTeX.head().contains(".base:has(.text)"))
        assertTrue(KaTeX.script().contains("node.textContent = prose[1]"))
    }
}
