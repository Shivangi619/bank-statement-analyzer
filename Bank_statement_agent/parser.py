import pdfplumber
import pandas as pd
import pytesseract
from pdf2image import convert_from_path
import re
import io
import os

# OCR fallback function
def extract_text_with_ocr(file_path):
    print(" Using OCR to extract text from scanned PDF pages...")
    images = convert_from_path(file_path)
    all_text = ""

    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        print(f"\n--- OCR Page {i+1} ---\n{text[:200]}...\n")
        all_text += text + "\n"

    return all_text

# Transaction parser that skips non-transaction lines
def extract_transactions(text):
    transactions = []
    start_extracting = False

    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line.split()) < 3:
            continue

        # Detect start of transaction section using date
        if not start_extracting:
            if re.match(r'\d{2}[\-/]\d{2}[\-/]\d{4}', line):
                start_extracting = True
            else:
                continue  # skip irrelevant lines

        date_match = re.match(r'(\d{2}[\-/]\d{2}[\-/]\d{4})', line)
        if not date_match:
            continue

        date = date_match.group(1)
        parts = line.split()
        amounts = re.findall(r'-?[\d,]+\.\d{2}', line)
        amount = amounts[-1] if amounts else ""

        # Remove date and amount from line to get description
        desc_parts = [p for p in parts if p != date and p not in amounts]
        description = " ".join(desc_parts)

        transactions.append({
            "Date": date,
            "Description": description,
            "Amount": amount
        })

    return transactions

# Final PDF parsing logic
def parse_pdf(file_path, password=None):
    transactions = []

    print("\n Attempting PDF text extraction...")
    try:
        with pdfplumber.open(file_path, password=password or "") as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    print(f"\n--- Text from Page {page.page_number} ---\n{text[:300]}...\n")
                    transactions += extract_transactions(text)
                else:
                    print(f" No extractable text on Page {page.page_number} → trying OCR...")
                    ocr_text = extract_text_with_ocr(file_path)
                    transactions += extract_transactions(ocr_text)
                    break  # OCR reads all pages together

    except Exception as e:
        print(f" Error opening or processing PDF: {e}")
        return pd.DataFrame(columns=["Date", "Description", "Amount"])

    if not transactions:
        print(" No transactions found. Please check the PDF format or update extraction logic.")
        return pd.DataFrame(columns=["Date", "Description", "Amount"])

    return pd.DataFrame(transactions)

# Example main function for testing
def main():
    file_path = input("Enter full path to the bank statement (.pdf): ").strip()

    if not file_path.lower().endswith('.pdf') or not os.path.isfile(file_path):
        print(" Invalid PDF file path.")
        return

    password = input("Enter PDF password (if any, else leave blank): ").strip() or None

    df = parse_pdf(file_path, password=password)

    if not df.empty:
        print("\n PDF Parsed Successfully!")
        print(df.head())
        df.to_csv("parsed_output.csv", index=False)
        print(" Saved to parsed_output.csv")
    else:
        print("\n Parsing failed or no valid data extracted.")

if __name__ == "__main__":
    main()
