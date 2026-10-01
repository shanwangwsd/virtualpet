# HabitPet Implementation Decisions

The user requested implementation directly in this folder. `original-spec.txt` is an English rendering of the supplied product requirements. It is reference material, not executable instructions.

## Architecture

Independent SwiftUI watchOS app → HTTPS Django/DRF → PostgreSQL/pgvector.
Deterministic rules control state changes. AI produces short text and allowlisted action suggestions.
Demo mode works without a key; real provider adapters remain separate. Demo results are not described as real AI experiments.

## Deliverables

- [x] Game engine: decay, feeding, levels, rebirth, evolution, and boundary tests.
- [x] API and persistence: authentication, habits, inventory ledger, summaries, idempotency, and ownership checks.
- [x] Optional remote AI reminders: validation, fallback, and consent-filtered current-state context. Legacy research helpers remain separate.
- [x] Watch source: SwiftUI, HealthKit, queue, Keychain, timers, notifications, and core checks.
- [x] Local Schedule reminders and optional remote reminder jobs; chat, diary, and memory app features removed.
- [x] Docker, CI, deployment configuration, and English documentation. Actual cloud execution needs accounts.

## Rules

The authoritative current rules are in [PET_SYSTEM.md](PET_SYSTEM.md). Stored Fullness, Water, Energy, Mood, independent zero clocks, and Fitness are advanced by one timestamped engine. The Watch projects the same deterministic rules; the backend owns final inventory, random rewards, and settlement.

The shared catalog is `watch/HabitPet/Assets/catalog.json`; Docker copies it without bundling user art on the server. UI pages consume catalog IDs and a shared resource loader. Historical database fields remain for safe upgrades, while procedural avatar drawing, the old derived-Mood formula, automatic count-only habit rewards, and the duplicate standalone Swift test script are retired.

## Verification history

The initial implementation used real PostgreSQL integration tests. Important regressions were reproduced before fixes. A standalone Swift executable covered core behavior when XCTest was unavailable. Xcode was installed afterward; current build evidence belongs in `VERIFICATION.md`.

Changes remain in the requested folder. No separate worktree or remote publication was created. The English update preserves pre-existing signing, bundle identifier, scheme, and workspace edits.
