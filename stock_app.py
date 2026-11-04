import streamlit as st
from stock_dashboard import render_stock_dashboard

st.set_page_config(
    page_title="StockLab Việt Nam",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; max-width: 1600px;}
[data-testid="stMetric"] {background: #101a2a; padding: 12px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

render_stock_dashboard()
