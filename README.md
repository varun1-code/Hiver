# AppleSupport AI support agent -- Hiver take-home

An AI support agent for the Twitter handle **@AppleSupport**, built from the full
"Customer Support on Twitter" Kaggle dataset (~2.8M rows, downloaded to
`reports/twcs/twcs.csv`, gitignored -- see Setup below). For an inbound customer
message it:

1. **Classifies** the message into one of 8 intents (see `src/config.py`).
2. **Drafts a reply** grounded in the closest historically-resolved AppleSupport
   case, retrieved via TF-IDF over a reference pool that is disjoint from the
   evaluation set (no leakage -- see "What's misleading" below).
3. **Decides auto-handle vs. escalate**, with a stated, auditable reason
   (`src/escalation.py` -- deliberately rule-based, not LLM-decided).

Three system tiers are implemented and compared head-to-head:

| Tier | Classifier | Reply | Escalation |
|---|---|---|---|
| `trivial` | majority class (constant) | one canned generic reply | always auto-handle |
| `simple` | keyword/regex rules | copy of nearest retrieved historical reply | rule-based (shared) |
| `llm` (main system) | Gemini, taxonomy in-context | Gemini, RAG-grounded in top-3 retrieved cases | rule-based (shared) |

## Setup

```powershell
pip install -r requirements.txt
cp .env.example .env   # then fill in GEMINI_API_KEY
```

Requires the Kaggle dataset at `reports/twcs/twcs.csv`. If you don't already have it:
```powershell
python -c "import kagglehub; print(kagglehub.dataset_download('thoughtvector/customer-support-on-twitter'))"
# then copy the twcs.csv it downloads to reports/twcs/twcs.csv
```

## Reproduce in under 15 minutes (quick demo)

```powershell
python scripts\01_prepare_dataset.py         # ~1-2 min: builds cases from the raw CSV
python scripts\02_sample_golden.py           # seconds: (re)builds the golden template
python scripts\03_run_pipeline.py --limit 40 # ~5 min: runs all 3 tiers on 40 golden cases
python scripts\04_run_judge.py --limit 40    # ~4 min: LLM-judge scores the drafted replies
python scripts\06_evaluate.py                # seconds: prints + writes reports/metrics.json
```

`--limit 40` exists because of a real constraint, not convenience: Gemini's free tier
caps `gemini-flash-latest` at **20 requests/minute**, and the `llm` tier makes 2 calls/case
(classify + generate) plus 1 judge call/case. At that rate the full 200-case golden set
takes **~45-60 minutes**, not 15. The quick-demo numbers on 40 cases are directionally
consistent with the full run but noisier (smaller n per intent bucket) -- see the
report's "what's misleading" section.

## Full run (what produced the report's headline numbers)

```powershell
python scripts\03_run_pipeline.py            # no --limit: all 200 golden cases, ~35-45 min
python scripts\04_run_judge.py               # judges simple + llm tiers, ~15-20 min
python scripts\05_sample_judge_calibration.py
# then manually fill reports/judge_calibration_template.jsonl's human_overall_score_1to5
python scripts\06_evaluate.py
```

Inspect `reports/predictions_{trivial,simple,llm}.jsonl` (per-case output with intent,
confidence, drafted reply, auto_handle + reason, and retrieval evidence used),
`reports/judged_{simple,llm}.jsonl` (LLM-judge scores), and `reports/metrics.json`
(everything aggregated: accuracy/F1, escalation precision/recall, judge scores, judge-human
agreement, and the two-labeler agreement on the golden set itself).

## Data pipeline & leakage guard

`scripts/01_prepare_dataset.py` builds ~83k (customer message -> AppleSupport's actual
reply) cases from first-turn @AppleSupport-directed tweets, dedupes near-identical text,
subsamples to 8,000, and splits by case into a **reference pool** (6,000 -- the retrieval
index used at inference time) and an **eval pool** (2,000 -- golden set is sampled from
here only). The eval pool is never added to the retrieval index, so a drafted reply can't
be "grounded" in its own case's real historical answer.

## Golden evaluation set

`data/golden.jsonl` -- 200 examples, stratified-sampled from the eval pool and labeled
independently of any classifier's suggestion. Full sampling/labeling methodology,
inter-rater agreement design, and an explicit disclosure about how these labels were
produced are in `data/LABELING_GUIDE.md` and `data/LABELING_NOTES.md` -- **read that
disclosure before treating these numbers as final**; it documents that automated
labeling was used for scaffolding and that a human pass is still needed before
submission.

## Decision log

See `REPORT.md` for the full report; the condensed decision log is in
`REPORT.md#decision-log`.

## Repository layout

```
src/
  config.py          intent taxonomy, brand, model, thresholds -- all in one place
  llm_client.py       minimal Gemini REST wrapper (no SDK dep), throttled to free-tier RPM
  text_utils.py        mention/URL stripping for matching (display text is never altered)
  classifiers.py       majority / keyword / llm intent classifiers
  retrieval.py          TF-IDF retrieval over the reference pool
  reply_drafters.py      template-copy baseline reply + LLM RAG-grounded reply
  escalation.py           shared rule-based auto-handle/escalate decision
  pipeline.py              ties each tier together into one run_*() call
  judge.py                  LLM-as-judge reply-quality scoring
scripts/
  01_prepare_dataset.py       build cases + reference/eval split from the raw CSV
  02_sample_golden.py          stratified golden-set sample + AI-drafted label template
  03_run_pipeline.py            run all 3 tiers over the golden set
  04_run_judge.py                 LLM-judge the drafted replies
  05_sample_judge_calibration.py    blind human-scoring template for judge calibration
  06_evaluate.py                     all metrics -> reports/metrics.json
  exploration/                        one-off EDA scripts used to pick the brand/taxonomy
data/
  cases.jsonl, reference_pool.jsonl, eval_pool.jsonl   (committed -- small, derived, needed to reproduce)
  golden_template.jsonl, golden.jsonl, golden_second_labeler_subset.jsonl
  LABELING_GUIDE.md, LABELING_NOTES.md
reports/
  twcs/twcs.csv          the raw ~500MB Kaggle dump (gitignored, see Setup)
  predictions_*.jsonl, judged_*.jsonl, metrics.json, judge_calibration_*.jsonl (committed -- these are the evidence)
```
