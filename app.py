import io
import json
import pandas as pd
import streamlit as st
from analyzer import load_checklist_from_excel, analyze, to_markdown, to_html
from feedback_store import apply_weights_to_checklist, record_feedback

st.set_page_config(page_title="CRO Landing Page AI Agent", layout="wide")
st.title("CRO Landing Page AI Agent")

st.markdown(
    """
Gebruik deze tool om een landingspagina te beoordelen op basis van jouw checklist.
- Vul een **URL** in
- (Optioneel) Upload een **eigen Excel-checklist** (kolommen: *Categorie*, *Tip*, *Prioriteit*, *Moeilijkheidsgraad*, *Uitleg*)
- Klik **Analyze**

Deze versie leert van jouw feedback: na afloop kun je een **rating** en **comment** geven. De agent past bij volgende analyses de **prioriteit/volgorde** van checks automatisch aan.
"""
)

url = st.text_input("Landingspagina URL", placeholder="https://...")
uploaded = st.file_uploader("Checklist Excel (optioneel)", type=["xlsx"])

if st.button("Analyze", type="primary") and url:
    try:
        checklist_bytes = uploaded.read() if uploaded else None
        checklist_df = load_checklist_from_excel(checklist_bytes) if checklist_bytes else load_checklist_from_excel()

        # Nieuwe stap: adaptieve weging o.b.v. verzamelde feedback
        checklist_df = apply_weights_to_checklist(checklist_df, alpha=1.0)

        result = analyze(url, checklist_df)

        st.subheader("Samenvatting")
        st.write(result.get("summary"))

        st.subheader("Checks")
        if hasattr(result.get("checks"), "head"):
            st.dataframe(result["checks"])
        else:
            st.write(result.get("checks"))

        md = to_markdown(result)
        html = to_html(result)
        j = json.dumps(
            {
                "summary": result.get("summary"),
                "checks": result.get("checks").to_dict(orient="records") if hasattr(result.get("checks"), "to_dict") else result.get("checks"),
            },
            ensure_ascii=False,
            indent=2,
        )

        st.download_button("Download Markdown", data=md.encode("utf-8"), file_name="cro_report.md")
        st.download_button("Download HTML", data=html.encode("utf-8"), file_name="cro_report.html")
        st.download_button("Download JSON", data=j.encode("utf-8"), file_name="cro_report.json")

        st.divider()
        st.subheader("Jouw feedback")
        col1, col2 = st.columns([1, 2])
        with col1:
            rating = st.slider("Hoe nuttig was dit?", 1, 5, 4)
            task_success = st.checkbox("Taak geslaagd?")
        with col2:
            comment = st.text_area("Licht kort toe (optioneel)")

        if st.button("Opslaan als feedback"):
            reward = (rating - 3) / 2  # schaal [-1, +1]
            checks_records = (
                result.get("checks").to_dict(orient="records") if hasattr(result.get("checks"), "to_dict") else []
            )
            event = {
                "agent_version": "1.0-feedback",
                "url": url,
                "rating": rating,
                "reward": reward,
                "task_success": bool(task_success),
                "comment": comment,
                "summary": result.get("summary"),
                "checks": checks_records,
            }
            try:
                record_feedback(event)
                st.success("Bedankt! Jouw feedback is opgeslagen en wordt bij volgende analyses toegepast.")
            except Exception as e:
                st.error(f"Feedback kon niet worden opgeslagen: {e}")

    except Exception as e:
        st.error(f"Er ging iets mis: {e}")
elif not url:
    st.info("Vul eerst een URL in en klik op Analyze.")