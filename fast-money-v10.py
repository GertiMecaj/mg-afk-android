#!/usr/bin/env python3
from pathlib import Path
import re


def read(path: str) -> str:
    return Path(path).read_text()


def write(path: str, text: str) -> None:
    Path(path).write_text(text)


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly 1 occurrence, found {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


def replace_after(path: str, anchor: str, old: str, new: str) -> None:
    text = read(path)
    pos = text.find(anchor)
    if pos < 0:
        raise SystemExit(f"{path}: anchor not found: {anchor!r}")
    before, tail = text[:pos], text[pos:]
    count = tail.count(old)
    if count < 1:
        raise SystemExit(f"{path}: target not found after anchor {anchor!r}: {old[:120]!r}")
    write(path, before + tail.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    text = read(path)
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{path}: regex expected exactly 1 match, found {count}: {pattern[:120]!r}")
    write(path, new_text)


# ---------------------------------------------------------------------------
# Persistent per-session setup.
# ---------------------------------------------------------------------------
session_file = "app/src/main/java/com/mgafk/app/data/model/Session.kt"
replace_once(
    session_file,
    '''    val autoPlantEggs: Boolean = false,
    val pets: List<PetSnapshot> = emptyList(),''',
    '''    val autoPlantEggs: Boolean = false,
    val godFastMoneyEnabled: Boolean = false,
    val godFastMoneySelectedSpecies: Set<String> = emptySet(),
    val godFastMoneyShopFilters: Set<String> = emptySet(),
    val godFastMoneyTierFilters: Set<String> = emptySet(),
    val godFastMoneySearchQuery: String = "",
    val pets: List<PetSnapshot> = emptyList(),''',
)

# ---------------------------------------------------------------------------
# GOD Fast Money UI: full plant catalog, search, shop/tier filters, persistent state.
# ---------------------------------------------------------------------------
god = "app/src/main/java/com/mgafk/app/ui/screens/god/GodCard.kt"
replace_once(
    god,
    "import com.mgafk.app.ui.components.SpriteImage\n",
    "import com.mgafk.app.ui.components.SpriteImage\nimport com.mgafk.app.ui.components.SearchFilterBar\n",
)

replace_once(
    god,
    '''    onFastMoneyChanged: (enabled: Boolean, selectedSpecies: Set<String>) -> Unit = { _, _ -> },''',
    '''    fastMoneyEnabled: Boolean = false,
    fastMoneySelectedSpecies: Set<String> = emptySet(),
    fastMoneyShopFilters: Set<String> = emptySet(),
    fastMoneyTierFilters: Set<String> = emptySet(),
    fastMoneySearchQuery: String = "",
    onFastMoneyChanged: (
        enabled: Boolean,
        selectedSpecies: Set<String>,
        selectedShops: Set<String>,
        selectedTiers: Set<String>,
        searchQuery: String,
    ) -> Unit = { _, _, _, _, _ -> },''',
)

replace_once(
    god,
    '''        GodFastMoneyCard(
            seeds = seeds,
            seedSilo = seedSilo,
            shops = shops,
            freePlantTiles = freePlantTiles,
            onFastMoneyChanged = onFastMoneyChanged,
        )''',
    '''        GodFastMoneyCard(
            seeds = seeds,
            seedSilo = seedSilo,
            shops = shops,
            freePlantTiles = freePlantTiles,
            enabled = fastMoneyEnabled,
            selectedSpecies = fastMoneySelectedSpecies,
            selectedShops = fastMoneyShopFilters,
            selectedTiers = fastMoneyTierFilters,
            searchQuery = fastMoneySearchQuery,
            onFastMoneyChanged = onFastMoneyChanged,
        )''',
)

fast_money_ui = r'''@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun GodFastMoneyCard(
    seeds: List<InventorySeedItem>,
    seedSilo: List<InventorySeedItem>,
    shops: List<ShopSnapshot>,
    freePlantTiles: Int,
    enabled: Boolean,
    selectedSpecies: Set<String>,
    selectedShops: Set<String>,
    selectedTiers: Set<String>,
    searchQuery: String,
    onFastMoneyChanged: (
        enabled: Boolean,
        selectedSpecies: Set<String>,
        selectedShops: Set<String>,
        selectedTiers: Set<String>,
        searchQuery: String,
    ) -> Unit,
) {
    data class FastMoneyPlantOption(
        val species: String,
        val displayName: String,
        val rarity: String,
        val shops: Set<String>,
    )

    var filtersExpanded by rememberSaveable { mutableStateOf(false) }

    val options = remember(shops) {
        val liveShopsByItem = mutableMapOf<String, MutableSet<String>>()
        shops.forEach { shop ->
            val shopType = shop.type.trim().lowercase()
            if (shopType.isBlank()) return@forEach
            (shop.itemNames + shop.itemStocks.keys).distinct().forEach { itemId ->
                liveShopsByItem.getOrPut(itemId) { linkedSetOf() }.add(shopType)
            }
        }

        MgApi.getPlants()
            .map { (species, entry) ->
                val eligible = entry.eligibleShops
                    .map { it.trim().lowercase() }
                    .filter { it.isNotBlank() }
                    .toMutableSet()
                if (eligible.isEmpty()) eligible.add("seed")
                eligible.addAll(liveShopsByItem[species].orEmpty())

                FastMoneyPlantOption(
                    species = species,
                    displayName = entry.name.removeSuffix(" Seed").ifBlank { species },
                    rarity = entry.rarity.orEmpty(),
                    shops = eligible,
                )
            }
            .sortedWith(
                compareBy<FastMoneyPlantOption>(
                    { MgApi.RARITY_ORDER.indexOf(it.rarity).let { idx -> if (idx < 0) Int.MAX_VALUE else idx } },
                    { it.displayName.lowercase() },
                ),
            )
    }

    val shopOptions = remember(options) {
        options.flatMap { it.shops }.distinct().sorted()
    }
    val tierOptions = remember(options) {
        val present = options.map { it.rarity }.filter { it.isNotBlank() }.toSet()
        MgApi.RARITY_ORDER.filter { it in present }
    }

    val normalizedQuery = searchQuery.trim().lowercase()
    val visibleOptions = remember(options, normalizedQuery, selectedShops, selectedTiers) {
        options.filter { option ->
            val matchesSearch = normalizedQuery.isBlank() ||
                option.displayName.lowercase().contains(normalizedQuery) ||
                option.species.lowercase().contains(normalizedQuery)
            val matchesShop = selectedShops.isEmpty() || option.shops.any { it in selectedShops }
            val matchesTier = selectedTiers.isEmpty() || option.rarity in selectedTiers
            matchesSearch && matchesShop && matchesTier
        }
    }

    val availableStock = remember(shops, selectedSpecies) {
        shops.sumOf { shop ->
            selectedSpecies.sumOf { species ->
                (shop.itemStocks[species] ?: 0).coerceAtLeast(0)
            }
        }
    }
    val ownedSeeds = remember(seeds, seedSilo, selectedSpecies) {
        (seeds + seedSilo)
            .filter { it.species in selectedSpecies }
            .sumOf { it.quantity.coerceAtLeast(0) }
    }
    val activeFilterCount = selectedShops.size + selectedTiers.size

    // Re-start a persisted Fast Money setup when this screen is reconstructed after process death.
    LaunchedEffect(enabled, selectedSpecies) {
        if (enabled && selectedSpecies.isNotEmpty()) {
            onFastMoneyChanged(
                true,
                selectedSpecies,
                selectedShops,
                selectedTiers,
                searchQuery,
            )
        }
    }

    AppCard(
        title = "GOD — Fast Money",
        persistKey = "god_fast_money",
        collapsible = true,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Accent.copy(alpha = 0.08f), RoundedCornerShape(12.dp))
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(
                imageVector = Icons.Outlined.Bolt,
                contentDescription = null,
                tint = Accent,
                modifier = Modifier.size(22.dp),
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "BUY → PLANT → HARVEST → LOG → SELL",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = TextPrimary,
                )
                Text(
                    "${selectedSpecies.size} selected • $availableStock in stock • $ownedSeeds owned • $freePlantTiles free tiles",
                    fontSize = 10.sp,
                    color = TextSecondary,
                )
            }
            Switch(
                checked = enabled,
                enabled = selectedSpecies.isNotEmpty(),
                onCheckedChange = { nextEnabled ->
                    onFastMoneyChanged(
                        nextEnabled,
                        selectedSpecies,
                        selectedShops,
                        selectedTiers,
                        searchQuery,
                    )
                },
            )
        }

        Spacer(modifier = Modifier.height(10.dp))
        Text(
            "Select any known plant, including plants that are not currently in stock. Fast Money buys selected plants whenever they appear in any eligible shop, plants the purchased excess in batches, harvests its own mature plots, logs the harvested batch, then sells only that batch.",
            fontSize = 10.sp,
            color = TextMuted,
        )

        Spacer(modifier = Modifier.height(10.dp))
        SearchFilterBar(
            query = searchQuery,
            onQueryChange = { nextQuery ->
                onFastMoneyChanged(
                    enabled,
                    selectedSpecies,
                    selectedShops,
                    selectedTiers,
                    nextQuery,
                )
            },
            placeholder = "Search plants…",
            activeFilterCount = activeFilterCount,
            filtersExpanded = filtersExpanded,
            onFiltersExpandedChange = { filtersExpanded = it },
            onClearFilters = {
                onFastMoneyChanged(
                    enabled,
                    selectedSpecies,
                    emptySet(),
                    emptySet(),
                    searchQuery,
                )
            },
        ) {
            Text("Shops", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                shopOptions.forEach { shop ->
                    FilterChip(
                        selected = shop in selectedShops,
                        onClick = {
                            val next = if (shop in selectedShops) selectedShops - shop else selectedShops + shop
                            onFastMoneyChanged(enabled, selectedSpecies, next, selectedTiers, searchQuery)
                        },
                        label = {
                            Text(
                                shop.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() },
                                fontSize = 10.sp,
                            )
                        },
                    )
                }
            }

            Text("Tier / rarity", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                tierOptions.forEach { tier ->
                    FilterChip(
                        selected = tier in selectedTiers,
                        onClick = {
                            val next = if (tier in selectedTiers) selectedTiers - tier else selectedTiers + tier
                            onFastMoneyChanged(enabled, selectedSpecies, selectedShops, next, searchQuery)
                        },
                        label = { Text(tier, fontSize = 10.sp) },
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OutlinedButton(
                modifier = Modifier.weight(1f),
                enabled = visibleOptions.isNotEmpty(),
                onClick = {
                    val nextSelection = selectedSpecies + visibleOptions.map { it.species }
                    onFastMoneyChanged(
                        enabled,
                        nextSelection,
                        selectedShops,
                        selectedTiers,
                        searchQuery,
                    )
                },
            ) {
                Text("Select visible", fontSize = 10.sp)
            }
            OutlinedButton(
                modifier = Modifier.weight(1f),
                enabled = selectedSpecies.isNotEmpty(),
                onClick = {
                    onFastMoneyChanged(
                        false,
                        emptySet(),
                        selectedShops,
                        selectedTiers,
                        searchQuery,
                    )
                },
            ) {
                Text("Clear", fontSize = 10.sp)
            }
        }

        Spacer(modifier = Modifier.height(8.dp))
        if (visibleOptions.isEmpty()) {
            Text("No plants match the current search and filters.", fontSize = 10.sp, color = TextMuted)
        } else {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                visibleOptions.forEach { option ->
                    val stock = shops.sumOf { (it.itemStocks[option.species] ?: 0).coerceAtLeast(0) }
                    FilterChip(
                        selected = option.species in selectedSpecies,
                        onClick = {
                            val nextSelection = if (option.species in selectedSpecies) {
                                selectedSpecies - option.species
                            } else {
                                selectedSpecies + option.species
                            }
                            onFastMoneyChanged(
                                enabled && nextSelection.isNotEmpty(),
                                nextSelection,
                                selectedShops,
                                selectedTiers,
                                searchQuery,
                            )
                        },
                        label = {
                            val suffix = buildString {
                                if (option.rarity.isNotBlank()) append(" • ${option.rarity}")
                                if (stock > 0) append(" • $stock")
                            }
                            Text("${option.displayName}$suffix", fontSize = 10.sp)
                        },
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(6.dp))
        Text(
            "Selections, filters, search text, and the ON/OFF state are saved per account. Closing and reopening the app keeps this setup.",
            fontSize = 9.sp,
            color = TextMuted,
        )

        if (enabled && selectedSpecies.isNotEmpty()) {
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                "FAST MONEY RUNNING",
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                color = StatusConnected,
            )
        }
    }
}

'''

regex_once(
    god,
    r'''@OptIn\(ExperimentalLayoutApi::class\)\n@Composable\nprivate fun GodFastMoneyCard\(.*?\n\}\n\n(?=private fun godShopSelectionKey)''',
    fast_money_ui,
)

# ---------------------------------------------------------------------------
# Main screen: feed persistent Fast Money setup into GOD.
# ---------------------------------------------------------------------------
main = "app/src/main/java/com/mgafk/app/ui/screens/MainScreen.kt"
replace_once(
    main,
    '''                onFastMoneyChanged = { enabled, selectedSpecies ->
                    viewModel.setGodFastMoney(session.id, enabled, selectedSpecies)
                },''',
    '''                fastMoneyEnabled = session.godFastMoneyEnabled,
                fastMoneySelectedSpecies = session.godFastMoneySelectedSpecies,
                fastMoneyShopFilters = session.godFastMoneyShopFilters,
                fastMoneyTierFilters = session.godFastMoneyTierFilters,
                fastMoneySearchQuery = session.godFastMoneySearchQuery,
                onFastMoneyChanged = { enabled, selectedSpecies, selectedShops, selectedTiers, searchQuery ->
                    viewModel.setGodFastMoney(
                        session.id,
                        enabled,
                        selectedSpecies,
                        selectedShops,
                        selectedTiers,
                        searchQuery,
                    )
                },''',
)

# ---------------------------------------------------------------------------
# MainViewModel: persist Fast Money, batch its pipeline, log before selling.
# ---------------------------------------------------------------------------
vm = "app/src/main/java/com/mgafk/app/ui/MainViewModel.kt"

replace_once(
    vm,
    '''    private val godFastMoneyPendingSiloRetrieveUntil = mutableMapOf<String, MutableMap<String, Long>>()
''',
    '''    private val godFastMoneyPendingSiloRetrieveUntil = mutableMapOf<String, MutableMap<String, Long>>()
    private val godFastMoneyPlantBatchPendingUntil = mutableMapOf<String, Long>()
''',
)

replace_after(
    vm,
    "fun removeSession(id: String)",
    '''        godFastMoneyPendingSiloRetrieveUntil.remove(id)
''',
    '''        godFastMoneyPendingSiloRetrieveUntil.remove(id)
        godFastMoneyPlantBatchPendingUntil.remove(id)
''',
)

replace_once(
    vm,
    '''    private suspend fun harvestAndSellGodPlants(
        sessionId: String,
        candidateKeys: Set<Pair<Int, Int>>,
        canHarvest: (GardenPlantSnapshot) -> Boolean,
    ): List<GardenPlantSnapshot> {''',
    '''    private suspend fun harvestAndSellGodPlants(
        sessionId: String,
        candidateKeys: Set<Pair<Int, Int>>,
        logBeforeSell: Boolean = false,
        canHarvest: (GardenPlantSnapshot) -> Boolean,
    ): List<GardenPlantSnapshot> {''',
)

replace_after(
    vm,
    "private suspend fun harvestAndSellGodPlants(",
    '''            val outputs = awaitGodHarvestOutputs(sessionId, beforeIds, targets)
            if (outputs.isNotEmpty()) {
                sellOnlyGodProduce(sessionId, outputs.map { it.id }.toSet())
            }''',
    '''            val outputs = awaitGodHarvestOutputs(sessionId, beforeIds, targets)
            if (outputs.isNotEmpty()) {
                if (logBeforeSell) {
                    // One real Garden Journal command for the complete harvested batch.
                    // Keep the batch in inventory briefly so the server can stamp it before sale.
                    actions.logItems()
                    delay(220)
                }
                sellOnlyGodProduce(sessionId, outputs.map { it.id }.toSet())
            }''',
)

fast_money_runtime = r'''    fun setGodFastMoney(
        sessionId: String,
        enabled: Boolean,
        selectedSpecies: Set<String>,
        selectedShops: Set<String> = emptySet(),
        selectedTiers: Set<String> = emptySet(),
        searchQuery: String = "",
    ) {
        val cleanedSelection = selectedSpecies.filter { it.isNotBlank() }.toSet()
        val cleanedShops = selectedShops.map { it.trim().lowercase() }.filter { it.isNotBlank() }.toSet()
        val cleanedTiers = selectedTiers.filter { it.isNotBlank() }.toSet()
        val shouldEnable = enabled && cleanedSelection.isNotEmpty()

        // UI setup is session data, not transient Compose state. This survives process death.
        updateSession(sessionId) {
            it.copy(
                godFastMoneyEnabled = shouldEnable,
                godFastMoneySelectedSpecies = cleanedSelection,
                godFastMoneyShopFilters = cleanedShops,
                godFastMoneyTierFilters = cleanedTiers,
                godFastMoneySearchQuery = searchQuery,
            )
        }

        if (!shouldEnable) {
            godFastMoneyConfigs.remove(sessionId)
            godFastMoneyJobs.remove(sessionId)?.cancel()
            godFastMoneyPendingPlants.remove(sessionId)
            godFastMoneyTrackedTiles.remove(sessionId)
            godFastMoneyPendingSiloRetrieveUntil.remove(sessionId)
            godFastMoneyPlantBatchPendingUntil.remove(sessionId)
            return
        }

        val session = _state.value.sessions.find { it.id == sessionId } ?: return
        val totals = seedTotals(session)
        val previous = godFastMoneyConfigs[sessionId]
        val baseline = cleanedSelection.associateWith { species ->
            if (previous != null && species in previous.selectedSpecies) {
                previous.baselineSeedTotals[species] ?: (totals[species] ?: 0)
            } else {
                totals[species] ?: 0
            }
        }

        godFastMoneyConfigs[sessionId] = GodFastMoneyConfig(
            selectedSpecies = cleanedSelection,
            baselineSeedTotals = baseline,
        )
        godFastMoneyTrackedTiles[sessionId]?.entries?.removeAll { it.value !in cleanedSelection }
        godFastMoneyPendingSiloRetrieveUntil[sessionId]?.keys?.removeAll { it !in cleanedSelection }

        if (godFastMoneyJobs[sessionId]?.isActive == true) return
        godFastMoneyJobs[sessionId] = viewModelScope.launch {
            while (true) {
                val config = godFastMoneyConfigs[sessionId] ?: break
                runGodFastMoneyStep(sessionId, config)
                delay(450)
            }
        }
    }

    private suspend fun runGodFastMoneyStep(sessionId: String, config: GodFastMoneyConfig) {
        val client = clients[sessionId] ?: return
        var session = _state.value.sessions.find { it.id == sessionId } ?: return
        if (!session.connected) return

        var now = System.currentTimeMillis()
        val tracked = godFastMoneyTrackedTiles.getOrPut(sessionId) { mutableMapOf() }
        val plantBatchSettling = now < (godFastMoneyPlantBatchPendingUntil[sessionId] ?: 0L)
        if (!plantBatchSettling) {
            godFastMoneyPlantBatchPendingUntil.remove(sessionId)
            // Once the batch has had time to patch in, keep ownership only for plants that
            // are genuinely still on those tiles.
            tracked.entries.removeAll { (tileId, species) ->
                species !in config.selectedSpecies ||
                    session.garden.none { it.tileId == tileId && it.species == species }
            }
        }

        // Harvest every mature plot owned by Fast Money in one serialized batch.
        val trackedSnapshot = tracked.toMap()
        val candidateKeys = session.garden
            .asSequence()
            .filter { plant -> trackedSnapshot[plant.tileId] == plant.species }
            .map { it.tileId to it.slotIndex }
            .toSet()
        if (candidateKeys.isNotEmpty()) {
            harvestAndSellGodPlants(
                sessionId = sessionId,
                candidateKeys = candidateKeys,
                logBeforeSell = true,
            ) { plant ->
                trackedSnapshot[plant.tileId] == plant.species
            }
            session = _state.value.sessions.find { it.id == sessionId } ?: return
        }

        // Buy selected plants from every shop that currently exposes them. Each shop-item
        // purchase is itself a full-stock burst; the short gap only separates item bursts.
        for (shop in session.shops) {
            for (species in config.selectedSpecies) {
                val stock = (shop.itemStocks[species] ?: 0).coerceAtLeast(0)
                val appearsHere = species in shop.itemNames || species in shop.itemStocks.keys
                if (stock > 0 && appearsHere && MgApi.getPlants().containsKey(species)) {
                    purchaseAllShopItem(sessionId, shop.type, species)
                    delay(20)
                }
            }
        }

        session = _state.value.sessions.find { it.id == sessionId } ?: return
        now = System.currentTimeMillis()

        // Never reuse the same stale empty-tile snapshot while a plant batch is patching in.
        if (now < (godFastMoneyPlantBatchPendingUntil[sessionId] ?: 0L)) return

        val totals = seedTotals(session)
        val excessBySpecies = config.selectedSpecies.associateWith { species ->
            ((totals[species] ?: 0) - (config.baselineSeedTotals[species] ?: 0)).coerceAtLeast(0)
        }.filterValues { it > 0 }
        if (excessBySpecies.isEmpty()) return

        // Auto-stock can move new purchases into the Seed Silo. Request all missing excess
        // stacks in one retrieval pass, while still planting any excess already in inventory.
        val retrievalPending = godFastMoneyPendingSiloRetrieveUntil
            .getOrPut(sessionId) { mutableMapOf() }
        retrievalPending.entries.removeAll { it.value <= now }

        for ((species, excess) in excessBySpecies) {
            val inventoryQty = session.inventory.seeds
                .find { it.species == species }
                ?.quantity
                ?.coerceAtLeast(0)
                ?: 0
            val siloQty = session.seedSilo
                .find { it.species == species }
                ?.quantity
                ?.coerceAtLeast(0)
                ?: 0
            if (inventoryQty < excess && siloQty > 0 && species !in retrievalPending) {
                retrievalPending[species] = now + 5000L
                moveSeedFromSilo(sessionId, species)
                delay(20)
            }
        }

        val occupied = occupiedPlantTiles(client) ?: return
        val freeSlots = (0 until GardenTiles.DIRT_TILES_PER_GARDEN)
            .filter { it !in occupied }
            .toMutableList()
        if (freeSlots.isEmpty()) return

        data class PlantPlan(val tileId: Int, val species: String)
        val plans = mutableListOf<PlantPlan>()
        var nextFreeIndex = 0

        val orderedSpecies = excessBySpecies.keys.sortedWith(
            compareBy<String>(
                { MgApi.findItem(it)?.rarityIndex ?: Int.MAX_VALUE },
                { MgApi.findItem(it)?.name?.lowercase() ?: it.lowercase() },
            ),
        )

        for (species in orderedSpecies) {
            if (nextFreeIndex >= freeSlots.size) break
            val excess = excessBySpecies[species] ?: continue
            val inventoryQty = session.inventory.seeds
                .find { it.species == species }
                ?.quantity
                ?.coerceAtLeast(0)
                ?: 0
            val amount = minOf(excess, inventoryQty, freeSlots.size - nextFreeIndex)
            repeat(amount) {
                plans += PlantPlan(freeSlots[nextFreeIndex++], species)
            }
        }
        if (plans.isEmpty()) return

        // Optimistically claim the planned tiles so the harvest loop knows exactly what it owns.
        // A settle window prevents a second batch from reusing those slots before patches arrive.
        plans.forEach { plan -> tracked[plan.tileId] = plan.species }
        plans.forEachIndexed { index, plan ->
            client.actions.plantSeed(slot = plan.tileId, species = plan.species)
            if (index < plans.lastIndex) delay(20)
        }
        godFastMoneyPlantBatchPendingUntil[sessionId] = System.currentTimeMillis() + 2200L
    }

'''

regex_once(
    vm,
    r'''    fun setGodFastMoney\(.*?\n    // ---- GOD Hoarder ----\n''',
    fast_money_runtime + "    // ---- GOD Hoarder ----\n",
)

# ---------------------------------------------------------------------------
# Egg automation: buy every available egg, batch-plant it, batch-hatch mature eggs.
# ---------------------------------------------------------------------------
egg_runtime = r'''    private val autoPlantEggJobs = mutableMapOf<String, Job>()
    private val autoEggPlantBatchPendingUntil = mutableMapOf<String, Long>()
    private val autoEggHatchPendingUntil = mutableMapOf<String, MutableMap<Int, Long>>()

    /**
     * Persistent egg automation. While enabled it:
     * 1) buys all currently available eggs from every shop,
     * 2) fills free dirt tiles with owned eggs in a fast batch,
     * 3) hatches every mature egg in a fast batch.
     */
    fun setAutoPlantEggs(sessionId: String, enabled: Boolean) {
        updateSession(sessionId) { it.copy(autoPlantEggs = enabled) }
        if (!enabled) {
            autoPlantEggJobs.remove(sessionId)?.cancel()
            autoEggPlantBatchPendingUntil.remove(sessionId)
            autoEggHatchPendingUntil.remove(sessionId)
            return
        }
        if (autoPlantEggJobs[sessionId]?.isActive == true) return

        autoPlantEggJobs[sessionId] = viewModelScope.launch {
            while (true) {
                var session = _state.value.sessions.find { it.id == sessionId } ?: break
                if (!session.autoPlantEggs) break
                if (!session.connected) {
                    delay(500)
                    continue
                }

                val client = clients[sessionId]
                if (client == null) {
                    delay(500)
                    continue
                }
                var now = System.currentTimeMillis()

                // Hatch all ready eggs, excluding only tiles already awaiting a server patch.
                val hatchPending = autoEggHatchPendingUntil.getOrPut(sessionId) { mutableMapOf() }
                hatchPending.entries.removeAll { it.value <= now }
                val liveEggTiles = session.gardenEggs.map { it.tileId }.toSet()
                hatchPending.keys.removeAll { it !in liveEggTiles }

                val matureEggs = session.gardenEggs
                    .filter { egg ->
                        egg.maturedAt > 0L &&
                            now >= egg.maturedAt &&
                            egg.tileId !in hatchPending
                    }
                    .sortedBy { it.tileId }

                if (matureEggs.isNotEmpty()) {
                    matureEggs.forEachIndexed { index, egg ->
                        hatchPending[egg.tileId] = now + 5000L
                        client.actions.hatchEgg(slot = egg.tileId)
                        if (index < matureEggs.lastIndex) delay(20)
                    }
                }

                // Buy full stock of every known egg wherever it appears.
                for (shop in session.shops) {
                    val eggIds = (shop.itemNames + shop.itemStocks.keys)
                        .distinct()
                        .filter { MgApi.getEggs().containsKey(it) }
                    for (eggId in eggIds) {
                        if ((shop.itemStocks[eggId] ?: 0) > 0) {
                            purchaseAllShopItem(sessionId, shop.type, eggId)
                            delay(20)
                        }
                    }
                }

                session = _state.value.sessions.find { it.id == sessionId } ?: break
                now = System.currentTimeMillis()

                // Do not reuse stale free tiles while the previous grow batch is patching in.
                if (now < (autoEggPlantBatchPendingUntil[sessionId] ?: 0L)) {
                    delay(450)
                    continue
                }
                autoEggPlantBatchPendingUntil.remove(sessionId)

                val occupied = occupiedPlantTiles(client)
                if (occupied == null) {
                    delay(450)
                    continue
                }
                val freeSlots = (0 until GardenTiles.DIRT_TILES_PER_GARDEN)
                    .filter { it !in occupied }
                if (freeSlots.isEmpty()) {
                    delay(450)
                    continue
                }

                data class EggPlan(val tileId: Int, val eggId: String)
                val plans = mutableListOf<EggPlan>()
                var freeIndex = 0
                val eggStacks = session.inventory.eggs
                    .filter { it.quantity > 0 }
                    .sortedWith(
                        compareBy<InventoryEggItem>(
                            { MgApi.findItem(it.eggId)?.rarityIndex ?: Int.MAX_VALUE },
                            { MgApi.findItem(it.eggId)?.name?.lowercase() ?: it.eggId.lowercase() },
                        ),
                    )

                for (stack in eggStacks) {
                    if (freeIndex >= freeSlots.size) break
                    val amount = minOf(stack.quantity, freeSlots.size - freeIndex)
                    repeat(amount) {
                        plans += EggPlan(freeSlots[freeIndex++], stack.eggId)
                    }
                }

                if (plans.isNotEmpty()) {
                    plans.forEachIndexed { index, plan ->
                        client.actions.growEgg(slot = plan.tileId, eggId = plan.eggId)
                        if (index < plans.lastIndex) delay(20)
                    }
                    autoEggPlantBatchPendingUntil[sessionId] = System.currentTimeMillis() + 2200L
                }

                delay(450)
            }
            autoPlantEggJobs.remove(sessionId)
        }
    }

    private val pendingGrowEggJobs = mutableMapOf<String, Job>()
'''

regex_once(
    vm,
    r'''    private val autoPlantEggJobs = mutableMapOf<String, Job>\(\).*?    private val pendingGrowEggJobs = mutableMapOf<String, Job>\(\)\n''',
    egg_runtime,
)

replace_after(
    vm,
    "fun removeSession(id: String)",
    '''        autoPlantEggJobs.remove(id)?.cancel()
''',
    '''        autoPlantEggJobs.remove(id)?.cancel()
        autoEggPlantBatchPendingUntil.remove(id)
        autoEggHatchPendingUntil.remove(id)
''',
)

# Restart persisted automations when the ViewModel is recreated.
replace_once(
    vm,
    '''                settings = settings,
            )
            // Collect service logs''',
    '''                settings = settings,
            )
            migratedSessions.filter { it.autoPlantEggs }.forEach { saved ->
                setAutoPlantEggs(saved.id, true)
            }
            migratedSessions
                .filter { it.godFastMoneyEnabled && it.godFastMoneySelectedSpecies.isNotEmpty() }
                .forEach { saved ->
                    setGodFastMoney(
                        saved.id,
                        true,
                        saved.godFastMoneySelectedSpecies,
                        saved.godFastMoneyShopFilters,
                        saved.godFastMoneyTierFilters,
                        saved.godFastMoneySearchQuery,
                    )
                }
            // Collect service logs''',
)

# Make the storage toggle describe the expanded egg automation.
inv = "app/src/main/java/com/mgafk/app/ui/screens/storage/InventoryCard.kt"
replace_once(
    inv,
    '''if (autoPlantEggs) "Auto Plant Eggs: ON" else "Auto Plant Eggs: OFF"''',
    '''if (autoPlantEggs) "Auto Eggs (Buy • Plant • Hatch): ON" else "Auto Eggs (Buy • Plant • Hatch): OFF"''',
)

print("Applied Fast Money batch + persistence + egg automation changes")
