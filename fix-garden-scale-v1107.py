#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 occurrence, found {count}")
    path.write_text(text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Magic Garden v1123 crop-size compatibility.
#
# Old model:
#   slot.targetScale = 1..crop.maxScale
#
# New model:
#   slot.size = 50..100
#   crop.maxSizeMultiplier replaces crop.maxScale
#   effective scale = 1 + (maxSizeMultiplier - 1) * (size - 50) / 50
#
# The rest of the Android app already works in terms of an effective scale, so
# normalize the new wire model back to that representation at the parser edge.
# This keeps old rooms/versions compatible while fixing v1123 garden, inventory,
# potted-plant and feeding-trough values.
# ---------------------------------------------------------------------------

mgapi = Path("app/src/main/java/com/mgafk/app/data/repository/MgApi.kt")
replace_once(
    mgapi,
    '                    maxScale = cropObj?.get("maxScale")?.jsonPrimitive?.doubleOrNull,\n',
    '                    maxScale = cropObj?.get("maxSizeMultiplier")?.jsonPrimitive?.doubleOrNull\n'
    '                        ?: cropObj?.get("maxScale")?.jsonPrimitive?.doubleOrNull,\n',
    "plant catalog maxSizeMultiplier",
)

vm = Path("app/src/main/java/com/mgafk/app/ui/MainViewModel.kt")
text = vm.read_text()

anchor = '''private fun WakeLockMode.toServiceMode(): Int = when (this) {
    WakeLockMode.OFF -> AfkService.MODE_OFF
    WakeLockMode.SMART -> AfkService.MODE_SMART
    WakeLockMode.ALWAYS -> AfkService.MODE_ALWAYS
}
'''
helper = '''private fun WakeLockMode.toServiceMode(): Int = when (this) {
    WakeLockMode.OFF -> AfkService.MODE_OFF
    WakeLockMode.SMART -> AfkService.MODE_SMART
    WakeLockMode.ALWAYS -> AfkService.MODE_ALWAYS
}

/**
 * Normalize both crop-size models to the effective scale multiplier used by
 * the existing UI and price calculator.
 *
 * v1123+: `size` is an integer 50..100 and the catalog exposes
 * `maxSizeMultiplier`. Older rooms use targetScale/scale directly.
 */
private fun cropScaleFromState(species: String, obj: JsonObject): Double {
    val size = obj["size"]?.jsonPrimitive?.doubleOrNull
        ?.takeIf { it.isFinite() && it >= 50.0 }
    if (size != null) {
        val maxMultiplier = MgApi.findItem(species)?.maxScale
            ?.takeIf { it.isFinite() && it >= 1.0 }
            ?: 1.0
        val clampedSize = size.coerceIn(50.0, 100.0)
        return 1.0 + (maxMultiplier - 1.0) * ((clampedSize - 50.0) / 50.0)
    }

    return obj["targetScale"]?.jsonPrimitive?.doubleOrNull
        ?.takeIf { it.isFinite() && it > 0.0 }
        ?: obj["scale"]?.jsonPrimitive?.doubleOrNull
            ?.takeIf { it.isFinite() && it > 0.0 }
        ?: obj["plantScale"]?.jsonPrimitive?.doubleOrNull
            ?.takeIf { it.isFinite() && it > 0.0 }
        ?: 1.0
}
'''
if text.count(anchor) != 1:
    raise SystemExit(f"cropScaleFromState helper anchor: expected 1, found {text.count(anchor)}")
text = text.replace(anchor, helper, 1)

# Garden grow slots.
old_garden = '                            targetScale = slot["targetScale"]?.jsonPrimitive?.doubleOrNull ?: 0.0,\n'
new_garden = '                            targetScale = cropScaleFromState(species, slot),\n'
if text.count(old_garden) != 1:
    raise SystemExit(f"garden crop scale parser: expected 1, found {text.count(old_garden)}")
text = text.replace(old_garden, new_garden, 1)

# Harvested produce in inventory now carries `size`; old versions carried `scale`.
old_produce = '''                        "Produce" -> produce.add(InventoryProduceItem(
                            id = obj["id"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                            species = obj["species"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                            scale = obj["scale"]?.jsonPrimitive?.doubleOrNull ?: 0.0,
                            mutations = (obj["mutations"] as? JsonArray)
                                ?.mapNotNull { it.jsonPrimitive.contentOrNull }
                                ?.filter { it.isNotBlank() } ?: emptyList(),
                        ))
'''
new_produce = '''                        "Produce" -> {
                            val produceSpecies = obj["species"]?.jsonPrimitive?.contentOrNull.orEmpty()
                            produce.add(InventoryProduceItem(
                                id = obj["id"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                                species = produceSpecies,
                                scale = cropScaleFromState(produceSpecies, obj),
                                mutations = (obj["mutations"] as? JsonArray)
                                    ?.mapNotNull { it.jsonPrimitive.contentOrNull }
                                    ?.filter { it.isNotBlank() } ?: emptyList(),
                            ))
                        }
'''
if text.count(old_produce) != 1:
    raise SystemExit(f"inventory produce parser: expected 1, found {text.count(old_produce)}")
text = text.replace(old_produce, new_produce, 1)

# Potted plant grow slots use the same new `size` field.
old_plant_slot = '                                val scale = slot["targetScale"]?.jsonPrimitive?.doubleOrNull ?: 0.0\n'
new_plant_slot = '                                val scale = cropScaleFromState(slotSpecies, slot)\n'
if text.count(old_plant_slot) != 1:
    raise SystemExit(f"inventory plant slot parser: expected 1, found {text.count(old_plant_slot)}")
text = text.replace(old_plant_slot, new_plant_slot, 1)

# Feeding-trough produce has the same harvested-produce schema.
old_trough = '''                            "FeedingTrough" -> troughCrops.add(InventoryCropsItem(
                                id = obj["id"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                                species = obj["species"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                                scale = obj["scale"]?.jsonPrimitive?.doubleOrNull ?: 0.0,
                                mutations = (obj["mutations"] as? JsonArray)
                                    ?.mapNotNull { it.jsonPrimitive.contentOrNull }
                                    ?.filter { it.isNotBlank() } ?: emptyList(),
                            ))
'''
new_trough = '''                            "FeedingTrough" -> {
                                val cropSpecies = obj["species"]?.jsonPrimitive?.contentOrNull.orEmpty()
                                troughCrops.add(InventoryCropsItem(
                                    id = obj["id"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                                    species = cropSpecies,
                                    scale = cropScaleFromState(cropSpecies, obj),
                                    mutations = (obj["mutations"] as? JsonArray)
                                        ?.mapNotNull { it.jsonPrimitive.contentOrNull }
                                        ?.filter { it.isNotBlank() } ?: emptyList(),
                                ))
                            }
'''
if text.count(old_trough) != 1:
    raise SystemExit(f"feeding trough crop parser: expected 1, found {text.count(old_trough)}")
text = text.replace(old_trough, new_trough, 1)

vm.write_text(text)
print("v1123 crop-size compatibility applied: size(50..100) -> effective scale; legacy scale fields preserved")
