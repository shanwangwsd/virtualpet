# Verification Record and Remaining Work

## Initial implementation evidence

- Real PostgreSQL 18.4 and pgvector 0.8.2 in an isolated project cluster, not a SQLite substitute.
- Python 3.12 with dependencies pinned in requirements.lock.
- 33 backend tests passed before the English update, covering decay, death, rebirth, rewards, ownership, concurrent inventory, health, memory, fallback, diaries, and push retries.
- Eight standalone Swift core checks passed: timer suspension/pause/resume, sleep interval merging, offline reward projection, action persistence, focus persistence, and offline decay.
- Django system checks, migration consistency, and Ruff checks passed.
- Swift networking/Keychain code passed macOS type checking; all Watch source passed syntax parsing.
- Xcode project, Info.plist, and entitlement files passed plutil validation.
- Real HTTP/JWT smoke tests registered/signed in a temporary account, exercised rewards and refresh-token rotation, then deleted the account.
- Development and production Compose configurations parsed successfully. Container execution was not verified because Docker Desktop did not start in the initial environment.
- Demo evaluation collected 36 replies across 12 synthetic scenarios, each with 10 candidate memories. These are smoke results, not real-model quality evidence.

## English update

All built-in Watch copy, notifications, accessibility labels, permission text, backend default replies, AI response language instructions, demo fixtures, and documentation are now English. The Watch explicitly selects the English locale. The user guide is now USER_GUIDE.md.

The user's Gemini API settings, credentials, provider routing, and timeout edits are outside this update. No live provider call is required for language verification. Existing user-authored records are not rewritten by the source translation.

Verified after the English update:

- All 34 backend tests passed in demo mode, including English demo and failure replies.
- The unsigned Watch simulator Debug build succeeded with Xcode and the installed watchOS SDK.
- Ruff checks passed.
- A source, documentation, and evaluation scan found no remaining Chinese characters (excluding local dependencies, build products, and historical work files).
- The demo evaluation regenerated 36 replies across 12 scenarios without fallback.

The initial sandboxed build could not access the SwiftUI compiler plugin correctly. The build succeeded with the required local execution access. This verifies compilation, not physical-device operation or a live Gemini connection.

## Regressions found during initial implementation

- FocusTimer's habitID did not round-trip through snake_case encoding. A standalone Swift regression reproduced and verified the fix.
- Walk starts could use stale steps. They now require a fresh steps_observed_at and a Watch sync before starting.
- An unfinished previous-day walk blocked new walks. The Watch now provides cancellation.
- Sleep-only updates must not make old steps look fresh. Step observations have their own timestamp.
- Revoking AI health consent could still leak prior generated health text through recent replies. Recent context now contains user messages only.
- Non-object JSON and invalid memory categories could produce 500 errors. They now return 400.
- Newly created push deliveries initially missed the same worker pass due to a stale comparison timestamp. A retry regression covers the correction.
- Retrieval now permits abstention instead of always including an unrelated memory.

A partial independent review identified several issues above before its agent reached a usage limit. The remaining review and regression checks were performed by the main implementer. This is not a completed independent audit.

## External verification still needed

| Area | Required verification |
|---|---|
| Physical Watch | Signing, installation, HealthKit permission, real data, background behavior, battery use |
| Real AI/embeddings | Provider compatibility, output quality, latency, and cost with the user's configuration |
| APNs | Actual credentials, capability, device token, and physical-device delivery |
| Docker | Image build and container startup |
| Hosted CI | Push to an authorized remote repository and inspect the workflow |
| Deployment | Hosting account, domain, HTTPS, backup/restore, and production access controls |
| Research | Independent examples, real-provider results, human blind ratings |
| Portfolio | Real screenshots and a physical-Watch recording |

## First-version limitations

- Evolution uses study/activity counts rather than a normalized four-dimensional behavioral model.
- Offline state uses the device clock and ordered projections; server settlement follows receipt time. Clock drift, date boundaries, and critical hunger can cause conflicts.
- The Watch timer is local and user-confirmed; online server focus sessions are a separate path.
- Deleting a vector memory does not erase the same fact from recent user messages. Account deletion currently provides full account-history removal.
- Prompts, schema validation, limited medical-phrase filtering, and fallback do not guarantee every model output is appropriate.
- Signing out revokes refresh tokens; issued access tokens can remain valid for up to 30 minutes. Deleting the account invalidates account access.
- DRF limits are per process; public multi-instance use needs shared or proxy-level limits.
- Final App Store artwork, App Icon validation, and release materials are not complete.

