package com.mgafk.app.ui.screens.nuclear

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mgafk.app.data.NuclearLogEntry
import com.mgafk.app.data.NuclearLogKind
import com.mgafk.app.data.NuclearLogStore
import com.mgafk.app.ui.theme.Accent
import com.mgafk.app.ui.theme.StatusError
import com.mgafk.app.ui.theme.SurfaceBorder
import com.mgafk.app.ui.theme.SurfaceCard
import com.mgafk.app.ui.theme.TextMuted
import com.mgafk.app.ui.theme.TextPrimary
import com.mgafk.app.ui.theme.TextSecondary
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private const val PAGE_SIZE = 200

@Composable
fun NuclearLogsCard() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val entries by NuclearLogStore.entries.collectAsState()

    var query by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf<NuclearLogKind?>(null) }
    var visibleLimit by remember { mutableIntStateOf(PAGE_SIZE) }
    var confirmClear by remember { mutableStateOf(false) }
    var exportFiltered by remember { mutableStateOf(false) }

    val filtered = remember(entries, query, kind) {
        val needle = query.trim()
        entries.asReversed().filter { entry ->
            (kind == null || entry.kind == kind) &&
                (needle.isBlank() ||
                    entry.label.contains(needle, ignoreCase = true) ||
                    entry.payload.contains(needle, ignoreCase = true))
        }
    }

    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("text/plain")
    ) { uri ->
        if (uri != null) {
            val useFiltered = exportFiltered
            val exportQuery = if (useFiltered) query else ""
            val exportKind = if (useFiltered) kind else null
            scope.launch(Dispatchers.IO) {
                val text = NuclearLogStore.buildExportText(exportQuery, exportKind)
                context.contentResolver.openOutputStream(uri)?.bufferedWriter()?.use { writer ->
                    writer.write(text)
                }
            }
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            text = "NUCLEAR",
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            color = TextPrimary,
        )
        Text(
            text = "Persistent raw WebSocket traffic, connection events, parser failures, state updates and app logs. " +
                "The recorder runs automatically; authentication cookies are not recorded.",
            fontSize = 12.sp,
            color = TextSecondary,
        )

        OutlinedTextField(
            value = query,
            onValueChange = {
                query = it
                visibleLimit = PAGE_SIZE
            },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Search logs") },
            placeholder = { Text("message type, crop id, rejection code…") },
        )

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            FilterChip(
                selected = kind == null,
                onClick = {
                    kind = null
                    visibleLimit = PAGE_SIZE
                },
                label = { Text("All") },
            )
            NuclearLogKind.entries.forEach { item ->
                FilterChip(
                    selected = kind == item,
                    onClick = {
                        kind = item
                        visibleLimit = PAGE_SIZE
                    },
                    label = { Text(item.label) },
                )
            }
        }

        Text(
            text = "${filtered.size} matching entries • ${entries.size} recent entries loaded",
            fontSize = 11.sp,
            color = TextMuted,
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = {
                    exportFiltered = false
                    exportLauncher.launch(exportFileName("all"))
                },
            ) {
                Text("Export All Logs")
            }
            OutlinedButton(
                onClick = {
                    exportFiltered = true
                    exportLauncher.launch(exportFileName("filtered"))
                },
            ) {
                Text("Export Filtered")
            }
            OutlinedButton(onClick = { confirmClear = true }) {
                Text("Clear")
            }
        }

        HorizontalDivider(color = SurfaceBorder)

        if (filtered.isEmpty()) {
            Text(
                text = "No matching logs yet.",
                color = TextMuted,
                fontSize = 12.sp,
                modifier = Modifier.padding(vertical = 16.dp),
            )
        } else {
            filtered.take(visibleLimit).forEach { entry ->
                NuclearLogRow(entry)
            }

            if (visibleLimit < filtered.size) {
                OutlinedButton(
                    onClick = { visibleLimit += PAGE_SIZE },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Show ${minOf(PAGE_SIZE, filtered.size - visibleLimit)} more")
                }
            }
        }

        Spacer(Modifier.height(4.dp))
        Text(
            text = "The on-screen list keeps the most recent 20,000 records in memory. Export All reads the complete persisted log file.",
            color = TextMuted,
            fontSize = 10.sp,
        )
    }

    if (confirmClear) {
        AlertDialog(
            onDismissRequest = { confirmClear = false },
            title = { Text("Clear NUCLEAR logs?") },
            text = { Text("This permanently deletes the local persisted log history.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        NuclearLogStore.clear()
                        confirmClear = false
                    }
                ) {
                    Text("Clear", color = StatusError)
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmClear = false }) {
                    Text("Cancel")
                }
            },
        )
    }
}

@Composable
private fun NuclearLogRow(entry: NuclearLogEntry) {
    val timestamp = remember(entry.timestampMs) {
        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS")
            .withZone(ZoneId.systemDefault())
            .format(Instant.ofEpochMilli(entry.timestampMs))
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = SurfaceCard,
        shape = RoundedCornerShape(10.dp),
        border = BorderStroke(1.dp, SurfaceBorder),
    ) {
        Column(
            modifier = Modifier.padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = entry.kind.label,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = Accent,
                )
                Text(
                    text = timestamp,
                    fontSize = 10.sp,
                    color = TextMuted,
                    fontFamily = FontFamily.Monospace,
                )
            }
            Text(
                text = entry.label,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                color = TextPrimary,
            )
            if (entry.payload.isNotBlank()) {
                SelectionContainer {
                    Text(
                        text = entry.payload,
                        fontSize = 10.sp,
                        color = TextSecondary,
                        fontFamily = FontFamily.Monospace,
                        lineHeight = 14.sp,
                    )
                }
            }
        }
    }
}

private fun exportFileName(suffix: String): String {
    val stamp = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss")
        .withZone(ZoneId.systemDefault())
        .format(Instant.now())
    return "mgafk-nuclear-$suffix-$stamp.txt"
}
