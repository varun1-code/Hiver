"""One-off script: ingest the final 134-case human review, bringing the golden
set to 200/200 cases with a genuine human decision behind every label.

Run once from repo root: python scripts/_ingest_final_134.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = ROOT / "data" / "golden.jsonl"
COMPLETED = Path(r"C:/Users/varun/Downloads/REVIEW_4_remaining_134_completed.csv")
OUT_EVIDENCE = ROOT / "data" / "human_review_remaining_134cases.csv"


def truthy(s):
    return s.strip().lower() in ("true", "1", "yes")


def main():
    golden_rows = [json.loads(l) for l in open(GOLDEN_PATH, encoding="utf-8") if l.strip()]
    golden_by_id = {r["case_id"]: r for r in golden_rows}

    rows = list(csv.DictReader(open(COMPLETED, encoding="utf-8-sig")))

    n_confirmed = 0
    n_changed = 0
    for r in rows:
        cid = r["case_id"]
        g = golden_by_id[cid]
        final_intent = r["YOUR_final_intent"].strip()
        final_auto = truthy(r["YOUR_final_auto_handle"])
        changed = (final_intent != g["gold_intent"]) or (final_auto != bool(g["gold_auto_handle"]))
        prior_labeler = g["labeler"]
        g["gold_intent"] = final_intent
        g["gold_auto_handle"] = final_auto
        g["gold_escalation_reason_note"] = r["YOUR_reasoning"].strip()
        g["labeler"] = f"{prior_labeler}+varun-human-review-v1"
        if changed:
            n_changed += 1
        else:
            n_confirmed += 1

    with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
        for r in golden_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Save the completed file into the repo as permanent evidence.
    with open(OUT_EVIDENCE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Updated {GOLDEN_PATH}: {len(rows)} rows reviewed "
          f"({n_confirmed} confirmed AI consensus, {n_changed} changed)")
    print(f"Wrote evidence file {OUT_EVIDENCE}")

    # Sanity check: every one of the 200 golden rows now has a human-review
    # marker in its labeler chain.
    n_human = sum(1 for r in golden_rows if "varun" in r["labeler"])
    print(f"\n{n_human}/{len(golden_rows)} golden rows now carry a genuine human decision.")


if __name__ == "__main__":
    main()
