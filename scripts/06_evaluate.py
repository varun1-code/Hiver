"""Compute all headline metrics: intent accuracy/macro-F1 per system tier,
escalation-decision precision/recall, judge scores per tier, judge-vs-human
agreement, and primary-vs-second-labeler agreement on the golden set itself.

Writes reports/metrics.json (machine-readable) and prints a human-readable
summary. Run AFTER 01-05.

Run: python scripts/06_evaluate.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    confusion_matrix, cohen_kappa_score,
)
from scipy.stats import spearmanr

from src.config import GOLDEN_PATH, REPORTS_DIR, INTENT_NAMES


def load_jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def main():
    golden = {r["case_id"]: r for r in load_jsonl(GOLDEN_PATH)}
    if not golden:
        print(f"No golden set at {GOLDEN_PATH} yet -- run the labeling step first.")
        return
    print(f"Golden set size: {len(golden)}")

    metrics = {"n_golden": len(golden), "tiers": {}}

    for tier in ["trivial", "simple", "llm"]:
        preds_path = REPORTS_DIR / f"predictions_{tier}.jsonl"
        preds = {r["case_id"]: r for r in load_jsonl(preds_path) if not r.get("error")}
        common_ids = [cid for cid in golden if cid in preds]
        if not common_ids:
            print(f"Tier {tier}: no predictions found, skipping.")
            continue

        y_true_intent = [golden[cid]["gold_intent"] for cid in common_ids]
        y_pred_intent = [preds[cid]["intent"] for cid in common_ids]
        intent_acc = accuracy_score(y_true_intent, y_pred_intent)
        intent_macro_f1 = f1_score(y_true_intent, y_pred_intent, labels=INTENT_NAMES, average="macro", zero_division=0)

        y_true_esc = [bool(golden[cid]["gold_auto_handle"]) for cid in common_ids]
        y_pred_esc = [bool(preds[cid]["auto_handle"]) for cid in common_ids]
        esc_acc = accuracy_score(y_true_esc, y_pred_esc)
        # "escalate" (auto_handle=False) is the safety-critical positive class.
        y_true_escalate = [not v for v in y_true_esc]
        y_pred_escalate = [not v for v in y_pred_esc]
        esc_precision = precision_score(y_true_escalate, y_pred_escalate, zero_division=0)
        esc_recall = recall_score(y_true_escalate, y_pred_escalate, zero_division=0)
        esc_f1 = f1_score(y_true_escalate, y_pred_escalate, zero_division=0)

        judged_path = REPORTS_DIR / f"judged_{tier}.jsonl"
        judged = load_jsonl(judged_path)
        overall_scores = [j["overall"] for j in judged if j.get("overall") is not None]
        judge_mean = sum(overall_scores) / len(overall_scores) if overall_scores else None

        auto_handled_frac = sum(1 for cid in common_ids if preds[cid]["auto_handle"]) / len(common_ids)

        metrics["tiers"][tier] = {
            "n": len(common_ids),
            "intent_accuracy": round(intent_acc, 4),
            "intent_macro_f1": round(intent_macro_f1, 4),
            "escalation_accuracy": round(esc_acc, 4),
            "escalation_precision_for_escalate_class": round(esc_precision, 4),
            "escalation_recall_for_escalate_class": round(esc_recall, 4),
            "escalation_f1_for_escalate_class": round(esc_f1, 4),
            "auto_handled_fraction": round(auto_handled_frac, 4),
            "judge_mean_overall_score": round(judge_mean, 3) if judge_mean else None,
            "n_judged": len(overall_scores),
        }

        if tier == "llm":
            cm = confusion_matrix(y_true_intent, y_pred_intent, labels=INTENT_NAMES)
            metrics["llm_confusion_matrix"] = {
                "labels": INTENT_NAMES,
                "matrix": cm.tolist(),
            }

    # --- Judge vs human agreement (calibration subset) ---
    calib_path = REPORTS_DIR / "judge_calibration_template.jsonl"
    calib = load_jsonl(calib_path)
    judged_llm = {r["case_id"]: r for r in load_jsonl(REPORTS_DIR / "judged_llm.jsonl")}
    paired = [
        (c["case_id"], c.get("human_overall_score_1to5"), judged_llm.get(c["case_id"], {}).get("overall"))
        for c in calib
    ]
    paired = [(cid, h, j) for cid, h, j in paired if h not in (None, "", ) and j is not None]
    if paired:
        human_scores = [int(h) for _, h, _ in paired]
        judge_scores = [int(j) for _, _, j in paired]
        exact_agree = sum(1 for h, j in zip(human_scores, judge_scores) if h == j) / len(paired)
        within1_agree = sum(1 for h, j in zip(human_scores, judge_scores) if abs(h - j) <= 1) / len(paired)
        kappa = cohen_kappa_score(human_scores, judge_scores, weights="quadratic")
        rho, _ = spearmanr(human_scores, judge_scores)
        metrics["judge_human_agreement"] = {
            "n": len(paired),
            "exact_agreement": round(exact_agree, 4),
            "within_1_point_agreement": round(within1_agree, 4),
            "quadratic_weighted_kappa": round(kappa, 4),
            "spearman_rho": round(float(rho), 4),
        }
    else:
        metrics["judge_human_agreement"] = {"n": 0, "note": "Fill reports/judge_calibration_template.jsonl (human_overall_score_1to5) then re-run."}

    # --- Primary vs second-labeler agreement (golden set inter-rater) ---
    second_path = Path("data/golden_second_labeler_subset.jsonl")
    second = load_jsonl(second_path)
    pair_ids = [r["case_id"] for r in second if r["case_id"] in golden]
    if pair_ids:
        primary_intent = [golden[cid]["gold_intent"] for cid in pair_ids]
        second_by_id = {r["case_id"]: r for r in second}
        second_intent = [second_by_id[cid]["gold_intent"] for cid in pair_ids]
        intent_kappa = cohen_kappa_score(primary_intent, second_intent, labels=INTENT_NAMES)
        intent_exact = accuracy_score(primary_intent, second_intent)

        primary_esc = [bool(golden[cid]["gold_auto_handle"]) for cid in pair_ids]
        second_esc = [bool(second_by_id[cid]["gold_auto_handle"]) for cid in pair_ids]
        esc_kappa = cohen_kappa_score(primary_esc, second_esc)
        esc_exact = accuracy_score(primary_esc, second_esc)

        metrics["labeler_agreement"] = {
            "n": len(pair_ids),
            "intent_exact_agreement": round(intent_exact, 4),
            "intent_cohen_kappa": round(intent_kappa, 4),
            "escalation_exact_agreement": round(esc_exact, 4),
            "escalation_cohen_kappa": round(esc_kappa, 4),
        }
    else:
        metrics["labeler_agreement"] = {"n": 0, "note": "data/golden_second_labeler_subset.jsonl not found or no overlapping case_ids."}

    out_path = REPORTS_DIR / "metrics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
