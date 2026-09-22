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
import java.time.Instant
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

/**
 * Persistent wire/debug recorder used by the NUCLEAR screen.
 *
 * The on-disk file is append-only JSONL so a crash cannot corrupt the already-written history.
 * Raw WebSocket payloads are recorded exactly as they pass through RoomClient. Authentication
 * cookies are deliberately never handed to this recorder.
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
    private const val MAX_IN_MEMORY = 20_000

    private val lock = Any()
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

    fun initialize(context: Context) {
        if (logFile != null) return
        synchronized(lock) {
            if (logFile != null) return
            val directory = File(context.applicationContext.filesDir, DIRECTORY).apply { mkdirs() }
            val file = File(directory, FILE_NAME)
            logFile = file

            val loaded = if (file.exists()) {
                runCatching {
                    file.useLines { lines ->
                        lines.mapNotNull(::decode).toList()
                    }
                }.onFailure {
                    Log.e(TAG, "Unable to load persisted NUCLEAR logs", it)
                }.getOrDefault(emptyList())
            } else {
                emptyList()
            }

            nextId.set(loaded.maxOfOrNull { it.id } ?: 0L)
            _entries.value = loaded.takeLast(MAX_IN_MEMORY)
        }
    }

    fun record(kind: NuclearLogKind, label: String, payload: String = "") {
        val file = logFile ?: return
        val entry = NuclearLogEntry(
            id = nextId.incrementAndGet(),
            timestampMs = System.currentTimeMillis(),
            kind = kind,
            label = label,
            payload = payload,
        )

        synchronized(lock) {
            _entries.value = (_entries.value + entry).takeLast(MAX_IN_MEMORY)
        }

        writer.execute {
            runCatching {
                synchronized(lock) {
                    file.appendText(encode(entry) + "\n")
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
        synchronized(lock) {
            _entries.value = emptyList()
            nextId.set(0L)
        }
        writer.execute {
            runCatching {
                synchronized(lock) {
                    logFile?.writeText("")
                }
            }.onFailure {
                Log.e(TAG, "Unable to clear NUCLEAR log", it)
            }
        }
    }

    /**
     * Builds a human-readable text export from the complete persisted history, not just the
     * in-memory UI window. Passing null/empty filters exports everything.
     */
    fun buildExportText(
        query: String = "",
        kind: NuclearLogKind? = null,
    ): String {
        val normalizedQuery = query.trim()
        val all = readAllPersisted()
        val filtered = all.filter { entry ->
            (kind == null || entry.kind == kind) &&
                (normalizedQuery.isBlank() ||
                    entry.label.contains(normalizedQuery, ignoreCase = true) ||
                    entry.payload.contains(normalizedQuery, ignoreCase = true))
        }

        return buildString {
            appendLine("MG AFK — NUCLEAR LOG EXPORT")
            appendLine("Generated: ${Instant.now()}")
            appendLine("Entries: ${filtered.size}")
            if (kind != null) appendLine("Kind: ${kind.label}")
            if (normalizedQuery.isNotBlank()) appendLine("Search: $normalizedQuery")
            appendLine("============================================================")
            filtered.forEach { entry ->
                appendLine("[${Instant.ofEpochMilli(entry.timestampMs)}] [${entry.kind.label}] ${entry.label}")
                if (entry.payload.isNotEmpty()) appendLine(entry.payload)
                appendLine("------------------------------------------------------------")
            }
        }
    }

    private fun readAllPersisted(): List<NuclearLogEntry> {
        val file = logFile ?: return _entries.value
        return runCatching {
            synchronized(lock) {
                if (!file.exists()) return@synchronized emptyList()
                file.useLines { lines -> lines.mapNotNull(::decode).toList() }
            }
        }.onFailure {
            Log.e(TAG, "Unable to read NUCLEAR export", it)
        }.getOrElse { _entries.value }
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
