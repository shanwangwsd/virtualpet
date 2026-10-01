# HabitPet Step-by-Step Guide

## What is included

The project lives at `/Users/a33/Downloads/virtualpet`. It includes the backend, migrations, game rules, optional AI reminder adapter, Watch source, offline queue, evaluation tools, and deployment configuration.

It is not an App Store release. Build results and outstanding physical-device, provider, notification, and deployment checks are listed in `VERIFICATION.md`.

## 1. Start the backend on this Mac

Open Terminal:

```sh
cd /Users/a33/Downloads/virtualpet
.venv/bin/python scripts/local_db.py start
scripts/manage.sh migrate
scripts/dev.sh
```

Keep the last terminal open. Visit `http://127.0.0.1:8000/healthz/`; `{"status":"ok"}` means the API is reachable.

If port 8000 is already in use, check that URL before starting another server. Alternatively, run `DEV_BIND=127.0.0.1:8001 scripts/dev.sh`.

### Test the actual workflow

In another terminal:

```sh
cd /Users/a33/Downloads/virtualpet
.venv/bin/python scripts/smoke_api.py
```

This creates its own temporary account, completes a habit, retries the action, feeds the pet, rotates credentials, and deletes the temporary account. Successful checks print PASS.

### Create an account

Use **Create account** on the Watch sign-in screen. To create a seeded demo account instead:

```sh
scripts/manage.sh seed_demo
```

The first run prints a random password. Save it privately. Re-running does not reset an existing password. To reset it:

```sh
scripts/manage.sh changepassword demo
```

## 2. Install on another computer

Use Python 3.12 or a compatible newer version, PostgreSQL 18, and C build tools; alternatively, use Docker Desktop.

```sh
cd /your/path/virtualpet
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
python3 scripts/create_env.py
.venv/bin/python scripts/local_db.py start
scripts/manage.sh migrate
scripts/dev.sh
```

`local_db.py` creates only the project's `work/pgdata` cluster, listening on localhost port 55439. It does not modify existing system clusters. Building pgvector uses its official release archive and requires network access. This development cluster uses local trust authentication: do not expose it publicly.

Docker alternative:

```sh
python3 scripts/create_env.py
docker compose up --build
```

Docker stores data in the `pgdata` volume. It does not automatically migrate data from the local `work/pgdata` cluster.

## 3. Open the Watch app

1. Install and open full Xcode; complete any additional component installation.
2. Install watchOS simulator components under Xcode Settings.
3. Open `watch/HabitPet.xcodeproj`.
4. Select the HabitPet target, then **Signing & Capabilities**.
5. Sign in to your Apple Account and select your Team.
6. Use your own unique Bundle Identifier. Existing signing settings are preserved by the English-language update.
7. Confirm the HealthKit capability is present. The app reads health records; it does not write them.
8. Select an Apple Watch simulator or paired physical Watch and run the app.
9. Enter the backend URL and sign in or create an account.

The deployment target is watchOS 10. Adapt it if your device requires a different supported version.

### Choose the correct backend URL

- A simulator may reach `http://127.0.0.1:8000`. If not, use the Mac's local network hostname.
- On a physical Watch, `127.0.0.1` refers to the Watch itself, not your Mac.
- A deployed HTTPS URL is the simplest physical-device endpoint.
- For LAN development, add the Mac's `.local` hostname to `.env`'s `ALLOWED_HOSTS`, run `DEV_BIND=0.0.0.0:8000 scripts/dev.sh`, and enter `http://your-mac.local:8000` on a reachable network.
- You control any firewall approval. Do not expose Django's development server publicly.
- The app permits local-network ATS exceptions, not arbitrary public HTTP. Prefer `.local` or HTTPS if an IP address is blocked.

### First physical-device walkthrough

