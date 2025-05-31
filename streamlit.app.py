import streamlit as st
import pandas as pd
from datetime import datetime
import io
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from supabase import create_client, Client
from openai import OpenAI

# ---- CONFIG ---- #
st.set_page_config(page_title="Knowverse Agent", layout="centered")
st.title("🌐 Knowverse: AI Knowledgebase PDF Generator")

# ---- LOAD SECRETS ---- #
openai_api_key = st.secrets["openai_key"]
supabase_url = st.secrets["supabase_url"]
supabase_key = st.secrets["supabase_key"]
admin_key = st.secrets["admin_key"]

client = OpenAI(api_key=openai_api_key)

# ---- LOAD DATA FROM SUPABASE ---- #
@st.cache_resource
def get_supabase():
    return create_client(supabase_url, supabase_key)

supabase = get_supabase()

# ---- USER INPUT STAGE 1: PRE-FORM INPUTS ---- #
project_name = st.text_input("Project / Business Name")
features = st.text_area("Key Features / Capabilities (markdown bullets)")

if st.button("✨ Generate Summary"):
    if project_name:
        prompt = f"Write a 1-2 sentence summary for a project called '{project_name}' that will be listed in an AI knowledgebase."
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state["generated_summary"] = response.choices[0].message.content.strip()
    else:
        st.warning("Please enter a project name first.")

if st.button("✨ Generate Use Cases"):
    if project_name and features:
        prompt = f"List 1 or 2 practical use cases for a project called '{project_name}' with features like: {features}."
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state["generated_use_cases"] = response.choices[0].message.content.strip()
    else:
        st.warning("Please enter project name and features first.")

# ---- SUBMISSION FORM ---- #
st.subheader("✍️ Submit a New Knowledgebase Entry")
with st.form("entry_form"):
    summary = st.text_area("Summary (1-2 sentences)", value=st.session_state.get("generated_summary", ""))
    use_cases = st.text_area("Primary Use Cases (1-2 max)", value=st.session_state.get("generated_use_cases", ""))
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

        try:
            upload_response = supabase.storage.from_("pdfs").upload(pdf_path, pdf_bytes, {"content-type": "application/pdf"})
            public_pdf_url = supabase.storage.from_("pdfs").get_public_url(pdf_path)
        except Exception as e:
            st.error(f"❌ Upload failed: {e}")
            public_pdf_url = ""

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
