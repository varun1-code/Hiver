import pandas as pd

DATA_PATH = r"D:\Varu_info\Hiver\reports\sample.csv"

df = pd.read_csv(DATA_PATH)

# Support accounts are authors of outbound tweets
support_tweets = df[df["inbound"] == False]

brand_counts = (
    support_tweets["author_id"]
    .value_counts()
    .sort_values(ascending=False)
)

print("\nTop 30 support accounts:")
print(brand_counts.head(30))

print("\nTotal support accounts:", len(brand_counts))