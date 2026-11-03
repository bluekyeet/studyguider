package nz.studyguider

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

// Accounts: who is signed in, their picture, username and password, and (administrators) every account.
// The server keeps each account's study data separate; this screen only manages the account itself.

/** The signed-in account, shared so any screen can ask whether the user is an administrator. */
object CurrentUser {
    var json by mutableStateOf<JSONObject?>(null)
    val isAdmin: Boolean get() = json?.optBoolean("is_admin") == true
    val username: String get() = json?.optString("username").orEmpty()
}

private fun JSONArray.users(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }

/** A round profile picture, or the first letter of the username when there is none. */
@Composable
fun AvatarView(base: String, token: String, user: JSONObject?, size: Dp, path: String = "/me/avatar") {
    val has = user?.optBoolean("has_avatar") == true
    val version = user?.optInt("avatar_version") ?: 0
    val bitmap by produceState<Bitmap?>(null, base, token, path, version, has) {
        value = if (!has || token.isEmpty()) null else try {
            withContext(Dispatchers.IO) {
                val c = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
                try {
                    c.setRequestProperty("Authorization", "Bearer $token")
                    if (c.responseCode !in 200..299) null else c.inputStream.use { BitmapFactory.decodeStream(it) }
                } finally { c.disconnect() }
            }
        } catch (e: CancellationException) { throw e } catch (e: Exception) { null }
    }
    Box(Modifier.size(size).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer), contentAlignment = Alignment.Center) {
        val shown = bitmap
        if (shown != null) Image(shown.asImageBitmap(), contentDescription = "Profile picture", contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
        else Text(user?.optString("username").orEmpty().take(1).uppercase().ifEmpty { "?" }, color = MaterialTheme.colorScheme.onPrimaryContainer, fontSize = (size.value * 0.42f).sp)
    }
}

private suspend fun uploadPicture(base: String, token: String, bytes: ByteArray): JSONObject = withContext(Dispatchers.IO) {
    val boundary = "avatar-${java.util.UUID.randomUUID()}"
    val c = URL(base.trimEnd('/') + "/me/avatar").openConnection() as HttpURLConnection
    try {
        c.connectTimeout = 10000; c.readTimeout = 60000; c.requestMethod = "POST"; c.doOutput = true
        c.setRequestProperty("Authorization", "Bearer $token")
        c.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        c.outputStream.use {
            it.write("--$boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"picture\"\r\nContent-Type: application/octet-stream\r\n\r\n".toByteArray())
            it.write(bytes); it.write("\r\n--$boundary--\r\n".toByteArray())
        }
        val status = c.responseCode
        val text = (if (status in 200..299) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (status !in 200..299) throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrDefault("").ifBlank { "Upload failed ($status)" })
        JSONObject(text)
    } finally { c.disconnect() }
}

@Composable
private fun PasswordField(value: String, onChange: (String) -> Unit, label: String, enabled: Boolean = true) {
    OutlinedTextField(value, onChange, modifier = Modifier.fillMaxWidth(), label = { Text(label) }, enabled = enabled, singleLine = true,
        visualTransformation = PasswordVisualTransformation(), shape = RoundedCornerShape(12.dp))
}

