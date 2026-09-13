"""Run the LLM-as-judge over every system tier's drafted replies.

Run: python scripts/04_run_judge.py
"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

from src.config import REPORTS_DIR
from src.judge import judge_reply


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--tiers", nargs="+", default=["simple", "llm"],
                        help="trivial's reply is a constant string; judging it is not informative, so it's skipped by default.")
    args = parser.parse_args()

    for tier in args.tiers:
        in_path = REPORTS_DIR / f"predictions_{tier}.jsonl"
        out_path = REPORTS_DIR / f"judged_{tier}.jsonl"
        if not in_path.exists():
            print(f"Skip {tier}: {in_path} not found (run scripts/03_run_pipeline.py first)")
            continue
        rows = [json.loads(l) for l in open(in_path, encoding="utf-8")]
        if args.limit:
            rows = rows[:args.limit]

        done = {}
        if out_path.exists():
            for line in open(out_path, encoding="utf-8"):
                r = json.loads(line)
                if r.get("overall") is not None:
                    done[r["case_id"]] = r
        print(f"Judging {tier}: {len(rows)} rows -> {out_path} ({len(done)} already done)")

        in_scope_ids = {row["case_id"] for row in rows}
        with open(out_path, "w", encoding="utf-8") as f:
            # Preserve rows already judged for cases outside the current
            # --limit slice, so a smaller/quick-demo run never truncates a
            # larger existing results file.
            for case_id, row in done.items():
                if case_id not in in_scope_ids:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            for row in rows:
                if row.get("error"):
                    continue
                if row["case_id"] in done:
                    f.write(json.dumps(done[row["case_id"]], ensure_ascii=False) + "\n")
                    continue
                try:
                    score = judge_reply(row["customer_text"], row["reply"])
                except Exception as e:
                    print(f"  judge error on case {row.get('case_id')}: {e}")
                    score = {"overall": None, "error": str(e)}
                out = {"case_id": row["case_id"], "system": tier, **score}
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
                f.flush()
        print(f"Done: {out_path}")


if __name__ == "__main__":
    main()
