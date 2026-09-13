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

## Genuine human-vs-AI agreement (30-case independent blind relabel)

Separately from the adjudication above, Varun independently blind-labeled 30 golden-set
cases from scratch -- `customer_text` only, no AI labels of any kind visible --
producing `data/golden_human_blind_30.jsonl`. This is the first genuine human-vs-AI
comparison in this project (the adjudication above is human-vs-AI *conditioned on
having already seen both AI outputs*, which is a different, easier task). Result
(`reports/human_vs_ai_agreement.json`):

- vs. the original primary AI pass: 80% exact / Cohen's kappa 0.69
- vs. an older, independently-generated 30-case AI second pass: 80% exact / kappa 0.70
- vs. `data/ai_blind_secondpass_full200.jsonl` (the newest AI pass): **100% exact (30/30,
  both fields)** -- disclosed but explicitly **not** used. This rate is statistically
  inconsistent with the ~80% agreement against the other two independent AI passes on
  the identical 30 cases; asked directly, the labeler confirmed the work was done
  independently, but a result this improbable is excluded from the reported kappa
  regardless of cause (see `REPORT.md` decision log #18). The two ~80% comparisons above
  are used as this project's genuine human-vs-AI agreement figure.

## Genuine human judge-calibration scores

`data/REVIEW_3_blind_40_judge.csv` -- Varun scored 40 drafted replies 1-5 for quality,
blind to the LLM judge's own scores for the same replies. These values now populate
`reports/judge_calibration_template.jsonl`'s `human_overall_score_1to5`, replacing an
earlier AI-filled placeholder. Result: judge mean 3.975 vs. human mean 3.35 (a genuine
~0.6-point leniency gap), quadratic-weighted kappa 0.32 -- see `REPORT.md` failure mode
#4 and "what's misleading" #3.

## The remaining 134 cases (AI-consensus review)

The 134 cases outside both the 43-adjudicated and 30-blind-labeled sets (200 - 66
unique = 134) still needed a human decision. For these, both independent AI passes had
already agreed with each other (that's exactly why they weren't among the 43
disagreements), so Varun reviewed each against that AI-consensus label rather than
blind -- confirm or correct, with a specific written reason per case either way
(`data/human_review_remaining_134cases.csv`). Outcome: 131 confirmed, 3 corrected
(cases `2608614`, `559184`, `1010032` -- see `REPORT.md` decision log #20 for detail).
This is a genuine human decision on every row, but it is *review of a suggestion*, not
blind labeling -- a materially easier task than the 30-case blind pass, so the low
3/134 correction rate should be read as "review confirmed AI-consensus labels were
mostly already right, under a review methodology biased toward confirming," not as an
independent accuracy measurement of those 134 labels.

**Process note, disclosed rather than quietly fixed**: while merging this final batch,
a sanity check (counting `golden.jsonl` rows with a human marker in `labeler`) found
only 177/200 instead of the expected 200. Cause: the 30-case blind pass had only ever
been used to compute the human-vs-AI kappa above -- it was never merged back into
`golden.jsonl` itself, so the 23 cases in that subset not also in the 43-case
adjudication still held pure-AI values in the master file even though Varun had
genuinely labeled them. Fixed by merging those 23 decisions in before finalizing
anything -- see `REPORT.md` decision log #20.

## Current disclosure

**All 200/200 golden labels now carry a genuine human decision** by Varun, but at three
different review depths, and that distinction matters more than the headline
percentage:

- **43/200 (21.5%)**: personally adjudicated after two AI passes disagreed or flagged
  ambiguity, each with a case-specific written rationale
  (`data/human_adjudication_43cases.csv`).
- **30/200 (15%, 7 overlapping the above)**: independently blind-labeled from scratch,
  no AI labels visible at all (`data/golden_human_blind_30.jsonl`) -- this is the only
  subset that supports a genuine human-vs-AI Cohen's kappa (~0.7), since it's the only
  one not conditioned on having already seen an AI answer.
- **134/200 (67%)**: reviewed against an AI-consensus label and confirmed or corrected
  (`data/human_review_remaining_134cases.csv`) -- a real decision, but an easier task
  than blind labeling, and the 3/134 correction rate reflects that.

This satisfies "hand-labeled examples you built yourself" in that every one of the 200
labels reflects a human decision, but it is not the claim "all 200 were blind-labeled
independently" -- only 15% of the set was. `REPORT.md` section 5, item 1, proposes the
remaining honest gap: a second independent human, blind, on the same 30-case subset,
to get a genuine human-vs-human kappa this project doesn't yet have.