## Reproduce checks

```sh
scripts/check.sh
.venv/bin/python scripts/smoke_api.py
scripts/manage.sh evaluate_ai
swiftc -frontend -parse watch/HabitPet/*.swift watch/HabitPet/Core/*.swift
docker compose config --quiet
```

For translation-only tests, explicitly use demo mode and avoid sourcing live provider configuration. Detailed logs are in work/. The local database is also in work/pgdata: do not delete the entire work/ directory as disposable scratch space.

## Daily Schedule update — 2026-09-30

Added an English Schedule list/editor with daily hour-and-minute reminders, enable/disable, deletion, Watch-local persistence, notification permission handling, and an expanded notification showing Mochi and a speech bubble. No AI provider is used by this feature.

- Swift package: 14 tests passed (4 existing core tests and 10 schedule tests).
- Schedule tests cover repeating notification payloads, edit identity, validation, same-time activities, capacity, persistence, disable/delete, permission denial, delivery registration failure, and clearing during a pending save.
- Notification service failures use an injected system boundary; unit tests do not prove real delivery.
- Unsigned Watch simulator Debug build: BUILD SUCCEEDED. The only final build warning concerned skipped App Intents metadata extraction.
- Backend suite in demo mode: 34 tests passed, with no live Gemini call.
- Ruff, Xcode project plist validation, and whitespace checks passed.
- Before/after hashes confirmed that backend/core/ai.py and backend/config/settings.py were unchanged by this feature. Environment configuration was not edited. Existing Xcode signing settings were preserved.

Actual timed delivery, the expanded notification layout, and physical-Watch operation still need the on-device check in USER_GUIDE.md. Times follow the Watch's local clock and delivery is subject to system notification settings. Schedule data is local and is cleared when the app leaves its authenticated session.

Logs: work/schedule-tests-green.log, work/schedule-watch-build.log, work/schedule-backend-tests.log.


## Removed features and responsive care actions — 2026-09-30

Chat, Diary, and Memories screens, Watch state/network methods, memory settings, and their API routes were removed. The evening diary job was removed. Remote reminder generation explicitly uses current-state context with no chat history or memory retrieval. Historical database records and optional research helpers were preserved; no destructive data migration was run.

The care-action path previously held the global UI busy flag while flushing the queue over network requests with a 25-second timeout. It now durably queues actions, gives immediate built-in pet feedback, and starts one ordered background flush. Sync failure keeps unacknowledged actions, releases the sync state, and reports an English connection/decoding/server error. Navigation remains available. Requests have an 8-second request timeout and 12-second resource timeout; these are per-request limits, not a whole-queue deadline. Queue replay still uses the same action IDs.

Verification:
- 38 backend tests passed, including removal of the old endpoints and proof that care actions do not call the AI provider.
- 16 Swift tests passed, including controlled slow-request and retry cases for the single-flight background synchronization runner.
- Unsigned Watch simulator Debug build succeeded after removing an unsupported watchOS text-selection modifier.
- Live local HTTP probe: water and play returned HTTP 200 in 11 ms and 9 ms respectively; repeated IDs returned identical receipts. The temporary probe account was deleted.
- The actual JSON receipt decoded successfully using the Watch's Swift models and decoder, including the updated water count and XP.
- The existing real HTTP/JWT smoke test passed; its obsolete chat call now asserts 404.
- Ruff and whitespace checks passed. Provider adapter/settings hashes still matched the values captured before the Schedule work; Gemini configuration was not edited.

The local backend health endpoint returned 200 and its listener was bound to 127.0.0.1:8000. The user's Watch/simulator type and configured server address have not been confirmed. Actual device synchronization is therefore not yet verified, and persistent pending actions must not be described as resolved on that device. A physical Watch needs a reachable backend address rather than the Mac's loopback address.

Current normal-app AI use: only optional server-generated remote reminders when the jobs command runs with live AI configured. Care actions, home messages, focus alerts, and Schedule notifications do not call AI. Explicit legacy evaluation commands remain separate.

## Pet identity, age, and growth — 2026-09-30

Added Cat/Dog/Rabbit artwork, a My pet editor, Male/Female/Unspecified gender, editable name, one-time initial age at adoption, and age/XP progress on the home screen. Existing pets keep their stored birth time, XP, level, and history. Optional fields in the Watch decoder preserve compatibility with old cached snapshots. Schedule request payloads and notification cards use the current pet identity; stored reminders are rescheduled under the same IDs after an identity change.

