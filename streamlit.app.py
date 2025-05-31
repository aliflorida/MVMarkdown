import streamlit as st
import openai
import pandas as pd
from supabase import create_client, Client
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import io

# ---- CONFIG ---- #
st.set_page_config(page_title="Knowverse Agent", layout="centered")
st.title("🌐 Knowverse: AI Knowledgebase PDF Generator")

# ---- LOAD SECRETS ---- #
openai_api_key = st.secrets["openai_key"]
supabase_url = st.secrets["supabase_url"]
supabase_key = st.secrets["supabase_key"]

# ---- LOAD DATA FROM SUPABASE ---- #
@st.cache_resource
def get_supabase():
    return create_client(supabase_url, supabase_key)

supabase = get_supabase()
data = supabase.table("responses").select("*").execute()
df = pd.DataFrame(data.data)

if df.empty:
    st.warning("No responses found in Supabase table 'responses'.")
else:
    st.success("✅ Supabase data loaded successfully")

    selected_row = st.selectbox("Select a response row to generate PDF", df.index)
    row_data = df.loc[selected_row]

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
