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
| `llm` (main system) | LLM, taxonomy in-context | LLM, RAG-grounded in top-3 retrieved cases | rule-based (shared) |

The `llm` tier's headline numbers were produced using **TheHive.ai's** chat completions
API (`hive/vision-language-model`), not Gemini -- see Setup and decision log #15 for why
(short version: free-tier Gemini quotas and an expiring OAuth-style credential made it
unworkable for a 200-case run; `src/llm_client.py` supports both behind one interface via
the `LLM_PROVIDER` env var).

## Setup

```powershell
pip install -r requirements.txt
cp .env.example .env   # then fill in HIVE_API_KEY (or set LLM_PROVIDER=gemini + GEMINI_API_KEY)
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
python scripts\03_run_pipeline.py --limit 40 # ~2 min: runs all 3 tiers on 40 golden cases
python scripts\04_run_judge.py --limit 40    # ~2 min: LLM-judge scores the drafted replies
python scripts\06_evaluate.py                # seconds: prints + writes reports/metrics.json
```

`--limit 40` keeps the quick demo comfortably under 15 minutes end-to-end (dataset prep is
the slow part at 1-2 min for ~2.8M rows; the Hive API calls themselves are fast with no
meaningful rate limit at this volume). The quick-demo numbers on 40 cases are directionally
consistent with the full run but noisier (smaller n per intent bucket) -- see the report's
"what's misleading" section.

**Note on resume behavior**: `reports/predictions_*.jsonl` and `reports/judged_*.jsonl`
are committed (they're the evaluation evidence). `scripts/03_run_pipeline.py` and
`scripts/04_run_judge.py` skip any case_id already present without an `"error"` field
(see README "Data pipeline" and the scripts themselves), so re-running the quick-demo
commands against a fresh clone will mostly replay cached results almost instantly rather
than re-calling the API. To actually exercise the live pipeline end-to-end, delete the
relevant `reports/*.jsonl` file(s) first.

**Note on the Gemini path** (`LLM_PROVIDER=gemini`): if you use a Gemini key instead,
budget much more time -- `gemini-flash-latest`'s free tier is capped at 20
REQUESTS PER DAY (not per minute), and even the more usable `gemini-flash-lite-latest`
(15 req/min) makes the full 200-case run take ~45-60 minutes. This is why the report's
headline numbers use Hive instead (see decision log #15).

## Full run (what produced the report's headline numbers)

```powershell
python scripts\03_run_pipeline.py            # no --limit: all 200 golden cases, ~10 min on Hive
python scripts\04_run_judge.py               # judges simple + llm tiers, ~10 min on Hive
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

`data/golden.jsonl` -- 200 examples, stratified-sampled from the eval pool. Every one
of the 200 labels carries a genuine human decision (43 personally adjudicated after an
AI disagreement, 30 independently blind-labeled from scratch, 134 reviewed against an
AI-consensus label and confirmed/corrected), but at three different review depths --
**read `data/LABELING_GUIDE.md` before treating "200 hand-labeled" as one uniform
claim**, since only the 30-case blind subset supports a genuine human-vs-AI agreement
number. `data/LABELING_NOTES.md` has the rubric and hard-case notes.

## Decision log

See `REPORT.md` for the full report; the condensed decision log is in
`REPORT.md#decision-log`.

## Repository layout

```
src/
  config.py          intent taxonomy, brand, model, thresholds -- all in one place
  llm_client.py       minimal REST wrapper for Hive or Gemini (no SDK dep), behind one interface
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
