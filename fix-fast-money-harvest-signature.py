#!/usr/bin/env python3
from pathlib import Path

path = Path("app/src/main/java/com/mgafk/app/ui/MainViewModel.kt")
text = path.read_text()
old = '''        candidateKeys: Set<Pair<Int, Int>>,
        canHarvest: (GardenPlantSnapshot) -> Boolean,
        logBeforeSell: Boolean = false,
    ): List<GardenPlantSnapshot> {'''
new = '''        candidateKeys: Set<Pair<Int, Int>>,
        logBeforeSell: Boolean = false,
        canHarvest: (GardenPlantSnapshot) -> Boolean,
    ): List<GardenPlantSnapshot> {'''
if old not in text:
    raise SystemExit("Fast Money harvest signature anchor not found")
path.write_text(text.replace(old, new, 1))
print("Fixed Fast Money harvest signature for Kotlin trailing lambdas")
