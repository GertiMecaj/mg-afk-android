#!/usr/bin/env python3
from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def write(path: str, text: str) -> None:
    Path(path).write_text(text)


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly 1 occurrence, found {count}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


def replace_many(path: str, old: str, new: str, expected: int) -> None:
    text = read(path)
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} occurrences, found {count}: {old[:100]!r}")
    write(path, text.replace(old, new))


def replace_after(path: str, anchor: str, old: str, new: str) -> None:
    text = read(path)
    pos = text.find(anchor)
    if pos < 0:
        raise SystemExit(f"{path}: anchor not found: {anchor!r}")
    before, tail = text[:pos], text[pos:]
    count = tail.count(old)
    if count < 1:
        raise SystemExit(f"{path}: target not found after anchor {anchor!r}: {old[:100]!r}")
    tail = tail.replace(old, new, 1)
    write(path, before + tail)


# ---------------------------------------------------------------------------
# Catalog prices: retain the live catalog's coin / credit prices for every item.
# ---------------------------------------------------------------------------
mgapi = "app/src/main/java/com/mgafk/app/data/repository/MgApi.kt"
replace_once(
    mgapi,
    "        val baseSellPrice: Double? = null,\n        val hoursToMature: Double? = null,",
    "        val baseSellPrice: Double? = null,\n        val coinPrice: Double? = null,\n        val creditPrice: Double? = null,\n        val hoursToMature: Double? = null,",
)
replace_once(
    mgapi,
    "                    rarity = seedObj?.get(\"rarity\")?.jsonPrimitive?.contentOrNull,\n                    cropSprite = cropObj?.get(\"sprite\")?.jsonPrimitive?.contentOrNull,",
    "                    rarity = seedObj?.get(\"rarity\")?.jsonPrimitive?.contentOrNull,\n                    coinPrice = seedObj?.get(\"coinPrice\")?.jsonPrimitive?.doubleOrNull,\n                    creditPrice = seedObj?.get(\"creditPrice\")?.jsonPrimitive?.doubleOrNull,\n                    cropSprite = cropObj?.get(\"sprite\")?.jsonPrimitive?.contentOrNull,",
)
replace_once(
    mgapi,
    "                    rarity = obj?.get(\"rarity\")?.jsonPrimitive?.contentOrNull,\n                    maxScale = obj?.get(\"maxScale\")?.jsonPrimitive?.doubleOrNull,",
    "                    rarity = obj?.get(\"rarity\")?.jsonPrimitive?.contentOrNull,\n                    coinPrice = obj?.get(\"coinPrice\")?.jsonPrimitive?.doubleOrNull,\n                    creditPrice = obj?.get(\"creditPrice\")?.jsonPrimitive?.doubleOrNull,\n                    maxScale = obj?.get(\"maxScale\")?.jsonPrimitive?.doubleOrNull,",
)

# ---------------------------------------------------------------------------
# Persist the egg auto-planter toggle per session.
# ---------------------------------------------------------------------------
session_file = "app/src/main/java/com/mgafk/app/data/model/Session.kt"
replace_once(
    session_file,
    "    val weather: String = \"\",\n    val pets: List<PetSnapshot> = emptyList(),",
    "    val weather: String = \"\",\n    val autoPlantEggs: Boolean = false,\n    val pets: List<PetSnapshot> = emptyList(),",
)

