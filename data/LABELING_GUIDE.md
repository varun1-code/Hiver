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
taxonomy in `src/config.py`. Two passes were run for exactly the purpose of computing
inter-rater agreement:

1. **Primary pass** (all 200 rows) -> `data/golden.jsonl`. Rubric applied: pick the most
   specific/actionable intent (avoid `complaint_feedback` unless there's truly no
   actionable ask); `gold_auto_handle=false` whenever the message involves money,
   account security/identity, safety/legal content, an explicit request for a human, or
   is too ambiguous to act on confidently.
2. **Second pass** (first 30 rows only, independently, blind to the primary labels and
   to the keyword baseline's suggestions) -> `data/golden_second_labeler_subset.jsonl`.
   Agreement (Cohen's kappa, both for intent and for the escalate/auto-handle call) is
   computed in `scripts/06_evaluate.py` and reported as `labeler_agreement` in
   `reports/metrics.json`.

**Important disclosure**: both labeling passes in this repository were produced by an
AI assistant reading each tweet directly and applying the rubric above -- not by two
independent human annotators. This is called out explicitly because the assignment
asks for a "hand-labelled" set the candidate built themselves. Treat `data/golden.jsonl`
as a high-quality *draft* golden set and a working demonstration of the full evaluation
pipeline (sampling -> labeling -> agreement -> metrics), not as a substitute for a
human doing a real pass before this is submitted as final work. Before submission,
a human should at minimum: (a) spot-check the ambiguous case_ids flagged in
`data/LABELING_NOTES.md`, and (b) re-label the 30-row calibration subset independently
to get a genuine human-vs-AI-judge agreement number to replace the AI-vs-AI proxy
currently in `reports/metrics.json`.
