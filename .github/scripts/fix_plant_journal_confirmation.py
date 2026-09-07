from pathlib import Path

path = Path("app/src/main/java/com/mgafk/app/data/websocket/PlantJournalLogger.kt")
text = path.read_text()
old = '''        val changed = withTimeoutOrNull(CONFIRM_TIMEOUT_MS) {
            while (true) {
                delay(POLL_INTERVAL_MS)
                if (journalSnapshot(client) != beforeJournal) {
                    return@withTimeoutOrNull true
                }
            }
        } ?: false
'''
new = '''        var changed = false
        withTimeoutOrNull(CONFIRM_TIMEOUT_MS) {
            while (!changed) {
                delay(POLL_INTERVAL_MS)
                changed = journalSnapshot(client) != beforeJournal
            }
        }
'''
if old not in text:
    raise SystemExit("confirmation-loop patch anchor not found")
path.write_text(text.replace(old, new, 1))
print("fixed PlantJournalLogger confirmation loop")