The new care bonus is 5 XP once per local day when fullness and mood are both at least 70. It is settled under the existing owner lock and recorded in the reward ledger. Replay does not duplicate XP. Level remains one plus total XP divided by 100, rounded down. A new generation resets age/progression and keeps species/gender/name; a daily bonus cannot be duplicated through rebirth.

Verification:
- 49 backend tests passed, including identity validation/ownership, preserving progression, initial-age lock, full-day age increments, daily XP threshold/limit/replay, next-day eligibility, and rebirth defaults.
- 20 Swift tests passed, including old-cache decoding, age freezing at death, XP progress, notification payload identity, and updating existing scheduled requests after a pet change.
- Final unsigned watchOS Simulator Debug build succeeded. The only build warning was skipped optional App Intents metadata extraction.
- Live local HTTP checks passed for setting name/species/gender/age, switching species without resetting age, and rejecting a later age change. The temporary test account was deleted.
- Migration 0004_pet_identity_and_daily_care was applied to the local development database. Django checks and migration consistency passed.
- Ruff, plist, and whitespace checks passed. Provider/settings hashes remained unchanged; no live Gemini calls were needed.
- The actual SwiftUI pet shapes were rendered and inspected as a static preview in work/pet-choices.png. Full editor layout and notification presentation on a physical Watch have not been visually verified.

Logs: work/pet-backend-tests.log, work/pet-swift-tests.log, work/pet-watch-build.log.

## Fitness and account exit — 2026-09-30

Walk controls, accepted actions, and rewards are removed. Fitness starts at 50, caps at 100, and kills the pet only below zero. Natural-day steps and the previous 18:00–current 12:00 asleep window settle independently once per date. Activation date, frozen tracking time zone, observation timestamps, generation ownership, and contiguous cursors prevent retroactive pre-activation penalties, partial-window finalization, duplicate rewards, and skipped dates. Unknown readings settle neutrally. HealthKit sleep intervals are clipped and merged. Local previews precede networking; actual scores remain server-confirmed.

The Watch checks on launch/foreground/sync and refreshes while the health page is visible. No midnight background execution is assumed. Gemini connection configuration was not changed; consent-filtered optional reminder context now includes Fitness/status. No live Gemini request was used for verification.

Sign-out clears local state before best-effort remote revocation. Account deletion clears local state only after server success. Errors distinguish connectivity and storage failures. Startup no longer clears Keychain credentials, so reopening the app preserves the saved session. Explicit sign-out and confirmed account deletion still clear credentials.

Verified on the final implementation:

- 70 backend tests passed in explicit demo mode, including thresholds, complete windows, chronological cap/death handling, retries, gaps, unknown data, stale generations, and rejected Walk actions.
- 28 Swift package tests passed, including Fitness boundaries/calendar batching/DST/null serialization and offline sign-out/failed deletion behavior.
- Unsigned watchOS simulator Debug build succeeded with Xcode.
- Real local HTTP smoke passed registration/sign-in, reward retry, feeding, Fitness preview and retry, rejected Walk, JWT rotation/revocation, and deletion of its own temporary account.
- Django system checks, migration consistency, Ruff, and whitespace checks passed. Migration 0005 was applied to the local development database.

Logs: work/fitness-full-tests.log, work/fitness-swift-tests.log, work/fitness-watch-build.log. Compilation and synthetic tests do not establish physical-Watch HealthKit authorization, sample availability, notification delivery, or real-device connectivity. Install the updated build and use Activity & Health → Connect Health for that verification. Finalized dates intentionally do not change when late samples arrive.

## Unified custom-art pet system — 2026-10-01

Implemented shared Potato/Cat art catalog, 20 empty pet-state PNGs and six item PNG slots, safe fallback and cached loading. Removed procedural avatar drawings and old derived-Mood calculation. Concrete Food/Toy inventory replaces automatic count-only habit rewards; rewards are chosen after daily completion and claimed exactly once. Migration 0006 preserves old records and converts existing food counts to Meal stock. It was applied locally.

The unified engine tracks five-hour decay, persisted Mood, both independent 48-hour zero-need clocks, one deprivation penalty per interval, Fitness death, rest recovery, and sleep Energy recovery. Age no longer uses manual offsets. Identity controls expose custom-art species/name and Personality. Optional Gemini care reactions are asynchronous and cannot refresh credentials or block care. Provider configuration is unchanged; all AI verification used demo/mocked responses.

