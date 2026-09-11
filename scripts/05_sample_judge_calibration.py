"""Sample a subset of the 'llm' tier's drafted replies for human 1-5 quality
scoring, blind to the LLM judge's own score, so we can measure judge/human
agreement. Run AFTER scripts/03_run_pipeline.py and scripts/04_run_judge.py.

Run: python scripts/05_sample_judge_calibration.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import REPORTS_DIR, RANDOM_SEED

N_CALIBRATION = 40


def main():
    random.seed(RANDOM_SEED)
    preds_path = REPORTS_DIR / "predictions_llm.jsonl"
    preds = {json.loads(l)["case_id"]: json.loads(l) for l in open(preds_path, encoding="utf-8")}
    ids = list(preds.keys())
    random.shuffle(ids)
    sample_ids = ids[:N_CALIBRATION]

    out_path = REPORTS_DIR / "judge_calibration_template.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for cid in sample_ids:
            p = preds[cid]
            f.write(json.dumps({
                "case_id": cid,
                "customer_text": p["customer_text"],
                "drafted_reply": p["reply"],
                "human_overall_score_1to5": "",
                "human_labeler": "",
            }, ensure_ascii=False) + "\n")
    print(f"Wrote {len(sample_ids)} rows to {out_path} (blind to judge scores by design)")


if __name__ == "__main__":
    main()
