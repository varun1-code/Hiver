# Labeling Notes

## Rubric (condensed)

**Intent**: Read only `customer_text`. Priority when signals overlap: (1) money/charges/refunds/subscriptions -> `billing_purchase`; (2) Apple ID/iCloud login/2FA/password/lockout/deletion -> `account_access`; (3) WiFi/Bluetooth/cellular/pairing -> `connectivity_issue`; (4) an explicit *physical* fault (cracked screen, dead button, swollen/overheating battery, broken camera) with no update mentioned -> `hardware_malfunction`; (5) trouble with the update/upgrade *process itself*, or "how do I update/downgrade" -> `update_install_issue`; (6) a plain how-to question, nothing broken -> `how_to_question`; (7) device/software misbehaving (freezing, crashing, battery drain, broken feature) -> `software_bug_after_update`, applied even without an explicit "since iOS X" phrase, since these symptoms are software-category by nature; (8) pure venting/sarcasm with no real ask -> `complaint_feedback`, last resort only.

**Auto-handle**: `false` when money is genuinely in motion (disputes, refunds, order-specific lookups); when `account_access` applies (always false); on any safety signal (injury, shock, overheating battery); when a warranty/replacement/repair-cost decision is implied; on an explicit demand for a manager; or when text is too vague/cryptic (often needs a linked image). `true` for routine, well-understood cases with a standard templated reply — most how-to questions, known post-update bugs, ordinary connectivity/hardware troubleshooting — even when angry or sarcastic (profanity alone isn't an escalation trigger).

## How wrong was the baseline?

- **Intent changed on 119/200 rows (~60%).** Dominant error: the baseline tagged almost any tweet naming a keyboard/button/screen/speaker as `hardware_malfunction` even with "since iOS 11"/"after the update" present — relabeled `software_bug_after_update`. It also mislabeled clear `account_access`/`connectivity_issue` cases, apparently on shallow keyword matches.
- **Auto-handle changed on 48/200 rows (~24%).** Most flips went **false->true**: the baseline's "high-risk keyword" rule fired on profanity/anger with no real safety/money/security content, over-escalating routine angry bug reports. Fewer flips went **true->false**: safety signals, data-loss incidents, warranty-decision cases, and already-escalated cases the baseline missed.

## Genuinely hard cases (spot-check first)

- `2294657` — "Gone from beard" + image: near-meaningless without the photo.
- `897701` — "who is hacking my camera": doesn't map to any of the 8 categories.
- `1458740` — "Everything is true!": no technical content without the linked image.
- `1551330` — vague reference to something unfixed in an update, plus an image.
- `1425142` — iCloud allegedly destroyed a work catalog, rep hung up: real data-loss stakes.
- `2110806` — iCloud storage forcing "defective" behavior + fee complaint: blends account/billing/feedback.
- `105396` — Spanish-language, ambiguous "should I install this patch" call.
- `208610` — bug persists even after a battery replacement was already tried.
- `2616618` / `1835143` — "shake/hit the phone" / "stuck in headphone mode": ambiguous hardware-vs-software.
- `1786985` / `1866211` / `617175` — smashed screen / non-charging new Mac / two defective MacBooks: clear `hardware_malfunction`, but false auto-handle is judgment, not a bright line.

## Underspecified taxonomy areas

Biggest tension: **`software_bug_after_update` vs. `hardware_malfunction`** for a keyboard/button/port that "doesn't respond" with no update mentioned — symptom type treated as more informative than the word "update" (~15 rows, e.g. `2302356`, `2757516`, `1123180`). Second: **`update_install_issue` vs. `how_to_question`** for "how do I downgrade/update" (`2078507`, `935951`, `1021156`) — taxonomy folds "asking how to update" into `update_install_issue`, but it reads equally well as generic how-to.
