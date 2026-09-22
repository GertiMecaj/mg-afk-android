#!/usr/bin/env python3
from pathlib import Path

ROOT = Path("app/src/main/java/com/mgafk/app")
MAIN = ROOT / "ui/screens/MainScreen.kt"
VM = ROOT / "ui/MainViewModel.kt"
LAB = ROOT / "ui/screens/lab/LabCard.kt"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"[LAB] anchor not found: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"[LAB] anchor count for {label}: {text.count(old)}")
    return text.replace(old, new, 1)

main = MAIN.read_text()
main = replace_once(main,
    "import com.mgafk.app.ui.screens.god.GodCard\n",
    "import com.mgafk.app.ui.screens.god.GodCard\nimport com.mgafk.app.ui.screens.lab.LabCard\n",
    "LabCard import")
main = replace_once(main,
    '    GOD("GOD", Icons.Outlined.Bolt, requiresConnection = true),\n',
    '    GOD("GOD", Icons.Outlined.Bolt, requiresConnection = true),\n    LAB("LAB", Icons.Outlined.BugReport, requiresConnection = true),\n',
    "LAB nav section")
main = replace_once(main,
    "        NavSection.PETS -> {\n",
    '''        NavSection.LAB -> {
            LabCard(
                sessionId = session.id,
                plants = session.garden,
                toolInventory = session.inventory.tools,
                toolShack = session.toolShack,
                apiReady = state.apiReady,
                onInjectFrost = { tileObjectIdx, growSlotIdx ->
                    viewModel.labInjectFrost(session.id, tileObjectIdx, growSlotIdx)
                },
            )
        }
        NavSection.PETS -> {
''',
    "LAB section content")
MAIN.write_text(main)

vm = VM.read_text()
vm = replace_once(vm,
    "    private val pendingCleanseJobs = mutableMapOf<String, Job>()\n",
    '''    /**
     * LAB experiment: ask the authoritative server to apply the Frozen mutation directly
     * to one mature crop slot. No local mutation or potion count is changed optimistically;
     * LAB observes the subsequent live Session.garden state to decide success/failure.
     */
    fun labInjectFrost(sessionId: String, tileObjectIdx: Int, growSlotIdx: Int) {
        val actions = clients[sessionId]?.actions ?: return
        val session = _state.value.sessions.find { it.id == sessionId } ?: return
        if (!session.connected) return

        val target = session.garden.find {
            it.tileId == tileObjectIdx && it.slotIndex == growSlotIdx
        } ?: return

        val now = System.currentTimeMillis()
        if (target.endTime <= 0L || now < target.endTime) return
        if (target.mutations.any { it.equals("Frozen", ignoreCase = true) }) return

        AppLog.d(TAG, "[LAB/Potions] Inject Frost tile=$tileObjectIdx slot=$growSlotIdx before=${target.mutations}")
        actions.mutationPotion(
            tileObjectIdx = tileObjectIdx,
            growSlotIdx = growSlotIdx,
            mutation = "Frozen",
        )
    }

    private val pendingCleanseJobs = mutableMapOf<String, Job>()
''',
    "LAB inject function")
VM.write_text(vm)