# ---------------------------------------------------------------------------
# Dashboard: Coins + Magic Dust + Bread balance + a clearly-labelled weather report.
# ---------------------------------------------------------------------------
live = "app/src/main/java/com/mgafk/app/ui/screens/status/LiveStatusCard.kt"
replace_once(
    live,
    "import com.mgafk.app.data.repository.MgApi\n",
    "import com.mgafk.app.data.repository.MgApi\nimport com.mgafk.app.data.repository.PriceCalculator\n",
)
replace_once(
    live,
    "import kotlinx.coroutines.delay\n",
    "import kotlinx.coroutines.delay\nimport kotlin.math.roundToLong\n",
)
replace_once(
    live,
    "fun LiveStatusCard(session: Session, modifier: Modifier = Modifier) {\n    AppCard(modifier = modifier, title = \"Live Status\", collapsible = true, persistKey = \"dashboard.liveStatus\") {\n        StatusRow(\"Players\", \"${session.players}\")\n        UptimeRow(session.connectedAt)\n        StatusRow(\"Player\", session.playerName.ifBlank { \"-\" })\n        StatusRow(\"Room ID\", session.roomId.ifBlank { \"-\" })\n        WeatherRow(session.weather)\n        StatusRow(\"Player ID\", session.playerId.ifBlank { \"-\" })\n    }\n}",
    "fun LiveStatusCard(session: Session, currencyBalance: Long? = null, modifier: Modifier = Modifier) {\n    val ownCoins = session.playersList.firstOrNull { it.id == session.playerId }?.coins ?: 0.0\n    AppCard(modifier = modifier, title = \"Live Status\", collapsible = true, persistKey = \"dashboard.liveStatus\") {\n        StatusRow(\"Players\", \"${session.players}\")\n        UptimeRow(session.connectedAt)\n        StatusRow(\"Player\", session.playerName.ifBlank { \"-\" })\n        StatusRow(\"Room ID\", session.roomId.ifBlank { \"-\" })\n        StatusRow(\"Coins\", PriceCalculator.formatFull(ownCoins.roundToLong()))\n        StatusRow(\"Magic Dust\", PriceCalculator.formatFull(session.magicDust.roundToLong()))\n        StatusRow(\"Breads\", currencyBalance?.let(PriceCalculator::formatFull) ?: \"-\")\n        WeatherRow(session.weather)\n        StatusRow(\"Player ID\", session.playerId.ifBlank { \"-\" })\n    }\n}",
)
replace_once(live, '            text = "Weather",', '            text = "Weather Report",')

# ---------------------------------------------------------------------------
# Storage inventory: keep every category window visible even when empty,
# expose catalog prices, pet values, and the Auto Plant Eggs toggle.
# ---------------------------------------------------------------------------
inv = "app/src/main/java/com/mgafk/app/ui/screens/storage/InventoryCard.kt"
replace_once(
    inv,
    "    onGrowEgg: (eggId: String) -> Unit = {},\n    onPlantGardenPlant: (itemId: String) -> Unit = {},",
    "    onGrowEgg: (eggId: String) -> Unit = {},\n    autoPlantEggs: Boolean = false,\n    onAutoPlantEggsChanged: (Boolean) -> Unit = {},\n    onPlantGardenPlant: (itemId: String) -> Unit = {},",
)
# Always run the section-rendering branch, including on a completely empty inventory.
replace_once(inv, "        if (totalItems == 0) {", "        if (false && totalItems == 0) {")
for expr in [
    "filteredSeeds.isNotEmpty()",
    "filteredTools.isNotEmpty()",
    "filteredEggs.isNotEmpty()",
    "filteredPlants.isNotEmpty()",
    "filteredProduce.isNotEmpty()",
    "filteredDecors.isNotEmpty()",
    "filteredPets.isNotEmpty()",
]:
    replace_once(inv, f"if ({expr})", "if (true)")

# Auto-plant control lives in the persistent Eggs window.
replace_once(
    inv,
    "                    }\n                }\n                if (true) {\n                    val totalPlantsValue",
    "                    }\n                    Spacer(modifier = Modifier.height(8.dp))\n                    Button(\n                        onClick = { onAutoPlantEggsChanged(!autoPlantEggs) },\n                        modifier = Modifier.fillMaxWidth(),\n                        colors = ButtonDefaults.buttonColors(\n                            containerColor = if (autoPlantEggs) StatusConnected else SurfaceDark,\n                        ),\n                        shape = RoundedCornerShape(10.dp),\n                    ) {\n                        Text(\n                            if (autoPlantEggs) \"Auto Plant Eggs: ON\" else \"Auto Plant Eggs: OFF\",\n                            fontSize = 11.sp,\n                            fontWeight = FontWeight.Bold,\n                            color = if (autoPlantEggs) Color.White else TextSecondary,\n                        )\n                    }\n                }\n                if (true) {\n                    val totalPlantsValue",
)