- Create a 30-minute Japanese study habit. Use **Mark complete** to test the reward flow first.
- Confirm Food +1, tap **Feed**, and verify food decreases while fullness increases.
- Repeat quickly and confirm the completion reward is not duplicated.
- Start focus, leave the app, return, and check the timer. Pausing should freeze elapsed time.
- Disconnect, complete another habit, and feed. Restart the app and confirm pending actions remain.
- Reconnect and refresh. Confirm inventory converges to the server state.
- If an action conflicts, later actions remain queued. **Discard first action** is explicit, not automatic.
- Use **Connect Health** and choose your permissions. Missing data is not treated as zero sleep.
- Activity & Health shows live readings and Fitness estimates. Open the app or sync to settle completed days.

## 4. Connect a real AI provider

`AI_MODE=demo` needs no key and makes no paid model calls. Demo vectors are lexical hashes, not semantic embeddings.

Edit `.env`:

```dotenv
AI_MODE=live
AI_BASE_URL=https://your-compatible-provider/v1
AI_API_KEY=your-private-key
AI_MODEL=your-structured-output-model
EMBEDDING_MODEL=your-1536-dimension-embedding-model
```

The remaining AI feature is optional server-generated remote reminders. It needs JSON Schema responses on `/chat/completions`. Normal app use no longer needs embeddings, chat, diaries, or saved memories. Existing provider settings are preserved. Only optional legacy research commands use the embedding setting.

Keep keys on the backend. Restart it after configuration changes. Enable **Share health with AI** only if you want health summaries included in remote reminder context. Failure uses a built-in fallback. Care actions may request optional Gemini reactions after sync. Schedule generates and caches its reminder text when saved.

## 5. Notifications

### Local reminders

Use Schedule to choose your daily reminder times. Focus completion also uses local notifications. Permission must be granted on your device.

### AI remote reminders

`scripts/manage.sh run_jobs` handles optional AI remote reminders. The deployed jobs service runs every 15 minutes.

Without APNs credentials, generated reminders are stored server-side but are not delivered to the Watch in the background. There is no Diary or Memories screen. Local Schedule reminders are independent of this service.

To enable APNs:

1. Enable Push Notifications for your App ID and add the Xcode capability.
2. Create an APNs signing key and store it in a private server location.
3. Set `APNS_KEY_PATH`, `APNS_KEY_ID`, `APNS_TEAM_ID`, and `APNS_TOPIC` in `.env`.
4. The topic must match the actual Watch Bundle ID. Development signing uses `APNS_SANDBOX=1`.
5. With Docker, mount the key read-only into the relevant containers and use the container path.
6. Sign in on the Watch and tap **Enable remote reminders**.
7. Run the jobs, check the logs, and verify delivery on the device.

Delivery supports retry backoff, invalid-device handling, and collapse IDs. Ambiguous network failures can still produce duplicates; delivery is not exactly-once, and immediate display is not guaranteed.

## 6. Tests and evaluation

```sh
scripts/check.sh
scripts/manage.sh evaluate_ai
```

Files in `evaluation/results/`:

- `report.json`: mode, model identifiers, Recall@K, and limitations.
- `responses.json`: outputs from the three systems.
- `retrieval.json`: per-scenario retrieval results.
- `human-ratings.csv`: shuffled human-rating sheet.
- `blind-key.json`: system labels to reveal after scoring.

The 12 synthetic scenarios are smoke tests. High demo retrieval scores do not establish improved user experience or support research conclusions.

After configuring a real provider:

```sh
scripts/manage.sh evaluate_ai --live
set -a; . ./.env; set +a
.venv/bin/python scripts/judge_responses.py --live
```

These commands incur API costs. Expand an independent test set, label relevant memories, and collect human blind ratings. Model judging is supplementary.

## 7. Responsibilities

| Area | Provided in the project | Your part |
|---|---|---|
| Backend | Rules, APIs, migrations, tests | Evaluate reward pacing |
| Watch | SwiftUI, services, queue, test code | Xcode, Team sign-in, device pairing |
| HealthKit | Reads, sleep merging, summaries | Device permission and real data |
| AI | Optional remote reminder adapter, context, fallback | Account, key, budget |
| Remote notifications | APNs sending and retry logic | Signing key, capability, device test |
| Deployment | Containers, proxy config, guide | Hosting, domain, fees, account access |
| Research | Scenarios, scripts, report generation | Human ratings and participant consent |
| Portfolio | README, diagrams, demo script | Real screenshots and recordings |