@Composable
private fun Status(text: String, bad: Boolean) {
    if (text.isNotEmpty()) Text(text, style = MaterialTheme.typography.bodySmall, color = if (bad) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
fun AccountPage(base: String, token: String) {
    val me = CurrentUser.json ?: return
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var busy by remember { mutableStateOf(false) }
    var pictureStatus by remember { mutableStateOf("") }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            busy = true; pictureStatus = "Uploading…"
            try {
                val bytes = withContext(Dispatchers.IO) { context.contentResolver.openInputStream(uri)?.use { it.readBytes() } } ?: throw IllegalStateException("Could not read that picture")
                if (bytes.size > 5 * 1024 * 1024) throw IllegalStateException("Choose a picture under 5 MB")
                CurrentUser.json = uploadPicture(base, token, bytes); pictureStatus = ""
            } catch (e: CancellationException) { throw e } catch (e: Exception) { pictureStatus = e.message ?: "Upload failed" }
            busy = false
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        StudyCard(tone = CardTone.Container) {
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.CenterVertically) {
                AvatarView(base, token, me, 72.dp)
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(me.optString("username"), style = MaterialTheme.typography.titleLarge)
                    Text(if (CurrentUser.isAdmin) "Administrator" else "User", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(enabled = !busy, shape = RoundedCornerShape(50), onClick = { picker.launch("image/*") }) { Text(if (me.optBoolean("has_avatar")) "Change picture" else "Add a picture") }
                if (me.optBoolean("has_avatar")) TextButton(enabled = !busy, onClick = {
                    scope.launch {
                        busy = true
                        try { CurrentUser.json = JSONObject(rapidCall(base, token, "/me/avatar", "DELETE")); pictureStatus = "" }
                        catch (e: CancellationException) { throw e } catch (e: Exception) { pictureStatus = e.message ?: "Could not remove it" }
                        busy = false
                    }
                }) { Text("Remove") }
            }
            Status(pictureStatus, true)
        }
        UsernameCard(base, token)
        PasswordCard(base, token)
        if (CurrentUser.isAdmin) AccountsAdmin(base, token)
    }
}

@Composable
private fun UsernameCard(base: String, token: String) {
    var name by remember { mutableStateOf("") }
    var current by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("") }
    var bad by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    StudyCard(tone = CardTone.Low) {
        Text("Username", style = MaterialTheme.typography.titleMedium)
        Text("Letters, numbers, dots, dashes and underscores; 3 to 32 characters.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        OutlinedTextField(name, { name = it }, modifier = Modifier.fillMaxWidth(), label = { Text("New username") }, singleLine = true, shape = RoundedCornerShape(12.dp))
        PasswordField(current, { current = it }, "Current password (to confirm)")
        Button(enabled = !busy && name.isNotBlank() && current.isNotEmpty(), shape = RoundedCornerShape(50), onClick = {
            scope.launch {
                busy = true
                try {
                    CurrentUser.json = JSONObject(rapidCall(base, token, "/me/username", "PUT", JSONObject().put("username", name.trim()).put("current_password", current)))
                    name = ""; current = ""; status = "Username changed"; bad = false
                } catch (e: CancellationException) { throw e } catch (e: Exception) { status = e.message ?: "Could not change it"; bad = true }
                busy = false
            }
        }) { Text("Change username") }
        Status(status, bad)
    }
}

@Composable
private fun PasswordCard(base: String, token: String) {
    var current by remember { mutableStateOf("") }
    var next by remember { mutableStateOf("") }
    var again by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("") }
    var bad by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    StudyCard(tone = CardTone.Low) {
        Text("Password", style = MaterialTheme.typography.titleMedium)
        Text("At least 12 characters. Changing it signs you out on your other devices.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        PasswordField(current, { current = it }, "Current password")
        PasswordField(next, { next = it }, "New password")
        PasswordField(again, { again = it }, "Repeat the new password")
        Button(enabled = !busy && current.isNotEmpty() && next.length >= 12 && again.isNotEmpty(), shape = RoundedCornerShape(50), onClick = {
            if (next != again) { status = "The new passwords do not match"; bad = true; return@Button }
            scope.launch {
                busy = true
                try {
                    rapidCall(base, token, "/me/password", "PUT", JSONObject().put("current_password", current).put("new_password", next))
                    current = ""; next = ""; again = ""; status = "Password changed"; bad = false
                } catch (e: CancellationException) { throw e } catch (e: Exception) { status = e.message ?: "Could not change it"; bad = true }
                busy = false
            }
        }) { Text("Change password") }
        Status(status, bad)
    }
}

/** Administrators: every account, with add, edit and remove. */
@Composable
private fun AccountsAdmin(base: String, token: String) {
    var users by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var status by remember { mutableStateOf("") }
    var bad by remember { mutableStateOf(false) }
    var reload by remember { mutableIntStateOf(0) }
    var editing by remember { mutableStateOf<JSONObject?>(null) }
    var removing by remember { mutableStateOf<JSONObject?>(null) }
    var newName by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var newAdmin by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val myId = CurrentUser.json?.optLong("id") ?: 0L
    LaunchedEffect(base, token, reload) {
        try { users = JSONArray(rapidCall(base, token, "/users")).users() } catch (e: CancellationException) { throw e } catch (e: Exception) { status = e.message ?: "Could not load accounts"; bad = true }
    }
    StudyCard(tone = CardTone.Low, modifier = Modifier.animateContentSize()) {
        Text("Accounts", style = MaterialTheme.typography.titleMedium)
        Text("Only administrators can add or remove accounts. Each account has its own subjects, files, lessons and teaching style.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        users.forEach { user ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                AvatarView(base, token, user, 36.dp, "/users/${user.optLong("id")}/avatar")
                Column(Modifier.weight(1f)) {
                    Text(user.optString("username") + if (user.optLong("id") == myId) " (you)" else "", style = MaterialTheme.typography.bodyLarge)
                    Text(if (user.optBoolean("is_admin")) "Administrator" else "User", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (user.optLong("id") != myId) {
                    TextButton(onClick = { editing = user }) { Text("Edit") }
                    TextButton(onClick = { removing = user }) { Text("Remove", color = MaterialTheme.colorScheme.error) }
                }
            }
        }
        HorizontalDivider()
        Text("Add an account", style = MaterialTheme.typography.titleSmall)
        OutlinedTextField(newName, { newName = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Username") }, singleLine = true, shape = RoundedCornerShape(12.dp))
        PasswordField(newPassword, { newPassword = it }, "Starting password (at least 12 characters)")
        Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(newAdmin, { newAdmin = it }); Text("Administrator") }
        Button(enabled = !busy && newName.isNotBlank() && newPassword.length >= 12, shape = RoundedCornerShape(50), onClick = {
            scope.launch {
                busy = true
                try {
                    rapidCall(base, token, "/users", "POST", JSONObject().put("username", newName.trim()).put("password", newPassword).put("is_admin", newAdmin))
                    status = "Added ${newName.trim()}. Give them their username and starting password; they can change both."; bad = false
                    newName = ""; newPassword = ""; newAdmin = false; reload++
                } catch (e: CancellationException) { throw e } catch (e: Exception) { status = e.message ?: "Could not add it"; bad = true }
                busy = false
            }
        }) { Text("Add account") }
        Status(status, bad)
    }
    editing?.let { user ->
        var name by remember(user) { mutableStateOf(user.optString("username")) }
        var password by remember(user) { mutableStateOf("") }
        var admin by remember(user) { mutableStateOf(user.optBoolean("is_admin")) }
        var error by remember(user) { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { editing = null },
            title = { Text("Edit ${user.optString("username")}") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(name, { name = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Username") }, singleLine = true)
                    PasswordField(password, { password = it }, "New password (leave empty to keep)")
                    Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(admin, { admin = it }); Text("Administrator") }
                    Status(error, true)
                }
            },
            confirmButton = { TextButton(enabled = !busy, onClick = {
                val body = JSONObject()
                if (name != user.optString("username")) body.put("username", name.trim())
                if (password.isNotEmpty()) body.put("password", password)
                if (admin != user.optBoolean("is_admin")) body.put("is_admin", admin)
                if (body.length() == 0) { editing = null; return@TextButton }
                scope.launch {
                    busy = true
                    try { rapidCall(base, token, "/users/${user.optLong("id")}", "PUT", body); editing = null; reload++ }
                    catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not save" }
                    busy = false
                }
            }) { Text("Save") } },
            dismissButton = { TextButton(onClick = { editing = null }) { Text("Cancel") } },
        )
    }
    removing?.let { user ->
        var typed by remember(user) { mutableStateOf("") }
        var error by remember(user) { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { removing = null },
            title = { Text("Remove ${user.optString("username")}?") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("This permanently deletes their subjects, files, lessons, reviews, exams and teaching style. It cannot be undone.", color = MaterialTheme.colorScheme.error)
                    OutlinedTextField(typed, { typed = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Type “${user.optString("username")}” to confirm") }, singleLine = true)
                    Status(error, true)
                }
            },
            confirmButton = { TextButton(enabled = !busy && typed.trim().equals(user.optString("username"), ignoreCase = true), onClick = {
                scope.launch {
                    busy = true
                    try {
                        rapidCall(base, token, "/users/${user.optLong("id")}?confirm=${java.net.URLEncoder.encode(typed.trim(), "UTF-8")}", "DELETE")
                        removing = null; status = "Removed ${user.optString("username")}"; bad = false; reload++
                    } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Could not remove it" }
                    busy = false
                }
            }) { Text("Remove account and all its data", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(onClick = { removing = null }) { Text("Cancel") } },
        )
    }
}
