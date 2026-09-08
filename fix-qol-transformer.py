#!/usr/bin/env python3
from pathlib import Path

p = Path("apply-qol-v9.py")
s = p.read_text()
old_target = '"            onCollect = onCollect,\\n        )\\n        GodPetAutoFeedCard(",'
new_target = '"            onCollect = onCollect,\\n        )\\n        GodFastMoneyCard(",'
old_replacement = '"            onCollect = onCollect,\\n            onCollectAndSell = onCollectAndSell,\\n        )\\n        GodPetAutoFeedCard(",'
new_replacement = '"            onCollect = onCollect,\\n            onCollectAndSell = onCollectAndSell,\\n        )\\n        GodFastMoneyCard(",'
if s.count(old_target) != 1 or s.count(old_replacement) != 1:
    raise SystemExit(
        f"QoL transformer mass-harvest targets changed: old={s.count(old_target)} new={s.count(old_replacement)}"
    )
s = s.replace(old_target, new_target, 1)
s = s.replace(old_replacement, new_replacement, 1)
p.write_text(s)
print("Adjusted QoL transformer for final GOD card ordering")