## 8. Stop and back up

Press Control-C in the backend terminal, then:

```sh
.venv/bin/python scripts/local_db.py stop
```

Stopping preserves the database. Do not delete `work/pgdata`; it contains your local data.

Local development backup:

```sh
pg_dump -h 127.0.0.1 -p 55439 -U habitpet -Fc habitpet > work/habitpet.backup
```

Backups may contain health summaries, conversations, and preferences. Keep them private. Test restoration into a new empty database before considering any replacement of existing data.

## Daily schedule reminders

1. Build and run the updated Watch app, then sign in.
2. Open **Schedule** on the home screen and choose **Add reminder**.
3. Enter an activity, such as `Read a book`, and choose its hour and minute (24-hour format).
4. Leave **Enabled** on, tap **Save reminder**, and allow notifications.
5. The reminder repeats every day at the Watch's local time. No duration or countdown is required. Expand the notification to see Mochi and an English speech bubble; watchOS controls its initial presentation.

Tap a reminder to edit it. Saving replaces the old notification. Switch **Enabled** off to pause it, or choose **Delete reminder** in the editor. You can save up to 30 reminders, including separate activities at the same time.

Schedules are stored on this Watch, work without a network connection after setup, and do not synchronize to other devices. **Turn off local notifications** also disables the saved reminders. Leaving the authenticated session clears the local schedule. Saving a Schedule asks Gemini for a short English reminder based on its activity and the current Personality. The generated text is stored locally and reused at notification time. Local fallback text is used if generation is unavailable. The list labels AI voice versus Local voice.

To verify on your Watch, create a reminder two or three minutes ahead, return to the watch face, wait, and expand the notification. Also check that editing replaces the old time and that disabled/deleted reminders stay off after reopening the app. Notification permission and Focus settings can affect visible delivery.

## Pending actions and connection troubleshooting

Item use and Drink first save an operation on the Watch. They give an immediate action animation while one ordered background sync sends saved operations to the backend. Optional Gemini care speech is requested separately after sync and cannot delay the action. Pending means unconfirmed, not an AI request. Only acknowledged operations leave the queue; failed requests stay available for retry.

The home screen remains navigable during sync. Check its status text, and use **Sync** after restoring connectivity. Settings → Connection displays the configured server URL. Request timeout is 8 seconds, with a 12-second resource limit per request.

A real Watch cannot use `127.0.0.1` or `localhost` to reach a server running on a Mac. Use a reachable server address. The default development server listens only on the Mac loopback interface. A simulator and a physical Watch therefore have different connection requirements. Do not discard pending actions merely to hide a connection issue.

## Choose and customize your pet

Open **My pet** and choose Potato or Cat. Both use your own artwork. Set a name and Personality. Age is automatic from the creation date; gender and manual age controls are removed. Switching artwork preserves progression. Each 100 XP adds one level; Food use grants 5 XP. Fullness and Mood >=70 grant the existing once-daily 5 XP bonus.

Tap **Complete & choose reward** in a habit, or **Finish & choose reward** after focus. The next page shows **Food** and **Toy** as separate buttons. While offline it shows that completion is saved and awaiting sync. You can also use **Choose reward** later. The server selects one item; a retry cannot reroll it. Open **Food** or **Toys** to see quantities and effects, then use a specific item. A full corresponding stat prevents item consumption. The inventory page shows the pet's temporary eat/play image.

**Drink** restores Water, **Toys** raise Mood, and **Rest** restores Energy over elapsed time. Death offers **Start a new generation**, keeping inventory and identity while resetting the pet's age and needs. See [current mechanics](PET_SYSTEM.md) for exact decay and death rules and [artwork instructions](ASSETS.md) to replace empty images.

## Fitness and Activity & Health

