"""Build (customer_text -> AppleSupport resolution) cases from the raw Kaggle
CSV, then split into a retrieval reference pool and a held-out eval pool.

Leakage guard: the split is by conversation (root customer tweet_id), and the
eval pool is *never* added to the retrieval index used at inference time. This
is what lets us later claim the drafted replies are grounded in genuinely
unseen-at-inference historical resolutions, not a copy of the answer key.

Run: python scripts/01_prepare_dataset.py
"""
import json
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import (
    RAW_CSV, BRAND, N_CASES_TARGET, EVAL_POOL_FRACTION, RANDOM_SEED,
    REFERENCE_POOL_PATH, EVAL_POOL_PATH, CASES_PATH,
)
from src.text_utils import clean_for_matching

random.seed(RANDOM_SEED)


def main():
    print(f"Loading {RAW_CSV} ...")
    df = pd.read_csv(
        RAW_CSV,
        dtype={
            "tweet_id": str,
            "author_id": str,
            "in_response_to_tweet_id": str,
            "response_tweet_id": str,
        },
    )
    print("Total rows:", len(df))

    brand_tweets = df[df["author_id"] == BRAND]

    # Map each customer tweet_id -> list of AppleSupport reply texts that
    # answered it (AppleSupport tweet whose in_response_to_tweet_id == that
    # customer tweet).
    reply_lookup = {}
    for _, r in brand_tweets.iterrows():
        parent = r["in_response_to_tweet_id"]
        if isinstance(parent, str) and parent and parent != "nan":
            reply_lookup.setdefault(parent, []).append(r["text"])
    print(f"Customer tweets that received an {BRAND} reply:", len(reply_lookup))

    # Customer messages that received an AppleSupport reply.
    customer_msgs = df[
        (df["inbound"] == True) & (df["tweet_id"].isin(reply_lookup.keys()))
    ].copy()
    print(f"Customer messages replied to by {BRAND}:", len(customer_msgs))

    # Only keep *first-turn* cases: the customer message itself was not a
    # reply to a prior AppleSupport message (i.e. it opens a fresh issue,
    # not a mid-thread follow-up). Scope decision: multi-turn follow-ups are
    # out of scope for this v1 (see decision log).
    # A first-turn customer message either has no parent, or its parent is
    # not authored by AppleSupport.
    parent_author = df.set_index("tweet_id")["author_id"].to_dict()
    def is_first_turn(row):
        parent_id = row["in_response_to_tweet_id"]
        if not isinstance(parent_id, str) or not parent_id or parent_id == "nan":
            return True
        return parent_author.get(parent_id) != BRAND

    customer_msgs = customer_msgs[customer_msgs.apply(is_first_turn, axis=1)]
    print("First-turn cases (customer opened the issue):", len(customer_msgs))

    cases = []
    for _, row in customer_msgs.iterrows():
        replies = reply_lookup.get(row["tweet_id"])
        if not replies:
            continue
        cases.append({
            "case_id": row["tweet_id"],
            "customer_text": row["text"],
            "customer_text_clean": clean_for_matching(row["text"]),
            "brand_reply": replies[0],
            "created_at": row["created_at"],
        })

    print("Cases with a captured resolution:", len(cases))

    # Deduplicate near-identical customer texts (bots / copy-paste spam) so
    # they don't dominate the retrieval index or the golden sample.
    seen = set()
    deduped = []
    for c in cases:
        key = c["customer_text_clean"].lower()
        if key in seen or len(key) < 10:
            continue
        seen.add(key)
        deduped.append(c)
    print("After dedup:", len(deduped))

    random.shuffle(deduped)
    if len(deduped) > N_CASES_TARGET:
        deduped = deduped[:N_CASES_TARGET]
    print("Working sample size:", len(deduped))

    n_eval = int(len(deduped) * EVAL_POOL_FRACTION)
    eval_pool = deduped[:n_eval]
    reference_pool = deduped[n_eval:]
    print("Reference pool (retrieval index):", len(reference_pool))
    print("Eval pool (held out, golden set drawn from here):", len(eval_pool))

    Path(CASES_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(CASES_PATH, "w", encoding="utf-8") as f:
        for c in deduped:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(REFERENCE_POOL_PATH, "w", encoding="utf-8") as f:
        for c in reference_pool:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(EVAL_POOL_PATH, "w", encoding="utf-8") as f:
        for c in eval_pool:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("Wrote:", CASES_PATH, REFERENCE_POOL_PATH, EVAL_POOL_PATH)


if __name__ == "__main__":
    main()
