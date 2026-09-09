#!/usr/bin/env python3
from pathlib import Path
import re

PATH = Path("app/src/main/java/com/mgafk/app/ui/screens/god/GodCard.kt")
MARKER = "data class GodHoarderShopOption"

text = PATH.read_text(encoding="utf-8")
starts = [m.start() for m in re.finditer(r"(?m)^\s*(?:private\s+)?data class GodHoarderShopOption\s*\(", text)]

if not starts:
    raise SystemExit("GodHoarderShopOption declaration not found after v11 transform")

if len(starts) == 1:
    print("GodHoarderShopOption already unique; no cleanup needed")
    raise SystemExit(0)


def declaration_end(source: str, start: int) -> int:
    open_paren = source.find("(", start)
    if open_paren < 0:
        raise RuntimeError("Malformed GodHoarderShopOption declaration: missing '('")

    depth = 0
    in_string = False
    escape = False
    close_paren = -1
    for i in range(open_paren, len(source)):
        ch = source[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                close_paren = i + 1
                break

    if close_paren < 0:
        raise RuntimeError("Malformed GodHoarderShopOption declaration: unbalanced parentheses")

    # Include an optional class body if one exists.
    j = close_paren
    while j < len(source) and source[j] in " \t\r":
        j += 1
    if j < len(source) and source[j] == "{":
        brace_depth = 0
        in_string = False
        escape = False
        for i in range(j, len(source)):
            ch = source[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    close_paren = i + 1
                    break

    while close_paren < len(source) and source[close_paren] in " \t\r\n":
        close_paren += 1
    return close_paren

# Remove later declarations from the end backwards so offsets remain valid.
for start in reversed(starts[1:]):
    line_start = text.rfind("\n", 0, start) + 1
    end = declaration_end(text, start)
    text = text[:line_start] + text[end:]

remaining = len(re.findall(r"(?m)^\s*(?:private\s+)?data class GodHoarderShopOption\s*\(", text))
if remaining != 1:
    raise SystemExit(f"Expected exactly one GodHoarderShopOption after cleanup, found {remaining}")

PATH.write_text(text, encoding="utf-8")
print(f"Removed {len(starts) - 1} duplicate GodHoarderShopOption declaration(s); exactly one remains")
