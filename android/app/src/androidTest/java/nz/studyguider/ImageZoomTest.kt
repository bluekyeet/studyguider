package nz.studyguider

import org.junit.Assert.assertEquals
import org.junit.Test

class ImageZoomTest {
    @Test fun imageZoomIsBounded() {
        assertEquals(1f, boundedImageZoom(0.5f), 0f)
        assertEquals(3f, boundedImageZoom(3f), 0f)
        assertEquals(8f, boundedImageZoom(20f), 0f)
    }
}
