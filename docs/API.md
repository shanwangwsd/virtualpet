# API Contract

Except health checks, registration, sign-in, and token refresh, endpoints require `Authorization: Bearer <access>`. Bodies must be JSON objects. Responses use JSON; errors use DRF field errors or `detail`.

Common status codes: 400 invalid input, 401 sign-in required, 404 missing/not owned, 409 state conflict, 429 rate limit.

| Method | Path | Purpose |
|---|---|---|
| POST | /api/auth/register/ | username/password → access and refresh |
| POST | /api/auth/login/ | username/password → access and refresh |
| POST | /api/auth/refresh/ | Rotate refresh token and invalidate the previous one |
| POST | /api/auth/logout/ | Revoke refresh; existing access lasts up to 30 minutes |
| GET | /api/today/ | Settle time decay and return a full snapshot |
| POST | /api/actions/ | Idempotent game action |
| GET/POST | /api/habits/ | List/create habits |
| GET/PATCH/DELETE | /api/habits/{id}/ | Read/update/archive habit |
| POST | /api/health/sync/ | Fitness observations, previews, and daily settlement |
| GET/PATCH | /api/profile/ | Time zone, personality, consent, sleep target, quiet hours |
| DELETE | /api/account/ | Delete account and associated data |
| GET | /api/pet/generations/ | Generation history |
| DELETE | /api/sessions/{id}/ | Cancel focus session |
| GET | /api/reminders/ | Unacknowledged reminders for today |
| POST | /api/reminders/{id}/ack/ | Mark reminder read |
| POST/DELETE | /api/devices/ | Register/remove APNs token |

## Actions

The original separate feed, complete, progress, and interaction routes are unified under `/api/actions/` so offline retries use one idempotency path. State changes serialize on the owner row.

```json
{
  "id": "a-valid-UUID",
  "generation": 1,
  "kind": "complete",
  "occurred_at": "2026-09-29T10:00:00Z",
  "payload": {"habit_id": 1}
}
```

Supported kinds: `use_item`, `claim_reward`, `water`, `rest`, `wake`, `complete`, `progress`, `rebirth`, `focus_start`, `focus_finish`.

- progress needs `habit_id` and positive integer `amount`.
- complete and focus_start need `habit_id`.
- `use_item` needs `item_id` from inventory. `claim_reward` needs `reward_id` and integer `category` (0 Food, 1 Toy).
- Other operations use an empty payload. Legacy `feed` returns a conflict directing the client to select a concrete Food.
- generation must match the current pet. Old-generation actions never apply to a reborn pet.
- The same user, UUID, and content return the saved response without another state change.
- Reusing a UUID with different content returns 409.
- HabitLog uniqueness, transactions, and RewardLedger prevent duplicate daily rewards.
- Users serialize independently; one user's lock does not lock every other user.
- Retry responses can contain the original snapshot. Fetch today again after draining the queue.
- Rejected actions are not stored as successes. They may be retried after resolving preconditions.
- `occurred_at` allows ordered replay of saved actions within seven days. The server applies at max(occurred_at, committed pet time), capped at now. It never rewinds an already committed timeline. Drain queued actions before final today/health settlement.

## Health sync

```json
{"generation": 1, "observed_at": "2026-09-30T04:00:00Z", "days": [{"date": "2026-09-29", "steps": 6521, "sleep_minutes": 480}, {"date": "2026-09-30", "steps": 1200, "sleep_minutes": null}]}
```

A batch contains at most 15 unique dates from the pet's Fitness activation date through today. Generation must match. Omitted fields mean no update; explicit null means unavailable and settles neutrally. Zero is a measured value. Older observations cannot overwrite newer observations. Future observations are rejected.

Steps settle after the natural day ends. Sleep settles after noon for the previous 18:00–current 12:00 window. A reading must have been taken after its window ended to settle. Unfinished readings only update previews. Each component has an independent contiguous settlement cursor; retries cannot duplicate rewards. Finalized records are immutable. Fitness is clamped to 0–100 after each chronological settlement; reaching zero ends the pet's life.

Snapshots expose `fitness`, `fitness_status`, `fitness_started_on`, `fitness_timezone`, `last_step_settlement_date`, `last_sleep_settlement_date`, `step_delta_preview`, `sleep_delta_preview`, and the latest main sleep date/minutes. Fitness fields are on `pet`; tracking and preview fields are on `health`. The time zone is fixed when the generation starts tracking. The legacy single-day health payload remains accepted for compatibility. Walk action kinds are rejected.

## Limits and privacy

- Habit frequency: daily only.
- Target: 1–10000; reward amount: 1–100.
- Chat: 1–1000 characters; AI reply: 1–160 characters, instructed to use English.
- Memory: at most 500 characters, 1536-dimensional embeddings, filtered by user and model.
- Never place credentials, health summaries, or memory content in URL parameters or public logs.
- The original HealthDailySummary concept is implemented as Daily, which also holds water and daily reward state.


Chat, diary, and memory endpoints have been removed and return 404. Care actions never invoke AI. Remote reminder jobs use current state only, without chat history or saved memories.

## Pet details and growth

`PATCH /api/pet/` accepts required `generation` plus optional `name` (1–40 characters), `species` (`potato`, `cat`), and `personality` (`gentle`, `playful`, `tsundere`, `energetic`, `calm`). Manual age and gender updates are rejected. Age derives only from birth and death timestamps. Appearance changes preserve progression.

Snapshots include `pet.mood`, `last_decay_at`, `critical_since` (Fullness zero clock), `water_zero_since`, `rest_at`, `sleep_deprived_until`, and `visual_state`. Inventory includes concrete `items` with id, key, name, category, effect, asset, quantity. `pending_rewards` lists completion reward IDs, habit names, and dates. A claim chooses exactly one uniformly random item in the selected category; retries keep the same item. An independently repeated claim returns 409. Existing habit reward configuration fields are legacy and do not alter this flow.

`POST /api/pet/reaction/` accepts `action_id`, referencing an owned, confirmed care action for the current living pet. It is an optional, rate-limited call separate from actions; provider failure uses a Personality-specific local response. No Chat endpoint is restored. Consent determines whether health-derived Fitness/Energy and raw health summaries are included. Provider connection configuration is unchanged.

See PET_SYSTEM.md for authoritative current mechanics and ASSETS.md for resource layout.


`POST /api/schedule/speech/` accepts `title` (1–80 characters), `hour` (0–23), and `minute` (0–59). It requires authentication, uses the profile Personality and consent-filtered current pet context without memory/history, and returns a PetMessage plus `personality`. It uses the AI throttle. The Watch saves this result into a local repeating notification; the endpoint does not create a server-side schedule. Provider failures return task-specific fallback text with `source=fallback`.
