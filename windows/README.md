# Windows port — protocol authority

This directory is the Windows desktop target for Magic Garden.

## Non-negotiable source authority
The wire protocol is copied from the Android implementation in this same repository. Do not invent replacement envelopes or infer success from timers.

Authoritative Android files:
- app/src/main/java/com/mgafk/app/data/websocket/RoomClient.kt
- app/src/main/java/com/mgafk/app/data/websocket/GameActions.kt
- app/src/main/java/com/mgafk/app/data/websocket/CommandSequencer.kt
- app/src/main/java/com/mgafk/app/data/websocket/JsonPatch.kt

## Required parity
1. WebSocket open immediately sends {"type":"SocketOpened"}.
2. Welcome supplies selfPlayerId and reseeds command sequencing.
3. Post-Welcome game selection/handshake must match RoomClient exactly.
4. RoomFrame state.patches is normalized to PartialState patches before the existing state pipeline.
5. JSON Patch semantics must match Android.
6. QuinoaCommand/GameActions payloads and commandSequence must match Android.
7. Reconnect resets transient state and obtains authoritative state before automation resumes.
8. An action is complete only when subsequent authoritative server state confirms it.

Projects A–F consume this state/action layer. They must not implement a second protocol stack.