# Catalog-value line for seeds / eggs / tools / decor.
replace_after(
    inv,
    "private fun QuantityTile(",
    "    val color = rarityColor(entry?.rarity)\n",
    "    val color = rarityColor(entry?.rarity)\n    val catalogPrice = entry?.coinPrice?.takeIf { it.isFinite() && it > 0.0 }?.toLong()\n    val creditPrice = entry?.creditPrice?.takeIf { it.isFinite() && it > 0.0 }?.toLong()\n",
)
replace_after(
    inv,
    "private fun QuantityTile(",
    "        Text(fmtQty(quantity), fontSize = 9.sp, fontWeight = FontWeight.Bold, color = Accent, lineHeight = 11.sp)\n",
    "        Text(fmtQty(quantity), fontSize = 9.sp, fontWeight = FontWeight.Bold, color = Accent, lineHeight = 11.sp)\n        when {\n            catalogPrice != null -> Text(PriceCalculator.formatPrice(catalogPrice), fontSize = 7.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD700), lineHeight = 9.sp)\n            creditPrice != null -> Text(\"${PriceCalculator.formatPrice(creditPrice)} credits\", fontSize = 7.sp, fontWeight = FontWeight.Bold, color = Accent, lineHeight = 9.sp)\n        }\n",
)

# Pet tiles now show their current sell value, just like produce and plants already do.
replace_after(
    inv,
    "private fun PetTile(pet: InventoryPetItem",
    "    val isMax = cs >= ms\n",
    "    val isMax = cs >= ms\n    val sellPrice = remember(pet.petSpecies, pet.xp, pet.targetScale, pet.mutations, apiReady) {\n        PriceCalculator.calculatePetSellPrice(pet.petSpecies, pet.xp, pet.targetScale, pet.mutations)\n    }\n",
)
replace_after(
    inv,
    "private fun PetTile(pet: InventoryPetItem",
    "            if (pet.abilities.isNotEmpty()) {\n",
    "            if (sellPrice != null) {\n                Text(PriceCalculator.formatPrice(sellPrice), fontSize = 7.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD700), lineHeight = 9.sp)\n            }\n            if (pet.abilities.isNotEmpty()) {\n",
)
replace_after(inv, "private fun PetTile(pet: InventoryPetItem", ".height(72.dp)", ".height(82.dp)")

# ---------------------------------------------------------------------------
# Storage-building tiles: show seed/tool/decor catalog values, produce values,
# and live pet values.
# ---------------------------------------------------------------------------
storage = "app/src/main/java/com/mgafk/app/ui/screens/storage/StorageCards.kt"
replace_after(
    storage,
    "private fun QtyTile(",
    "    val color = rarityColor(entry?.rarity)\n",
    "    val color = rarityColor(entry?.rarity)\n    val catalogPrice = entry?.coinPrice?.takeIf { it.isFinite() && it > 0.0 }?.toLong()\n    val creditPrice = entry?.creditPrice?.takeIf { it.isFinite() && it > 0.0 }?.toLong()\n",
)
replace_after(
    storage,
    "private fun QtyTile(",
    "        Text(fmtQty(quantity), fontSize = 9.sp, fontWeight = FontWeight.Bold, color = Accent, lineHeight = 11.sp)\n",
    "        Text(fmtQty(quantity), fontSize = 9.sp, fontWeight = FontWeight.Bold, color = Accent, lineHeight = 11.sp)\n        when {\n            catalogPrice != null -> Text(PriceCalculator.formatPrice(catalogPrice), fontSize = 7.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD700), lineHeight = 9.sp)\n            creditPrice != null -> Text(\"${PriceCalculator.formatPrice(creditPrice)} credits\", fontSize = 7.sp, fontWeight = FontWeight.Bold, color = Accent, lineHeight = 9.sp)\n        }\n",
)
replace_after(
    storage,
    "private fun CropTile(",
    "    val color = rarityColor(entry?.rarity)\n",
    "    val color = rarityColor(entry?.rarity)\n    val sellPrice = remember(item.species, item.scale, item.mutations, apiReady) {\n        PriceCalculator.calculateCropSellPrice(item.species, item.scale, item.mutations)\n    }\n",
)
replace_after(
    storage,
    "private fun CropTile(",
    "        if (item.mutations.isNotEmpty()) {\n",
    "        if (sellPrice != null) {\n            Text(PriceCalculator.formatPrice(sellPrice), fontSize = 8.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD700), lineHeight = 10.sp)\n        }\n        if (item.mutations.isNotEmpty()) {\n",
)
replace_after(
    storage,
    "private fun PetTile(pet: InventoryPetItem",
    "    val isMax = cs >= ms\n",
    "    val isMax = cs >= ms\n    val sellPrice = remember(pet.petSpecies, pet.xp, pet.targetScale, pet.mutations, apiReady) {\n        PriceCalculator.calculatePetSellPrice(pet.petSpecies, pet.xp, pet.targetScale, pet.mutations)\n    }\n",
)
replace_after(
    storage,
    "private fun PetTile(pet: InventoryPetItem",
    "            if (pet.abilities.isNotEmpty()) {\n",
    "            if (sellPrice != null) {\n                Text(PriceCalculator.formatPrice(sellPrice), fontSize = 7.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD700), lineHeight = 9.sp)\n            }\n            if (pet.abilities.isNotEmpty()) {\n",
)
replace_after(storage, "private fun PetTile(pet: InventoryPetItem", ".height(72.dp)", ".height(82.dp)")

