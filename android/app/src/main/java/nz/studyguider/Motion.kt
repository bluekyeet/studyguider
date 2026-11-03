package nz.studyguider

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.interaction.InteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlin.math.sign

/**
 * Motion used across the app. Everything here is a fluid transition of position, size or opacity
 * (eased or spring curves, a few hundred milliseconds): no spinners, skeletons or loading screens.
 * Compose scales these durations by the system "Animator duration scale", so turning animations off
 * in Android's developer or accessibility settings turns them off here too.
 */
object Motion {
    /** Fast start, long gentle settle. */
    val easeOut = CubicBezierEasing(0.22f, 1f, 0.36f, 1f)
}

/** A block eases up and fades in when it first appears; later blocks follow a beat behind it. */
fun Modifier.staggeredEnter(index: Int, key: Any? = Unit): Modifier = composed {
    val progress = remember(key) { Animatable(0f) }
    LaunchedEffect(key) {
        delay((index * 55L).coerceAtMost(440L))
        progress.animateTo(1f, tween(520, easing = Motion.easeOut))
    }
    graphicsLayer {
        alpha = progress.value
        translationY = (1f - progress.value) * 22.dp.toPx()
    }
}

/** Springy press feedback: the element sinks slightly while held and rebounds on release. */
fun Modifier.pressScale(source: InteractionSource, pressed: Float = 0.97f): Modifier = composed {
    val isPressed by source.collectIsPressedAsState()
    val scale by animateFloatAsState(if (isPressed) pressed else 1f, spring(dampingRatio = 0.55f, stiffness = 620f), label = "press")
    graphicsLayer { scaleX = scale; scaleY = scale }
}

/**
 * The content slides in from the side it is heading towards (forwards from the right, back from the
 * left) and fades up, every time [index] changes. The first appearance does not animate.
 */
fun Modifier.sectionTransition(index: Int): Modifier = composed {
    var previous by remember { mutableIntStateOf(index) }
    val enter = remember { Animatable(1f) }
    var direction by remember { mutableIntStateOf(1) }
    LaunchedEffect(index) {
        if (index != previous) {
            direction = (index - previous).sign
            previous = index
            enter.snapTo(0f)
            enter.animateTo(1f, tween(420, easing = Motion.easeOut))
        }
    }
    graphicsLayer {
        alpha = 0.25f + 0.75f * enter.value
        translationX = (1f - enter.value) * 36.dp.toPx() * direction
    }
}

/** A number that counts up to [target] with an ease-out curve. */
@Composable
fun animatedCount(target: Float, durationMillis: Int = 800): Float {
    val value = remember { Animatable(0f) }
    LaunchedEffect(target) { value.animateTo(target, tween(durationMillis, easing = Motion.easeOut)) }
    return value.value
}

/** A fill fraction that grows from empty to [target], for progress bars. */
@Composable
fun animatedFill(target: Float, durationMillis: Int = 1100, delayMillis: Int = 250): Float {
    val value = remember { Animatable(0f) }
    LaunchedEffect(target) { value.animateTo(target, tween(durationMillis, delayMillis, Motion.easeOut)) }
    return value.value
}


/**
 * Loading feedback only when a wait is really long: nothing shows for the first moments (most requests finish by then, so
 * the screen simply fills in), and what does show fades in rather than flashing.
 */
@Composable
fun DelayedLoading(delayMillis: Long = 500, content: @Composable () -> Unit) {
    var show by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { delay(delayMillis); show = true }
    AnimatedVisibility(show, enter = fadeIn(tween(250))) { content() }
}

/** A thin progress bar for a wait that is still going after a moment. */
@Composable
fun LoadingBar(modifier: Modifier = Modifier) = DelayedLoading { LinearProgressIndicator(modifier) }
