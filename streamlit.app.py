import streamlit as st
import pandas as pd
from supabase import create_client, Client
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import io
from openai import OpenAI
import base64

# ---- CONFIG ---- #
st.set_page_config(page_title="Knowverse Agent", layout="centered")
st.title("🌐 Knowverse: AI Knowledgebase PDF Generator")

# ---- LOAD SECRETS ---- #
openai_api_key = st.secrets["openai_key"]
supabase_url = st.secrets["supabase_url"]
supabase_key = st.secrets["supabase_key"]

# ---- OPENAI CLIENT ---- #
client = OpenAI(api_key=openai_api_key)

# ---- SUPABASE ---- #
@st.cache_resource
def get_supabase():
    return create_client(supabase_url, supabase_key)

supabase = get_supabase()

# ---- SUBMISSION FORM ---- #
st.subheader("✍️ Submit a New Knowledgebase Entry")
with st.form("entry_form"):
    project_name = st.text_input("Project / Business Name")
    audience = st.text_input("Target Audience")
    platforms = st.multiselect("Supported Platforms", ["Web", "VR", "Discord", "WhatsApp", "Horizon Worlds", "Mobile", "Desktop"])
    tags = st.text_input("Tags (comma-separated keywords)")

    if st.form_submit_button("🧠 Generate Summary with AI"):
        if project_name and audience:
            summary_prompt = f"Write a 1-2 sentence summary for a project called '{project_name}', which targets {audience} and works on platforms like {', '.join(platforms)}. The tags are: {tags}."
            summary_response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": summary_prompt}]
            )
            st.session_state.generated_summary = summary_response.choices[0].message.content.strip()
            st.success("AI-generated summary inserted below. You can review and edit it.")

    summary = st.text_area("Summary (1-2 sentences)", value=st.session_state.get("generated_summary", ""))

    features = st.text_area("Key Features / Capabilities (markdown bullets)")

    if st.form_submit_button("🧠 Generate Use Cases with AI"):
        if project_name and audience:
            use_prompt = f"List primary use cases for a project named '{project_name}' that runs on {', '.join(platforms)} and serves {audience}. Tags: {tags}."
            use_response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": use_prompt}]
            )
            st.session_state.generated_use_cases = use_response.choices[0].message.content.strip()
            st.success("AI-generated use cases inserted below. You can review and edit it.")

    use_cases = st.text_area("Primary Use Cases", value=st.session_state.get("generated_use_cases", ""))

    url = st.text_input("Website or Project URL (optional)")
    contact_email = st.text_input("Optional Contact Email")
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
                # ---- Generate Markdown Report with GPT ---- #
                report_prompt = f"""
                You are a report assistant. Format the following knowledgebase entry into a clean markdown document suitable for PDF export and upload to a Multiverse knowledge base:

                {payload}
                """
                with st.spinner("Generating markdown report and PDF..."):
                    response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": report_prompt}]
                    )
                    report_text = response.choices[0].message.content

                    # ---- Generate PDF ---- #
                    buffer = io.BytesIO()
                    c = canvas.Canvas(buffer, pagesize=LETTER)
                    text_obj = c.beginText(40, 750)
                    for line in report_text.split('\n'):
                        text_obj.textLine(line)
                    c.drawText(text_obj)
                    c.showPage()
                    c.save()

                    buffer.seek(0)
                    file_bytes = buffer.read()
                    file_name = f"{project_name.replace(' ', '_')}.pdf"

                    # ---- Upload to Supabase Storage ---- #
                    supabase.storage.from_('pdfs').upload(file=file_bytes, path=file_name, file_options={"content-type": "application/pdf"})
                    public_url = f"{supabase_url}/storage/v1/object/public/pdfs/{file_name}"

                    # ---- Save to responses table with PDF URL ---- #
                    payload["pdf_url"] = public_url
                    supabase.table("responses").insert(payload).execute()

                    st.success("✅ Your entry has been submitted to the Knowverse.")
                    st.markdown("🧾 A copy of your submission has been saved.")
                    st.download_button(
                        label="📄 Download Your Submission as PDF",
                        data=file_bytes,
                        file_name=file_name,
                        mime="application/pdf"
                    )
                    st.markdown(f"[🔗 View PDF in Supabase Storage]({public_url})")

                    st.session_state.pop("generated_summary", None)
                    st.session_state.pop("generated_use_cases", None)

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
    prompt = f"""
    You are a report assistant. Format the following knowledgebase entry into a clean markdown document suitable for PDF export and upload to a Multiverse knowledge base:

    {row_data.to_dict()}
    """

    if st.button("Generate Report Text"):
        with st.spinner("Calling GPT..."):
            response = client.chat.completions.create(
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
