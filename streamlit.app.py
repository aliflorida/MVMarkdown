import streamlit as st
import openai
import pandas as pd
from supabase import create_client, Client
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import io
from datetime import datetime

# ---- CONFIG ---- #
st.set_page_config(page_title="Knowverse Agent", layout="centered")
st.title("🌐 Knowverse: AI Knowledgebase PDF Generator")

# ---- LOAD SECRETS ---- #
openai_api_key = st.secrets["openai_key"]
supabase_url = st.secrets["supabase_url"]
supabase_key = st.secrets["supabase_key"]
admin_key = st.secrets["admin_key"]

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
    use_cases = st.text_area("Primary Use Cases (1-2 max)")
    platforms = st.multiselect("Supported Platforms", ["Multiverse", "Web", "VR", "Discord", "WhatsApp", "Horizon Worlds", "Mobile", "Desktop"])
    audience = st.text_input("Target Audience")
    url = st.text_input("Website or Project URL (optional)")
    contact_email = st.text_input("Optional Contact Email")
    tags = st.text_input("Tags (comma-separated keywords)")
    language = st.selectbox("Language", ["English", "Spanish", "French", "German", "Other"])
    submit = st.form_submit_button("Submit Entry")

    if submit:
        submission_date = datetime.utcnow().isoformat()

        markdown_text = f"""
## {project_name}

**Summary**  
{summary}

**Key Features**  
{features}

**Primary Use Cases**  
{use_cases}

**Supported Platforms**: {', '.join(platforms)}  
**Target Audience**: {audience}  
**Project URL**: {url}  
**Tags**: {tags}
        """

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=LETTER)
        text_obj = c.beginText(40, 750)
        for line in markdown_text.split('\n'):
            text_obj.textLine(line)
        c.drawText(text_obj)
        c.showPage()
        c.save()
        buffer.seek(0)
        pdf_bytes = buffer.getvalue()

        file_name = f"{project_name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
        pdf_path = f"knowledgebase_pdfs/{file_name}"

        upload_response = supabase.storage.from_("pdfs").upload(pdf_path, pdf_bytes, {"content-type": "application/pdf"})
        public_pdf_url = supabase.storage.from_("pdfs").get_public_url(pdf_path)

        st.session_state["pdf_bytes"] = pdf_bytes
        st.session_state["pdf_filename"] = file_name

        response = supabase.table("responses").insert({
            "project_name": project_name,
            "summary": summary,
            "features": features,
            "use_cases": use_cases,
            "platforms": ", ".join(platforms),
            "audience": audience,
            "url": url,
            "contact_email": contact_email,
            "tags": tags,
            "language": language,
            "submission_date": submission_date,
            "pdf_url": public_pdf_url
        }).execute()

        if response.data:
            st.success("✅ Your entry has been submitted to the Knowverse.\n\n🧾 A copy of your submission has been saved.")
        else:
            st.error(f"❌ Error submitting entry: {response}")

# ---- PDF DOWNLOAD ---- #
if "pdf_bytes" in st.session_state:
    st.download_button(
        label="📄 Download Your PDF Copy",
        data=st.session_state["pdf_bytes"],
        file_name=st.session_state["pdf_filename"],
        mime="application/pdf"
    )

# ---- ADMIN VIEWER ---- #
if st.query_params.get("admin") == admin_key:
    st.subheader("🧠 Admin: View All Responses")
    data = supabase.table("responses").select("*").execute()
    df = pd.DataFrame(data.data)
    if df.empty:
        st.info("No responses found.")
    else:
        st.dataframe(df)
        selected_row = st.selectbox("Select a response row to view PDF", df.index)
        row_data = df.loc[selected_row]
        st.markdown(f"[📄 View PDF]({row_data['pdf_url']})")