# ---------------------------------------------------------------------------
# Shops: show the catalog purchase price on every visible shop item.
# ---------------------------------------------------------------------------
shops_file = "app/src/main/java/com/mgafk/app/ui/screens/shops/ShopsCard.kt"
replace_once(
    shops_file,
    "import com.mgafk.app.data.repository.MgApi\n",
    "import com.mgafk.app.data.repository.MgApi\nimport com.mgafk.app.data.repository.PriceCalculator\n",
)
replace_after(
    shops_file,
    "private fun ShopItemTile(",
    "    val color = rarityColor(rarity)\n",
    "    val color = rarityColor(rarity)\n    val catalogPrice = entry?.coinPrice?.takeIf { it.isFinite() && it > 0.0 }?.toLong()\n    val creditPrice = entry?.creditPrice?.takeIf { it.isFinite() && it > 0.0 }?.toLong()\n",
)
replace_after(
    shops_file,
    "private fun ShopItemTile(",
    "            Text(\n                text = displayName,\n                fontSize = 9.sp,\n                fontWeight = FontWeight.Medium,\n                color = if (dimmed) TextMuted else TextPrimary,\n                maxLines = 1,\n                overflow = TextOverflow.Ellipsis,\n                textAlign = TextAlign.Center,\n                lineHeight = 11.sp,\n            )\n",
    "            Text(\n                text = displayName,\n                fontSize = 9.sp,\n                fontWeight = FontWeight.Medium,\n                color = if (dimmed) TextMuted else TextPrimary,\n                maxLines = 1,\n                overflow = TextOverflow.Ellipsis,\n                textAlign = TextAlign.Center,\n                lineHeight = 11.sp,\n            )\n            when {\n                catalogPrice != null -> Text(PriceCalculator.formatPrice(catalogPrice), fontSize = 8.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD700), lineHeight = 9.sp)\n                creditPrice != null -> Text(\"${PriceCalculator.formatPrice(creditPrice)} credits\", fontSize = 7.sp, fontWeight = FontWeight.Bold, color = Accent, lineHeight = 9.sp)\n            }\n",
)
replace_after(shops_file, "private fun ShopItemTile(", "modifier = Modifier.size(76.dp),", "modifier = Modifier.size(84.dp),")

