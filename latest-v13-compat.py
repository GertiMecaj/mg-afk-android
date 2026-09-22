#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 occurrence, found {count}")
    p.write_text(text.replace(old, new, 1))


# GOD crop filters: v2.4.23 GardenPlantSnapshot already exposes whole crop size 50..100.
god = "app/src/main/java/com/mgafk/app/ui/god/GodAutomation.kt"
replace_once(
    god,
    '''fun godCropSizePercent(plant: GardenPlantSnapshot): Double {
    val maxScale = MgApi.getPlants()[plant.species]?.maxScale ?: 1.0
    val targetScale = plant.targetScale
    val percent = if (maxScale <= 1.0) {
        if (targetScale >= 1.0) 100.0 else targetScale * 100.0
    } else if (targetScale <= 1.0) {
        targetScale * 50.0
    } else {
        50.0 + (targetScale - 1.0) / (maxScale - 1.0) * 50.0
    }
    return percent.coerceIn(0.0, 100.0)
}''',
    '''fun godCropSizePercent(plant: GardenPlantSnapshot): Double =
    plant.size.toDouble().coerceIn(0.0, 100.0)''',
    "GOD crop size filter",
)

# Generated GOD automation still refers to the pre-V30 crop scale fields.
vm = "app/src/main/java/com/mgafk/app/ui/MainViewModel.kt"
replace_once(
    vm,
    "            abs(plant.targetScale - produce.scale) <= 0.01",
    "            plant.size == produce.size",
    "exact harvest output size match",
)
replace_once(vm, "                    food.scale,", "                    food.size,", "inventory food size")
replace_once(vm, "                    { it.first.scale },", "                    { it.first.size },", "inventory food size sort")
replace_once(vm, "                    crop.targetScale,", "                    crop.size,", "garden food size")
replace_once(vm, "                    { it.first.targetScale },", "                    { it.first.size },", "garden food size sort")

# QoL storage valuation: calculateCropSellPrice now accepts integer size, not scale.
storage = "app/src/main/java/com/mgafk/app/ui/screens/storage/StorageCards.kt"
replace_once(
    storage,
    "remember(item.species, item.scale, item.mutations, apiReady)",
    "remember(item.species, item.size, item.mutations, apiReady)",
    "storage crop remember size",
)
replace_once(
    storage,
    "PriceCalculator.calculateCropSellPrice(item.species, item.scale, item.mutations)",
    "PriceCalculator.calculateCropSellPrice(item.species, item.size, item.mutations)",
    "storage crop valuation size",
)

print("Applied v2.4.23 crop-size compatibility to generated GOD/QoL code")
