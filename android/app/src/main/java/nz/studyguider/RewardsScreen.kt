package nz.studyguider

import android.graphics.BitmapFactory
import android.net.Uri
import android.util.LruCache
import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

// Rewards: points earned from correct work, a gacha and shop for cosmetic collectables, a dressable character and leaderboards.
// The server draws all the art (as PNG for the app), so this screen only places pictures and sends choices; the rules live on the server.

private val RARITY = listOf("Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic")
private val RARITY_COLOURS = listOf(Color(0xFFA1A7B5), Color(0xFF3DDC97), Color(0xFF5AA9FF), Color(0xFFB77CFF), Color(0xFFFFC23D), Color(0xFFFF5FB7))
private val GOLD = Color(0xFFFFCF4A)
private val BOARDS = listOf("networth" to "Net worth", "questions" to "Questions", "lessons" to "Lessons", "papers" to "Papers",
    "grade" to "Est. grade", "gpa" to "Est. GPA", "collection" to "Collection")

/** Send a change to the server: path, method, body, and what else to do with the reply (null if it failed). */
private typealias Act = (String, String, JSONObject, ((JSONObject?) -> Unit)?) -> Unit

private fun JSONArray.objects(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }
private fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }
private fun Int.grouped(): String = "%,d".format(this)

/** One call to the rewards API. Failures carry the server's own explanation (for example "You need 100 points"). */
private suspend fun game(base: String, token: String, path: String, method: String = "GET", body: JSONObject? = null): JSONObject = withContext(Dispatchers.IO) {
    val c = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        c.requestMethod = method
        c.connectTimeout = 15000; c.readTimeout = 30000
        c.setRequestProperty("Authorization", "Bearer $token")
        if (body != null) {
            c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toString().toByteArray()) }
        }
        val ok = c.responseCode in 200..299
        val text = (if (ok) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (!ok) throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrNull()?.takeIf { it.isNotBlank() } ?: "Request failed (${c.responseCode})")
        JSONObject(text)
    } finally { c.disconnect() }
}

private object ArtCache { val pictures = LruCache<String, ImageBitmap>(200) }

private fun avatarPath(outfit: JSONObject?, skin: String, width: Int): String {
    val query = StringBuilder("w=$width")
    if (skin.isNotEmpty()) query.append("&skin=").append(Uri.encode(skin))
    outfit?.keys()?.forEach { slot -> query.append('&').append(Uri.encode(slot)).append('=').append(Uri.encode(outfit.optString(slot))) }
    return "/game/art/avatar.png?$query"
}
private fun itemPath(id: String, width: Int = 256) = "/game/art/item/${Uri.encode(id)}.png?w=$width"

/** A server-drawn picture, kept in memory once loaded so lists scroll without reloading. */
@Composable
private fun Art(base: String, path: String, description: String?, modifier: Modifier = Modifier, scale: ContentScale = ContentScale.Fit) {
    val url = base.trimEnd('/') + path
    val picture by produceState(ArtCache.pictures.get(url), url) {
        if (value != null) return@produceState
        value = try {
            withContext(Dispatchers.IO) {
                val c = URL(url).openConnection() as HttpURLConnection
                try { if (c.responseCode !in 200..299) null else c.inputStream.use { BitmapFactory.decodeStream(it) }?.asImageBitmap() } finally { c.disconnect() }
            }?.also { ArtCache.pictures.put(url, it) }
        } catch (e: CancellationException) { throw e } catch (e: Exception) { null }
    }
    Box(modifier, contentAlignment = Alignment.Center) {
        val shown = picture
        if (shown != null) Image(shown, description, Modifier.fillMaxSize(), contentScale = scale)
    }
}

@Composable
private fun Coin(size: Int = 14) = Box(Modifier.size(size.dp).clip(CircleShape).background(Brush.radialGradient(listOf(Color(0xFFFFF6C8), GOLD, Color(0xFFC58A00)))))

