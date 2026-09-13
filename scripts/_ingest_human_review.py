"""One-off script: ingest Varun's genuine blind human labels (REVIEW_2, 30 cases)
and genuine blind human judge-calibration scores (REVIEW_3, 40 cases).

REVIEW_2 gives the first real human-vs-AI Cohen's kappa in this project (every
prior agreement number was AI-vs-AI, or human-vs-AI-conditioned-on-having-seen-
both-AI-outputs via the 43-case adjudication). REVIEW_3 replaces the previously
AI-filled human_overall_score_1to5 in the judge calibration file with Varun's
real scores.

Run once from repo root: python scripts/_ingest_human_review.py
"""
import csv
import json
from pathlib import Path

from sklearn.metrics import cohen_kappa_score, accuracy_score

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = Path(r"C:/Users/varun/Downloads")

REVIEW_2 = DOWNLOADS / "REVIEW_2_blind_30_completed.csv"
REVIEW_3 = DOWNLOADS / "REVIEW_3_blind_40_judge_completed.csv"

HUMAN_LABELS_OUT = ROOT / "data" / "golden_human_blind_30.jsonl"
CALIB_PATH = ROOT / "reports" / "judge_calibration_template.jsonl"


def load_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def truthy(s):
    return s.strip().lower() in ("true", "1", "yes")


def main():
    # ---- REVIEW_2: genuine human-vs-AI kappa over 30 blind cases ----
    r2 = list(csv.DictReader(open(REVIEW_2, encoding="utf-8-sig")))

    human_out = [
        {
            "case_id": r["case_id"],
            "gold_intent": r["YOUR_intent"].strip(),
            "gold_auto_handle": truthy(r["YOUR_auto_handle"]),
            "gold_escalation_reason_note": r["YOUR_notes"].strip(),
            "labeler": "varun-human-blind-v1",
        }
        for r in r2
    ]
    with open(HUMAN_LABELS_OUT, "w", encoding="utf-8") as f:
        for row in human_out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {HUMAN_LABELS_OUT} ({len(human_out)} rows)")

    pre = {r["case_id"]: r for r in load_jsonl(ROOT / "data" / "golden_ai_primary_pre_adjudication.jsonl")}
    human = {r["case_id"]: r for r in human_out}
    common = [cid for cid in human if cid in pre]

    def agreement(a_key_intent, a_key_esc, source, label):
        a_intent = [source[cid][a_key_intent] for cid in common]
        h_intent = [human[cid]["gold_intent"] for cid in common]
        a_esc = [bool(source[cid][a_key_esc]) for cid in common]
        h_esc = [bool(human[cid]["gold_auto_handle"]) for cid in common]
        result = {
            "n": len(common),
            "intent_exact_agreement": round(accuracy_score(h_intent, a_intent), 4),
            "intent_cohen_kappa": round(cohen_kappa_score(h_intent, a_intent), 4),
            "escalation_exact_agreement": round(accuracy_score(h_esc, a_esc), 4),
            "escalation_cohen_kappa": round(cohen_kappa_score(h_esc, a_esc), 4),
        }
        print(f"\nHuman (varun) vs {label}:")
        print(json.dumps(result, indent=2))
        return result

    human_vs_primary = agreement("gold_intent", "gold_auto_handle", pre, "AI primary pass (pre-adjudication)")

    sec_old = {r["case_id"]: r for r in load_jsonl(ROOT / "data" / "golden_second_labeler_subset.jsonl")}
    human_vs_sec_old = agreement("gold_intent", "gold_auto_handle", sec_old, "AI second pass (original 30-case)")

    sec_new_raw = {r["case_id"]: r for r in load_jsonl(ROOT / "data" / "ai_blind_secondpass_full200.jsonl")}
    human_vs_sec_new = agreement("gold_intent", "gold_auto_handle", sec_new_raw, "AI blind second pass (full-200)")

    out_path = ROOT / "reports" / "human_vs_ai_agreement.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "human_vs_ai_primary_pass": human_vs_primary,
            "human_vs_ai_secondpass_v1_30case": human_vs_sec_old,
            "human_vs_ai_secondpass_v2_full200": human_vs_sec_new,
        }, f, indent=2)
    print(f"\nWrote {out_path}")

    # ---- REVIEW_3: genuine human judge-calibration scores ----
    r3 = list(csv.DictReader(open(REVIEW_3, encoding="utf-8-sig")))
    r3_by_id = {r["case_id"]: r for r in r3}

    calib = load_jsonl(CALIB_PATH)
    n_filled = 0
    for row in calib:
        r = r3_by_id.get(row["case_id"])
        if r:
            row["human_overall_score_1to5"] = int(r["YOUR_score_1to5"].strip())
            row["human_labeler"] = "varun-human-blind-v1"
            n_filled += 1

    with open(CALIB_PATH, "w", encoding="utf-8") as f:
        for row in calib:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nUpdated {CALIB_PATH}: {n_filled}/{len(calib)} rows filled with genuine human scores")


if __name__ == "__main__":
    main()
