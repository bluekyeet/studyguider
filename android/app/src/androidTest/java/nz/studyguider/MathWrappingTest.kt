package nz.studyguider

import org.junit.Assert.assertTrue
import org.junit.Test

class MathWrappingTest {
    @Test fun rendererAllowsTextWrappingAndHandlesProseOnlyMath() {
        assertTrue(KaTeX.head().contains("white-space:nowrap; overflow-wrap:normal; word-break:normal"))
        assertTrue(!KaTeX.head().contains(".base:has(.text)"))
        assertTrue(KaTeX.script().contains("node.textContent = prose[1]"))
        assertTrue(KaTeX.head().contains(".katex .katex-html { white-space:normal"))
        assertTrue(KaTeX.script().contains("tex.split"))
        assertTrue(!KaTeX.script().contains("Math.max(0.8"))
        assertTrue(KaTeX.script().contains("Swipe sideways to see the full formula"))
    }
}
