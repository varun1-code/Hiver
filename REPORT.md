# Report: AI support agent for @AppleSupport

_All numbers below are from the full 200-case golden-set run (`reports/metrics.json`,
regenerate with `scripts/06_evaluate.py`). LLM calls used TheHive.ai's
`hive/vision-language-model` (Gemini was used during earlier development; see
`APPENDIX.md` decision log #15 for why the backend changed). This report is kept to the
assignment's length limit -- **`APPENDIX.md` has the full methodology, the complete
20-item decision log, and expanded detail behind every section here.**_

**Citations / borrowed material**: standard open-source libraries only (`scikit-learn`,
`pandas`, `python-dotenv`, `scipy` -- see `requirements.txt`), no copied implementation
code. Banking77 was considered and deliberately not used (see below). Claude Code
(Anthropic) was used throughout as an AI coding assistant per the assignment's rules,
including for the golden-set/judge-calibration labeling passes -- fully disclosed in
`data/LABELING_GUIDE.md`, since that disclosure is load-bearing for how the numbers
below should be read.

## 1. Problem framing

**What "good" means here**: high enough intent accuracy that the downstream escalation
decision is trustworthy (not perfect classification for its own sake); reply drafts
faithful to real historical AppleSupport behavior over cleverness; near-zero false
negatives on "should have escalated but didn't" for money/security/safety, even at the
cost of some false positives.

**What I chose not to build**: multi-turn conversation state (every case is a fresh
turn-1 message); a fine-tuned classifier (the main system uses a prompted LLM call
instead); unsupervised intent discovery (the 8-intent taxonomy came from manual EDA on
~50k tweets, not clustering); non-English or image-dependent message handling. Banking77
was rejected as a taxonomy source -- its banking-chatbot intents don't map onto
AppleSupport's actual failure modes (hardware, iOS updates, connectivity), and importing
it would have been taxonomy-shopping rather than data-driven design. Full rationale for
each in `APPENDIX.md` section 1.

## 2. Results vs. baselines

| Tier | Intent accuracy | Intent macro-F1 | Escalation accuracy | Escalation precision (escalate) | Escalation recall (escalate) | Escalation F1 (escalate) | Mean judge score |
|---|---|---|---|---|---|---|---|
| trivial | 4.5% | 0.011 | 75.5% | 0.0 | 0.0 | 0.0 | n/a |
| simple (keyword) | 39.0% | 0.391 | 73.5% | 0.470 | 0.633 | 0.539 | 3.43 |
| **llm (main)** | **80.5%** | **0.746** | **81.5%** | **0.630** | **0.592** | **0.611** | **3.86** |

The main system roughly doubles the simple baseline's intent accuracy and macro-F1.
**Trivial's 75.5% escalation "accuracy" is a base-rate artifact, not a capability**: it
would auto-send a reply to every one of the 49 cases (24.5%) a human said needed review,
including the safety-relevant case in failure mode #1 below -- escalate-class F1 is the
metric that actually matters. **The LLM judge is measurably more lenient than a real
human scorer**: on a 40-case blind calibration subset scored by Varun with no visibility
into the judge's scores, mean human score was 3.35 vs. judge 3.975 (~0.6-point
inflation; quadratic-weighted kappa 0.32, "fair" not "good"). This headline number also
moved twice as ground truth got more reviewed (77.5% -> 81.5% -> 80.5%, purely from
fixing labels, not tuning the model -- full trajectory in `APPENDIX.md`).

