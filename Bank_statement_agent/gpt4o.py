import streamlit as st
import pandas as pd
import openai
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import io
import re
import warnings
from pdfminer.pdfparser import PDFSyntaxError

#  Set your OpenAI API Key
openai_api_key = "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"  
client = openai.OpenAI(api_key=openai_api_key)

warnings.filterwarnings("ignore", category=UserWarning)
st.set_page_config(page_title="Bank Statement Analyzer", layout="wide")
st.title("💳 Bank Statement Analyzer with GPT-4o")

# File uploader
uploaded_file = st.file_uploader(" Upload your bank statement (.csv or .pdf)", type=["csv", "pdf"])

# Ask password if file is PDF
pdf_password = ""
if uploaded_file and uploaded_file.name.endswith(".pdf"):
    pdf_password = st.text_input(" Enter PDF password (if locked)", type="password")

# OCR fallback for scanned PDFs
def extract_text_with_ocr(pdf_stream):
    images = convert_from_bytes(pdf_stream.read())
    return "\n".join(pytesseract.image_to_string(img) for img in images)

# Transaction extractor from raw text
def extract_transactions(text):
    transactions = []
    start_extracting = False
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line.split()) < 3:
            continue

        if not start_extracting:
            if re.match(r'\d{2}[\-/]\d{2}[\-/]\d{4}', line):
                start_extracting = True
            else:
                continue

        date_match = re.match(r'(\d{2}[\-/]\d{2}[\-/]\d{4})', line)
        if not date_match:
            continue

        date = date_match.group(1)
        parts = line.split()
        amounts = re.findall(r'-?[\d,]+\.\d{2}', line)
        amount = amounts[-1] if amounts else ""
        desc_parts = [p for p in parts if p != date and p not in amounts]
        description = " ".join(desc_parts)

        transactions.append({
            "Date": date,
            "Description": description,
            "Amount": amount
        })
    return transactions

# Parse PDF with fallback to OCR
def parse_structured_table_pdf(uploaded_file, password=None):
    import io
    import pdfplumber

    file_bytes = uploaded_file.read()
    stream = io.BytesIO(file_bytes)

    try:
        with pdfplumber.open(stream, password=password or "") as pdf:
            transactions = []
            for page in pdf.pages:
                table = page.extract_table()
                if not table:
                    continue

                for row in table:
                    if row[0] == "Date" or not row[0]:
                        continue  # Skip header or empty rows

                    date = row[0].strip()
                    description = row[1].strip().replace("\n", " ") if row[1] else ""
                    debit = row[3].strip().replace(",", "") if row[3] else ""
                    credit = row[4].strip().replace(",", "") if row[4] else ""
                    balance = row[5].strip().replace(",", "") if row[5] else ""

                    # Determine final signed amount
                    if credit and credit != "-":
                        amount = float(credit)
                    elif debit and debit != "-":
                        amount = -float(debit)
                    else:
                        amount = 0.0

                    transactions.append({
                        "Date": date,
                        "Description": description,
                        "Amount": amount,
                        "Balance": float(balance) if balance else ""
                    })

            return pd.DataFrame(transactions)
    except Exception as e:
        st.error(f"❌ Error parsing structured table: {e}")
        return pd.DataFrame()


# Categorize each transaction using GPT-4o
def categorize_transactions(df):
    categories = []
    for _, row in df.iterrows():
        prompt = f"""Categorize this transaction into: Food & Dining, Transport, Utilities, Salary, Shopping, Rent, Medical, Entertainment, Others.

        Description: {row['Description']}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a financial assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            category = response.choices[0].message.content.strip()
        except Exception:
            category = "Unknown"
        categories.append(category)

    df["Category"] = categories
    return df

# Summarize using GPT-4o
def ask_gpt4o(df, user_question=None):
    # Reduce size: only keep top 30 rows and needed columns
    reduced_df = df[["Description", "Amount"]].head(30)
    context = reduced_df.to_string(index=False)

    messages = [
        {"role": "system", "content": "You are a financial assistant. Categorize and summarize the user's bank statement."},
        {"role": "user", "content": f"This is my bank statement:\n{context}\n\n{user_question or 'Please summarize the spending by category.'}"}
    ]

    client = openai.OpenAI(api_key=openai_api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f" Error during GPT-4o response: {e}"


# ==== MAIN LOGIC ====
if uploaded_file:
    file_type = uploaded_file.name.split(".")[-1].lower()

    if file_type == "pdf":
        st.info("🔍 Parsing PDF...")
        df = parse_structured_table_pdf(uploaded_file, password=pdf_password)
    elif file_type == "csv":
        df = pd.read_csv(uploaded_file)
    else:
        st.error("Unsupported file type.")
        st.stop()

    if df.empty:
        st.warning(" No valid transactions extracted.")
        st.stop()

    # Clean Amount: remove commas and convert to float
    df["Amount"] = df["Amount"].astype(str).str.replace(",", "").astype(float)


    # Categorize transactions
    df = categorize_transactions(df)

    # Show results
    st.subheader(" Parsed & Categorized Transactions")
    st.dataframe(df)

    # Save
    df.to_csv("cleaned_output.csv", index=False)
    st.success(" Cleaned file saved as 'cleaned_output.csv'")

    # GPT-4o button
    if st.button(" Summarize with GPT-4o"):
        with st.spinner("GPT-4o analyzing..."):
            result = ask_gpt4o(df)
            st.subheader(" GPT-4o Summary")
            st.markdown(result)

    # Optional user query
    question = st.text_input(" Ask GPT-4o about your data")
    if question:
        with st.spinner("Thinking..."):
            answer = ask_gpt4o(df, user_question=question)
            st.markdown("####  GPT-4o Answer")
            st.markdown(answer)