Open **Activity & Health → Connect Health** and allow step and sleep reads on your Watch. The app checks health data at launch, on returning to the foreground, during synchronization, and while the health page is visible. It does not require a midnight background run.

Fitness starts at 50 and stays within 0–100. At zero, the pet passes away. Status is energetic at 70–100, normal at 40–69, tired at 20–39, and weak at 1–19. Rebirth starts a new Fitness record.

| Completed observation | Fitness change |
|---|---:|
| Steps ≥ 5000 | +30 |
| Steps 1000–4999 | +10 |
| Steps 500–999 | 0 |
| Steps < 500 | −10 |
| Main sleep ≥ 8 hours | +10 |
| Main sleep 5–<8 hours | 0 |
| Main sleep < 5 hours | −10 |
| Unavailable steps or sleep | No penalty |

Steps use a natural calendar day. Main sleep totals asleep intervals from 6 PM the previous day to noon on the displayed date. Overlapping sleep samples are merged; awake/in-bed time is excluded. There is no separate nap settlement. Scores settle only after their windows finish, once for each date and component, starting on the generation's tracking activation date. Missed dates are processed in order on the next successful sync. The time zone shown on this page stays fixed for that generation.

Local readings and hypothetical changes can display before the server connects. Actual Fitness changes require server confirmation. After today's sleep is settled, its estimate does not grant another reward. HealthKit does not disclose read-permission denial; missing readings are treated as unavailable, never guessed as zero. An already finalized date is not recalculated if late HealthKit samples arrive.

Walk controls and rewards are removed. Fitness rules do not call Gemini. Optional AI reminders may receive Fitness and its status only when AI health consent is enabled; the provider connection settings are unchanged.

Signing out clears this Watch's session even if the server cannot be reached, with a notice if remote revocation is unconfirmed. Account deletion requires server confirmation and retains the local session on failure. Connection errors now explain the failure rather than only displaying a generic message.


## Simplified navigation and AI use

Home keeps the pet, age/level, five needs, Food/Toys, care controls, and the main navigation. Growth explanations are under My pet → Growth. Health settlement dates and time zone are under Activity & Health → Details. Personality is edited only in My pet. The old fixed 7 PM reminder setup is removed; use Schedule. Saving a habit returns to the list; Start focus opens the timer directly. Repeated reward claims and new-pet actions are rejected locally before they can block the queue.

In live mode, optional pet speech is requested after a confirmed Drink, Food/Toy use, Rest, or Wake action. The Watch attempts at most one speech request per 15 seconds and keeps the action animation if unavailable. Concrete item use includes the item's name and category in the generation context. The response does not change game state.

Backend reminder jobs may also generate speech, only when run: Fullness below 40; unfinished habits from 6 PM onward; or fewer than three Drink actions between noon and 8 PM, subject to quiet hours, once per reason/day, and a maximum of three stored reminders/day. Receiving pushes additionally requires APNs setup and notification permission. A low stat alone does not call Gemini from the Watch.

Schedule delivery uses already saved text and does not call Gemini at the notification time. HealthKit reads, decay/death, XP, image switching, inventory consumption, and random reward selection do not use Gemini. AI_MODE=demo uses built-in responses. Research/evaluation commands are separate manual tools; the app does not run them.


## Automatic care display and Schedule voice

Drink, Food/Toy use, Rest, and Wake automatically show the pet over the current page for four seconds. The corresponding custom state image moves gently; Done closes it early. Empty image slots still use the missing-image fallback. No scrolling is needed to see the action.

For a Personality-based Schedule: choose Personality in My pet, open Schedule, enter the activity and time, then Save reminder. A short generation indicator appears. The saved message is used for each daily occurrence, even offline. Existing schedules, or schedules created before a Personality change, should be saved again to regenerate their voice. Notifications still require Watch permission. AI failure does not prevent saving the reminder; the UI identifies Local voice and offers re-saving online.

Example style for Tsundere + Study Japanese: “Hmph! Japanese time. Impress me with a sentence, will you?” This is an illustrative example, not a recorded provider response.
