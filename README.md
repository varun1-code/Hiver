# AppleSupport Twitter support agent

This repository contains a small, reproducible baseline for the Hiver take-home assignment. It classifies an inbound message, retrieves a historically similar AppleSupport resolution, drafts a grounded reply, and escalates low-confidence or sensitive cases.

## Important data limitation

`C:\Users\varun\Downloads\sample.csv` contains 93 rows and only 13 inbound AppleSupport messages. It is useful for demonstrating the pipeline, but it cannot honestly produce the required 150–250-example hand-labelled golden set. The included preparation command creates a labelling template; do not present its auto-filled fields as human labels. Download the full Kaggle dataset or a larger approved subsample before reporting headline metrics.

## Run in under 15 minutes

The code uses only the Python standard library (Python 3.10+):

```powershell
python src\prepare.py --csv C:\Users\varun\Downloads\sample.csv --brand AppleSupport
python src\run_agent.py --csv C:\Users\varun\Downloads\sample.csv --brand AppleSupport
```

Inspect `reports\predictions.jsonl`. Every prediction includes the intent, confidence, draft reply, auto-handle decision, reason, and the historical evidence used.

After manually labelling `data\golden_template.jsonl` (rename or copy it to `data\golden.jsonl`), run:

```powershell
python src\evaluate.py --gold data\golden.jsonl --predictions reports\predictions.jsonl
```

## Labelling protocol

Sample 150–250 inbound AppleSupport messages stratified by time and predicted intent. A human labels `gold_intent`, `gold_auto_handled`, and `gold_reply_quality` (1–5), while preserving the original text. A second person independently labels at least 30 examples; report Cohen's kappa for intent and escalation, plus exact agreement for the 1–5 quality score. Resolve disagreements before locking the set.

## What the current system does and does not claim

The classifier is an auditable keyword baseline, not a trained language model. Retrieval uses token overlap and only copies a historical reply when there is a sufficiently close match; otherwise it uses a conservative template. Escalation is intentionally biased toward safety. The evaluation script includes a majority-intent baseline and is designed to be extended with a random or “always escalate” baseline once the golden set is labelled.

The headline number will be misleading if the golden set is sampled from the same threads used as retrieval evidence, if duplicates or near-duplicates cross the split, or if reply quality is judged only by an LLM. Keep conversations grouped by thread, deduplicate before splitting, and report human agreement and abstention coverage alongside accuracy.

## Decision log

- Chose AppleSupport because it has the most brand-authored support rows in the supplied sample.
- Used an explicit intent taxonomy rather than importing Banking77 labels, because the domain and observable failure modes differ.
- Kept the implementation dependency-free so the small-sample reproduction is reliable.
- Used retrieval only above a similarity threshold to avoid inventing a historical resolution.
- Escalated sensitive terms and low-confidence cases instead of optimizing auto-handling coverage.
- Removed URLs and mentions for matching but preserved original text in outputs.
- Required human labels before evaluation metrics are emitted as evidence.
- Kept evidence text in every prediction for auditability.
- Grouped the intended evaluation split by conversation thread to prevent leakage.
- Treated the supplied CSV as a development sample, not a valid final benchmark.