# ---------------------------------------------------------------------------
# MainViewModel: background egg auto-planter + safe manual collect-and-sell.
# ---------------------------------------------------------------------------
vm = "app/src/main/java/com/mgafk/app/ui/MainViewModel.kt"
replace_after(
    vm,
    "fun removeSession(id: String)",
    "        collectorJobs.remove(id)?.cancel()\n",
    "        collectorJobs.remove(id)?.cancel()\n        autoPlantEggJobs.remove(id)?.cancel()\n",
)
replace_once(
    vm,
    "    private val pendingGrowEggJobs = mutableMapOf<String, Job>()\n",
    "    private val autoPlantEggJobs = mutableMapOf<String, Job>()\n\n    /** Continuously plants eggs from inventory into available dirt tiles until disabled. */\n    fun setAutoPlantEggs(sessionId: String, enabled: Boolean) {\n        updateSession(sessionId) { it.copy(autoPlantEggs = enabled) }\n        if (!enabled) {\n            autoPlantEggJobs.remove(sessionId)?.cancel()\n            return\n        }\n        if (autoPlantEggJobs[sessionId]?.isActive == true) return\n        autoPlantEggJobs[sessionId] = viewModelScope.launch {\n            while (true) {\n                val session = _state.value.sessions.find { it.id == sessionId } ?: break\n                if (!session.autoPlantEggs) break\n                if (!session.connected || session.freePlantTiles <= 0) {\n                    delay(1200)\n                    continue\n                }\n                val egg = session.inventory.eggs\n                    .filter { it.quantity > 0 }\n                    .sortedBy { MgApi.findItem(it.eggId)?.rarityIndex ?: Int.MAX_VALUE }\n                    .firstOrNull()\n                if (egg == null) {\n                    delay(1200)\n                    continue\n                }\n                growEgg(sessionId, egg.eggId)\n                delay(650)\n            }\n            autoPlantEggJobs.remove(sessionId)\n        }\n    }\n\n    private val pendingGrowEggJobs = mutableMapOf<String, Job>()\n",
)
replace_once(
    vm,
    "    // ---- GOD automation ----\n",
    "    /** Harvest the selected GOD targets and sell only the produce created by that batch. */\n    fun harvestAndSellCrops(\n        sessionId: String,\n        targets: List<Pair<Int, Int>>,\n        blockRules: GodHarvestBlockRules = GodHarvestBlockRules(),\n    ) {\n        val keys = targets.distinct().toSet()\n        if (keys.isEmpty()) return\n        viewModelScope.launch {\n            harvestAndSellGodPlants(sessionId, keys) { plant ->\n                !isGodHarvestBlocked(plant, blockRules)\n            }\n        }\n    }\n\n    // ---- GOD automation ----\n",
)

# ---------------------------------------------------------------------------
# MainScreen wiring for dashboard, egg automation, and collect+sell.
# ---------------------------------------------------------------------------
main = "app/src/main/java/com/mgafk/app/ui/screens/MainScreen.kt"
replace_once(
    main,
    "            LiveStatusCard(session = session)\n",
    "            LaunchedEffect(session.id, session.connected) {\n                if (session.connected) viewModel.fetchCurrencyBalance(session.id)\n            }\n            LiveStatusCard(session = session, currencyBalance = state.currencyBalance)\n",
)
replace_once(
    main,
    "                onGrowEgg = { eggId -> viewModel.growEgg(session.id, eggId) },\n                onPlantGardenPlant = { itemId -> viewModel.plantGardenPlant(session.id, itemId) },",
    "                onGrowEgg = { eggId -> viewModel.growEgg(session.id, eggId) },\n                autoPlantEggs = session.autoPlantEggs,\n                onAutoPlantEggsChanged = { enabled -> viewModel.setAutoPlantEggs(session.id, enabled) },\n                onPlantGardenPlant = { itemId -> viewModel.plantGardenPlant(session.id, itemId) },",
)
replace_once(
    main,
    "                onCollect = { targets, blockRules ->\n                    viewModel.harvestCrops(session.id, targets, blockRules)\n                },\n                onAutoFeedChanged = { enabled, petIds, feedBelowPercent ->",
    "                onCollect = { targets, blockRules ->\n                    viewModel.harvestCrops(session.id, targets, blockRules)\n                },\n                onCollectAndSell = { targets, blockRules ->\n                    viewModel.harvestAndSellCrops(session.id, targets, blockRules)\n                },\n                onAutoFeedChanged = { enabled, petIds, feedBelowPercent ->",
)

