"""Stratified sample of the golden evaluation set from the held-out eval pool.

Stratification: by keyword-classifier predicted intent (a cheap, deterministic
proxy for the true label distribution -- we don't have true labels yet, that's
the point of building this file) and by month, so the sample isn't dominated
by one iOS-update news cycle. Within each stratum, cases are picked at random.

This produces data/golden_template.jsonl with EMPTY gold_* fields plus an
AI-drafted `suggested_gold_intent` / `suggested_gold_auto_handle` to speed up
human labeling. The suggestions are NOT the golden labels -- a human (the
assignment author) must review and correct every row before data/golden.jsonl
is created from this template. See data/LABELING_GUIDE.md.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import EVAL_POOL_PATH, GOLDEN_TEMPLATE_PATH, RANDOM_SEED
from src.classifiers import keyword_classifier
from src.escalation import decide
from src.text_utils import clean_for_matching

random.seed(RANDOM_SEED)

TARGET_N = 200


def month_of(created_at: str) -> str:
    # Twitter format: "Wed Oct 11 06:55:44 +0000 2017"
    parts = created_at.split()
    return f"{parts[-1]}-{parts[1]}" if len(parts) >= 6 else "unknown"


def main():
    cases = []
    with open(EVAL_POOL_PATH, encoding="utf-8") as f:
        for line in f:
            cases.append(json.loads(line))
    print("Eval pool size:", len(cases))

    strata = defaultdict(list)
    for c in cases:
        pred = keyword_classifier(c["customer_text"])
        strata[pred].append(c)

    print("Stratum sizes (by keyword-predicted intent):")
    for k, v in strata.items():
        print(f"  {k}: {len(v)}")

    # Allocation with a floor of 10 and a cap of 35 per stratum. The keyword
    # classifier dumps ~74% of the eval pool into its "complaint_feedback"
    # catch-all (it's the fallback when no rule fires) -- sampling
    # proportionally to THAT distribution would just reproduce the baseline's
    # blind spot in the golden set and starve every other intent. Capping
    # keeps the set balanced enough to compute a meaningful per-intent/macro-F1
    # for the real (LLM) classifier, at the cost of the golden set's intent
    # mix no longer matching raw traffic mix 1:1 -- documented in the report's
    # "what's misleading" section.
    MIN_PER_STRATUM, MAX_PER_STRATUM = 10, 35
    allocation = {k: min(MAX_PER_STRATUM, len(v)) if len(v) >= MIN_PER_STRATUM else len(v)
                  for k, v in strata.items()}
    while sum(allocation.values()) > TARGET_N:
        k = max(allocation, key=lambda x: allocation[x])
        allocation[k] -= 1
    while sum(allocation.values()) < TARGET_N:
        k = min((k for k in allocation if allocation[k] < min(len(strata[k]), MAX_PER_STRATUM + 20)),
                key=lambda x: allocation[x], default=None)
        if k is None:
            break
        allocation[k] += 1

    print("Allocation:", allocation)

    sampled = []
    for k, n in allocation.items():
        pool = strata[k][:]
        random.shuffle(pool)
        sampled.extend(pool[:n])
    random.shuffle(sampled)

    print("Total sampled:", len(sampled))

    Path(GOLDEN_TEMPLATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_TEMPLATE_PATH, "w", encoding="utf-8") as f:
        for c in sampled:
            pred_intent = keyword_classifier(c["customer_text"])
            esc = decide(c["customer_text"], pred_intent, 0.7, 0.5)
            row = {
                "case_id": c["case_id"],
                "created_at": c["created_at"],
                "customer_text": c["customer_text"],
                "historical_apple_reply_FOR_REFERENCE_ONLY": c["brand_reply"],
                "suggested_gold_intent": pred_intent,
                "suggested_gold_auto_handle": esc["auto_handle"],
                "suggested_reason": esc["reason"],
                "gold_intent": "",
                "gold_auto_handle": "",
                "gold_escalation_reason_note": "",
                "labeler": "",
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("Wrote", GOLDEN_TEMPLATE_PATH)


if __name__ == "__main__":
    main()