LAB.parent.mkdir(parents=True, exist_ok=True)
LAB.write_text(r'''package com.mgafk.app.ui.screens.lab

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mgafk.app.data.model.GardenPlantSnapshot
import com.mgafk.app.data.model.InventoryToolItem
import com.mgafk.app.data.repository.MgApi
import com.mgafk.app.ui.components.AppCard
import com.mgafk.app.ui.components.SpriteImage
import com.mgafk.app.ui.theme.Accent
import com.mgafk.app.ui.theme.StatusConnected
import com.mgafk.app.ui.theme.StatusError
import com.mgafk.app.ui.theme.SurfaceDark
import com.mgafk.app.ui.theme.TextMuted
import com.mgafk.app.ui.theme.TextPrimary
import com.mgafk.app.ui.theme.TextSecondary
import kotlinx.coroutines.delay

private const val CHILLED_POTION = "ChilledPotion"
private const val FROZEN_POTION = "FrozenPotion"
private const val LAB_TIMEOUT_MS = 6000L

private fun cropKey(crop: GardenPlantSnapshot): String = "${crop.tileId}:${crop.slotIndex}"

private fun potionCount(
    inventory: List<InventoryToolItem>,
    shack: List<InventoryToolItem>,
    id: String,
): Int =
    (inventory.find { it.toolId == id }?.quantity ?: 0) +
        (shack.find { it.toolId == id }?.quantity ?: 0)

private fun mutationsText(mutations: List<String>): String =
    if (mutations.isEmpty()) "None" else mutations.joinToString(", ")

@Composable
private fun rememberLabClock(): Long {
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(1000)
            now = System.currentTimeMillis()
        }
    }
    return now
}

@Composable
fun LabCard(
    sessionId: String,
    plants: List<GardenPlantSnapshot>,
    toolInventory: List<InventoryToolItem>,
    toolShack: List<InventoryToolItem>,
    apiReady: Boolean = false,
    onInjectFrost: (tileObjectIdx: Int, growSlotIdx: Int) -> Unit = { _, _ -> },
) {
    val now = rememberLabClock()

    var selectedKey by remember(sessionId) { mutableStateOf<String?>(null) }
    var pendingKey by remember(sessionId) { mutableStateOf<String?>(null) }
    var testNonce by remember(sessionId) { mutableIntStateOf(0) }
    var beforeMutations by remember(sessionId) { mutableStateOf<List<String>>(emptyList()) }
    var beforeChilled by remember(sessionId) { mutableIntStateOf(0) }
    var beforeFrozen by remember(sessionId) { mutableIntStateOf(0) }
    var resultText by remember(sessionId) {
        mutableStateOf(
            "READY\nSelect a mature crop, then tap INJECT FROST. " +
                "LAB will only report SUCCESSFUL if the authoritative garden state changes to Frozen."
        )
    }

    val crops = remember(plants, apiReady) {
        plants.sortedWith(
            compareBy<GardenPlantSnapshot>(
                { MgApi.findItem(it.species)?.name?.removeSuffix(" Seed") ?: it.species },
                { it.tileId },
                { it.slotIndex },
            )
        )
    }
    val availableKeys = remember(crops) { crops.map(::cropKey).toSet() }

    LaunchedEffect(sessionId, availableKeys) {
        if (selectedKey !in availableKeys) selectedKey = null
        if (pendingKey !in availableKeys) pendingKey = null
    }

    val chilledNow = potionCount(toolInventory, toolShack, CHILLED_POTION)
    val frozenNow = potionCount(toolInventory, toolShack, FROZEN_POTION)

    LaunchedEffect(sessionId, pendingKey, plants, chilledNow, frozenNow) {
        val key = pendingKey ?: return@LaunchedEffect
        val target = plants.find { cropKey(it) == key } ?: return@LaunchedEffect
        if (target.mutations.any { it.equals("Frozen", ignoreCase = true) }) {
            resultText = buildString {
                appendLine("SUCCESSFUL")
                appendLine("Requested mutation: Frozen")
                appendLine("Before: ${mutationsText(beforeMutations)}")
                appendLine("After: ${mutationsText(target.mutations)}")
                appendLine("Chilled Potions: $beforeChilled → $chilledNow")
                append("Frozen Potions: $beforeFrozen → $frozenNow")
            }
            pendingKey = null
        }
    }

    LaunchedEffect(sessionId, testNonce) {
        if (testNonce == 0) return@LaunchedEffect
        val nonce = testNonce
        delay(LAB_TIMEOUT_MS)
        if (testNonce == nonce && pendingKey != null) {
            resultText = buildString {
                appendLine("FAILED")
                appendLine("Requested mutation: Frozen")
                appendLine("Before: ${mutationsText(beforeMutations)}")
                appendLine("No Frozen mutation was observed in authoritative garden state within 6 seconds.")
                appendLine("Chilled Potions at send: $beforeChilled")
                append("Frozen Potions at send: $beforeFrozen")
            }
            pendingKey = null
        }
    }

    AppCard(
        title = "LAB — Potions",
        persistKey = "lab_potions",
        collapsible = true,
    ) {
        Text(
            "Experimental mutation command tester. Nothing is changed locally: the result is based only on the server-fed garden state.",
            fontSize = 11.sp,
            color = TextSecondary,
        )

        Spacer(modifier = Modifier.height(8.dp))
        Text(
            "Potions available • Chilled: $chilledNow • Frozen: $frozenNow",
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            color = TextPrimary,
        )
        Text(
            if (chilledNow > 0 && frozenNow == 0) {
                "Controlled-test inventory detected: Chilled available, Frozen = 0."
            } else {
                "For the cleanest experiment, keep at least 1 Chilled Potion and 0 Frozen Potions."
            },
            fontSize = 10.sp,
            color = if (chilledNow > 0 && frozenNow == 0) StatusConnected else TextMuted,
        )

        Spacer(modifier = Modifier.height(12.dp))
        Text(
            "All planted crop slots",
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = TextPrimary,
        )

        if (crops.isEmpty()) {
            Spacer(modifier = Modifier.height(6.dp))
            Text("No crops are currently planted.", fontSize = 11.sp, color = TextMuted)
        } else {
            Spacer(modifier = Modifier.height(6.dp))
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                crops.forEach { crop ->
                    val key = cropKey(crop)
                    val selected = selectedKey == key
                    val mature = crop.endTime > 0L && now >= crop.endTime
                    val displayName = MgApi.findItem(crop.species)?.name
                        ?.removeSuffix(" Seed")
                        ?.takeIf { it.isNotBlank() }
                        ?: crop.species

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(
                                if (selected) Accent.copy(alpha = 0.12f) else SurfaceDark,
                                RoundedCornerShape(10.dp),
                            )
                            .clickable(enabled = pendingKey == null) { selectedKey = key }
                            .padding(horizontal = 8.dp, vertical = 7.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        RadioButton(
                            selected = selected,
                            enabled = pendingKey == null,
                            onClick = { selectedKey = key },
                        )
                        SpriteImage(
                            category = "plants",
                            name = crop.species,
                            size = 34.dp,
                            contentDescription = displayName,
                        )
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                "$displayName • Tile ${crop.tileId} / Slot ${crop.slotIndex}",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = TextPrimary,
                            )
                            Text(
                                "Mutations: ${mutationsText(crop.mutations)}",
                                fontSize = 9.sp,
                              color = TextMuted,
                              )
                        }
                        Text(
                            if (mature) "MATURE" else "GROWING",
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (mature) StatusConnected else TextMuted,
                        )
                    }
                }
            }
        }

        val selectedCrop = crops.find { cropKey(it) == selectedKey }
        val selectedMature =
            selectedCrop != null && selectedCrop.endTime > 0L && now >= selectedCrop.endTime
        val selectedAlreadyFrozen =
            selectedCrop?.mutations?.any { it.equals("Frozen", ignoreCase = true) } == true
        val canInject =
            selectedCrop != null && selectedMature && !selectedAlreadyFrozen && pendingKey == null

        Spacer(modifier = Modifier.height(12.dp))
        Button(
            modifier = Modifier.fillMaxWidth(),
            enabled = canInject,
            onClick = {
                val target = selectedCrop ?: return@Button
                beforeMutations = target.mutations.toList()
                beforeChilled = chilledNow
                beforeFrozen = frozenNow
                pendingKey = cropKey(target)
                testNonce += 1
                resultText = buildString {
                    appendLine("TESTING...")
                    appendLine("Requested mutation: Frozen")
                    appendLine("Target: ${MgApi.findItem(target.species)?.name?.removeSuffix(" Seed") ?: target.species}")
                    appendLine("Tile ${target.tileId} / Slot ${target.slotIndex}")
                    append("Before: ${mutationsText(target.mutations)}")
                }
                onInjectFrost(target.tileId, target.slotIndex)
            },
        ) {
            Text(if (pendingKey != null) "WAITING FOR SERVER..." else "INJECT FROST")
        }

        if (selectedCrop != null && !selectedMature) {
            Text(
                "Selected crop is still growing. Mutation tests are enabled only on mature crops.",
                fontSize = 10.sp,
                color = TextMuted,
                modifier = Modifier.padding(top = 6.dp),
            )
        } else if (selectedAlreadyFrozen) {
            Text(
                "Selected crop is already Frozen; choose a neutral crop so the test cannot false-positive.",
                fontSize = 10.sp,
                color = StatusError,
                modifier = Modifier.padding(top = 6.dp),
            )
        }

        Spacer(modifier = Modifier.height(10.dp))
        OutlinedTextField(
            value = resultText,
            onValueChange = {},
            readOnly = true,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Experiment result") },
            minLines = 5,
        )
    }
}
''')

print("Applied LAB -> Potions experimental Frost injection UI and command")
