package com.mgafk.app.data

import android.content.Context
import android.util.Log
import com.mgafk.app.data.model.GardenPlantSnapshot
import com.mgafk.app.data.model.InventoryToolItem
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.json.JsonArray
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
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

/**
 * Compact persistent protocol/debug recorder.
 *
 * NUCLEAR intentionally does not archive the server's full once-per-second userSlot snapshots.
 * Those can be ~100 KB each while carrying almost no new information. Instead we keep:
 * connection/handshake events, gameplay commands, command results, parser failures, meaningful
 * patch paths, ability events, and focused high-resolution INJECT traces.
 */
enum class NuclearLogKind(val label: String) {
    WS_IN("WS IN"),
    WS_OUT("WS OUT"),
    CONNECTION("Connection"),
    PARSER("Parser"),
    STATE("State"),
    EXPERIMENT("Experiment"),
    APP("App"),
}

data class NuclearLogEntry(
    val id: Long,
    val timestampMs: Long,
    val kind: NuclearLogKind,
    val label: String,
    val payload: String,
)

private data class InjectTrace(
    val id: String,
    val sessionId: String,
    val startedAtMs: Long,
    val tileObjectIdx: Int,
    val growSlotIdx: Int,
    val slotId: Int,
    val species: String,
    val mutation: String,
    val toolId: String,
    var lastCropSignature: String = "",
    var lastPotionSignature: String = "",
)

object NuclearLogStore {
    private const val TAG = "NuclearLogStore"
    private const val DIRECTORY = "nuclear"
    private const val FILE_NAME = "nuclear-events.jsonl"
    private const val MAX_UI_ENTRIES = 500
    private const val MAX_UI_PAYLOAD_CHARS = 8_000
    private const val TRACE_WINDOW_MS = 15_000L

