import pandas as pd

DATA_PATH =r"D:\Varu_info\Hiver\reports\sample.csv"

df = pd.read_csv(DATA_PATH)

# Normalize IDs
df["tweet_id"] = df["tweet_id"].astype(str)

df["in_response_to_tweet_id"] = (
    df["in_response_to_tweet_id"]
    .fillna("")
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
)

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

print("\n===== CONVERSATION QUALITY =====")

# Create a lookup:
# tweet_id -> author
tweet_author = dict(
    zip(df["tweet_id"], df["author_id"])
)

for brand in brands:

    # All tweets written by this brand
    brand_tweets = df[df["author_id"] == brand]

    brand_ids = set(brand_tweets["tweet_id"])

    # Customer tweets directly replying to the brand
    customer_messages = df[
        (df["inbound"] == True) &
        (df["in_response_to_tweet_id"].isin(brand_ids))
    ]

    customer_ids = set(customer_messages["tweet_id"])

    # Brand replies directly to those customers
    brand_responses = df[
        (df["author_id"] == brand) &
        (df["in_response_to_tweet_id"].isin(customer_ids))
    ]

    responded_to_customers = set(
        brand_responses["in_response_to_tweet_id"]
    )

    # Number of customer messages that received a brand response
    resolved = customer_messages[
        customer_messages["tweet_id"].isin(
            responded_to_customers
        )
    ]

    print(f"\n{brand}")
    print("-" * 40)
    print("Brand tweets:", len(brand_tweets))
    print("Customer messages:", len(customer_messages))
    print("Customer messages with brand response:", len(resolved))

    if len(customer_messages) > 0:
        coverage = (
            len(resolved) /
            len(customer_messages) *
            100
        )

        print(
            "Response coverage:",
            round(coverage, 2),
            "%"
        )