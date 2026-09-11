import pandas as pd
from collections import defaultdict

DATA_PATH = r"D:\Varu_info\Hiver\reports\sample.csv"

df = pd.read_csv(DATA_PATH)

brands = [
    "AmazonHelp",
    "AppleSupport",
    "Uber_Support",
    "SpotifyCares",
    "Delta",
    "Tesco",
    "AmericanAir",
    "TMobileHelp"
]

# Make tweet lookup
tweet_lookup = df.set_index("tweet_id")["author_id"].to_dict()

for brand in brands:

    brand_tweets = df[df["author_id"] == brand]

    # Tweets where this brand is involved
    involved = df[
        (df["author_id"] == brand) |
        (
            df["in_response_to_tweet_id"].isin(
                brand_tweets["tweet_id"]
            )
        )
    ].copy()

    # Count direct customer -> brand interactions
    customer_messages = involved[
        involved["inbound"] == True
    ]

    # Messages that have a parent tweet
    with_parent = customer_messages[
        customer_messages["in_response_to_tweet_id"].notna()
    ]

    print(f"\n{brand}")
    print("-" * 40)
    print("Customer messages:", len(customer_messages))
    print("Customer messages with parent:", len(with_parent))

    if len(customer_messages) > 0:
        print(
            "Parent coverage:",
            round(len(with_parent) / len(customer_messages) * 100, 2),
            "%"
        )