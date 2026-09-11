import pandas as pd

DATA_PATH = r"D:\Varu_info\Hiver\reports\sample.csv"

df = pd.read_csv(DATA_PATH)

print("Shape:", df.shape)

print("\nColumns:")
print(df.columns.tolist())

print("\nFirst 5 rows:")
print(df.head())

print("\nData types:")
print(df.dtypes)

print("\nMissing values:")
print(df.isnull().sum())