
import io
import json
import pandas as pd
import streamlit as st
from analyzer import load_checklist_from_excel, analyze, to_markdown, to_html

st.set_page_config(page_title="CRO Landing Page AI Agent", layout="wide")

st.title("CRO Landing Page AI Agent")

st.markdown("""
Gebruik deze tool om een landingspagina te beoordelen o.b.v. jouw **Excel-checklist** (standaard: de bijgevoegde *Landingspagina CRO checklist.xlsx*).
- Vul een URL in
- Upload desgewenst een andere Excel-checklist (kolommen: *Categorie*, *Tip*, *Prioriteit*, *Moeilijkheidsgraad*, *Uitleg*)
- Klik **Analyze**
""")

default_path = "checklist.xlsx"  # komt uit de meegeleverde Excel
uploaded = st.file_uploader("Upload (optioneel) een eigen checklist (.xlsx)", type=["xlsx"])

url = st.text_input("URL om te analyseren", placeholder="https://...")

if st.button("Analyze", type="primary") and url:
    with st.spinner("Bezig met ophalen & analyseren..."):
        try:
            if uploaded is not None:
                checklist_df = load_checklist_from_excel(uploaded)
            else:
                checklist_df = load_checklist_from_excel(default_path)

            result = analyze(url, checklist_df)

            st.subheader("Samenvatting")
            st.json(result["summary"])

            st.subheader("Checks")
            st.dataframe(result["checks"], use_container_width=True)

            # Downloads
            md = to_markdown(result)
            html = to_html(result)
            j = json.dumps({
                "summary": result["summary"],
                "checks": result["checks"].to_dict(orient="records")
            }, ensure_ascii=False, indent=2)

            st.download_button("Download Markdown", data=md.encode("utf-8"), file_name="cro_report.md")
            st.download_button("Download HTML", data=html.encode("utf-8"), file_name="cro_report.html")
            st.download_button("Download JSON", data=j.encode("utf-8"), file_name="cro_report.json")

        except Exception as e:
            st.error(f"Er ging iets mis: {e}")
else:
    st.info("Vul eerst een URL in en klik op Analyze.")

st.caption("Checklist default: 'checklist.xlsx' (meegeleverd uit jouw Excel). Je kunt altijd een eigen checklist uploaden.")
