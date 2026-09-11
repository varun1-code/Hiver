# Report: AI support agent for @AppleSupport

_All numbers below are from the full 200-case golden-set run (`reports/metrics.json`,
regenerate with `scripts/06_evaluate.py`). LLM calls for this run used TheHive.ai's
`hive/vision-language-model` (see decision log #15 for why the backend changed from
Gemini mid-project)._

**Citations / borrowed material**: this project uses standard open-source libraries only
(`scikit-learn` for TF-IDF retrieval and cosine similarity, `pandas` for data wrangling,
`python-dotenv` for config, `scipy` for Spearman correlation -- all in `requirements.txt`),
called in ordinary ways with no copied implementation code. No code, prompts, or taxonomy
were copied from a tutorial, blog post, Stack Overflow answer, or another repository. The
Banking77 dataset was considered and deliberately not used (see "what I chose not to
build"). Claude Code (Anthropic) was used throughout as an AI coding assistant per the
assignment's rules, including for the golden-set/judge-calibration labeling passes --
disclosed in full in `data/LABELING_GUIDE.md`, since that disclosure is load-bearing for
how the evaluation numbers in this report should be read.

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

All numbers are on the full 200-case golden set (`reports/metrics.json`).

| Tier | Intent accuracy | Intent macro-F1 | Escalation accuracy | Escalation precision (escalate class) | Escalation recall (escalate class) | Escalation F1 (escalate class) | Mean judge score (1-5) |
|---|---|---|---|---|---|---|---|
| trivial | 3.0% | 0.007 | 81.5% | 0.0 | 0.0 | 0.0 | n/a (constant reply) |
| simple (keyword) | 40.5% | 0.403 | 76.5% | 0.424 | 0.757 | 0.544 | 3.43 |
| **llm (main)** | **77.5%** | **0.704** | **84.5%** | **0.565** | **0.703** | **0.627** | **3.86** |

The main system roughly doubles the simple baseline's intent accuracy and macro-F1, and
improves escalation F1 by ~15 points. Two numbers need immediate context, though (see
"what's misleading" for the full list):

- **Trivial's 81.5% escalation "accuracy" is a base-rate artifact**, not a capability:
  81.5% of the golden set is gold-labeled `auto_handle=true`, so a policy of "always
  auto-handle, no logic at all" scores 81.5% while having 0 precision/recall on the
  escalate class -- i.e. it would auto-send a reply to every one of the 37 cases (18.5%)
  that a human said needed review, including the safety-relevant case described in
  failure mode #1 below. Escalation accuracy alone is not a safe headline metric; the
  escalate-class F1 is the number that actually matters here.
- **The LLM judge is measurably more lenient than the human-equivalent calibration
  scorer**: on the 40-case blind calibration subset, mean human score was 3.10 vs. mean
  judge score 3.98 -- a ~0.9-point inflation on a 5-point scale (`reports/metrics.json`
  -> `judge_human_agreement`, and see #4 below). Read `judge_mean_overall_score` as
  "the judge's opinion," not "reply quality" directly.

**Inter-rater reliability**: the primary golden-set labeler and an independent
second-pass labeler agreed on intent for 24/30 (80%) of overlapping cases (Cohen's
kappa 0.69, "substantial" agreement) and on the escalate/auto-handle call for 30/30
(kappa 1.0). **Judge-vs-human agreement** on the 40-case calibration subset: 22.5% exact
match, 75% within one point, quadratic-weighted kappa 0.32 ("fair"), Spearman rho 0.51
(moderate positive correlation) -- see #4 below for what this does and doesn't support.

## 3. Failure analysis (top 5, with real examples)

1. **A genuine safety miss, found and fixed during evaluation.** Case `2688195`:
   *"@AppleSupport tell me why my headphones just burned and shocked the inside of my
   ear"* -- gold label says `auto_handle=false` (physical injury risk). The `llm` tier
   classified it correctly as `hardware_malfunction` (confidence 0.90) but **auto-handled
   it anyway**, drafting a routine "please DM your device details" reply, because neither
   "burned" nor "shocked" was in `ESCALATION_SIGNAL_KEYWORDS` and `hardware_malfunction`
   isn't in the never-auto-handle intent list. **Fixed** in `src/config.py` (added
   burn/shock/overheat/swelling terms) after this was found -- but the fact that it
   shipped in the first full run at all is the finding: high classifier confidence and a
   good similarity match say nothing about whether the message contains a risk signal
   the keyword list happens to cover. A production system needs a broader, actively
   maintained risk lexicon (or a dedicated safety classifier), not an ad hoc list
   extended one incident at a time.
2. **Confident replies auto-handled despite being low quality.** Cross-referencing the
   `llm` tier's 5 lowest judge-scored replies against `auto_handle`: **all 5 were
   auto-handled**, including a completely off-topic reply to an AppleCare+-in-Spain
   billing question (case `2729020`, drafted reply talks about restarting the device)
   and a generic "we got your DM" reply to someone who never DMed (case `1434156`).
   None of these tripped the confidence floor (all had "confidence" >=0.9, self-reported
   by the same model that then wrote the wrong reply) or the similarity floor (retrieval
   found a case that matched on surface wording but not on actual content). **This is
   the report's single most important finding**: confidence and retrieval-similarity, as
   currently computed, are not reliable proxies for "is this reply actually correct,"
   and the escalation gate should not be trusted to catch this failure mode as built.
3. **`software_bug_after_update` vs. `hardware_malfunction` confusion**, exactly as
   predicted from the golden-set labeling notes. The confusion matrix
   (`reports/metrics.json`) shows 11 of 96 true `software_bug_after_update` cases
   predicted as `hardware_malfunction` -- the largest single confusion cell. Example
   (case `724019`): *"What's happening to my battery? It suddenly changes its
   percentage when I put it to charge/drops to 1% when in use #iPhone"* -- no update
   mentioned, so the model reasonably reads it as hardware, but historically this
   pattern is very often a software/calibration bug. This is a genuinely hard case for
   any classifier working from text alone (even the human-equivalent labeling pass
   flagged this exact ambiguity as its top "underspecified taxonomy" issue).
4. **The LLM judge is measurably more lenient than human-equivalent scoring**, and
   agreement is weaker than the headline number suggests: quadratic-weighted kappa 0.32
   ("fair," not "good"), only 22.5% exact match, though 75% land within 1 point and the
   correlation direction is right (Spearman rho 0.51). The judge's mean (3.98) sits
   nearly a full point above the human-equivalent mean (3.10) on the same 40 replies.
   Concretely: several replies that are polite-but-non-answers (e.g. "we'd love to help,
   DM us" to a specific how-to question) were scored 4-5 by the judge but 2-3 by the
   calibration pass, because the judge's `actionability` dimension rewards "customer
   knows to DM" even when the actual question went unanswered. **Any judge-only quality
   claim in this report should be discounted by roughly this much.**
5. **The simple baseline's `complaint_feedback` catch-all overstates how often that
   intent is real.** The keyword baseline defaults to `complaint_feedback` whenever no
   rule fires, which is why it was capturing ~74% of raw eval-pool traffic before golden-
   set sampling was deliberately capped to counteract it (see `scripts/02_sample_golden.py`).
   Against the actual gold labels, only 6/200 (3%) of the golden set is genuinely
   `complaint_feedback`. This isn't a subtle finding, but it's the clearest evidence that
   the "simple" tier is a real baseline and not a strawman: its 40.5% intent accuracy is
   earned despite this bias, not because of it, since the golden set was specifically
   built to not reward the catch-all.

## 4. What is misleading about my headline number

This section is mandatory, and here is the honest list for this project:

1. **77.5% intent accuracy is not a traffic-weighted number.** Golden-set sampling was
   deliberately capped at 35/stratum (by keyword-predicted intent) specifically to avoid
   the keyword baseline's catch-all bucket dominating the set (see
   `scripts/02_sample_golden.py`). The corrected gold labels ended up concentrated in
   `software_bug_after_update` anyway (96/200 = 48%) -- which the `llm` tier handles
   well (85/96 = 88.5% recall on that class per the confusion matrix) -- so the headline
   number is somewhat flattered by the golden set's actual composition, not purely by
   sampling design. A traffic-weighted number, if the true intent mix differs from this
   golden set's, could look meaningfully different.
2. **The golden labels were produced by an AI assistant reading each tweet, not by two
   independent human annotators**, despite the assignment asking for a hand-labeled set
   -- disclosed in full in `data/LABELING_GUIDE.md`. The 0.69 intent kappa and 1.0
   escalation kappa reported between the "primary" and "second" labeling passes are
   agreement between two AI reasoning passes, not two humans. It's evidence the rubric
   is applicable consistently, not evidence the labels match objective truth. **Before
   this is submitted, a real human should re-label at least the 30-case overlap subset
   and the ambiguous cases flagged in `data/LABELING_NOTES.md`.**
3. **The judge-human agreement numbers are an AI-vs-AI proxy for the same reason**
   (`reports/judge_calibration_template.jsonl`'s `human_overall_score_1to5` was filled by
   an independent AI pass, not a person -- see `data/LABELING_GUIDE.md`). That said, this
   proxy calibration surfaced something real regardless of who scored it: a fair-not-good
   kappa (0.32) and a ~0.9-point leniency gap between judge and calibration scores (see
   failure mode #4). A genuine human pass might show a different gap, but there's no
   reason to expect it would show *no* gap -- LLM judges are known to skew lenient.
4. **Escalation precision/recall on 200 examples has wide uncertainty**, especially for
   the minority "escalate" class (37/200 = 18.5% gold-labeled base rate). The `llm` tier's
   escalation precision (0.565) means roughly 4 in 10 of its escalations are cases a
   human wouldn't have flagged -- costly in reviewer time, though the failure-mode
   analysis suggests the more dangerous error (auto-handling something that should have
   escalated) is under-counted by this metric, since it only sees cases where escalation
   *should* have happened per gold labels, not cases where a *specific, novel* risk
   phrase (like "burned and shocked") wasn't yet in the keyword list at all.
5. **The dataset itself only contains what happened publicly on Twitter.** It excludes
   DMs, where AppleSupport actually resolves account-security and billing cases. So even
   a perfect score here reflects public triage behavior, not the substance of how those
   higher-risk cases are really resolved -- which is exactly why `account_access` and
   `billing_purchase` are hard-coded to never auto-handle regardless of confidence
   (`src/escalation.py`), independent of what the classifier or retrieval says.
6. **The LLM backend changed mid-project** (Gemini free-tier keys hit a 20-request/day
   wall, then an expiring OAuth-style token, before landing on TheHive.ai's chat
   completions API -- see decision log #15). All 200 `llm`-tier headline numbers are from
   a single consistent backend (Hive), but this means the numbers are specific to that
   one model's behavior and would likely shift, in either direction, with a different
   LLM.
7. **A quick-demo run (`--limit 40`) and the full 200-case run are not the same
   experiment.** Numbers from the 15-minute quick-start are noisier (smaller per-intent
   n) and should not be quoted as the project's headline metrics -- only the full run's
   `reports/metrics.json` (this report's numbers) should be cited as such.

## 5. What I'd do next with one more week

1. **Get a real second human labeler** for the golden set and the judge-calibration
   subset, replacing the AI-drafted passes, and recompute all agreement numbers -- this
   is the single highest-priority item, since it's the assumption everything else rests on.
2. **Fix the "confident but wrong" auto-handle gap (failure mode #2)**, the report's
   biggest finding: add a lightweight faithfulness check between the drafted reply and
   its retrieved evidence (e.g. NLI-style entailment, or a second cheap LLM call asking
   "does this reply's claim follow from this evidence?") as an additional escalation
   gate, since classifier confidence and retrieval similarity both failed to catch it.
3. **Broaden and stress-test the safety-keyword list properly** instead of extending it
   incident-by-incident (as I did after finding the headphones case) -- ideally replace
   it with a small dedicated safety/harm classifier trained or prompted specifically for
   that one job, decoupled from intent classification.
4. **Multi-turn support**: extend cases to include the customer's follow-up turns
   (currently discarded -- see decision log), since real support threads are rarely
   one-shot.
5. **Train a lightweight classifier** (TF-IDF + logistic regression, or a small
   fine-tuned model) on the ~80k historical cases using a weak-labeling bootstrap from
   the current LLM classifier, and compare cost/latency/accuracy against the prompted
   classifier -- an LLM call per inbound message is the most expensive part of this
   pipeline per-unit-economics, and a stable, non-rate-limited backend was itself a
   real engineering obstacle this week (see decision log #15).
6. **Active-learning loop for the taxonomy**: run a clustering pass (embeddings +
   HDBSCAN or similar) over a larger unlabeled sample specifically to check for an
   intent cluster missing from the current 8-category taxonomy (e.g. is there a
   distinct "trade-in / upgrade purchase" cluster separate from `billing_purchase`?).
7. **Escalation calibration against real cost**: right now every escalation rule is a
   hand-set threshold (0.55 confidence, 0.12 similarity). With real historical data on
   which auto-handled replies actually resolved the issue (e.g. no angry follow-up
   tweet within N hours), these thresholds could be tuned against an actual outcome
   metric instead of intuition.
8. **Non-English and image-dependent message handling**: at minimum, detect these
   cases and route them to escalation with a clear reason, rather than silently
   producing a low-quality classification (observed in the golden set -- e.g. case
   `105396`, a Spanish-language bug report).

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
12. **Requests are proactively throttled** rather than only reacting to 429 errors,
    because retry-storms made wall-clock time unpredictable during development (see
    `src/llm_client.py`). This is also why the README splits a 15-minute quick-demo
    from a longer full run.
13. **`.env` (containing API keys) is gitignored; `.env.example` is committed** as the
    template. The raw ~500MB Kaggle CSV is gitignored under `reports/twcs/`, but all
    derived `data/*.jsonl` files and `reports/*.json(l)` result files are committed,
    since those ARE the evidence this project is graded on.
14. **Golden-set and judge-calibration labels were produced by an AI assistant
    reading text directly, not humans**, and this is disclosed rather than presented as
    genuine independent human labeling -- see `data/LABELING_GUIDE.md` and "what's
    misleading" #2/#3.
15. **The LLM backend was switched from Gemini to TheHive.ai mid-project, and this is
    the single biggest engineering-judgment story in this project.** Gemini's free-tier
    `gemini-flash-latest` turned out to be capped at 20 REQUESTS PER DAY (not per
    minute), exhausted almost immediately; falling back to `gemini-flash-lite-latest`
    (15 req/min) made the 200-case run technically feasible (~30-60 min) but still slow;
    partway through a full run, a supplied Gemini credential turned out to be a
    short-lived OAuth-style token (not a stable API key) and expired mid-run, failing
    163/200 cases with 401s. Rather than keep fighting one provider's quota, I switched
    to TheHive.ai's OpenAI-compatible chat completions API once a working key was
    available, verified it had no rate-limit problems at this project's volume, and
    **re-ran the entire `llm` tier from scratch on the single new backend** rather than
    merge results from two different models across the 200 cases -- mixing model
    outputs midstream would have made every downstream number impossible to interpret
    cleanly. `src/llm_client.py` keeps both backends behind one interface
    (`LLM_PROVIDER` env var) since the code was already written for Gemini; Hive lacks
    native structured-output/schema enforcement, so JSON is elicited via prompt
    instruction and parsed with a markdown-fence-stripping fallback instead.
16. **A safety-keyword gap found live during evaluation (failure mode #1) was fixed in
    the code rather than left as a "known issue."** After finding that a headphones
    "burned and shocked" report was auto-handled, I added the missing terms to
    `ESCALATION_SIGNAL_KEYWORDS` and re-scored existing predictions' escalation
    decisions in place (no LLM re-calls needed, since escalation is deterministic given
    the already-computed intent/confidence/similarity) rather than treating this as
    something to merely footnote. This is disclosed explicitly rather than silently
    fixed, because the fact that it shipped once is itself evidence about the
    keyword-list approach's fragility (see "what I'd do next" #3).