# ---------------------------------------------------------------------------
# GOD UI: full-catalog Hoarder options + Collect & Sell Selected.
# ---------------------------------------------------------------------------
god = "app/src/main/java/com/mgafk/app/ui/screens/god/GodCard.kt"
replace_once(
    god,
    "    onCollect: (List<Pair<Int, Int>>, GodHarvestBlockRules) -> Unit = { _, _ -> },\n    onAutoFeedChanged:",
    "    onCollect: (List<Pair<Int, Int>>, GodHarvestBlockRules) -> Unit = { _, _ -> },\n    onCollectAndSell: (List<Pair<Int, Int>>, GodHarvestBlockRules) -> Unit = { _, _ -> },\n    onAutoFeedChanged:",
)
replace_once(
    god,
    "            onCollect = onCollect,\n        )\n        GodPetAutoFeedCard(",
    "            onCollect = onCollect,\n            onCollectAndSell = onCollectAndSell,\n        )\n        GodPetAutoFeedCard(",
)
replace_after(
    god,
    "private fun GodMassHarvestCard(",
    "    onCollect: (List<Pair<Int, Int>>, GodHarvestBlockRules) -> Unit,\n) {",
    "    onCollect: (List<Pair<Int, Int>>, GodHarvestBlockRules) -> Unit,\n    onCollectAndSell: (List<Pair<Int, Int>>, GodHarvestBlockRules) -> Unit,\n) {",
)
replace_after(
    god,
    "private fun GodMassHarvestCard(",
    "        if (selectedSpecies.isNotEmpty() && selectedTargets.isEmpty()) {",
    "        Spacer(modifier = Modifier.height(8.dp))\n        OutlinedButton(\n            onClick = {\n                val targets = selectedTargets\n                if (targets.isNotEmpty()) {\n                    onCollectAndSell(targets, blockRules)\n                    selectedSpecies = emptySet()\n                }\n            },\n            enabled = selectedTargets.isNotEmpty(),\n            modifier = Modifier.fillMaxWidth(),\n        ) {\n            Text(\n                if (selectedTargets.isEmpty()) \"COLLECT & SELL SELECTED\"\n                else \"COLLECT & SELL ${selectedTargets.size} SELECTED\",\n                fontWeight = FontWeight.Bold,\n                fontSize = 11.sp,\n            )\n        }\n\n        if (selectedSpecies.isNotEmpty() && selectedTargets.isEmpty()) {",
)

# Turn the Hoarder UI's shop snapshots into a union of live shop data + every
# item in the current catalog, using eligibleShops so future/event items stay selectable.
replace_once(
    god,
    "@OptIn(ExperimentalLayoutApi::class)\n@Composable\nprivate fun GodHoarderCard(",
    "private data class GodHoarderShopOption(\n    val type: String,\n    val itemNames: List<String>,\n    val itemStocks: Map<String, Int>,\n)\n\n@OptIn(ExperimentalLayoutApi::class)\n@Composable\nprivate fun GodHoarderCard(",
)
replace_once(
    god,
    "    val shopOptions = remember(shops) {\n        shops\n            .filter { it.type.isNotBlank() }\n            .sortedBy { it.type.lowercase() }\n    }\n    val allKeys = remember(shopOptions) {",
    "    val shopOptions = remember(shops) {\n        val liveByType = shops\n            .filter { it.type.isNotBlank() }\n            .associateBy { it.type.lowercase() }\n        val catalogByShop = linkedMapOf<String, MutableSet<String>>()\n\n        fun addCatalogItem(itemId: String, defaultShop: String, eligibleShops: List<String>) {\n            val targets = if (eligibleShops.isNotEmpty()) eligibleShops else listOf(defaultShop)\n            targets.forEach { rawShop ->\n                val shopType = rawShop.trim().lowercase()\n                if (shopType.isNotBlank()) catalogByShop.getOrPut(shopType) { linkedSetOf() }.add(itemId)\n            }\n        }\n\n        MgApi.getPlants().forEach { (id, entry) -> addCatalogItem(id, \"seed\", entry.eligibleShops) }\n        MgApi.getEggs().forEach { (id, entry) -> addCatalogItem(id, \"egg\", entry.eligibleShops) }\n        MgApi.getItems().forEach { (id, entry) -> addCatalogItem(id, \"tool\", entry.eligibleShops) }\n        MgApi.getDecors().forEach { (id, entry) -> addCatalogItem(id, \"decor\", entry.eligibleShops) }\n        shops.forEach { shop ->\n            val type = shop.type.lowercase()\n            shop.itemNames.forEach { catalogByShop.getOrPut(type) { linkedSetOf() }.add(it) }\n        }\n\n        (catalogByShop.keys + liveByType.keys)\n            .distinct()\n            .sorted()\n            .map { type ->\n                val live = liveByType[type]\n                GodHoarderShopOption(\n                    type = type,\n                    itemNames = catalogByShop[type].orEmpty()\n                        .distinct()\n                        .sortedBy { MgApi.findItem(it)?.name?.lowercase() ?: it.lowercase() },\n                    itemStocks = live?.itemStocks.orEmpty(),\n                )\n            }\n    }\n    val allKeys = remember(shopOptions) {",
)

print("Applied GOD QoL v9 changes successfully")
