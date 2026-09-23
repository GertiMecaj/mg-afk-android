package com.mgafk.app.ui.screens.lab

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mgafk.app.data.model.GardenPlantSnapshot
import com.mgafk.app.data.model.Session
import com.mgafk.app.ui.theme.Accent
import com.mgafk.app.ui.theme.StatusConnected
import com.mgafk.app.ui.theme.SurfaceBorder
import com.mgafk.app.ui.theme.SurfaceCard
import com.mgafk.app.ui.theme.TextMuted
import com.mgafk.app.ui.theme.TextPrimary
import com.mgafk.app.ui.theme.TextSecondary
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlin.math.max

private const val DNA_PAGE_SIZE = 75

@Composable
fun DnaCard(
    session: Session,
    onInject: (
        tileObjectIdx: Int,
        growSlotIdx: Int,
        slotId: Int,
        mutation: String,
    ) -> Unit,
) {
    var visibleLimit by remember { mutableIntStateOf(DNA_PAGE_SIZE) }
    val crops = remember(session.garden) {
        session.garden.sortedWith(compareBy<GardenPlantSnapshot> { it.tileId }.thenBy { it.growSlotIdx })
    }
    val chilledCount = session.inventory.tools.firstOrNull { it.toolId == "ChilledPotion" }?.quantity ?: 0
    val frozenCount = session.inventory.tools.firstOrNull { it.toolId == "FrozenPotion" }?.quantity ?: 0
    val frozenObserved = session.inventory.tools.any { it.toolId == "FrozenPotion" }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            text = "LAB / DNA",
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            color = TextPrimary,
        )
        Text(
            text = "Every server-reported garden crop is shown individually. growSlotIdx is the " +
                "position in slots[]; slotId is the server's explicit id and can be different.",
            fontSize = 12.sp,
            color = TextSecondary,
        )

        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = SurfaceCard,
            shape = RoundedCornerShape(10.dp),
            border = BorderStroke(1.dp, SurfaceBorder),
        ) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text("Potion observations", color = Accent, fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
                Text("ChilledPotion: $chilledCount", color = TextPrimary, fontSize = 12.sp)
                Text(
                    text = if (frozenObserved) "FrozenPotion: $frozenCount"
                    else "FrozenPotion: 0 (not observed in server inventory)",
                    color = TextPrimary,
                    fontSize = 12.sp,
                )
                Text(
                    text = "Both INJECT controls remain available. The app sends the normal " +
                        "MutationPotion command; the server remains authoritative and may reject it.",
                    color = TextMuted,
                    fontSize = 10.sp,
                )
            }
        }

        Text(
            text = "Crops: ${crops.size}",
            color = TextMuted,
            fontSize = 11.sp,
        )

        crops.take(visibleLimit).forEach { crop ->
            DnaCropCard(
                crop = crop,
                onInject = onInject,
            )
        }

        if (visibleLimit < crops.size) {
            OutlinedButton(
                onClick = { visibleLimit += DNA_PAGE_SIZE },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Show ${minOf(DNA_PAGE_SIZE, crops.size - visibleLimit)} more")
            }
        }

        if (crops.isEmpty()) {
            Text(
                text = "No crops have been received from the server yet.",
                color = TextMuted,
                fontSize = 12.sp,
                modifier = Modifier.padding(vertical = 12.dp),
            )
        }
    }
}

@Composable
private fun DnaCropCard(
    crop: GardenPlantSnapshot,
    onInject: (Int, Int, Int, String) -> Unit,
) {
    val now = System.currentTimeMillis()
    val remainingMs = max(0L, crop.endTime - now)
    val maturity = when {
        crop.endTime <= 0L -> "Unknown"
        remainingMs == 0L -> "Mature"
        else -> "Growing"
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = SurfaceCard,
        shape = RoundedCornerShape(10.dp),
        border = BorderStroke(1.dp, SurfaceBorder),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = crop.species.ifBlank { "Unknown crop" },
                    color = TextPrimary,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                )
                Text(
                    text = maturity,
                    color = if (maturity == "Mature") StatusConnected else Accent,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }

            DnaLine("mutations", if (crop.mutations.isEmpty()) "[]" else crop.mutations.joinToString(prefix = "[", postfix = "]"))
            DnaLine("size", crop.size.toString())
            DnaLine("tileObjectIdx", crop.tileId.toString())
            DnaLine("growSlotIdx", crop.growSlotIdx.toString())
            DnaLine("slotId", crop.slotId.toString())
            DnaLine("startTime", formatTime(crop.startTime))
            DnaLine("endTime", formatTime(crop.endTime))
            if (remainingMs > 0L) DnaLine("remaining", formatDuration(remainingMs))
            if (crop.preserved) DnaLine("preserved", "true")

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(
                    onClick = {
                        onInject(crop.tileId, crop.growSlotIdx, crop.slotId, "Chilled")
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Text("INJECT CHILLED", fontSize = 10.sp)
                }
                OutlinedButton(
                    onClick = {
                        onInject(crop.tileId, crop.growSlotIdx, crop.slotId, "Frozen")
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Text("INJECT FROZEN", fontSize = 10.sp)
                }
            }
        }
    }
}

@Composable
private fun DnaLine(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = "$label:",
            modifier = Modifier.weight(0.36f),
            color = TextMuted,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
        )
        Text(
            text = value,
            modifier = Modifier.weight(0.64f),
            color = TextSecondary,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
        )
    }
}

private fun formatTime(value: Long): String {
    if (value <= 0L) return "—"
    return DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
        .withZone(ZoneId.systemDefault())
        .format(Instant.ofEpochMilli(value)) + " ($value)"
}

private fun formatDuration(ms: Long): String {
    val totalSeconds = ms / 1000L
    val hours = totalSeconds / 3600L
    val minutes = (totalSeconds % 3600L) / 60L
    val seconds = totalSeconds % 60L
    return when {
        hours > 0 -> "${hours}h ${minutes}m ${seconds}s"
        minutes > 0 -> "${minutes}m ${seconds}s"
        else -> "${seconds}s"
    }
}