**Inter-rater reliability**: all 200 golden labels now carry a genuine human decision
(43 personally adjudicated, 30 independently blind-labeled from scratch, 134 reviewed
against an AI-consensus label -- three different depths, not one uniform claim; full
breakdown in `data/LABELING_GUIDE.md`). The one genuinely blind human-vs-AI comparison
(the 30-case subset) gives 80% exact / kappa 0.69-0.70 against two independent AI
passes -- close to the 78.5% AI-vs-AI agreement rate, a reassuring result. One anomaly
was found (that same subset hit 100% agreement against a third AI pass) and is
disclosed but **excluded** from the reported kappa as statistically implausible rather
than used (`APPENDIX.md` decision log #18).

## 3. Failure analysis (top 5, with real examples)

1. **A genuine safety miss, found and fixed during evaluation.** Case `2688195`: *"tell
   me why my headphones just burned and shocked the inside of my ear"* -- classified
   correctly as `hardware_malfunction` (confidence 0.90) but auto-handled anyway,
   because neither "burned" nor "shocked" was in the risk-keyword list. Fixed by
   extending the list -- but the fact it shipped once shows confidence and similarity
   say nothing about whether a message contains a risk signal the keyword list happens
   to cover.
2. **Confident replies auto-handled despite being low quality.** The 5 lowest
   judge-scored `llm`-tier replies were **all auto-handled**, including a completely
   off-topic reply to an AppleCare+-in-Spain billing question (case `2729020`). None
   tripped the confidence floor (all >=0.9 self-reported) or the similarity floor. **This
   is the single most important finding**: confidence and retrieval-similarity are not
   reliable proxies for "is this reply actually correct."
3. **`software_bug_after_update` vs. `hardware_malfunction` confusion**: 5 of 94 true
   `software_bug_after_update` cases predicted as `hardware_malfunction` -- the largest
   confusion cell. Example (case `1835143`): a phone going into headphone mode with no
   update mentioned -- genuinely hard for any text-only classifier.
4. **The LLM judge is measurably more lenient than a real human scorer** (see section
   2). Case `811638` got a generic "please DM your iOS version" reply that never
   engages with the actual payment/sign-in problem -- judge scored it 5/5, the human
   scorer 2/5, because the judge's `actionability` dimension rewards "customer knows to
   DM" even when the real question went unanswered.
5. **The simple baseline's `complaint_feedback` catch-all overstates how often that
   intent is real**: it captured ~74% of raw traffic (its fallback when no rule fires),
   but only 9/200 (4.5%) of the golden set is genuinely that intent -- the simple
   baseline's 39.0% accuracy is earned despite this bias, not because of it.

## 4. What is misleading about my headline number

1. **80.5% intent accuracy is not traffic-weighted.** Gold labels concentrated in
   `software_bug_after_update` (94/200 = 47%), which the `llm` tier handles well (87.2%
   recall) -- the number is somewhat flattered by the golden set's composition.
2. **Not every label got the same review depth.** 43/200 were personally adjudicated,
   30/200 independently blind-labeled, 134/200 reviewed against an AI-consensus label
   (easier task, lower correction rate by construction -- read 3/134 corrections as
   "review confirmed labels were mostly right under a confirmation-biased method," not
   as an accuracy measurement). Only the 30-case subset supports a genuine human-vs-AI
   kappa. Full breakdown: `data/LABELING_GUIDE.md`.
3. **Escalation precision/recall on 200 examples has wide uncertainty**, especially for
   the minority escalate class (49/200 = 24.5% base rate). Precision 0.630 means ~4 in
   10 escalations are cases a human wouldn't have flagged -- and the more dangerous
   error (auto-handling something that should have escalated) is under-counted by this
   metric, since it can't see risk phrases not yet in the keyword list.
4. **The dataset only contains what happened publicly on Twitter**, excluding DMs where
   AppleSupport actually resolves account-security and billing cases -- which is
   exactly why those intents are hard-coded to never auto-handle.
5. **The LLM backend changed mid-project** (Gemini quota/credential failures -> Hive).
   All 200 `llm`-tier numbers are from one consistent backend, but are specific to that
   model's behavior and would likely shift with a different LLM.
6. **A 40-case quick-demo run and the full 200-case run are not the same experiment.**
   Quick-demo numbers are noisier and shouldn't be quoted as headline metrics.

Full list (7 items) and supporting detail: `APPENDIX.md` section 4.

## 5. What I'd do next with one more week

- **Get a genuine human-vs-human kappa**, not just human-vs-AI -- a second independent
  human, blind, on the same 30-case subset.
- **Add a faithfulness gate** between drafted reply and retrieved evidence (NLI-style
  entailment or a second cheap LLM call) as an escalation check -- the report's biggest
  finding (#2 above) shows confidence/similarity alone won't catch this.
- **Replace the incident-grown safety-keyword list** with a small dedicated safety/harm
  classifier, decoupled from intent classification.
- **Calibrate classifier confidence** against observed accuracy per bucket before
  trusting it as an escalation signal at all.
- **Multi-turn support**, a lightweight/fine-tuned classifier for cost, embedding-based
  retrieval (TF-IDF is lexical-only and can't handle paraphrase or non-English text), a
  `run_manifest.json` tying cached predictions to the config that produced them, and a
  basic test suite + CI.

Full list (12 items) with rationale: `APPENDIX.md` section 5.

## 6. Decision log

1. **Brand: AppleSupport** -- highest-volume, cleanest first-turn-reply structure among
   candidates inspected (106,860 outbound replies).
2. **8-intent taxonomy from manual EDA**, not Banking77 or unsupervised clustering --
   faster to ship and audit, at the cost of possibly missing a real traffic cluster.
3. **Escalation logic is rule-based, not LLM-decided**, even in the `llm` tier -- the
   one decision with real downstream cost if wrong should be the most auditable.
4. **Escalation logic is identical across the `simple` and `llm` tiers**, to isolate
   what's actually being compared (classification + reply quality) rather than also
   varying escalation policy.
5. **Retrieval index and golden/eval set are split by case at data-prep time**, before
   any retrieval happens -- structurally impossible for retrieval to surface a golden
   case's own historical answer.
6. **Only first-turn customer messages are used**; multi-turn follow-ups are explicitly
   out of scope for v1.
7. **The trivial baseline always auto-handles (no escalation logic at all)**, chosen
   specifically so the report can show the escalation module's value directly.
8. **Golden-set sampling caps any stratum at 35/200**, trading "matches raw traffic
   mix" for "computable macro-F1 across all 8 intents."
9. **One model is used for classification, reply generation, AND judging** (Hive) --
   cheaper and simpler to reproduce, at the cost of a judge that may share the
   generator's blind spots.
10. **The LLM-judge never sees the real historical AppleSupport reply**, only the
    customer message and drafted reply -- to stop it from just scoring "closeness to
    the answer key" instead of genuine quality.
11. **The LLM backend was switched from Gemini to TheHive.ai mid-project** after real
    free-tier quota walls and an expiring OAuth-style credential caused 163/200 cases to
    fail with 401s -- the entire `llm` tier was then re-run from scratch on one backend
    rather than merge results from two different models. Full story: `APPENDIX.md`
    decision log #15.
12. **A real safety-keyword gap (missed "burned and shocked") was found live during
    evaluation, fixed, and disclosed rather than left as a footnote** -- see failure
    mode #1.
13. **The golden set was brought to 200/200 genuine human-reviewed labels across three
    review depths** (43 adjudicated, 30 blind, 134 consensus-reviewed), and one
    anomalous 100%-agreement result was found and deliberately excluded from the
    reported kappa rather than used, because a result that improbable would undermine
    the report's credibility more than omitting it. Full process, including a
    self-caught process bug along the way: `APPENDIX.md` decision log #17-20.
14. **`.env` (API keys) is gitignored; all derived `data/*.jsonl` and `reports/*.json(l)`
    files are committed**, since those ARE the evidence this project is graded on.

Full narrative for every item above, plus several smaller disclosed decisions (request
throttling strategy, the simple baseline's arbitrary constant-confidence handling, and
how a second external review was incorporated), are in `APPENDIX.md` section 6 (20
items total).