@Composable
private fun Points(value: Int, style: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.titleMedium) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Coin(if (style.fontSize.value > 20) 18 else 14)
        Text(value.grouped(), style = style, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun RarityChip(rarity: Int) {
    val colour = RARITY_COLOURS[rarity.coerceIn(0, 5)]
    Text(RARITY[rarity.coerceIn(0, 5)].uppercase(), Modifier.clip(RoundedCornerShape(50)).background(colour).padding(horizontal = 8.dp, vertical = 1.dp),
        color = Color(0xFF11131B), fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp)
}

/** One collectable: its art on a plate tinted by rarity, the name, and the actions it allows. */
@Composable
private fun ItemCard(base: String, item: JSONObject, modifier: Modifier = Modifier, badge: String = "", worn: Boolean = false, compact: Boolean = false,
                     footer: (@Composable () -> Unit)? = null, actions: (@Composable RowScope.() -> Unit)? = null) {
    val rarity = item.optInt("rarity")
    val tint = RARITY_COLOURS[rarity.coerceIn(0, 5)]
    val colours = LocalStudyColours.current
    Surface(modifier, shape = RoundedCornerShape(16.dp), color = colours.containerHigh,
        border = BorderStroke(if (worn) 2.dp else 1.dp, if (worn) colours.teal else tint.copy(alpha = if (rarity >= 3) 0.75f else 0.4f))) {
        Column {
            Box(Modifier.fillMaxWidth().aspectRatio(1f).background(Brush.radialGradient(listOf(lerpColour(tint, Color(0xFFF3F4F8), 0.58f), lerpColour(tint, Color(0xFFE2E5EE), 0.82f), lerpColour(tint, Color(0xFFC9CCD8), 0.7f))))) {
                Art(base, itemPath(item.optString("id")), item.optString("name"), Modifier.fillMaxSize().padding(8.dp))
                val count = item.optInt("count")
                if (count > 1) Text("×$count", Modifier.align(Alignment.TopStart).padding(8.dp).clip(RoundedCornerShape(50)).background(Color(0xBF14141E)).padding(horizontal = 7.dp),
                    color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                val label = if (worn) "WEARING" else badge.uppercase()
                if (label.isNotEmpty()) Text(label, Modifier.align(Alignment.TopEnd).padding(8.dp).clip(RoundedCornerShape(50)).background(if (worn) colours.teal else Color(0xFF34D399)).padding(horizontal = 8.dp),
                    color = Color(0xFF06251A), fontSize = 10.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
            }
            Column(Modifier.padding(horizontal = if (compact) 8.dp else 12.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(item.optString("name"), style = if (compact) MaterialTheme.typography.labelMedium else MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                RarityChip(rarity)
                footer?.invoke()
                if (actions != null) Row(Modifier.fillMaxWidth().padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically, content = actions)
            }
        }
    }
}

private fun lerpColour(a: Color, b: Color, t: Float) = Color(a.red + (b.red - a.red) * t, a.green + (b.green - a.green) * t, a.blue + (b.blue - a.blue) * t, 1f)

/** Items two to a row (three on wide screens), without a nested lazy list inside the scrolling page. */
@Composable
private fun <T> Grid(entries: List<T>, columns: Int = 2, cell: @Composable (T, Modifier) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        entries.chunked(columns).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { cell(it, Modifier.weight(1f)) }
                repeat(columns - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun Pills(options: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        items(options) { (key, label) -> FilterChip(selected = key == selected, onClick = { onSelect(key) }, label = { Text(label) }) }
    }
}

@Composable
fun RewardsScreen(base: String, token: String, onDismiss: () -> Unit) {
    var me by remember { mutableStateOf<JSONObject?>(null) }
    var error by remember { mutableStateOf("") }
    var tab by remember { mutableStateOf("character") }
    var player by remember { mutableStateOf<JSONObject?>(null) }
    val scope = rememberCoroutineScope()
    val scroll = rememberScrollState()
    BackHandler { if (player != null) player = null else onDismiss() }
    LaunchedEffect(base, token) {
        try { me = game(base, token, "/game/me") } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not load rewards" }
    }
    // Every action answers with the new state, which replaces the old one; `after` also sees the full reply (null when it failed,
    // in which case the server's reason is shown and nothing changes).
    val act: Act = { path, method, body, after ->
        scope.launch {
            val reply = try { game(base, token, path, method, body).also { me = it.optJSONObject("state") ?: it; error = "" } }
                catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "That did not work"; null }
            after?.invoke(reply)
        }
    }
    fun openPlayer(id: Long) {
        scope.launch {
            try { player = game(base, token, "/game/players/$id") } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not open that player" }
        }
    }

    androidx.compose.ui.window.Dialog(onDismissRequest = onDismiss, properties = androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
                Box(Modifier.fillMaxWidth().heightIn(min = 56.dp), contentAlignment = Alignment.Center) {
                    TextButton(onClick = onDismiss, modifier = Modifier.align(Alignment.CenterStart)) { Text("‹ Back") }
                    Text("Rewards", style = MaterialTheme.typography.titleLarge)
                }
                val state = me
                if (state == null) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(24.dp), textAlign = TextAlign.Center) else CircularProgressIndicator()
                    }
                    return@Column
                }
                Column(Modifier.fillMaxSize().verticalScroll(scroll).padding(horizontal = 16.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Banner(base, state)
                    Pills(listOf("character" to "Character", "gacha" to "Gacha", "shop" to "Shop", "boards" to "Leaderboards"), tab) { tab = it }
                    if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                    when (tab) {
                        "gacha" -> GachaTab(base, state, act)
                        "shop" -> ShopTab(base, token, state, act, onError = { error = it })
                        "boards" -> BoardsTab(base, token, onOpen = ::openPlayer, onError = { error = it })
                        else -> CharacterTab(base, state, act)
                    }
                }
            }
        }
        player?.let { PlayerCard(base, it) { player = null } }
    }
}

@Composable
private fun Banner(base: String, me: JSONObject) {
    val colours = LocalStudyColours.current
    val catalog = me.getJSONObject("catalog")
    val owned = catalog.optInt("owned"); val total = catalog.optInt("total").coerceAtLeast(1)
    Surface(shape = RoundedCornerShape(20.dp), color = colours.container) {
        Column(Modifier.background(Brush.linearGradient(listOf(colours.teal.copy(alpha = 0.14f), Color.Transparent, MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)))).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                Art(base, avatarPath(me.optJSONObject("outfit"), me.optString("skin"), 240), "Your character",
                    Modifier.width(72.dp).aspectRatio(2f / 3f).clip(RoundedCornerShape(14.dp)).background(colours.containerHighest), ContentScale.Crop)
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("REWARDS", style = MaterialTheme.typography.labelSmall, color = colours.teal, letterSpacing = 1.5.sp, fontFamily = FontFamily.Monospace)
                    Text("Your collection", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text("${owned.grouped()} of ${total.grouped()} collected · ${"%.1f".format(100f * owned / total)}%", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    LinearProgressIndicator(progress = { owned.toFloat() / total }, modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(50)), color = colours.teal, trackColor = colours.containerHighest, gapSize = 0.dp, drawStopIndicator = {})
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Figure("POINTS", Modifier.weight(1f), highlight = true) { Points(animatedCount(me.optInt("balance").toFloat()).toInt(), MaterialTheme.typography.headlineSmall) }
                Figure("NET WORTH", Modifier.weight(1f)) { Text(me.optInt("networth").grouped(), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
            }
        }
    }
}

@Composable
private fun Figure(label: String, modifier: Modifier, highlight: Boolean = false, content: @Composable () -> Unit) {
    val colours = LocalStudyColours.current
    Surface(modifier, shape = RoundedCornerShape(14.dp), color = if (highlight) GOLD.copy(alpha = 0.12f) else colours.containerHigh,
        border = BorderStroke(1.dp, if (highlight) GOLD.copy(alpha = 0.45f) else colours.outline.copy(alpha = 0.3f))) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            Text(label, style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant, letterSpacing = 1.sp)
            content()
        }
    }
}