    private val uiLock = Any()
    private val fileLock = Any()
    private val traceLock = Any()
    private val nextId = AtomicLong(0L)
    private val writer = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "mgafk-nuclear-log").apply { isDaemon = true }
    }

    @Volatile private var logFile: File? = null
    @Volatile private var activeTrace: InjectTrace? = null
    private var lastTraceId: String? = null
    private val lastTraceEntries = mutableListOf<NuclearLogEntry>()

    private val _entries = MutableStateFlow<List<NuclearLogEntry>>(emptyList())
    val entries: StateFlow<List<NuclearLogEntry>> = _entries.asStateFlow()

    val isInitialized: Boolean get() = logFile != null

    fun initialize(context: Context) {
        if (logFile != null) return
        synchronized(fileLock) {
            if (logFile != null) return
            val directory = File(context.applicationContext.filesDir, DIRECTORY).apply { mkdirs() }
            logFile = File(directory, FILE_NAME)
        }
    }

    fun record(kind: NuclearLogKind, label: String, payload: String = ""): NuclearLogEntry? {
        val file = logFile ?: return null
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

        writer.execute {
            runCatching {
                synchronized(fileLock) {
                    file.appendText(encode(diskEntry) + "\n")
                }
            }.onFailure {
                Log.e(TAG, "Unable to persist NUCLEAR log", it)
            }
        }
        return diskEntry
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

    /** Record useful outbound protocol traffic, dropping heartbeat noise. */
    fun recordOutgoing(text: String) {
        if (text == "pong" || text == "\"pong\"" || text == "ping" || text == "\"ping\"") return
        val parsed = runCatching { AppJson.default.parseToJsonElement(text).jsonObject }.getOrNull()
        val type = parsed?.get("type")?.jsonPrimitive?.contentOrNull
        val commandType = parsed?.get("command")?.jsonObject
            ?.get("type")?.jsonPrimitive?.contentOrNull
        val label = when {
            type == "QuinoaCommand" && !commandType.isNullOrBlank() -> "command:$commandType"
            !type.isNullOrBlank() -> type
            else -> "raw"
        }
        val entry = record(NuclearLogKind.WS_OUT, label, text)
        if (commandType == "MutationPotion" && entry != null) appendTrace(entry)
    }

    fun recordIncoming(type: String?, msg: JsonObject, raw: String) {
        when (type) {
            "Welcome" -> {
                val executed = msg["executedCommandSequence"]?.jsonPrimitive?.longOrNull
                val self = msg["selfPlayerId"]?.jsonPrimitive?.contentOrNull.orEmpty()
                record(
                    NuclearLogKind.WS_IN,
                    "Welcome",
                    "selfPlayerId=$self executedCommandSequence=${executed ?: "?"}",
                )
            }
            "PartialState" -> recordMeaningfulPatches(msg["patches"] as? JsonArray)
            "QuinoaCommandResult" -> {
                val entry = record(NuclearLogKind.WS_IN, "QuinoaCommandResult", raw)
                if (entry != null) appendTrace(entry)
            }
            "QuinoaMovementSnapshot", "Config" -> Unit
            else -> {
                if (!type.isNullOrBlank()) {
                    val payload = if (raw.length <= 16_000) raw else "payloadBytes=${raw.length}"
                    record(NuclearLogKind.WS_IN, type, payload)
                }
            }
        }
    }

    private fun recordMeaningfulPatches(patches: JsonArray?) {
        if (patches.isNullOrEmpty()) return

        val interesting = patches.mapNotNull { el ->
            val patch = el as? JsonObject ?: return@mapNotNull null
            val path = patch["path"]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
            val op = patch["op"]?.jsonPrimitive?.contentOrNull.orEmpty()

            if (path.endsWith("/currentTime")) return@mapNotNull null
            if (path.contains("/secondsUntilRestock")) return@mapNotNull null
            if (path.contains("/petSlotInfos/") && !path.contains("lastActionEvent")) return@mapNotNull null
            if (path.matches(Regex("^/child/data/userSlots/\\d+$"))) return@mapNotNull null

            val relevant = path.contains("/garden") ||
                path.contains("/inventory") ||
                path.contains("/activityLogs") ||
                path.contains("lastActionEvent") ||
                path.contains("/petTeams") ||
                path.contains("/weather") ||
                path.contains("/gameVotes") ||
                path.contains("/selectedGame")
            if (!relevant) return@mapNotNull null

            val value = patch["value"]
            val shortValue = when (value) {
                is JsonPrimitive -> value.content.take(240)
                null -> ""
                else -> "[structured value omitted]"
            }
            "$op $path${if (shortValue.isNotBlank()) " = $shortValue" else ""}"
        }

        if (interesting.isNotEmpty()) {
            record(NuclearLogKind.STATE, "meaningful_patches", interesting.joinToString("\n"))
        }
    }

    fun recordAbility(
        action: String,
        petSpecies: String,
        petId: String?,
        timestamp: Long,
        params: Map<String, String>,
    ) {
        val payload = buildString {
            append("pet=").append(petSpecies)
            if (!petId.isNullOrBlank()) append(" id=").append(petId)
            append(" timestamp=").append(timestamp)
            if (params.isNotEmpty()) {
                append("\n")
                append(params.entries.joinToString(" ") { "${it.key}=${it.value}" })
            }
        }
        record(NuclearLogKind.STATE, "ability:$action", payload)
    }

    fun beginInjectTrace(
        sessionId: String,
        tileObjectIdx: Int,
        growSlotIdx: Int,
        slotId: Int,
        species: String,
        mutation: String,
        toolId: String,
        inventoryCount: Int,
        size: Int,
        mutations: List<String>,
        startTime: Long,
        endTime: Long,
    ): String {
        val trace = InjectTrace(
            id = UUID.randomUUID().toString(),
            sessionId = sessionId,
            startedAtMs = System.currentTimeMillis(),
            tileObjectIdx = tileObjectIdx,
            growSlotIdx = growSlotIdx,
            slotId = slotId,
            species = species,
            mutation = mutation,
            toolId = toolId,
        )
        synchronized(traceLock) {
            activeTrace = trace
            lastTraceId = trace.id
            lastTraceEntries.clear()
        }
        traceEntry(
            "inject_start",
            buildString {
                appendLine("traceId=${trace.id}")
                appendLine("mutation=$mutation toolId=$toolId observedInventory=$inventoryCount")
                appendLine("tileObjectIdx=$tileObjectIdx growSlotIdx=$growSlotIdx slotId=$slotId species=$species")
                appendLine("size=$size mutations=${mutations.joinToString(prefix = "[", postfix = "]")}")
                append("startTime=$startTime endTime=$endTime")
            },
        )
        return trace.id
    }

    fun observeGarden(sessionId: String, garden: List<GardenPlantSnapshot>) {
        val trace = currentTrace(sessionId) ?: return
        val crop = garden.firstOrNull {
            it.tileId == trace.tileObjectIdx && it.growSlotIdx == trace.growSlotIdx
        } ?: run {
            traceEntry("inject_crop_state", "target crop no longer present")
            return
        }
        val signature = "${crop.species}|${crop.size}|${crop.mutations}|${crop.startTime}|${crop.endTime}|${crop.slotId}"
        synchronized(traceLock) {
            if (trace.lastCropSignature == signature) return
            trace.lastCropSignature = signature
        }
        traceEntry(
            "inject_crop_state",
            "tileObjectIdx=${crop.tileId} growSlotIdx=${crop.growSlotIdx} slotId=${crop.slotId} " +
                "species=${crop.species} size=${crop.size} mutations=${crop.mutations} " +
                "startTime=${crop.startTime} endTime=${crop.endTime}",
        )
    }

    fun observePotionInventory(sessionId: String, tools: List<InventoryToolItem>) {
        val trace = currentTrace(sessionId) ?: return
        val chilled = tools.firstOrNull { it.toolId == "ChilledPotion" }?.quantity ?: 0
        val frozen = tools.firstOrNull { it.toolId == "FrozenPotion" }?.quantity ?: 0
        val signature = "$chilled|$frozen"
        synchronized(traceLock) {
            if (trace.lastPotionSignature == signature) return
            trace.lastPotionSignature = signature
        }
        traceEntry("inject_inventory_state", "ChilledPotion=$chilled FrozenPotion=$frozen")
    }

    fun noteCommandResult(msg: JsonObject) {
        val trace = synchronized(traceLock) { activeTrace } ?: return
        if (System.currentTimeMillis() - trace.startedAtMs > TRACE_WINDOW_MS) return
        val ok = msg["ok"]?.jsonPrimitive?.contentOrNull.orEmpty()
        val type = msg["commandType"]?.jsonPrimitive?.contentOrNull.orEmpty()
        val code = msg["code"]?.jsonPrimitive?.contentOrNull.orEmpty()
        traceEntry("inject_command_result", "commandType=$type ok=$ok code=$code")
    }

    fun hasLastInjectTrace(): Boolean = synchronized(traceLock) { lastTraceEntries.isNotEmpty() }

    fun writeLastInjectTrace(destination: Writer) {
        val entries = synchronized(traceLock) { lastTraceEntries.toList() }
        destination.appendLine("MG AFK — LAST INJECT TRACE")
        destination.appendLine("Generated: ${Instant.now()}")
        destination.appendLine("Trace: ${lastTraceId ?: "none"}")
        destination.appendLine("============================================================")
        entries.forEach { writeEntry(destination, it) }
    }

    private fun currentTrace(sessionId: String): InjectTrace? {
        val trace = synchronized(traceLock) { activeTrace } ?: return null
        if (trace.sessionId != sessionId) return null
        if (System.currentTimeMillis() - trace.startedAtMs > TRACE_WINDOW_MS) {
            synchronized(traceLock) {
                if (activeTrace?.id == trace.id) activeTrace = null
            }
            return null
        }
        return trace
    }

    private fun traceEntry(label: String, payload: String) {
        val entry = record(NuclearLogKind.EXPERIMENT, label, payload) ?: return
        appendTrace(entry)
    }

    private fun appendTrace(entry: NuclearLogEntry) {
        val trace = synchronized(traceLock) { activeTrace } ?: return
        if (System.currentTimeMillis() - trace.startedAtMs > TRACE_WINDOW_MS) return
        synchronized(traceLock) {
            if (lastTraceEntries.none { it.id == entry.id }) lastTraceEntries += entry
        }
    }

    fun clear() {
        synchronized(uiLock) { _entries.value = emptyList() }
        synchronized(traceLock) {
            activeTrace = null
            lastTraceId = null
            lastTraceEntries.clear()
        }
        writer.execute {
            runCatching {
                synchronized(fileLock) { logFile?.writeText("") }
            }.onFailure { Log.e(TAG, "Unable to clear NUCLEAR log", it) }
        }
    }

    fun writeExport(destination: Writer, query: String = "", kind: NuclearLogKind? = null) {
        val normalizedQuery = query.trim()
        destination.appendLine("MG AFK — NUCLEAR EVENT LOG")
        destination.appendLine("Generated: ${Instant.now()}")
        if (kind != null) destination.appendLine("Kind: ${kind.label}")
        if (normalizedQuery.isNotBlank()) destination.appendLine("Search: $normalizedQuery")
        destination.appendLine("============================================================")

        val file = logFile
        if (file == null || !file.exists()) {
            _entries.value.forEach { if (matches(it, normalizedQuery, kind)) writeEntry(destination, it) }
            return
        }

        synchronized(fileLock) {
            runCatching {
                file.useLines { lines ->
                    lines.forEach { line ->
                        val entry = decode(line) ?: return@forEach
                        if (matches(entry, normalizedQuery, kind)) writeEntry(destination, entry)
                    }
                }
            }.onFailure {
                Log.e(TAG, "Unable to stream NUCLEAR export", it)
                destination.appendLine("[EXPORT ERROR] ${it.message ?: it::class.java.simpleName}")
            }
        }
    }

    private fun payloadForUi(payload: String): String =
        if (payload.length <= MAX_UI_PAYLOAD_CHARS) payload
        else payload.take(MAX_UI_PAYLOAD_CHARS) +
            "\n… [UI preview truncated; complete event preserved in export]"

    private fun matches(entry: NuclearLogEntry, query: String, kind: NuclearLogKind?): Boolean =
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
                kind = obj["kind"]?.jsonPrimitive?.contentOrNull?.let { NuclearLogKind.valueOf(it) }
                    ?: return null,
                label = obj["label"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                payload = obj["payload"]?.jsonPrimitive?.contentOrNull.orEmpty(),
            )
        }.getOrNull()
    }
}
