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
- No fine-tuned classifier -- the "main system" classifier is a prompted LLM call
  (Hive by default; see `config.LLM_PROVIDER`), not a trained model. For a brand with
  80k+ labeled historical cases available, a
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
| trivial | 4.5% | 0.011 | 75.5% | 0.0 | 0.0 | 0.0 | n/a (constant reply) |
| simple (keyword) | 39.0% | 0.391 | 73.5% | 0.470 | 0.633 | 0.539 | 3.43 |
| **llm (main)** | **80.5%** | **0.746** | **81.5%** | **0.630** | **0.592** | **0.611** | **3.86** |

These numbers reflect the golden set after **every one of the 200 labels received a
genuine human decision** (see the inter-rater paragraph below and decision log #17/#18/#20
for exactly how). The number moved twice as ground truth got more reviewed, each time as
a byproduct of fixing labels, not tuning the model: 77.5% intent accuracy (single
unreviewed AI pass) -> 81.5% (after the 43-case human adjudication) -> **80.5%** (after
the remaining 157 cases also received a human decision -- 134 confirmed/corrected against
AI consensus, 23 more merged in from the independent blind pass). It went up, then down
slightly; the report says so either way, because that's the point of tracking this at
all. The main system still roughly doubles the simple baseline's intent accuracy and
macro-F1. Two numbers need immediate context, though (see "what's misleading" for the
full list):

- **Trivial's 75.5% escalation "accuracy" is a base-rate artifact**, not a capability:
  75.5% of the golden set is gold-labeled `auto_handle=true`, so a policy of "always
  auto-handle, no logic at all" scores 75.5% while having 0 precision/recall on the
  escalate class -- i.e. it would auto-send a reply to every one of the 49 cases (24.5%)
  that a human said needed review, including the safety-relevant case described in
  failure mode #1 below. Escalation accuracy alone is not a safe headline metric; the
  escalate-class F1 is the number that actually matters here.
- **The LLM judge is measurably more lenient than a real human scorer**: on the 40-case
  blind calibration subset, scored by Varun with no visibility into the judge's own
  scores, mean human score was 3.35 vs. mean judge score 3.975 -- a ~0.6-point inflation
  on a 5-point scale (`reports/metrics.json` -> `judge_human_agreement`, and see #4
  below). Read `judge_mean_overall_score` as "the judge's opinion," not "reply quality"
  directly.

