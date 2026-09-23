package com.mgafk.app.data

import android.content.Context
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import java.io.File
import java.io.Writer
import java.time.Instant
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

/**
 * Persistent wire/debug recorder used by the NUCLEAR screen.
 *
 * The complete payload is written to disk. The UI only keeps a small, truncated rolling preview
 * so high-frequency or very large server messages cannot freeze Compose or exhaust app memory.
 */
enum class NuclearLogKind(val label: String) {
    WS_IN("WS IN"),
    WS_OUT("WS OUT"),
    CONNECTION("Connection"),
    PARSER("Parser"),
    STATE("State"),
    APP("App"),
}

data class NuclearLogEntry(
    val id: Long,
    val timestampMs: Long,
    val kind: NuclearLogKind,
    val label: String,
    val payload: String,
)

object NuclearLogStore {
    private const val TAG = "NuclearLogStore"
    private const val DIRECTORY = "nuclear"
    private const val FILE_NAME = "nuclear.jsonl"

    // Deliberately small. The complete log remains on disk and is streamed during export.
    private const val MAX_UI_ENTRIES = 600
    private const val MAX_UI_PAYLOAD_CHARS = 12_000

    private val uiLock = Any()
    private val fileLock = Any()
    private val nextId = AtomicLong(0L)
    private val writer = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "mgafk-nuclear-log").apply { isDaemon = true }
    }

    @Volatile
    private var logFile: File? = null

    private val _entries = MutableStateFlow<List<NuclearLogEntry>>(emptyList())
    val entries: StateFlow<List<NuclearLogEntry>> = _entries.asStateFlow()

    val isInitialized: Boolean
        get() = logFile != null

    /**
     * Startup must stay cheap even if a previous run produced a very large trace.
     * Existing history is intentionally not parsed here; Export All streams it directly from disk.
     */
    fun initialize(context: Context) {
        if (logFile != null) return
        synchronized(fileLock) {
            if (logFile != null) return
            val directory = File(context.applicationContext.filesDir, DIRECTORY).apply { mkdirs() }
            logFile = File(directory, FILE_NAME)
        }
    }

    fun record(kind: NuclearLogKind, label: String, payload: String = "") {
        val file = logFile ?: return
        val diskEntry = NuclearLogEntry(
            id = nextId.incrementAndGet(),
            timestampMs = System.currentTimeMillis(),
            kind = kind,
            label = label,
            payload = payload,
        )
        val uiEntry = diskEntry.copy(payload = payloadForUi(payload))

        synchronized(uiLock) {
            val current = _entries.value
            _entries.value = if (current.size < MAX_UI_ENTRIES) {
                current + uiEntry
            } else {
                current.drop(current.size - MAX_UI_ENTRIES + 1) + uiEntry
            }
        }

        // Never do file I/O on the socket callback or Compose thread.
        writer.execute {
            runCatching {
                synchronized(fileLock) {
                    file.appendText(encode(diskEntry) + "\n")
                }
            }.onFailure {
                Log.e(TAG, "Unable to persist NUCLEAR log", it)
            }
        }
    }

    fun recordApp(level: String, tag: String, message: String, throwable: Throwable? = null) {
        val detail = buildString {
            append(message)
            if (throwable != null) {
                append("\n")
                append(throwable.stackTraceToString())
            }
        }
        record(NuclearLogKind.APP, "$level/$tag", detail)
    }

    fun clear() {
        synchronized(uiLock) {
            _entries.value = emptyList()
        }
        writer.execute {
            runCatching {
                synchronized(fileLock) {
                    logFile?.writeText("")
                }
            }.onFailure {
                Log.e(TAG, "Unable to clear NUCLEAR log", it)
            }
        }
    }

    /**
     * Streams the full persisted history directly to the destination writer.
     * This avoids creating one enormous String/List when a trace has been running for hours.
     */
    fun writeExport(
        destination: Writer,
        query: String = "",
        kind: NuclearLogKind? = null,
    ) {
        val normalizedQuery = query.trim()
        destination.appendLine("MG AFK — NUCLEAR LOG EXPORT")
        destination.appendLine("Generated: ${Instant.now()}")
        if (kind != null) destination.appendLine("Kind: ${kind.label}")
        if (normalizedQuery.isNotBlank()) destination.appendLine("Search: $normalizedQuery")
        destination.appendLine("============================================================")

        val file = logFile
        if (file == null || !file.exists()) {
            _entries.value.forEach { entry ->
                if (matches(entry, normalizedQuery, kind)) writeEntry(destination, entry)
            }
            return
        }

        synchronized(fileLock) {
            runCatching {
                file.useLines { lines ->
                    lines.forEach { line ->
                        val entry = decode(line) ?: return@forEach
                        if (matches(entry, normalizedQuery, kind)) {
                            writeEntry(destination, entry)
                        }
                    }
                }
            }.onFailure {
                Log.e(TAG, "Unable to stream NUCLEAR export", it)
                destination.appendLine("[EXPORT ERROR] ${it.message ?: it::class.java.simpleName}")
            }
        }
    }

    private fun payloadForUi(payload: String): String {
        if (payload.length <= MAX_UI_PAYLOAD_CHARS) return payload
        return payload.take(MAX_UI_PAYLOAD_CHARS) +
            "\n… [UI preview truncated; full payload is preserved in Export All]"
    }

    private fun matches(
        entry: NuclearLogEntry,
        query: String,
        kind: NuclearLogKind?,
    ): Boolean =
        (kind == null || entry.kind == kind) &&
            (query.isBlank() ||
                entry.label.contains(query, ignoreCase = true) ||
                entry.payload.contains(query, ignoreCase = true))

    private fun writeEntry(destination: Writer, entry: NuclearLogEntry) {
        destination.appendLine(
            "[${Instant.ofEpochMilli(entry.timestampMs)}] [${entry.kind.label}] ${entry.label}"
        )
        if (entry.payload.isNotEmpty()) destination.appendLine(entry.payload)
        destination.appendLine("------------------------------------------------------------")
    }

    private fun encode(entry: NuclearLogEntry): String =
        buildJsonObject {
            put("id", JsonPrimitive(entry.id))
            put("timestampMs", JsonPrimitive(entry.timestampMs))
            put("kind", JsonPrimitive(entry.kind.name))
            put("label", JsonPrimitive(entry.label))
            put("payload", JsonPrimitive(entry.payload))
        }.toString()

    private fun decode(line: String): NuclearLogEntry? {
        if (line.isBlank()) return null
        return runCatching {
            val obj: JsonObject = AppJson.default.parseToJsonElement(line).jsonObject
            NuclearLogEntry(
                id = obj["id"]?.jsonPrimitive?.longOrNull ?: return null,
                timestampMs = obj["timestampMs"]?.jsonPrimitive?.longOrNull ?: return null,
                kind = obj["kind"]?.jsonPrimitive?.contentOrNull
                    ?.let { NuclearLogKind.valueOf(it) } ?: return null,
                label = obj["label"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                payload = obj["payload"]?.jsonPrimitive?.contentOrNull.orEmpty(),
            )
        }.getOrNull()
    }
}
