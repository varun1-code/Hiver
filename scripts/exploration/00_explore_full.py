"""One-off exploration of the full twcs.csv to size up AppleSupport data.
Not part of the reproducible pipeline; run manually, prints to stdout.
"""
import pandas as pd

DATA_PATH = r"D:\Varu_info\Hiver\reports\twcs\twcs.csv"
BRAND = "AppleSupport"

df = pd.read_csv(
    DATA_PATH,
    dtype={"tweet_id": str, "author_id": str, "in_response_to_tweet_id": str, "response_tweet_id": str},
)
print("Total rows:", len(df))

brand_tweets = df[df["author_id"] == BRAND]
print(f"{BRAND} outbound tweets:", len(brand_tweets))

brand_ids = set(brand_tweets["tweet_id"])
customer_to_brand = df[(df["inbound"] == True) & (df["in_response_to_tweet_id"].isin(brand_ids))]
print(f"Customer messages replying directly to {BRAND}:", len(customer_to_brand))

# First-turn customer messages: mentions AppleSupport and has no in_response_to (i.e. opens a new thread)
first_turn = df[
    (df["inbound"] == True)
    & (df["text"].str.contains("@AppleSupport", case=False, na=False))
    & (df["in_response_to_tweet_id"].isna())
]
print("First-turn customer messages mentioning @AppleSupport:", len(first_turn))

# sample some first-turn texts
print("\nSample first-turn customer messages:")
for t in first_turn["text"].sample(20, random_state=42):
    print("-", t.replace("\n", " ")[:180])
