# Report: AI support agent for @AppleSupport

_Status: scaffolded with real pipeline architecture and the golden-set labeling story;
numeric results below are placeholders (`TBD`) until `scripts/06_evaluate.py` finishes
running against the full 200-case golden set (blocked on Gemini free-tier rate limits --
see README). This file will be updated with final numbers once that run completes._

## 1. Problem framing

**What "good" means for this agent, concretely:**
- **Classification**: high enough accuracy on the intents that drive different actions
  (billing vs. account vs. routine bug) that the escalation decision downstream is
  trustworthy. Perfect intent accuracy is not the bar -- *safe escalation given
  imperfect classification* is.
- **Reply drafting**: faithful to real historical AppleSupport behavior (never invents
  a troubleshooting step the brand doesn't actually use) over fluency. A boring,
  correct, on-brand reply beats a creative, wrong one.
- **Escalation**: near-zero false negatives on "should have escalated but didn't" for
  money/security/safety categories, even at the cost of some false positives (routine
  cases escalated unnecessarily). An over-cautious bot wastes agent time; an
  over-confident one damages trust and creates real liability (e.g. auto-replying to a
  billing dispute with a made-up refund promise).

**What I chose not to build:**
- No multi-turn conversation state / follow-up handling -- every case is treated as a
  fresh inbound message. Real support threads often go 3-5 turns; this only handles
  turn 1. (See "what I'd do next.")
- No fine-tuned classifier -- the "main system" classifier is a prompted Gemini call,
  not a trained model. For a brand with 80k+ labeled historical cases available, a
  fine-tuned or even a simple TF-IDF+logistic-regression classifier trained on
  historical replies (using reply content as a weak label source) would likely be
  cheaper and faster at inference than an LLM call, and is a natural next iteration.
- No unsupervised intent discovery (clustering) -- the 8-intent taxonomy was chosen
  from manual inspection of ~50k first-turn tweets, not derived statistically. This is
  faster to ship and easier to audit, but it means the taxonomy could be missing a real
  cluster of traffic (see "what's misleading").
- No handling of non-English tweets, image-only complaints, or tweets that only make
  sense with an attached screenshot -- these were observed in the data (see
  `data/LABELING_NOTES.md` hard cases) and are explicitly out of scope for v1.
- Banking77 was not used. Its 77-intent taxonomy is for a banking chatbot; AppleSupport's
  actual failure modes (hardware, iOS updates, connectivity) don't map onto it, and
  importing an unrelated taxonomy would have been taxonomy-shopping rather than
  data-driven design.

## 2. Results vs. baselines

_TBD -- populate from `reports/metrics.json` after the full run._

| Tier | Intent accuracy | Intent macro-F1 | Escalation precision (escalate class) | Escalation recall (escalate class) | Mean judge score (1-5) |
|---|---|---|---|---|---|
| trivial | | | | | n/a (constant reply) |
| simple | | | | | |
| llm (main) | | | | | |

## 3. Failure analysis (top 5, with real examples)

_TBD -- to be filled from actual `llm` tier misclassifications and low judge-score cases
in the full run. Expected candidates based on the golden-set labeling pass
(`data/LABELING_NOTES.md`) and pipeline smoke-testing:_

1. **software_bug_after_update vs. hardware_malfunction confusion** -- symptoms like
   "keyboard unresponsive" or "screen not responding" are ambiguous between a software
   regression and a physical fault when the customer doesn't explicitly name an update.
   Hypothesis: both the keyword baseline and the LLM classifier will show this as their
   single largest confusion pair (see `data/LABELING_NOTES.md`, ~15 rows where even the
   human-equivalent labeling pass found this ambiguous).
2. **Over-reliance on the `complaint_feedback` catch-all in the simple baseline** -- the
   keyword baseline defaults to it whenever no rule fires, capturing 74% of raw eval-pool
   traffic (see `scripts/02_sample_golden.py` comments), vs. only 6/200 (3%) in the human
   -equivalent gold labels. This is the single clearest "simple baseline is not a real
   system" data point.
3. **Retrieval failing on rare intents** -- `account_access` and `billing_purchase` are
   under-represented in the reference pool relative to `software_bug_after_update`, so
   retrieval similarity is likely lower for these cases, which (correctly, by design)
   pushes them toward escalation via the similarity floor -- but also means the "simple"
   tier's template-copy reply is more likely to fall back to the generic message for
   exactly the categories where a specific answer matters most.
4. **Escalation over-triggering on profanity/anger without real risk** -- the *keyword*
   escalation-signal list risks conflating "angry customer" with "high-risk message."
   The human-equivalent labeling pass explicitly rejected this: profanity alone was not
   treated as an escalation trigger, while the code's escalation module currently has no
   sentiment-based rule (it only escalates on explicit risk keywords/phrases, low
   confidence, or low similarity) -- so this is a predicted *simple-baseline-only* failure
   mode via its fixed 0.70 confidence never tripping the confidence floor.
5. **Non-English / image-dependent tweets** -- several hard cases in the golden set
   (`data/LABELING_NOTES.md`) are only interpretable with an attached image or are in
   Spanish. The pipeline has no image or language handling, so these will likely produce
   low-confidence, low-relevance classifications and drafted replies -- worth checking
   whether the escalation logic's confidence floor actually catches them.

## 4. What is misleading about my headline number

This section is mandatory, and here is the honest list for this project:

1. **The golden set's intent distribution does not match real traffic.** Sampling was
   capped at 35/stratum specifically to avoid the keyword baseline's catch-all bucket
   dominating the set (see `scripts/02_sample_golden.py`). That means whatever intent
   -accuracy number comes out of this golden set is **not** a traffic-weighted accuracy;
   a system could score well here and still perform worse in production if its weak
   spot happens to be the most common real intent (which, per the corrected gold labels,
   is `software_bug_after_update` at 52% of the golden set -- so this particular risk is
   partially mitigated, but that's a property of how the correction happened to land,
   not something the sampling design guaranteed).
2. **The golden labels themselves were produced by an AI assistant reading each tweet,
   not by two independent human annotators**, despite the assignment asking for a
   hand-labeled set. This is disclosed in full in `data/LABELING_GUIDE.md`. Any
   agreement/kappa numbers reported against this golden set inherit whatever blind
   spots or systematic biases that single labeling process has -- an accuracy number
   against a flawed ground truth is not the same as an accuracy number against truth.
3. **The judge-human agreement number (if computed via the AI-drafted calibration
   pass rather than a genuine human pass) is an AI-vs-AI proxy, not evidence the judge
   agrees with a human.** See `reports/judge_calibration_template.jsonl` -- if
   `human_overall_score_1to5` was filled by an automated process rather than a person,
   the reported kappa/correlation measures self-consistency between two LLM calls, which
   is a much weaker claim than "the judge tracks human judgment."
4. **Escalation precision/recall on 200 examples has wide confidence intervals**,
   especially for the minority "escalate" class (~36/200 = 18% base rate per the gold
   labels). A handful of golden-set labeling disagreements on ambiguous cases (there are
   several -- see `data/LABELING_NOTES.md`) can move the reported precision/recall by
   several points. Report point estimates with this in mind, not as settled facts.
5. **The retrieval reference pool and the LLM's classification are not independent of
   the underlying dataset's own biases.** The Kaggle dataset only contains conversations
   that reached Twitter and got a public reply; it excludes DMs (where the *actual*
   account-security and billing resolution steps usually happen, since AppleSupport
   routes those off-platform). So even "success" here reflects public triage behavior,
   not the substance of how those higher-risk cases are actually resolved -- which is
   exactly why `account_access` and `billing_purchase` are hard-coded to never
   auto-handle regardless of confidence (see `src/escalation.py`).
6. **A quick-demo run (`--limit 40`) and the full 200-case run are not the same
   experiment.** Numbers from the 15-minute quick-start are noisier (smaller per-intent
   n) and should not be quoted as the project's headline metrics -- only the full run's
   `reports/metrics.json` should be cited as such.

## 5. What I'd do next with one more week

1. **Get a real second human labeler** for the golden set and the judge-calibration
   subset, replacing the AI-drafted passes, and recompute all agreement numbers.
2. **Multi-turn support**: extend cases to include the customer's follow-up turns
   (currently discarded -- see decision log), since real support threads are rarely
   one-shot.
3. **Train a lightweight classifier** (TF-IDF + logistic regression, or a small
   fine-tuned model) on the ~80k historical cases using a weak-labeling bootstrap from
   the current LLM classifier, and compare cost/latency/accuracy against the prompted
   Gemini classifier -- an LLM call per inbound message is the most expensive part of
   this pipeline per-unit-economics.
4. **Active-learning loop for the taxonomy**: run a clustering pass (embeddings +
   HDBSCAN or similar) over a larger unlabeled sample specifically to check for an
   intent cluster missing from the current 8-category taxonomy (e.g. is there a
   distinct "trade-in / upgrade purchase" cluster separate from `billing_purchase`?).
5. **Escalation calibration against real cost**: right now every escalation rule is a
   hand-set threshold (0.55 confidence, 0.12 similarity). With real historical data on
   which auto-handled replies actually resolved the issue (e.g. no angry follow-up
   tweet within N hours), these thresholds could be tuned against an actual outcome
   metric instead of intuition.
6. **Non-English and image-dependent message handling**: at minimum, detect these
   cases and route them to escalation with a clear reason, rather than silently
   producing a low-quality classification.

## 6. Decision log

1. **Brand: AppleSupport.** Highest-volume, cleanest-first-turn-reply structure among
   the candidate brands inspected (106,860 outbound replies; see
   `scripts/exploration/00_explore_full.py`).
2. **8-intent taxonomy chosen from manual EDA on the raw data, not Banking77 or
   unsupervised clustering.** Faster to ship, directly grounded in observed AppleSupport
   traffic, easy to audit -- but see "what I chose not to build" for the tradeoff.
3. **Escalation logic is rule-based, not LLM-decided**, even in the `llm` tier. The one
   decision with real downstream cost if wrong should be the most auditable, testable
   piece of the system, not an opaque model judgment (`src/escalation.py`).
4. **Escalation logic is shared across the `simple` and `llm` tiers.** This isolates
   what's actually being compared (classification + reply quality) instead of also
   varying the escalation policy, which would confound the baseline comparison.
5. **Retrieval index (reference pool) and golden/eval set are split by case before any
   retrieval happens, and this split is fixed at data-prep time**, not at eval time --
   so it's structurally impossible for retrieval to surface a golden case's own
   historical answer (`scripts/01_prepare_dataset.py`).
6. **Only first-turn customer messages are used as "cases."** Follow-up messages within
   an existing thread are out of scope for v1 (see "what I chose not to build").
7. **The trivial baseline always auto-handles (no escalation logic at all)**, rather
   than always escalating. This was chosen specifically so the report can show the
   escalation module's value directly: "the trivial baseline would send N replies to
   billing/account-security cases with zero human review; the shared escalation logic
   prevents that."
8. **The simple baseline is assigned a constant classifier confidence (0.70)**, purely
   so its output can flow through the same shared `escalation.decide()` function as the
   other tiers. This is disclosed in `src/pipeline.py` as an arbitrary constant, not a
   real confidence estimate.
9. **Golden-set sampling caps any single keyword-predicted-intent stratum at 35/200**,
   trading "matches raw traffic mix" for "computable macro-F1 across all 8 intents" --
   see "what's misleading" #1 for the cost of this choice.
10. **A single Gemini model (`gemini-flash-latest`) is used for classification, reply
    generation, AND judging.** Cheaper and simpler to reproduce than mixing models, at
    the cost of a judge that may share the classifier/generator's blind spots (a
    same-family-judge risk, distinct from the human-agreement caveat in "what's
    misleading" #3).
11. **The LLM-judge never sees the real historical AppleSupport reply**, only the
    customer message, the drafted reply, and (implicitly, via the drafted reply's own
    content) the retrieved evidence -- specifically to prevent the judge from just
    scoring "how close is this to the answer key" instead of genuine quality.
12. **Requests are proactively throttled to Gemini's free-tier 20 RPM limit** rather
    than only reacting to 429 errors, because retry-storms made wall-clock time
    unpredictable during development (see `src/llm_client.py`). This is also why the
    README splits a 15-minute quick-demo from a longer full run.
13. **`.env` (containing the API key) is gitignored; `.env.example` is committed** as
    the template. The raw ~500MB Kaggle CSV is gitignored under `reports/twcs/`, but
    all derived `data/*.jsonl` files and `reports/*.json(l)` result files are committed,
    since those ARE the evidence this project is graded on.
14. **Golden-set and judge-calibration labels were produced by an AI assistant
    reading text directly, not humans**, and this is disclosed rather than presented as
    genuine independent human labeling -- see `data/LABELING_GUIDE.md` and "what's
    misleading" #2/#3.
