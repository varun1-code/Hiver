"""One-off script: ingest the 43-case human adjudication + full-200 blind AI
second pass into data/golden.jsonl, and freeze the pre-adjudication snapshot +
full-200 second pass as permanent artifacts for a reproducible, non-circular
AI-vs-AI agreement metric (see REPORT.md decision log).

Run once from repo root: python scripts/_ingest_adjudication.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = ROOT / "data" / "golden.jsonl"
DOWNLOADS = Path(r"C:/Users/varun/Downloads")

BLIND_SECOND_PASS = DOWNLOADS / "BLIND_SECOND_PASS_200.jsonl"
ADJUDICATED_43 = DOWNLOADS / "REVIEW_1B_adjudicate_43_completed.csv"

PRE_ADJUDICATION_SNAPSHOT = ROOT / "data" / "golden_ai_primary_pre_adjudication.jsonl"
FULL200_SECOND_PASS_OUT = ROOT / "data" / "ai_blind_secondpass_full200.jsonl"


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    golden_rows = load_jsonl(GOLDEN_PATH)
    golden_by_id = {r["case_id"]: r for r in golden_rows}

    # 1. Freeze pre-adjudication snapshot of the primary AI labels (for a
    #    reproducible, non-circular full-200 AI-vs-AI comparison later).
    snapshot = [
        {
            "case_id": r["case_id"],
            "gold_intent": r["gold_intent"],
            "gold_auto_handle": r["gold_auto_handle"],
            "labeler": r["labeler"],
        }
        for r in golden_rows
    ]
    with open(PRE_ADJUDICATION_SNAPSHOT, "w", encoding="utf-8") as f:
        for row in snapshot:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {PRE_ADJUDICATION_SNAPSHOT} ({len(snapshot)} rows)")

    # 2. Freeze the full-200 independent blind AI second pass as a permanent
    #    artifact, reformatted to match the existing labeler schema.
    second_pass_rows = load_jsonl(BLIND_SECOND_PASS)
    with open(FULL200_SECOND_PASS_OUT, "w", encoding="utf-8") as f:
        for r in second_pass_rows:
            f.write(json.dumps({
                "case_id": r["case_id"],
                "gold_intent": r["intent"],
                "gold_auto_handle": r["auto_handle"],
                "gold_escalation_reason_note": r["rationale"],
                "labeler": "claude-blind-secondpass-v2",
            }, ensure_ascii=False) + "\n")
    print(f"Wrote {FULL200_SECOND_PASS_OUT} ({len(second_pass_rows)} rows)")

    # 3. Apply the 43 human adjudications to golden.jsonl; relabel the other
    #    157 as confirmed-by-independent-agreement.
    adjudicated = list(csv.DictReader(open(ADJUDICATED_43, encoding="utf-8-sig")))
    adjudicated_ids = {r["case_id"] for r in adjudicated}
    second_pass_by_id = {r["case_id"]: r for r in second_pass_rows}

    n_adjudicated = 0
    n_agreed = 0
    sided_fresh = sided_draft = sided_neither = 0

    for r in adjudicated:
        cid = r["case_id"]
        g = golden_by_id[cid]
        final_intent = r["YOUR_final_intent"].strip()
        final_auto = r["YOUR_final_auto_handle"].strip().lower() in ("true", "1", "yes")
        prior_labeler = g["labeler"]
        g["gold_intent"] = final_intent
        g["gold_auto_handle"] = final_auto
        g["gold_escalation_reason_note"] = r["YOUR_reasoning"].strip()
        g["labeler"] = f"{prior_labeler}+claude-blind-secondpass-v2, human-adjudicated"
        n_adjudicated += 1

        matches_fresh = (final_intent == r["fresh_ai_intent"].strip()) and (
            final_auto == (r["fresh_ai_auto_handle"].strip().lower() in ("true", "1", "yes"))
        )
        matches_draft = (final_intent == r["ai_draft_intent"].strip()) and (
            final_auto == (r["ai_draft_auto_handle"].strip().lower() in ("true", "1", "yes"))
        )
        if matches_fresh:
            sided_fresh += 1
        elif matches_draft:
            sided_draft += 1
        else:
            sided_neither += 1

    for cid, g in golden_by_id.items():
        if cid in adjudicated_ids:
            continue
        g["labeler"] = f"{g['labeler']}+claude-blind-secondpass-v2 (independent agreement)"
        n_agreed += 1

    with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
        for r in golden_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nUpdated {GOLDEN_PATH}:")
    print(f"  {n_adjudicated} rows human-adjudicated")
    print(f"  {n_agreed} rows confirmed by independent AI-pass agreement")
    print(f"  Of the {n_adjudicated} adjudicated: sided with fresh pass={sided_fresh}, "
          f"sided with original draft={sided_draft}, sided with neither={sided_neither}")

    # 4. Full-200 AI-vs-AI agreement, computed on the FROZEN pre-adjudication
    #    snapshot vs the frozen full-200 second pass (non-circular, since
    #    neither file is touched by the adjudication step above).
    from sklearn.metrics import cohen_kappa_score, accuracy_score
    pre = {r["case_id"]: r for r in snapshot}
    second = {r["case_id"]: r for r in second_pass_rows}
    common = [cid for cid in pre if cid in second]
    primary_intent = [pre[cid]["gold_intent"] for cid in common]
    second_intent = [second[cid]["intent"] for cid in common]
    primary_esc = [bool(pre[cid]["gold_auto_handle"]) for cid in common]
    second_esc = [bool(second[cid]["auto_handle"]) for cid in common]

    intent_kappa = cohen_kappa_score(primary_intent, second_intent)
    intent_exact = accuracy_score(primary_intent, second_intent)
    esc_kappa = cohen_kappa_score(primary_esc, second_esc)
    esc_exact = accuracy_score(primary_esc, second_esc)

    result = {
        "n": len(common),
        "intent_exact_agreement": round(intent_exact, 4),
        "intent_cohen_kappa": round(intent_kappa, 4),
        "escalation_exact_agreement": round(esc_exact, 4),
        "escalation_cohen_kappa": round(esc_kappa, 4),
    }
    print("\nFull-200 pre-adjudication AI-vs-AI agreement (independent, non-circular):")
    print(json.dumps(result, indent=2))

    out_path = ROOT / "reports" / "ai_pass_agreement_full200.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
