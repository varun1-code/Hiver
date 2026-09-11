"""Run all three system tiers (trivial, simple, llm) over the golden set's
inputs and write one predictions file per tier. Only customer_text/case_id
are used as input -- gold labels are never read here, so predictions can't
leak into evaluation.

Run: python scripts/03_run_pipeline.py
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

from src.config import GOLDEN_TEMPLATE_PATH, REFERENCE_POOL_PATH, REPORTS_DIR
from src.classifiers import keyword_classifier
from src.pipeline import run_trivial, run_simple, run_llm
from src.retrieval import CaseRetriever


def compute_majority_label() -> str:
    counts = Counter()
    with open(REFERENCE_POOL_PATH, encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            counts[keyword_classifier(c["customer_text"])] += 1
    label, n = counts.most_common(1)[0]
    print(f"Majority label from reference pool (keyword-predicted): {label} ({n} occurrences)")
    return label


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Only run the first N golden cases (for a quick <15min demo; omit for the full 200-case run used in the report).")
    parser.add_argument("--tiers", nargs="+", default=["trivial", "simple", "llm"])
    args = parser.parse_args()

    cases = []
    with open(GOLDEN_TEMPLATE_PATH, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            cases.append({"case_id": row["case_id"], "customer_text": row["customer_text"]})
    if args.limit:
        cases = cases[:args.limit]
    print("Cases to run:", len(cases))

    majority_label = compute_majority_label()
    retriever = CaseRetriever()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    tier_runners = {
        "trivial": lambda t: run_trivial(t, majority_label),
        "simple": lambda t: run_simple(t, retriever),
        "llm": lambda t: run_llm(t, retriever),
    }
    for tier_name in args.tiers:
        runner = tier_runners[tier_name]
        out_path = REPORTS_DIR / f"predictions_{tier_name}.jsonl"

        # Resume support: a free-tier daily/per-minute quota wall can kill a
        # long run partway through. Skip cases already successfully written
        # (no "error" field) so re-running the same command continues instead
        # of re-spending quota on completed cases.
        done = {}
        if out_path.exists():
            for line in open(out_path, encoding="utf-8"):
                row = json.loads(line)
                if not row.get("error"):
                    done[row["case_id"]] = row
        todo = [c for c in cases if c["case_id"] not in done]
        print(f"\nRunning tier: {tier_name} -> {out_path} ({len(done)} already done, {len(todo)} to run)")

        with open(out_path, "w", encoding="utf-8") as f:
            for c in cases:
                if c["case_id"] in done:
                    f.write(json.dumps(done[c["case_id"]], ensure_ascii=False) + "\n")
                    continue
                try:
                    result = runner(c["customer_text"])
                except Exception as e:
                    print(f"  ERROR on case {c['case_id']}: {e}")
                    result = {"system": tier_name, "error": str(e)}
                result["case_id"] = c["case_id"]
                result["customer_text"] = c["customer_text"]
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()
        n_done_now = sum(1 for c in cases if c["case_id"] not in done)
        print(f"Done: {out_path} ({n_done_now} newly run)")


if __name__ == "__main__":
    main()