**Inter-rater reliability, and how the golden set became 200/200 human-reviewed**: an
independent blind second AI pass over the full 200-case golden set agreed with the
original primary pass on 157/200 (78.5%) of cases (intent Cohen's kappa 0.799,
escalation kappa 0.781 -- `reports/ai_pass_agreement_full200.json`). From there, every
label got a human decision through three different review depths (full breakdown in
`data/LABELING_GUIDE.md`): (1) the 43 disagreement/ambiguous cases were personally
adjudicated by Varun with a written case-specific rationale each
(`data/human_adjudication_43cases.csv`); (2) a 30-case subset was independently
blind-labeled from scratch, no AI labels visible at all
(`data/golden_human_blind_30.jsonl`, 7 of these overlap with the 43); (3) the remaining
134 cases were reviewed against the AI consensus label (both AI passes had already
agreed on these) and confirmed or corrected, each with a specific written reason
(`data/human_review_remaining_134cases.csv` -- 131 confirmed, 3 corrected). The blind
30-case pass also gives this project's only genuine **human-vs-AI** Cohen's kappa,
computed before those labels were merged into the master set: 80% exact / kappa 0.69
against the original primary AI labels, and 80% exact / kappa 0.70 against an older,
independently-generated 30-case AI pass (`reports/human_vs_ai_agreement.json`). Both
land close to the AI-vs-AI agreement rate itself (78.5%), a reassuring result -- an
independent human disagrees with this project's AI labeling about as often as two AI
passes disagree with each other, not more. **One anomaly is disclosed rather than
used**: that same 30-case blind pass also agreed 100% (30/30, both fields) with a
*third* AI pass (`data/ai_blind_secondpass_full200.jsonl`) -- a rate inconsistent with
the ~80% agreement against the other two independent AI passes on the identical 30
cases. That comparison is excluded from the reported kappa above for exactly this
reason (see decision log #18). **Judge-vs-human agreement**, genuine, on the 40-case
calibration subset: 40% exact match, 77.5% within one point, quadratic-weighted kappa
0.32 ("fair"), Spearman rho 0.37 -- see #4 below. Full methodology:
`data/LABELING_GUIDE.md`.

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
   (`reports/metrics.json`) shows 5 of 94 true `software_bug_after_update` cases
   predicted as `hardware_malfunction` -- the largest single confusion cell. Example
   (case `1835143`): *"iPhone 6s+ turned into Headphone mode, no headphone inserted, BT
   off, restart didnt help. Speaker works in phone calls."* -- no update mentioned, so
   the model reasonably reads it as a hardware/speaker fault, but the gold label treats
   this as a software state bug given the symptom pattern. This is a genuinely hard case
   for any classifier working from text alone (`data/LABELING_NOTES.md` flags this exact
   case, and case `724019`, as ambiguous hardware-vs-software calls; `724019` was in fact
   one of the 43 human-adjudicated cases and its gold label was flipped to
   `hardware_malfunction` on review, which is itself evidence of how genuinely
   borderline this class boundary is).
4. **The LLM judge is measurably more lenient than a real human scorer**, and agreement
   is weaker than the headline number suggests: quadratic-weighted kappa 0.32 ("fair,"
   not "good"), only 40% exact match, though 77.5% land within 1 point and the
   correlation direction is right (Spearman rho 0.37). The judge's mean (3.975) sits
   ~0.6 points above the genuine human mean (3.35) on the same 40 replies
   (`data/REVIEW_3_blind_40_judge.csv`, scored blind to the judge's own output).
   Concretely: case `811638` (a payment-failure/iTunes-sign-in issue) got the generic
   reply *"We'd be happy to help. Please DM us with your iOS version and the error
   message you're seeing"* -- the judge scored it 5/5, the human scorer 2/5, because the
   reply never engages with the actual payment/sign-in problem and the judge's
   `actionability` dimension rewards "customer knows to DM" even when the real question
   went unanswered. This pattern (judge 4-5, human 2) repeats across several of the
   generic-DM-request replies (`184501`, `1458740`, `897701`). **Any judge-only quality
   claim in this report should be discounted by roughly this much.**
5. **The simple baseline's `complaint_feedback` catch-all overstates how often that
   intent is real.** The keyword baseline defaults to `complaint_feedback` whenever no
   rule fires, which is why it was capturing ~74% of raw eval-pool traffic before golden-
   set sampling was deliberately capped to counteract it (see `scripts/02_sample_golden.py`).
   Against the actual gold labels, only 9/200 (4.5%) of the golden set is genuinely
   `complaint_feedback`. This isn't a subtle finding, but it's the clearest evidence that
   the "simple" tier is a real baseline and not a strawman: its 40.0% intent accuracy is
   earned despite this bias, not because of it, since the golden set was specifically
   built to not reward the catch-all.

## 4. What is misleading about my headline number

This section is mandatory, and here is the honest list for this project:

1. **80.5% intent accuracy is not a traffic-weighted number.** Golden-set sampling was
   deliberately capped at 35/stratum (by keyword-predicted intent) specifically to avoid
   the keyword baseline's catch-all bucket dominating the set (see
   `scripts/02_sample_golden.py`). The corrected gold labels ended up concentrated in
   `software_bug_after_update` anyway (94/200 = 47%) -- which the `llm` tier handles
   well (82/94 = 87.2% recall on that class per the confusion matrix) -- so the headline
   number is somewhat flattered by the golden set's actual composition, not purely by
   sampling design. A traffic-weighted number, if the true intent mix differs from this
   golden set's, could look meaningfully different.
2. **Every one of the 200 golden labels now carries a genuine human decision, but not
   all at the same review depth -- read the breakdown before treating this as one
   uniform claim.** 43/200 (21.5%) were personally adjudicated case-by-case after two AI
   passes disagreed or flagged ambiguity (`data/human_adjudication_43cases.csv`); 30/200
   (with 7 overlapping the 43) were independently blind-labeled from scratch with no AI
   labels visible at all (`data/golden_human_blind_30.jsonl`); the remaining 134/200 were
   reviewed against an AI-consensus label (both independent AI passes had already agreed)
   and confirmed or corrected -- 131 confirmed, 3 corrected
   (`data/human_review_remaining_134cases.csv`). That last category is a real human
   decision with a specific written reason per case, but it is *review-of-a-suggestion*,
   not blind labeling -- a materially easier task than the 30-case blind pass, and the
   low 3/134 correction rate should be read in that light rather than as "97.8% of AI
   labels were already perfect." The one genuinely blind human-vs-AI comparison in this
   project (the 30-case subset, scored *before* being merged into the master set) gives
   80% exact / kappa 0.69-0.70 against two independently-generated AI passes -- reassuringly
   close to the 78.5% AI-vs-AI agreement rate itself, but that comparison covers 15% of
   the golden set, not all of it. **One important caveat on that same 30-case file**: it
   also showed 100% (30/30) agreement against a *third* AI pass, a rate inconsistent with
   its ~80% agreement against the other two AI passes on the identical cases. That
   specific comparison is disclosed but excluded from the reported kappa above, since a
   rate that anomalous is more likely to reflect some non-independence in how that file
   was produced than genuine blind labeling -- see decision log #18.
3. **The judge-human agreement numbers are now genuine** (`reports/judge_calibration_template.jsonl`'s
   `human_overall_score_1to5` was scored by Varun, blind to the judge's own scores --
   `data/REVIEW_3_blind_40_judge.csv`). Result: a fair-not-good kappa (0.32) and a
   ~0.6-point leniency gap between judge (3.975) and human (3.35) scores on the same 40
   replies (see failure mode #4) -- somewhat smaller than an earlier AI-proxy estimate of
   this same gap (~0.9 points), but the direction and existence of the gap holds up under
   real human scoring. LLM judges are known to skew lenient; this project's own judge is
   no exception.
4. **Escalation precision/recall on 200 examples has wide uncertainty**, especially for
   the minority "escalate" class (49/200 = 24.5% gold-labeled base rate, up from an
   earlier 18.5% once the 43-case human adjudication corrected several under-escalated
   labels). The `llm` tier's escalation precision (0.630) means roughly 4 in 10 of its
   escalations are cases a human wouldn't have flagged -- costly in reviewer time,
   though the failure-mode analysis suggests the more dangerous error (auto-handling
   something that should have escalated) is under-counted by this metric, since it only
   sees cases where escalation *should* have happened per gold labels, not cases where a
   *specific, novel* risk phrase (like "burned and shocked") wasn't yet in the keyword
   list at all.
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

1. **Get a genuine human-vs-human kappa, not just human-vs-AI.** All 200 golden labels
   now carry a human decision (decision log #17/#18/#20), and the 30-case blind subset
   gives a real human-vs-AI kappa (~0.69-0.70), but every human decision in this project
   was made by one person (Varun) working from one rubric. A second independent human
   relabeling the same 30-case subset, blind to both the AI labels and Varun's labels,
   would answer the one open question this report can't yet answer: whether that ~80%
   agreement reflects the AI converging on the right answer, or two different-but-
   equally-plausible readings of ambiguous rubric edge cases that a second human might
   also disagree with. It would also stress-test whether the 134-case "review a
   consensus label" pass (materially easier than blind labeling, see "what's misleading"
   #2) would have looked different if done blind instead.
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
9. **Calibrate confidence instead of trusting it raw**: `llm_classifier`'s confidence
   is self-reported by the same call that produced the label, and nothing here checks
   whether "0.8" actually means ~80% correct. Before using it as an escalation input
   (as `escalation.decide` currently does via `CONFIDENCE_FLOOR`), bucket golden-set
   predictions by predicted confidence and check observed accuracy per bucket; if it's
   not well-calibrated, drop it as a safety signal and lean on retrieval similarity and
   the rule-based checks instead.
10. **Move retrieval from TF-IDF to embeddings.** `CaseRetriever` is lexical
    (`TfidfVectorizer`, `stop_words="english"`), so it structurally misses paraphrases
    and can't handle non-English text at all. A hybrid approach -- TF-IDF for a fast
    top-20, then a sentence-embedding rerank to top-3 -- would likely fix a chunk of
    the "not grounded" failures without discarding the cheap lexical pass entirely.
11. **Add a run manifest.** Predictions are cached and resumed by `case_id` alone
    (see resume logic in `03_run_pipeline.py`/`04_run_judge.py`), with nothing tying a
    cached row to the prompt/model/threshold version that produced it. A
    `run_manifest.json` per run (git SHA, `LLM_PROVIDER`/model, prompt text hash,
    dataset hashes, thresholds, timestamp) plus a `run_id` on each record would make
    stale-cache bugs impossible instead of just unlikely.
12. **Basic test suite + CI.** There are currently no automated tests. At minimum:
    unit tests for `escalation.decide`'s branches, the keyword classifier's rule
    order, `retrieval.CaseRetriever`'s similarity floor behavior, and a malformed-JSON
    fallback path in `llm_client`; wired into GitHub Actions as a no-API smoke test on
    every push.

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
10. **A single model is used for classification, reply generation, AND judging**
    (`hive/vision-language-model` for the reported headline numbers; `gemini-flash-lite-latest`
    was used during earlier development -- see decision log #15). Cheaper and simpler
    to reproduce than mixing models, at the cost of a judge that may share the
    classifier/generator's blind spots (a same-family-judge risk, distinct from the
    human-agreement caveat in "what's misleading" #3).
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
14. **Golden-set and judge-calibration labels were initially produced by an AI
    assistant reading text directly, not humans**, and this was disclosed rather than
    presented as genuine independent human labeling -- see `data/LABELING_GUIDE.md`.
    (Superseded by decision log #17/#18/#20: all 200/200 golden labels now carry a
    genuine human decision, at three different review depths; see "what's misleading"
    #2/#3 for the current, precise breakdown.)
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
17. **43/200 golden labels were personally re-adjudicated by Varun after a second,
    independent, blind AI pass was run over the full golden set specifically to surface
    disagreements.** Process: (a) a fresh AI pass read only `case_id`+`customer_text`
    for all 200 cases, blind to the primary pass's labels
    (`data/ai_blind_secondpass_full200.jsonl`); (b) it agreed with the original primary
    pass on 157/200 (kappa 0.799 intent, 0.781 escalation --
    `reports/ai_pass_agreement_full200.json`, frozen against
    `data/golden_ai_primary_pre_adjudication.jsonl` so the comparison stays reproducible
    even after step (c) edits `golden.jsonl`); (c) the 43 disagreement/ambiguous cases
    were handed to Varun with both AI passes' calls and rationale, and he made the final
    decision on each with his own written reasoning
    (`data/human_adjudication_43cases.csv`) -- siding with the fresh pass on 32, the
    original draft on 2, both agreeing already on 8, and neither on 1 (case `1861359`,
    judged more serious than either AI call). This is disclosed precisely as what it is
    -- 21.5% of the golden set genuinely human-decided, 78.5% AI-confirmed-by-agreement
    -- rather than rounded up to "human-labeled," per "what's misleading" #2. An earlier
    attempt at this (a first CSV where a human column was auto-filled to match the AI
    draft with templated notes on ~98% of rows) was caught and explicitly discarded
    rather than used, precisely because it would have misrepresented AI output as human
    review.
18. **Genuine human labeling was added for a 30-case subset and 40-case judge
    calibration, and one anomalous result was found and excluded rather than reported.**
    Varun independently blind-labeled 30 golden-set cases from scratch
    (`data/golden_human_blind_30.jsonl`, no AI labels visible) and blind-scored 40
    drafted replies for the judge calibration (`data/REVIEW_3_blind_40_judge.csv`, no
    judge scores visible). The judge-calibration numbers are used as-is (genuine
    40%/kappa 0.32/0.6-point leniency gap). The 30-case labeling agreed with two
    independent AI passes at a believable ~80% (kappa 0.69-0.70) each, consistent with
    the 78.5% AI-vs-AI agreement rate -- but also agreed 100% (30/30, both fields) with
    a third specific AI pass, a rate statistically inconsistent with the other two
    comparisons on the identical cases. Asked directly, the labeler confirmed the work
    was done independently; the number is disclosed here anyway and excluded from the
    reported kappa in section 2 and "what's misleading" #2, because a result this
    improbable would undermine the report's credibility more than omitting it,
    regardless of cause. This mirrors decision log #17's discarded first attempt: when a
    human-labeling result looks too clean, the right move in this project has
    consistently been to say so rather than use it.
19. **A second external review (post-submission-draft) confirmed the priority order of
    "what I'd do next"** -- human-label validation, a faithfulness gate, and a dedicated
    safety classifier as the top three -- and surfaced three items not yet written down:
    confidence calibration, embedding-based retrieval, and run manifests for cache
    safety (now items 9-11 above). Its other suggestions (agent inbox/webhook, PII
    redaction pipeline, multi-language routing infra) were left out of "what I'd do
    next" as out of scope for a take-home's one-week horizon rather than incorporated,
    to avoid turning an evaluation project into an open-ended platform build.
20. **The remaining 157/200 golden labels were also brought to a genuine human
    decision, closing the golden set to 200/200 -- and a process bug in doing so was
    caught by my own sanity check and fixed before being reported.** The 134 cases
    where both AI passes had already agreed were reviewed by Varun against that
    consensus label, each with a specific written reason -- 131 confirmed, 3 corrected
    (`data/human_review_remaining_134cases.csv`). While wiring this in, a sanity check
    (counting rows with a human marker in their `labeler` field) found only 177/200
    instead of the expected 200/200: the 30-case blind-labeling pass had only ever been
    used to compute the human-vs-AI kappa in decision log #18, never merged back into
    `golden.jsonl` itself, so the 23 cases in that subset that weren't also in the
    43-case adjudication still held pure-AI values. Fixed by merging those 23 decisions
    into the master set before recomputing anything. Net effect on headline numbers:
    intent accuracy moved from 81.5% to 80.5%, escalation numbers unchanged (see section
    2's revised table) -- disclosed as a further, real shift from more ground-truth
    review, not something to chase back upward.
