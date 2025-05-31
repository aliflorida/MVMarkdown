import streamlit as st
import pandas as pd
import io
import datetime
from openai import OpenAI
from supabase import create_client
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

# ---- CONFIG ---- #
st.set_page_config(page_title="Knowverse Agent", layout="centered")
st.title("🌐 Knowverse: AI Knowledgebase PDF Generator")

# ---- SECRETS ---- #
openai_api_key = st.secrets["openai_key"]
supabase_url = st.secrets["supabase_url"]
supabase_key = st.secrets["supabase_key"]
admin_key = st.secrets.get("admin_key", "")

# ---- SUPABASE ---- #
supabase = create_client(supabase_url, supabase_key)

# ---- OPENAI CLIENT ---- #
client = OpenAI(api_key=openai_api_key)

# ---- SESSION STATE FOR AI HELP ---- #
if "generated_summary" not in st.session_state:
    st.session_state.generated_summary = ""
if "generated_use_cases" not in st.session_state:
    st.session_state.generated_use_cases = ""

# ---- AI GENERATION BUTTONS ---- #
st.subheader("🧠 AI Assistance")
project_name = st.text_input("Project / Business Name")
features = st.text_area("Key Features / Capabilities")

if st.button("✨ Generate Summary"):
    if project_name:
        prompt = f"Write a professional 1-2 sentence summary for a project called '{project_name}'."
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state.generated_summary = response.choices[0].message.content.strip()

if st.button("✨ Generate Use Cases"):
    if project_name and features:
        prompt = f"Suggest 1 or 2 primary use cases for a project called '{project_name}' with features: {features}."
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state.generated_use_cases = response.choices[0].message.content.strip()

# ---- FORM ---- #
st.subheader("✍️ Submit a New Knowledgebase Entry")
with st.form("entry_form"):
    summary = st.text_area("Summary", value=st.session_state.generated_summary)
    use_cases = st.text_area("Use Cases", value=st.session_state.generated_use_cases)
    platforms = st.multiselect("Supported Platforms", ["Multiverse", "Web", "VR", "Discord", "WhatsApp", "Horizon Worlds", "Mobile", "Desktop"])
    audience = st.text_input("Target Audience")
    url = st.text_input("Website or Project URL (optional)")
    contact_email = st.text_input("Optional Contact Email")
    tags = st.text_input("Tags (comma-separated keywords)")
    language = st.selectbox("Language", ["English", "Spanish", "French", "German", "Portuguese", "Chinese"])
    submit = st.form_submit_button("Submit Entry")

    if submit:
        try:
            now = datetime.datetime.utcnow().isoformat()
            supabase.table("responses").insert({
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
                "created_at": now
            }).execute()

            # Generate markdown
            markdown = f"""
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
            # Create PDF
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=LETTER)
            text_obj = c.beginText(40, 750)
            for line in markdown.split('\n'):
                text_obj.textLine(line)
            c.drawText(text_obj)
            c.showPage()
            c.save()

            pdf_bytes = buffer.getvalue()
            pdf_path = f"{project_name.replace(' ', '_')}_{now}.pdf"

            # Upload to Supabase bucket with upsert
            res = supabase.storage.from_("pdfs").upload(
                pdf_path,
                pdf_bytes,
                {"content-type": "application/pdf"},
                upsert=True
            )

            st.success("✅ Your entry has been submitted to the Knowverse.")
            st.info("🧾 A copy of your submission has been saved.")
            st.download_button("📄 Download Your PDF", data=pdf_bytes, file_name=pdf_path, mime="application/pdf")

        except Exception as e:
            st.error(f"❌ Error submitting entry: {e}")

# ---- ADMIN VIEW ---- #
if st.query_params.get("admin") == admin_key:
    st.subheader("🔒 Admin Viewer")
    data = supabase.table("responses").select("*").execute()
    df = pd.DataFrame(data.data)
    if df.empty:
        st.info("No responses found in Supabase table 'responses'.")
    else:
        st.dataframe(df.sort_values("created_at", ascending=False))
