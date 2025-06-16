import pandas as pd
import re

def clean_parsed_data(input_path="parsed_output1.csv", output_path="cleaned_output.csv"):
    try:
        # Load parsed data
        df = pd.read_csv(input_path)

        # Drop rows where required columns are missing or malformed
        df.dropna(subset=["Date", "Description", "Amount"], inplace=True)

        # Clean and standardize the 'Date' column
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.dropna(subset=["Date"], inplace=True)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")  # Format as YYYY-MM-DD

        # Clean 'Amount' column: remove any unwanted characters, convert to float
        df["Amount"] = df["Amount"].astype(str)
        df["Amount"] = df["Amount"].apply(lambda x: re.sub(r"[^\d\.-]", "", x))
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df.dropna(subset=["Amount"], inplace=True)

        # Optional: Remove duplicate rows
        df.drop_duplicates(inplace=True)

        # Optional: Strip whitespace from text columns
        df["Description"] = df["Description"].str.strip()

        # Save cleaned data
        df.to_csv(output_path, index=False)
        print(f"\n Cleaned data saved to: {output_path}")
        print(df.head())

    except FileNotFoundError:
        print(f" File '{input_path}' not found.")
    except Exception as e:
        print(f" An error occurred: {e}")


if __name__ == "__main__":
    clean_parsed_data()
