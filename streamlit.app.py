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

# ---- SUBMISSION FORM ---- #
st.subheader("✍️ Submit a New Knowledgebase Entry")
with st.form("entry_form"):
    project_name = st.text_input("Project / Business Name")
    summary = st.text_area("Summary (1-2 sentences)")
    features = st.text_area("Key Features / Capabilities (markdown bullets)")
    use_cases = st.text_area("Primary Use Cases")
    platforms = st.multiselect("Supported Platforms", ["Web", "VR", "Discord", "WhatsApp", "Horizon Worlds", "Mobile", "Desktop"])
    audience = st.text_input("Target Audience")
    url = st.text_input("Website or Project URL (optional)")
    contact_email = st.text_input("Optional Contact Email")
    tags = st.text_input("Tags (comma-separated keywords)")
    submit = st.form_submit_button("Submit Entry")

    if submit:
        if not project_name or not summary:
            st.warning("Please fill in at least the project name and summary.")
        else:
            payload = {
                "project_name": project_name,
                "summary": summary,
                "features": features,
                "use_cases": use_cases,
                "platforms": ", ".join(platforms),
                "audience": audience,
                "url": url,
                "contact_email": contact_email,
                "tags": tags
            }
            st.write("Attempting to insert:", payload)
            try:
                supabase.table("responses").insert(payload).execute()
                st.success("✅ Thank you for your submission! You'll receive an update via email when your knowledgebase entry goes live.")
            except Exception as e:
                st.error(f"❌ Error submitting entry: {e}")

# ---- DISPLAY EXISTING RESPONSES ---- #
data = supabase.table("responses").select("*").execute()
df = pd.DataFrame(data.data)

if df.empty:
    st.info("No responses found in Supabase table 'responses'.")
else:
    st.subheader("🧠 Generate PDF from a Response")
    selected_row = st.selectbox("Select a response row to generate PDF", df.index)
    row_data = df.loc[selected_row]

    # ---- GPT PROCESSING ---- #
    openai.api_key = openai_api_key
    prompt = f"""
    You are a report assistant. Format the following knowledgebase entry into a clean markdown document suitable for PDF export and upload to a Multiverse knowledge base:

    {row_data.to_dict()}
    """

    if st.button("Generate Report Text"):
        with st.spinner("Calling GPT..."):
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            report_text = response.choices[0].message.content
            st.text_area("Generated Markdown Report", report_text, height=300)

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
