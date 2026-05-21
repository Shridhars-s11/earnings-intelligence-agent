import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Earnings Intelligence Agent",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Earnings Intelligence Agent")
st.markdown("AI-powered financial research using SEC filings and live news")

tab1, tab2, tab3 = st.tabs(["🔍 Analyze Company", "💬 Ask Questions", "📋 Past Reports"])

# TAB 1 — Analyze
with tab1:
    st.subheader("Generate Earnings Intelligence Report")
    company = st.text_input("Company Name", placeholder="e.g. Apple Inc, Microsoft, Tesla Inc")
    form_type = st.selectbox("Filing Type", ["10-K (Annual)", "10-Q (Quarterly)"])
    form_type_code = "10-K" if "10-K" in form_type else "10-Q"

    if st.button("Analyze", type="primary"):
        if not company.strip():
            st.error("Please enter a company name.")
        else:
            with st.spinner(f"Analyzing {company}... this may take 1-2 minutes"):
                try:
                    response = requests.post(
                        f"{API_URL}/analyze",
                        json={"company": company, "form_type": form_type_code},
                        timeout=300
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"Report generated for {data['company']}")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("SEC Filing Date", data["sec_date"])
                        with col2:
                            st.metric("News Articles Used", data["news_count"])

                        st.markdown("---")
                        st.markdown(data["report"])
                    else:
                        st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
                except requests.exceptions.Timeout:
                    st.error("Request timed out. The agent is still processing — check Past Reports in a moment.")
                except Exception as e:
                    st.error(f"Connection error: {str(e)}")

# TAB 2 — Semantic Search
with tab2:
    st.subheader("Ask Questions About a Company")
    st.info("You must analyze a company first before asking questions about it.")

    search_company = st.text_input("Company Name", placeholder="e.g. Apple Inc", key="search_company")
    question = st.text_area("Your Question", placeholder="e.g. What are the main risks this company faces?", height=100)
    top_k = st.slider("Number of sources to use", min_value=1, max_value=10, value=5)

    if st.button("Search", type="primary"):
        if not search_company.strip() or not question.strip():
            st.error("Please enter both company name and question.")
        else:
            with st.spinner("Searching through filings..."):
                try:
                    response = requests.post(
                        f"{API_URL}/search",
                        json={
                            "company": search_company,
                            "question": question,
                            "top_k": top_k
                        },
                        timeout=60
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"Answer based on {data['sources_used']} relevant chunks")
                        st.markdown("### Answer")
                        st.markdown(data["answer"])
                    elif response.status_code == 404:
                        st.warning(f"No data found for {search_company}. Please analyze it first in the Analyze tab.")
                    else:
                        st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
                except Exception as e:
                    st.error(f"Connection error: {str(e)}")

# TAB 3 — Past Reports
with tab3:
    st.subheader("Previously Generated Reports")

    if st.button("Refresh Reports"):
        st.rerun()

    try:
        response = requests.get(f"{API_URL}/reports", timeout=10)
        if response.status_code == 200:
            reports = response.json()
            if not reports:
                st.info("No reports yet. Analyze a company first.")
            else:
                for r in reports:
                    with st.expander(f"{r['company']} — {r['created_at'][:10]}"):
                        detail = requests.get(f"{API_URL}/reports/{r['id']}", timeout=10)
                        if detail.status_code == 200:
                            st.markdown(detail.json()["report"])
    except Exception as e:
        st.error(f"Could not load reports: {str(e)}")