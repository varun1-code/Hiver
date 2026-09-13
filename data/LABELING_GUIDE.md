# Golden set labeling guide

## Sampling

The golden set (`data/golden.jsonl`, 200 examples) is drawn from `data/eval_pool.jsonl`,
which is held out from the retrieval index (`data/reference_pool.jsonl`) used at
inference time -- see `scripts/01_prepare_dataset.py` for the split logic and why it
matters (retrieval must never be able to "cheat" by finding a golden case's own
historical resolution).

Stratification (`scripts/02_sample_golden.py`): the eval pool is bucketed by the
*keyword baseline's* predicted intent, then sampled with a floor of 10 and a cap of 35
per bucket, landing on 25 per bucket x 8 buckets = 200. The cap matters: the keyword
baseline dumps ~74% of real traffic into its `complaint_feedback` catch-all (it's the
fallback when no rule fires), so proportional sampling would have produced a golden set
that mostly measures how well systems handle catch-all noise. Capping trades "matches
raw traffic mix" for "can compute a meaningful per-intent macro-F1" -- documented in the
report's "what's misleading" section, because it means the golden set's intent
distribution is NOT representative of true @AppleSupport traffic volume.

## Labeling

Every row was labeled independently from the raw `customer_text` alone, using the
taxonomy in `src/config.py`. The final `data/golden.jsonl` is the product of three
passes, run specifically so disagreement could be measured and routed to a human
rather than accepted on either AI pass's say-so:

1. **Primary AI pass** (all 200 rows). Rubric applied: pick the most specific/
   actionable intent (avoid `complaint_feedback` unless there's truly no actionable
   ask); `gold_auto_handle=false` whenever the message involves money, account
   security/identity, safety/legal content, an explicit request for a human, or is too
   ambiguous to act on confidently.
2. **Independent blind second AI pass** (all 200 rows, `data/ai_blind_secondpass_full200.jsonl`)
   -- given only `case_id` + `customer_text`, no visibility into the primary pass's
   labels. Compared against the primary pass (frozen at
   `data/golden_ai_primary_pre_adjudication.jsonl` so this comparison stays
   reproducible even after later edits): **157/200 (78.5%) agreed exactly on both
   intent and auto-handle**; intent Cohen's kappa 0.799, escalation kappa 0.781
   (`reports/ai_pass_agreement_full200.json`) -- a real AI-vs-AI inter-rater number,
   computed on the full golden set rather than a 30-case sample.
3. **Human adjudication of the 43 disagreement/ambiguous cases**
   (`data/human_adjudication_43cases.csv`) -- Varun personally read each of the 43
   cases where the two AI passes disagreed or one flagged ambiguity, and made the
   final call with his own written rationale per case (not a template). Outcome: sided
   with the fresh second pass on 32, with the original draft on 2, both passes already
   agreed on 8 of the 43 (flagged for ambiguity alone), and sided with **neither** AI
   pass on 1 (case `1861359`, a post-update inability to make phone calls -- judged
   more consequential than either AI pass's call).

The 30-row AI-vs-AI subset (`data/golden_second_labeler_subset.jsonl`) and its
agreement stat in `reports/metrics.json`'s `labeler_agreement` predate this process
and are left as an independent check (it wasn't used to build or adjudicate anything
above).

**Current disclosure**: 43/200 (21.5%) of the golden labels reflect a genuine human
decision by Varun, each with a case-specific written rationale in
`data/human_adjudication_43cases.csv`. The remaining 157/200 are AI-labeled, confirmed
only by agreement between two independent AI passes -- not individually verified by a
human. This is a real improvement over a single unreviewed AI pass, but it is not yet
"every label hand-built by the candidate," which is what the assignment literally asks
for. `data/REVIEW_2_blind_30.csv` (an independent, blind, from-scratch human relabel of
30 cases) is the remaining step needed for a genuine human-vs-AI Cohen's kappa, as
opposed to the adjudication-based agreement numbers above, which are conditioned on
having already seen both AI passes' outputs.
