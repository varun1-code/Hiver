import pandas as pd

DATA_PATH = r"D:\Varu_info\Hiver\reports\sample.csv"

df = pd.read_csv(DATA_PATH)

df["tweet_id"] = df["tweet_id"].astype(str)

df["in_response_to_tweet_id"] = (
    df["in_response_to_tweet_id"]
    .fillna("")
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
)

def show_conversations(brand, n=5):

    print("\n" + "=" * 70)
    print(f"{brand} SAMPLE CONVERSATIONS")
    print("=" * 70)

    brand_tweets = df[df["author_id"] == brand]

    # Customer messages directly responding to the brand
    customer_messages = df[
        (df["inbound"] == True) &
        (df["in_response_to_tweet_id"].isin(
            brand_tweets["tweet_id"]
        ))
    ]

    shown = 0

    for _, customer in customer_messages.iterrows():

        customer_id = customer["tweet_id"]

        # Brand response to customer
        responses = df[
            (df["author_id"] == brand) &
            (df["in_response_to_tweet_id"] == customer_id)
        ]

        if len(responses) == 0:
            continue

        print("\nCUSTOMER:")
        print(customer["text"])

        for _, response in responses.iterrows():
            print("\nBRAND:")
            print(response["text"])

        print("\n" + "-" * 70)

        shown += 1

        if shown >= n:
            break


show_conversations("Uber_Support", 5)
show_conversations("SpotifyCares", 5)