# Current Pet Mechanics

Both Potato and Cat are custom-image pets. No procedural animal artwork is used. The asset loader falls back from the requested state to that pet's normal image, then to a neutral missing-image label.

## Attributes and survival

A new generation starts with Fitness 50, Fullness 70, Water 70, Energy 70, and Mood 70. All five attributes clamp to 0–100. Fitness reaching zero causes death.

Every complete five hours since `last_decay_at`: Fullness -10, Water -20, Energy -5, Mood -5. Incomplete intervals carry forward. If Fullness or Water was already zero at the interval's start, Fitness loses 30 once, even if both were zero. Example: Water 20 reaches zero at hour 5; the first deprivation penalty occurs at hour 10.

Death occurs at the earliest of Fitness =0, Fullness continuously zero for 48 hours, or Water continuously zero for 48 hours. Restoring a need clears only its own zero timer. Fitness penalties can cause death before either 48-hour limit. Death freezes the current pet; starting a new generation resets needs, age, clocks, and Fitness, while preserving inventory, selected appearance/name, Personality, and old records.

Drink restores 20 Water. Toys restore Mood and consume one inventory item. Rest restores 10 Energy per complete 30 minutes and stops at full Energy, on another care interaction, or on death. Five-hour decay continues during rest. Main sleep restores 5 Energy per whole asleep hour (maximum +40), once per completed window. Missing sleep restores none and carries no Fitness penalty.

## HealthKit

Daily steps: >=5000 +30 Fitness; 1000–4999 +10; 500–999 0; <500 -10. Main asleep time from previous 18:00 to current 12:00: >=8 hours +10; 5–<8 hours 0; <5 hours -10. Merge overlapping asleep intervals; no separate nap settlement. Unknown data is neutral, never assumed zero. Read errors retain unprocessed dates for retry.

The page shows live local observations, latest main sleep and date, and hypothetical deltas. Final scores require sync. Persisted independent step/sleep cursors backfill completed windows starting at activation; no midnight background task is required. Frozen per-generation time zone keeps date identity consistent.

Known health events and decay settle chronologically; at identical boundaries, decay is processed first. Late health observations apply at the already committed timeline position, once, and cannot revive a dead pet. Settled dates do not change with late samples. New decay rules start at migration, without retroactive new penalties.

## Rewards and growth

Each daily habit completion offers exactly one Food or Toy choice. The chosen category yields one uniformly random concrete item, persisted once. Dismissed choices remain available. Food: Apple +15 Fullness, Carrot +20, Meal +35. Toys: Ball +15 Mood, Yarn +20, Teddy +30. Each use consumes one; a full target stat rejects use without consumption. Existing food counts migrate to Meals. Legacy coins remain in historical storage, not the new reward flow.

Age is whole elapsed 24-hour periods since creation, frozen at death. No manual age offset or gender setting. Each 100 XP grants a level. Food grants 5 XP; Fullness and Mood >=70 grants the existing 5 XP daily care bonus once. These XP caps do not prevent need restoration.

## Pictures and speech

Durable visual priority: dead; sick when Fitness <20; angry when Fullness or Water is zero; sad when Fullness/Water/Energy <30, Mood <40, or a completed main sleep under five hours is still within its next 24 hours; happy when Mood >=70 and Fullness/Water/Energy >=40; otherwise normal. Rest uses rest artwork except when sick/dead. Accepted care opens a four-second overlay on the current page using eat/drink/play/rest art with a gentle scale/rotation animation; Done closes it early. Death always overrides it.

Personality shapes fallback and optional Gemini speech. Generated care speech is asynchronous, bounded to one request per 15 seconds on the Watch and 10/minute on the server. Gemini configuration is unchanged. With AI health consent, context includes all five needs, visual state, and current health data; without it, health-derived Fitness/Energy and health-specific visual context are omitted. Mood, Water, Fullness, and general state remain available. No chat screen returns.

## Offline behavior

Actions persist with UUID, generation, and timestamp. Normal reconnection drains saved actions before final health/today settlement; actions replay no earlier than the server's last committed pet time. A timeline already committed by another device or a reminder worker cannot be rewound, so offline projections remain estimates and cannot resurrect a confirmed death. Random rewards are never fabricated offline. Conflicts retain the queued action for review.


Schedule voice is generated on Save from the activity, time, current Personality, and consent-filtered pet context. The English message is cached in the local reminder and delivered without a network request at its scheduled time. Re-save after changing Personality to regenerate. Generation failure keeps a task-specific local fallback and labels it as Local voice. This is separate from the short care-action reaction path.
