import streamlit as st
from groq import Groq
import pandas as pd
import json
from fpdf import FPDF
import os

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

FRAMEWORKS = {
    "GRI": {"Energy": ["Total energy consumption", "Renewable energy %"], "Emissions": ["Scope 1", "Scope 2", "Scope 3"], "Water": ["Water withdrawal", "Water recycled"], "Waste": ["Total waste", "Recycled waste"], "Social": ["Employees", "Turnover", "Training hours", "Injuries"], "Governance": ["Board composition", "Anti-corruption policy"]},
    "TCFD": {"Governance": ["Board climate oversight", "Management role"], "Strategy": ["Climate risks", "Business impact", "Scenario analysis"], "Risk Management": ["Risk identification", "Risk mitigation"], "Metrics & Targets": ["Scope 1", "Scope 2", "Scope 3", "Climate targets"]},
    "SASB": {"Environment": ["GHG emissions", "Energy management", "Water management"], "Social Capital": ["Human rights", "Data security"], "Human Capital": ["Health & safety", "Employee engagement"], "Governance": ["Business ethics", "Compliance"]},
    "CSRD": {"Climate Change": ["GHG targets", "Climate mitigation"], "Pollution": ["Air", "Water", "Soil"], "Workforce": ["Working conditions", "Equal treatment"], "Governance": ["Board oversight", "Risk management"]},
    "CDP": {"Climate Change": ["Scope 1", "Scope 2", "Scope 3", "Reduction targets"], "Water Security": ["Water withdrawal", "Water risks"], "Governance": ["Board oversight", "Accountability"]}
}

def extract_esg_data(raw_data):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": f"""Extract all sustainability data from the input and return ONLY valid JSON.

Input: {raw_data}

Return this structure (null for missing values):
{{
  "company_name": null, "reporting_year": null, "industry": null,
  "energy": {{"total_consumption_mwh": null, "renewable_energy_mwh": null, "renewable_percentage": null}},
  "emissions": {{"scope1_tco2e": null, "scope2_tco2e": null, "scope3_tco2e": null, "total_tco2e": null, "reduction_target": null}},
  "water": {{"total_withdrawal_m3": null, "recycled_m3": null}},
  "waste": {{"total_generated_tonnes": null, "recycled_tonnes": null, "hazardous_tonnes": null}},
  "social": {{"total_employees": null, "female_employees_percent": null, "turnover_percent": null, "training_hours_per_employee": null, "work_injuries": null}},
  "governance": {{"board_size": null, "female_board_percent": null, "anti_corruption_policy": null, "esg_committee": null}}
}}"""}],
        temperature=0
    )
    text = response.choices[0].message.content.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)

def map_to_framework(data, framework):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": f"""Map this ESG data to {framework} framework. Return ONLY valid JSON.

ESG Data: {json.dumps(data)}
Framework categories: {json.dumps(FRAMEWORKS[framework])}