// --- Character ---------------------------------------------------------------------------------------------------------------

@Composable
private fun CharacterTab(base: String, me: JSONObject, act: Act) {
    val colours = LocalStudyColours.current
    val catalog = me.getJSONObject("catalog")
    val outfit = me.optJSONObject("outfit") ?: JSONObject()
    val owned = me.getJSONArray("owned").objects()
    val showcase = me.getJSONArray("showcase").strings()
    val skin = me.optString("skin")
    var slot by rememberSaveable { mutableStateOf("hat") }
    fun send(path: String, method: String, body: JSONObject) = act(path, method, body, null)

    StudyCard(tone = CardTone.Container) {
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Art(base, avatarPath(outfit, skin, 480), "Your character",
                Modifier.width(130.dp).aspectRatio(2f / 3f).clip(RoundedCornerShape(16.dp)).background(Brush.radialGradient(listOf(Color(0xFF3A3D52), Color(0xFF20212A)))), ContentScale.Crop)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("SKIN TONE", style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant)
                val skins = catalog.getJSONArray("skins").objects()
                skins.chunked(4).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        row.forEach { tone ->
                            val on = tone.optString("id") == skin
                            Box(Modifier.size(30.dp).clip(CircleShape).background(Color(android.graphics.Color.parseColor(tone.optString("colour"))))
                                .border(if (on) 3.dp else 1.dp, if (on) colours.teal else colours.outline.copy(alpha = 0.4f), CircleShape)
                                .clickable(role = Role.RadioButton, onClickLabel = tone.optString("name")) { send("/game/outfit", "PUT", JSONObject().put("skin", tone.optString("id"))) })
                        }
                    }
                }
                val worn = outfit.length()
                Text(if (worn == 0) "Wearing nothing yet" else "Wearing $worn piece${if (worn == 1) "" else "s"}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (worn > 0) OutlinedButton(onClick = { send("/game/outfit", "PUT", JSONObject().put("clear", true)) }, contentPadding = PaddingValues(horizontal = 12.dp)) { Text("Undress") }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Switch(checked = me.optBoolean("visible"), onCheckedChange = { send("/game/settings", "PUT", JSONObject().put("visible", it)) })
                    Text("On leaderboards", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }

    StudyCard(tone = CardTone.Container) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Wardrobe", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            Text("${owned.size} items", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        val slots = catalog.getJSONArray("slots").objects()
        val bySlot = catalog.getJSONObject("by_slot")
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(slots) { s ->
                val id = s.optString("id"); val on = id == slot
                val count = bySlot.optJSONObject(id)?.optInt("owned") ?: 0
                Surface(onClick = { slot = id }, shape = RoundedCornerShape(14.dp), color = if (on) MaterialTheme.colorScheme.primaryContainer else colours.containerHigh,
                    border = BorderStroke(1.dp, if (on) colours.teal else colours.outline.copy(alpha = 0.3f)), modifier = Modifier.width(76.dp).graphicsLayer { alpha = if (count == 0 && !on) 0.6f else 1f }) {
                    Column(Modifier.padding(vertical = 8.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Art(base, itemPath(s.optString("icon"), 128), null, Modifier.size(42.dp).clip(RoundedCornerShape(10.dp)).background(Color(0xFFE9ECF4)), ContentScale.Crop)
                        Text(s.optString("name"), style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text("$count", style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        val info = slots.firstOrNull { it.optString("id") == slot }
        val list = owned.filter { it.optString("slot") == slot }
        if (list.isEmpty()) Text("No ${info?.optString("name")?.lowercase().orEmpty()} yet. Try the shop or the gacha.", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 12.dp))
        else Grid(list) { item, modifier ->
            val id = item.optString("id")
            val isWorn = outfit.optString(slot) == id
            val shown = id in showcase
            ItemCard(base, item, modifier, worn = isWorn) {
                if (info?.optBoolean("worn") == true) {
                    if (isWorn) OutlinedButton(onClick = { send("/game/outfit", "PUT", JSONObject().put("slot", slot).put("item_id", JSONObject.NULL)) }, Modifier.weight(1f), contentPadding = PaddingValues(0.dp)) { Text("Take off", maxLines = 1) }
                    else Button(onClick = { send("/game/outfit", "PUT", JSONObject().put("slot", slot).put("item_id", id)) }, Modifier.weight(1f), contentPadding = PaddingValues(0.dp)) { Text("Wear") }
                }
                IconToggle(if (shown) "★" else "☆", if (shown) GOLD else MaterialTheme.colorScheme.onSurfaceVariant, if (shown) "Remove from showcase" else "Add to showcase") {
                    val next = JSONArray((if (shown) showcase - id else showcase + id))
                    send("/game/showcase", "PUT", JSONObject().put("items", next))
                }
                if (item.optInt("count") > 1) IconToggle("♻", colours.teal, "Recycle a spare for ${Math.round(item.optInt("value") * 0.4)} points") {
                    send("/game/recycle", "POST", JSONObject().put("item_id", id).put("count", 1))
                }
            }
        }
    }

    StudyCard(tone = CardTone.Container) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Showcase", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            Text("${showcase.size} / 6 on your player card", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Grid((0 until 6).toList(), columns = 3) { index, modifier ->
            val item = owned.firstOrNull { it.optString("id") == showcase.getOrNull(index) }
            if (item != null) ItemCard(base, item, modifier, compact = true)
            else Box(modifier.aspectRatio(0.8f).clip(RoundedCornerShape(14.dp)).border(1.5.dp, colours.outline.copy(alpha = 0.4f), RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
                Text("☆", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 20.sp)
            }
        }
        if (showcase.isEmpty()) Text("Tap ☆ on anything in your wardrobe to put it here.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    StudyCard(tone = CardTone.Low) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("How you earn", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            Points(me.optInt("earned"))
        }
        me.getJSONArray("breakdown").objects().forEach { line ->
            val count = line.optInt("count")
            Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(line.optString("label"), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f), color = if (count == 0) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface)
                Text("$count × ${line.optInt("each")}", style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(line.optInt("points").grouped(), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.End, modifier = Modifier.width(64.dp))
            }
        }
        Text(me.optString("notice"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        me.optJSONObject("estimate")?.let { estimate ->
            Text("Estimated grade ${estimate.optString("grade")} · GPA ${estimate.optDouble("gpa")} / 9, from ${estimate.optInt("topics")} topic(s) with enough review answers. Unofficial.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun IconToggle(symbol: String, colour: Color, label: String, onClick: () -> Unit) {
    OutlinedButton(onClick = onClick, modifier = Modifier.size(width = 40.dp, height = 36.dp), contentPadding = PaddingValues(0.dp),
        shape = RoundedCornerShape(10.dp)) { Text(symbol, color = colour, fontSize = 16.sp, modifier = Modifier.semantics { contentDescription = label }) }
}

// --- Gacha -------------------------------------------------------------------------------------------------------------------

@Composable
private fun GachaTab(base: String, me: JSONObject, act: Act) {
    val colours = LocalStudyColours.current
    var results by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    var round by remember { mutableIntStateOf(0) }
    val balance = me.optInt("balance")
    val costs = me.getJSONObject("costs"); val pity = me.getJSONObject("pity")
    StudyCard(tone = CardTone.Container) {
        Text("Gacha", style = MaterialTheme.typography.titleMedium)
        Text("Each pull is a random collectable from the whole catalogue. Duplicates stack; recycle spares for points.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            for ((count, cost) in listOf(1 to costs.optInt("pull"), 10 to costs.optInt("ten"))) {
                val ten = count == 10
                Surface(onClick = {
                    busy = true
                    act("/game/pull", "POST", JSONObject().put("count", count)) { result ->
                        if (result != null) { results = result.getJSONArray("results").objects(); round++ }
                        busy = false
                    }
                }, enabled = !busy && balance >= cost, modifier = Modifier.weight(1f).graphicsLayer { alpha = if (balance >= cost) 1f else 0.5f }, shape = RoundedCornerShape(16.dp),
                    color = if (ten) GOLD.copy(alpha = 0.12f) else MaterialTheme.colorScheme.primary.copy(alpha = 0.1f),
                    border = BorderStroke(1.dp, if (ten) GOLD.copy(alpha = 0.55f) else MaterialTheme.colorScheme.primary.copy(alpha = 0.45f))) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(if (ten) "Pull ×10" else "Pull ×1", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Points(cost, MaterialTheme.typography.bodyMedium)
                        if (ten) Text("one free pull", style = MaterialTheme.typography.labelSmall, color = colours.teal)
                    }
                }
            }
        }
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (balance < costs.optInt("pull")) Text("You have ${balance.grouped()} points. Correct review answers, marked exam questions, lessons and passed papers earn more.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        val rareIn = pity.optInt("rare_in"); val epicIn = pity.optInt("epic_in")
        Text("Rare or better guaranteed in $rareIn pull${if (rareIn == 1) "" else "s"}", style = MaterialTheme.typography.bodySmall)
        LinearProgressIndicator(progress = { (10 - rareIn) / 10f }, modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(50)), color = RARITY_COLOURS[2], trackColor = colours.containerHighest, gapSize = 0.dp, drawStopIndicator = {})
        Text("Epic or better guaranteed in $epicIn pull${if (epicIn == 1) "" else "s"}", style = MaterialTheme.typography.bodySmall)
        LinearProgressIndicator(progress = { (30 - epicIn) / 30f }, modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(50)), color = RARITY_COLOURS[3], trackColor = colours.containerHighest, gapSize = 0.dp, drawStopIndicator = {})
        val odds = me.getJSONObject("odds")
        Row(Modifier.fillMaxWidth().height(10.dp).clip(RoundedCornerShape(50)), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
            RARITY.forEachIndexed { i, name -> Box(Modifier.weight(odds.optDouble(name.lowercase()).toFloat().coerceAtLeast(1.5f)).fillMaxHeight().background(RARITY_COLOURS[i])) }
        }
        Text(RARITY.joinToString("  ·  ") { "$it ${odds.optDouble(it.lowercase()).let { v -> if (v % 1.0 == 0.0) v.toInt().toString() else v.toString() }}%" },
            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    if (results.isNotEmpty()) {
        val best = results.maxOf { it.optInt("rarity") }
        StudyCard(tone = CardTone.Container) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(if (results.size == 1) "You pulled" else "You pulled ${results.size}", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                Text("Best: ${RARITY[best]} · ${results.count { it.optBoolean("new") }} new", style = MaterialTheme.typography.labelMedium, color = RARITY_COLOURS[best])
            }
            key(round) {
                Grid(results.withIndex().toList()) { (index, item), modifier ->
                    // Cards turn over one after another; the best rarity of the round is outlined.
                    val turn = remember { Animatable(0f) }
                    LaunchedEffect(Unit) { delay(index * 90L); turn.animateTo(1f, tween(420)) }
                    ItemCard(base, item, modifier.graphicsLayer {
                        rotationY = (1f - turn.value) * 80f; alpha = turn.value; scaleX = 0.9f + 0.1f * turn.value; scaleY = scaleX; cameraDistance = 12f * density
                    }, badge = if (item.optBoolean("new")) "New" else "", compact = true)
                }
            }
        }
    }
}

// --- Shop --------------------------------------------------------------------------------------------------------------------

@Composable
private fun ShopTab(base: String, token: String, me: JSONObject, act: Act, onError: (String) -> Unit) {
    val catalog = me.getJSONObject("catalog")
    var slot by rememberSaveable { mutableStateOf("hat") }
    var rarity by rememberSaveable { mutableIntStateOf(-1) }
    var shown by remember(slot, rarity) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var total by remember(slot, rarity) { mutableIntStateOf(0) }
    var page by remember(slot, rarity) { mutableIntStateOf(0) }
    val balance = me.optInt("balance")
    LaunchedEffect(slot, rarity, page) {
        try {
            val result = game(base, token, "/game/shop?slot=$slot&offset=${page * 24}&limit=24" + if (rarity >= 0) "&rarity=$rarity" else "")
            shown = shown + result.getJSONArray("items").objects(); total = result.optInt("total")
        } catch (e: CancellationException) { throw e } catch (e: Exception) { onError(e.message ?: "Could not load the shop") }
    }
    StudyCard(tone = CardTone.Container) {
        Text("Item shop", style = MaterialTheme.typography.titleMedium)
        Text("Common to rare at fixed prices. Epic and above only come from the gacha.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Pills(catalog.getJSONArray("slots").objects().map { it.optString("id") to it.optString("name") }, slot) { slot = it }
        Pills(listOf("-1" to "All", "0" to "Common", "1" to "Uncommon", "2" to "Rare"), rarity.toString()) { rarity = it.toInt() }
        Grid(shown, columns = 3) { item, modifier ->
            val price = item.optInt("price"); val owned = item.optInt("owned")
            ItemCard(base, item, modifier, compact = true, footer = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Points(price, MaterialTheme.typography.bodyMedium)
                    Spacer(Modifier.weight(1f))
                    if (owned > 0) Text("×$owned", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }) {
                val buy = {
                    act("/game/shop/buy", "POST", JSONObject().put("item_id", item.optString("id"))) { result ->
                        if (result != null) shown = shown.map { if (it.optString("id") == item.optString("id")) JSONObject(it.toString()).put("owned", owned + 1) else it }
                    }
                }
                if (owned > 0) OutlinedButton(onClick = buy, enabled = balance >= price, modifier = Modifier.fillMaxWidth(), contentPadding = PaddingValues(0.dp)) { Text("Again", maxLines = 1) }
                else Button(onClick = buy, enabled = balance >= price, modifier = Modifier.fillMaxWidth(), contentPadding = PaddingValues(0.dp)) { Text("Buy") }
            }
        }
        if (shown.size < total) TextButton(onClick = { page++ }, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Show more · ${total - shown.size} left") }
    }
}

// --- Leaderboards and player cards -------------------------------------------------------------------------------------------

@Composable
private fun BoardsTab(base: String, token: String, onOpen: (Long) -> Unit, onError: (String) -> Unit) {
    val colours = LocalStudyColours.current
    var board by rememberSaveable { mutableStateOf("networth") }
    var data by remember(board) { mutableStateOf<JSONObject?>(null) }
    LaunchedEffect(board) {
        try { data = game(base, token, "/game/leaderboard/$board") } catch (e: CancellationException) { throw e } catch (e: Exception) { onError(e.message ?: "Could not load the leaderboard") }
    }
    StudyCard(tone = CardTone.Container) {
        Text("Leaderboards", style = MaterialTheme.typography.titleMedium)
        Pills(BOARDS, board) { board = it }
        val result = data
        if (result == null) { LinearProgressIndicator(Modifier.fillMaxWidth()); return@StudyCard }
        result.optString("note").takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        val rows = result.getJSONArray("rows").objects()
        val you = result.optLong("you")
        if (rows.isEmpty()) { Text("Nobody is on this board yet. Correct answers put you on it.", color = MaterialTheme.colorScheme.onSurfaceVariant); return@StudyCard }
        // The top three stand on a podium: second, first, third.
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Bottom) {
            for (index in listOf(1, 0, 2)) {
                val row = rows.getOrNull(index)
                Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                    if (row != null) {
                        val first = index == 0
                        Box(Modifier.clickable(role = Role.Button) { onOpen(row.optLong("user_id")) }) {
                            Art(base, avatarPath(row.optJSONObject("outfit"), row.optString("skin"), 240), row.optString("username"),
                                Modifier.width(if (first) 84.dp else 66.dp).aspectRatio(2f / 3f).clip(RoundedCornerShape(12.dp)).background(colours.containerHighest), ContentScale.Crop)
                            val medal = listOf(Color(0xFFE0B13A), Color(0xFFB9BFCC), Color(0xFFC27C46))[index]
                            Text("${row.optInt("rank")}", Modifier.align(Alignment.TopEnd).offset(8.dp, (-8).dp).size(26.dp).clip(CircleShape).background(medal).padding(top = 3.dp),
                                textAlign = TextAlign.Center, fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Color(0xFF2A1D00))
                        }
                        Text(row.optString("username"), style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis,
                            color = if (row.optLong("user_id") == you) colours.teal else MaterialTheme.colorScheme.onSurface, modifier = Modifier.padding(top = 4.dp))
                        Text(row.optString("text"), style = MaterialTheme.typography.labelMedium, color = colours.teal, fontWeight = FontWeight.Bold)
                    }
                    Box(Modifier.fillMaxWidth().padding(top = 4.dp).height(listOf(64.dp, 46.dp, 32.dp)[index]).clip(RoundedCornerShape(topStart = 12.dp, topEnd = 12.dp, bottomStart = 4.dp, bottomEnd = 4.dp))
                        .background(if (index == 0) Brush.verticalGradient(listOf(GOLD.copy(alpha = 0.3f), colours.containerHigh)) else Brush.verticalGradient(listOf(colours.containerHighest, colours.containerHigh))))
                }
            }
        }
        val rest = rows.drop(3).toMutableList()
        result.optJSONObject("mine")?.takeIf { mine -> rows.none { it.optLong("user_id") == you } }?.let { rest += it }
        rest.forEach { row ->
            val mine = row.optLong("user_id") == you
            Surface(onClick = { onOpen(row.optLong("user_id")) }, shape = RoundedCornerShape(14.dp), color = if (mine) MaterialTheme.colorScheme.primaryContainer else colours.containerHigh) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("#${row.optInt("rank")}", fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.width(36.dp))
                    Art(base, avatarPath(row.optJSONObject("outfit"), row.optString("skin"), 96), null, Modifier.size(32.dp, 48.dp).clip(RoundedCornerShape(8.dp)).background(colours.containerHighest), ContentScale.Crop)
                    Text(if (mine) "${row.optString("username")} (you)" else row.optString("username"), Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(row.optString("text"), color = colours.teal, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun PlayerCard(base: String, p: JSONObject, onDismiss: () -> Unit) {
    val colours = LocalStudyColours.current
    androidx.compose.ui.window.Dialog(onDismissRequest = onDismiss) {
        Surface(shape = RoundedCornerShape(22.dp), color = colours.container) {
            Column(Modifier.verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("PLAYER CARD", style = MaterialTheme.typography.labelSmall, color = colours.teal, fontFamily = FontFamily.Monospace, letterSpacing = 1.5.sp)
                Art(base, avatarPath(p.optJSONObject("outfit"), p.optString("skin"), 400), p.optString("username"),
                    Modifier.width(140.dp).aspectRatio(2f / 3f).clip(RoundedCornerShape(16.dp)).background(Brush.radialGradient(listOf(Color(0xFF3A3D52), Color(0xFF20212A)))), ContentScale.Crop)
                Text(if (p.optBoolean("you")) "${p.optString("username")} (you)" else p.optString("username"), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                val estimate = p.optJSONObject("estimate")
                val facts = listOf(p.optInt("networth").grouped() to "Net worth", p.optInt("questions").grouped() to "Questions", p.optInt("lessons").grouped() to "Lessons",
                    p.optInt("papers").grouped() to "Papers", (estimate?.optString("grade") ?: "—") to "Est. grade", (estimate?.optDouble("gpa")?.toString() ?: "—") to "Est. GPA / 9")
                Grid(facts, columns = 3) { (value, label), modifier ->
                    Surface(modifier, shape = RoundedCornerShape(12.dp), color = colours.containerHigh) {
                        Column(Modifier.padding(8.dp)) {
                            Text(value, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(label.uppercase(), style = MaterialTheme.typography.labelSmall, fontSize = 9.sp, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                val collection = p.getJSONObject("collection")
                Text("Collection ${collection.optInt("owned").grouped()} / ${collection.optInt("total").grouped()} · ${collection.optDouble("percent")}%", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                p.optJSONObject("rarest")?.let { rarest ->
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Rarest: ${rarest.optString("name")}", style = MaterialTheme.typography.bodySmall); RarityChip(rarest.optInt("rarity"))
                    }
                }
                Text("Showcase", style = MaterialTheme.typography.titleSmall, modifier = Modifier.align(Alignment.Start))
                val showcase = p.getJSONArray("showcase").objects()
                if (showcase.isEmpty()) Text("Nothing on the shelf yet.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                else Grid(showcase, columns = 3) { item, modifier -> ItemCard(base, item, modifier, compact = true) }
                TextButton(onClick = onDismiss) { Text("Close") }
            }
        }
    }
}
