import streamlit as st
import pdfplumber
import requests
import json
import pandas as pd
import re
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    try:
        API_KEY = st.secrets["OPENROUTER_API_KEY"]
    except:
        st.error("API key not found. Please set it in .env or Streamlit secrets.")
        st.stop()

st.set_page_config(page_title="AI Bulk PDF Extractor", layout="wide")

st.title("📂 AI Bulk PDF Extractor")

# Input folder path
folder_path = st.text_input("Enter folder path (e.g. resumes/)")

if st.button("🚀 Process All PDFs"):
    all_results = []
    failed_files = []

    if not os.path.exists(folder_path):
        st.error("❌ Folder not found")
    else:
        pdf_files = [f for f in os.listdir(folder_path) if f.endswith(".pdf")]

        st.write(f"📄 Found {len(pdf_files)} PDFs")

        if len(pdf_files) == 0:
            st.warning("⚠️ No PDF files found")
        else:
            progress = st.progress(0)

            for i, file in enumerate(pdf_files):

                file_path = os.path.join(folder_path, file)

                # -------- STEP 1: Extract text --------
                all_text = ""
                try:
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text:
                                all_text += text + "\n"
                except:
                    all_text = ""

                # -------- STEP 2: AI Extraction --------
                prompt = f"""
Extract the following from this resume:

- Name
- Email
- Phone

Return ONLY valid JSON like:
{{
 "name": "",
 "email": "",
 "phone": ""
}}

Text:
{all_text}
"""

                try:
                    with st.spinner(f"🤖 Processing {file}..."):
                        url = "https://openrouter.ai/api/v1/chat/completions"

                        headers = {
                            "Authorization": f"Bearer {API_KEY}",
                            "Content-Type": "application/json"
                                }

                        payload = {
                            "model": "stepfun/step-3.5-flash:free",
                            "messages": [
                                {"role": "user", "content": prompt}
                            ]
                        }

                        response = requests.post(url, headers=headers, json=payload)

                        raw_output = response.json()["choices"][0]["message"]["content"]

                    # -------- STEP 3: Extract JSON safely --------
                    match = re.search(r'\{.*\}', raw_output, re.DOTALL)

                    if match:
                        try:
                            data = json.loads(match.group())

                            # Clean missing values
                            data["name"] = data.get("name") or ""
                            data["email"] = data.get("email") or ""
                            data["phone"] = data.get("phone") or ""

                        except:
                            data = {"name": "", "email": "", "phone": ""}
                    else:
                        data = {"name": "", "email": "", "phone": ""}

                except:
                    data = {"name": "", "email": "", "phone": ""}

                # Check if data is empty
                if data["name"] == "" and data["email"] == "" and data["phone"] == "":
                    failed_files.append(file)
                else:
                    data["file"] = file
                    all_results.append(data)

                # Update progress
                progress.progress((i + 1) / len(pdf_files))

            # -------- STEP 4: Create DataFrame --------
            df = pd.DataFrame(all_results)
            if failed_files:
                st.warning(f"⚠️ Failed to process {len(failed_files)} files")
                st.write(failed_files)

            st.success("✅ All PDFs processed")
            st.dataframe(df, use_container_width=True)

            # -------- STEP 5: Download CSV --------
            csv = df.to_csv(index=False).encode('utf-8')

            st.download_button(
                "⬇️ Download CSV",
                csv,
                "bulk_output.csv",
                "text/csv"
            )
