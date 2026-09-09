#!/usr/bin/env python3
from pathlib import Path

# 1) Keep harvestAndSellGodPlants source-compatible with existing trailing-lambda callers.
vm_path = Path("app/src/main/java/com/mgafk/app/ui/MainViewModel.kt")
vm = vm_path.read_text()
old_sig = '''        candidateKeys: Set<Pair<Int, Int>>,
        canHarvest: (GardenPlantSnapshot) -> Boolean,
        logBeforeSell: Boolean = false,
    ): List<GardenPlantSnapshot> {'''
new_sig = '''        candidateKeys: Set<Pair<Int, Int>>,
        logBeforeSell: Boolean = false,
        canHarvest: (GardenPlantSnapshot) -> Boolean,
    ): List<GardenPlantSnapshot> {'''
if old_sig not in vm:
    raise SystemExit("Fast Money harvest signature anchor not found")
vm_path.write_text(vm.replace(old_sig, new_sig, 1))

# 2) Resume persisted Fast Money / Auto Eggs from SectionContent itself, regardless of which
# page the app reopens on. Remove the page-local resume effects inserted by the v10 transformer.
main_path = Path("app/src/main/java/com/mgafk/app/ui/screens/MainScreen.kt")
main = main_path.read_text()

god_local = '''        NavSection.GOD -> {
            LaunchedEffect(session.id, session.connected, session.fastMoneyEnabled, session.fastMoneySelectedSpecies) {
                if (session.connected && session.fastMoneyEnabled && session.fastMoneySelectedSpecies.isNotEmpty()) {
                    viewModel.setGodFastMoney(
                        session.id,
                        true,
                        session.fastMoneySelectedSpecies,
                        session.fastMoneySearch,
                        session.fastMoneyShopFilters,
                        session.fastMoneyTierFilters,
                    )
                }
            }
            GodCard('''
if god_local not in main:
    raise SystemExit("Fast Money page-local resume anchor not found")
main = main.replace(god_local, '''        NavSection.GOD -> {
            GodCard(''', 1)

egg_local = '''            LaunchedEffect(session.id, session.connected, session.autoPlantEggs) {
                if (session.connected && session.autoPlantEggs) {
                    viewModel.setAutoPlantEggs(session.id, true)
                }
            }

            InventoryCard('''
if egg_local not in main:
    raise SystemExit("Auto Eggs page-local resume anchor not found")
main = main.replace(egg_local, '''            InventoryCard(''', 1)

section_anchor = '''    onPlayRequest: (sessionId: String, cookie: String, room: String, gameUrl: String) -> Unit = { _, _, _, _ -> },
) {
    when (section) {'''
section_replacement = '''    onPlayRequest: (sessionId: String, cookie: String, room: String, gameUrl: String) -> Unit = { _, _, _, _ -> },
) {
    LaunchedEffect(session.id, session.connected, session.fastMoneyEnabled, session.fastMoneySelectedSpecies) {
        if (session.connected && session.fastMoneyEnabled && session.fastMoneySelectedSpecies.isNotEmpty()) {
            viewModel.setGodFastMoney(
                session.id,
                true,
                session.fastMoneySelectedSpecies,
                session.fastMoneySearch,
                session.fastMoneyShopFilters,
                session.fastMoneyTierFilters,
            )
        }
    }
    LaunchedEffect(session.id, session.connected, session.autoPlantEggs) {
        if (session.connected && session.autoPlantEggs) {
            viewModel.setAutoPlantEggs(session.id, true)
        }
    }

    when (section) {'''
if section_anchor not in main:
    raise SystemExit("SectionContent global resume anchor not found")
main_path.write_text(main.replace(section_anchor, section_replacement, 1))

print("Fixed harvest lambda compatibility and global persistent automation resume")
