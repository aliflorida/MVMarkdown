import streamlit as st
import openai
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import io

# ---- CONFIG ---- #
st.set_page_config(page_title="Form to PDF Agent", layout="centered")
st.title("📝 Google Form to PDF Generator")

# ---- API & CREDENTIAL INPUT ---- #
openai_api_key = st.text_input("🔑 OpenAI API Key", type="password")
gsheet_json = st.file_uploader("📁 Upload Google Service Account Credentials (.json)", type="json")
sheet_url = st.text_input("🔗 Google Sheet URL")

if openai_api_key and gsheet_json and sheet_url:
    # ---- SHEET SETUP ---- #
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(gsheet_json.name, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(sheet_url).sheet1
    data = pd.DataFrame(sheet.get_all_records())

    st.success("✅ Google Sheet Loaded Successfully")

    # ---- SELECT ROW TO PROCESS ---- #
    selected_row = st.selectbox("Select a response row to generate PDF", data.index)
    row_data = data.loc[selected_row]

    # ---- GPT PROCESSING ---- #
    openai.api_key = openai_api_key
    prompt = f"""
    You are a report assistant. Format the following form response into a professional summary:

    {row_data.to_dict()}

    Write it as a report suitable for PDF output.
    """

    if st.button("🧠 Generate Report Text"):
        with st.spinner("Calling GPT..."):
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            report_text = response.choices[0].message.content
            st.text_area("📝 Generated Report", report_text, height=300)

            # ---- PDF GENERATION ---- #
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=LETTER)
            text_obj = c.beginText(40, 750)
            for line in report_text.split('\n'):
                text_obj.textLine(line)
            c.drawText(text_obj)
            c.showPage()
            c.save()

            st.download_button(
                label="📄 Download PDF",
                data=buffer.getvalue(),
                file_name=f"response_{selected_row}.pdf",
                mime="application/pdf"
            )
