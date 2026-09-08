#!/usr/bin/env python3
from pathlib import Path

p = Path("apply-qol-v9.py")
s = p.read_text()
old = '''            onCollect = onCollect,\n        )\n        GodPetAutoFeedCard('''
new = '''            onCollect = onCollect,\n            onCollectAndSell = onCollectAndSell,\n        )\n        GodFastMoneyCard('''
if old not in s:
    raise SystemExit("QoL transformer fix target not found")
s = s.replace(old, new, 1)
# The original transformer has a second replacement that would try to add the
# same callback. Remove that replacement block by making its target impossible.
s = s.replace(
    '''    "            onCollect = onCollect,\\n        )\\n        GodPetAutoFeedCard(",''',
    '''    "__QOL_ALREADY_WIRED__",''',
    1,
)
p.write_text(s)
print("Adjusted QoL transformer for final GOD card ordering")