Return:
{{
  "framework": "{framework}", "company": "name", "year": "year",
  "overall_completeness": 0,
  "categories": {{
    "category_name": {{
      "completeness": 0,
      "metrics": {{
        "metric_name": {{"value": "value or null", "status": "available|partial|missing", "notes": "notes"}}
      }}
    }}
  }},
  "gaps": ["missing items"],
  "recommendations": ["improvements"]
}}"""}],
        temperature=0
    )
    text = response.choices[0].message.content.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)

def generate_pdf(data, framework):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    pdf.set_fill_color(34, 139, 34)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, f"{framework} Sustainability Report", ln=True, fill=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, f"Company: {str(data.get('company','N/A'))[:50]}  |  Year: {data.get('year','N/A')}  |  Completeness: {data.get('overall_completeness',0)}%", ln=True)
    pdf.ln(4)
    for cat, cat_data in data.get("categories", {}).items():
        pdf.set_fill_color(200, 235, 200)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"{cat} ({cat_data.get('completeness',0)}% complete)", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 9)
        for metric, mdata in cat_data.get("metrics", {}).items():
            status = mdata.get("status", "missing")
            value = str(mdata.get("value") or "Not reported")[:80]
            icon = "[OK]" if status == "available" else "[~]" if status == "partial" else "[X]"
            try:
                pdf.multi_cell(0, 6, f"  {icon} {str(metric)[:50]}: {value}")
            except:
                pass
        pdf.ln(2)
    for title, items, color in [("Data Gaps", data.get("gaps",[]), (255,210,210)), ("Recommendations", data.get("recommendations",[]), (210,220,255))]:
        if items:
            pdf.set_fill_color(*color)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, title, ln=True, fill=True)
            pdf.set_font("Helvetica", "", 9)
            for item in items:
                try:
                    pdf.multi_cell(0, 6, f"- {str(item)[:100]}")
                except:
                    pass
    return bytes(pdf.output())

# ── UI ────────────────────────────────────────────────────────
st.set_page_config(page_title="Sustainability Reporter", page_icon="🌱", layout="wide")
st.title("🌱 Sustainability Reporting Tool")
st.markdown("Upload your data and automatically generate reports for GRI, TCFD, SASB, CSRD and CDP frameworks")

with st.sidebar:
    st.header("⚙️ Settings")
    selected = st.multiselect("Select Frameworks", ["GRI", "TCFD", "SASB", "CSRD", "CDP"], default=["GRI", "TCFD"])

tab1, tab2, tab3 = st.tabs(["📤 Upload Data", "📊 Dashboard", "📄 Download Reports"])

with tab1:
    st.subheader("Add your sustainability data")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Upload Excel or CSV**")
        file = st.file_uploader("", type=["xlsx", "xls", "csv"])
        if file:
            df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
            st.success(f"Uploaded: {df.shape[0]} rows x {df.shape[1]} columns")
            st.dataframe(df.head(10))
    with col2:
        st.markdown("**Or paste your data / notes**")
        text = st.text_area("", height=220, placeholder="e.g. In 2023 we used 50,000 MWh electricity. Scope 1 emissions were 8,000 tCO2e. We have 400 employees...")

    st.markdown("---")
    if st.button("🚀 Generate Reports", type="primary", use_container_width=True):
        if not file and not text:
            st.error("Please upload a file or paste some data.")
        elif not selected:
            st.error("Please select at least one framework.")
        else:
            raw = ""
            if file: raw += f"File data:\n{df.to_string()}\n\n"
            if text: raw += f"Notes:\n{text}"

            with st.spinner("Extracting ESG data..."):
                try:
                    extracted = extract_esg_data(raw)
                    st.session_state["extracted"] = extracted
                    st.success("Data extracted!")
                except Exception as e:
                    st.error(f"Extraction error: {e}")
                    st.stop()

            results = {}
            for fw in selected:
                with st.spinner(f"Mapping to {fw}..."):
                    try:
                        results[fw] = map_to_framework(extracted, fw)
                        st.success(f"{fw} done!")
                    except Exception as e:
                        st.error(f"{fw} error: {e}")

            st.session_state["results"] = results
            st.success("🎉 Done! Check Dashboard and Download tabs.")

with tab2:
    if "results" not in st.session_state:
        st.info("Upload your data first.")
    else:
        results = st.session_state["results"]
        extracted = st.session_state.get("extracted", {})
        st.subheader("Framework Completeness")
        cols = st.columns(len(results))
        for i, (fw, d) in enumerate(results.items()):
            with cols[i]:
                pct = d.get("overall_completeness", 0)
                st.metric(fw, f"{pct}%")
                st.progress(pct / 100)
        st.markdown("---")
        st.subheader("Key Metrics")
        c1, c2, c3, c4 = st.columns(4)
        em = extracted.get("emissions", {})
        en = extracted.get("energy", {})
        so = extracted.get("social", {})
        c1.metric("Scope 1", f"{em.get('scope1_tco2e') or 'N/A'} tCO2e")
        c2.metric("Scope 2", f"{em.get('scope2_tco2e') or 'N/A'} tCO2e")
        c3.metric("Total Energy", f"{en.get('total_consumption_mwh') or 'N/A'} MWh")
        c4.metric("Employees", str(so.get("total_employees") or "N/A"))
        st.markdown("---")
        for fw, d in results.items():
            with st.expander(f"📋 {fw} Full Breakdown"):
                for cat, cdata in d.get("categories", {}).items():
                    st.markdown(f"**{cat}** — {cdata.get('completeness',0)}% complete")
                    for metric, mdata in cdata.get("metrics", {}).items():
                        s = mdata.get("status", "missing")
                        v = mdata.get("value") or "Not reported"
                        icon = "✅" if s == "available" else "⚠️" if s == "partial" else "❌"
                        st.markdown(f"{icon} **{metric}:** {v}")
                    st.markdown("---")
                if d.get("gaps"):
                    st.markdown("**Gaps:**")
                    for g in d["gaps"]: st.markdown(f"- {g}")

with tab3:
    if "results" not in st.session_state:
        st.info("Upload your data first.")
    else:
        st.subheader("Download your PDF reports")
        cols = st.columns(len(st.session_state["results"]))
        for i, (fw, d) in enumerate(st.session_state["results"].items()):
            with cols[i]:
                st.markdown(f"**{fw}**")
                st.metric("Completeness", f"{d.get('overall_completeness',0)}%")
                pdf = generate_pdf(d, fw)
                st.download_button(f"⬇️ Download {fw} PDF", data=pdf, file_name=f"{fw}_report.pdf", mime="application/pdf", use_container_width=True)
