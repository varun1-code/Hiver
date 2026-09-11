import pandas as pd

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

print("\n===== BRAND ANALYSIS =====\n")

for brand in brands:

    brand_outbound = df[
        (df["author_id"] == brand) &
        (df["inbound"] == False)
    ]

    # Customer tweets directly replying to this brand
    customer_inbound = df[
        (df["inbound"] == True) &
        (df["in_response_to_tweet_id"].isin(
            brand_outbound["tweet_id"]
        ))
    ]

    print(f"\n{brand}")
    print("-" * 40)
    print("Brand responses:", len(brand_outbound))
    print("Customer replies:", len(customer_inbound))
    print("Total:", len(brand_outbound) + len(customer_inbound))