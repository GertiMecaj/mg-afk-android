#!/usr/bin/env python3
from pathlib import Path

path = Path("app/src/main/java/com/mgafk/app/ui/MainViewModel.kt")
text = path.read_text()

old = '                            targetScale = slot["targetScale"]?.jsonPrimitive?.doubleOrNull ?: 0.0,\n'
new = '''                            targetScale =\n                                slot["targetScale"]?.jsonPrimitive?.doubleOrNull?.takeIf { it.isFinite() && it > 0.0 }\n                                    ?: slot["scale"]?.jsonPrimitive?.doubleOrNull?.takeIf { it.isFinite() && it > 0.0 }\n                                    ?: slot["plantScale"]?.jsonPrimitive?.doubleOrNull?.takeIf { it.isFinite() && it > 0.0 }\n                                    ?: 0.0,\n'''

count = text.count(old)
if count != 1:
    raise SystemExit(f"Expected exactly one garden targetScale parser, found {count}")

path.write_text(text.replace(old, new, 1))
print("Garden scale compatibility applied: targetScale -> scale -> plantScale")