A fresh read-only review found three material issues, all fixed: queued care replay must precede normal reconnect final settlement; inventory use must display the action avatar; resting must not indefinitely override sick imagery. A failing offline replay regression and failing Swift image-priority regression were observed before fixes. Final tests cover these cases. Previously committed timelines cannot be rewound by another device's late offline actions; estimates remain explicitly non-authoritative.

Final evidence:

- 81 backend tests passed, including concurrent reward selection and item use, no consumption at full stats, all care/health boundaries, reaction ownership, and Personality/consent.
- 31 Swift tests passed, including custom catalog slots, new deterministic decay, image priorities, and existing account/schedule tests.
- Unsigned Watch simulator Debug build succeeded. All 26 PNG slots and catalog.json verified in the built app bundle.
- Local HTTP/JWT smoke passed with a temporary account: completion, reward choice, concrete Food consumption, Fitness preview/retry, token revocation, removed Walk, and account deletion. The temporary account was removed; no real account was deleted.
- Ruff, Django system checks, migration consistency, and whitespace validation passed.

The redundant standalone Swift test script was removed; scripts/check.sh now runs the Swift package suite and explicitly selects demo mode for backend verification. Real image art, physical-Watch HealthKit data/permissions, and real-provider speech quality still require user/device checks. No cloud deployment or Git commit was performed.


## Self-check and simpler Watch UI — 2026-10-01

Fixed misleading Food-only habit reward copy and duplicate local reward/new-pet queue submissions. Habit save now returns to the list; Start focus navigates directly to its timer. Settings waits for an active sync before fetching its profile. Home periodically updates projected needs while visible and requests a refresh on entry. Optional care speech now identifies the concrete food/toy, rather than sending only `use_item`.

Removed duplicate Personality settings and fixed 7 PM reminder setup. Moved growth explanations, health settlement details, and connection details behind short navigation links; hid routine successful-sync messages. WatchOS does not support DisclosureGroup, so the intermediate attempt was replaced with supported NavigationLink detail pages before the successful final build. Built-in UI copy was scanned for Chinese characters; none were found.

Verification: 82 backend tests and 33 Swift tests passed; Ruff, whitespace checks, actual temporary-account HTTP smoke, and the unsigned Watch simulator build passed. No live Gemini call was used and no provider configuration was changed. These checks cover source, deterministic behavior, HTTP workflows, and compilation; actual taps, layout, permissions, and connectivity on the user's physical Watch remain device checks.


## Direct habit reward selection — 2026-10-01

Replaced the home-only reward-count sheet trigger with direct navigation from the habit completion and focus completion controls. Habit detail now resolves the current habit by stable ID instead of holding a copied list value. The reward page shows waiting/sync failures, then separate Food and Toy buttons in separate List rows, plus a direct inventory link after selection. Pending rewards include habit_id; same-name habits do not share a selection screen. Existing cached reward records without that optional field still decode.

Regression evidence: observed missing RewardFlow and missing habit_id failures before fixes. Final 83 backend and 34 Swift tests passed; actual temporary-account HTTP completion/claim/consume smoke passed; Watch simulator build succeeded. The physical Watch app must be rebuilt/reinstalled; a separately hosted backend must also receive the updated source. No Gemini connection configuration was changed and reward selection does not use AI.


## Care overlay and generated Schedule voice — 2026-10-01

Care now displays its custom action image with scale/rotation movement in a root overlay for four seconds, with manual Done dismissal. Schedule Save requests task- and Personality-specific speech, persists it with task/personality identity and source, and uses the saved text at notification time. Editing the title invalidates an old preview. Provider/network failure uses a visible local fallback rather than preventing notification setup. Existing schedules require re-saving for generated voice; Personality changes require re-saving to regenerate existing schedules.

85 backend tests and 35 Swift tests passed. New regressions were observed failing before implementation: missing schedule endpoint and missing persisted speech fields. Tests verify Personality/task context, no memory/history, provider-failure fallback, persisted notification content, and changed-title invalidation. Watch simulator Debug build succeeded; Ruff/whitespace checks passed. Tests used demo or mocked providers; the live Gemini connection and physical-device animation/notification delivery were not exercised. Provider configuration/credentials were unchanged.
