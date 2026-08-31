import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Chartink Screener", page_icon="📊", layout="wide")

st.title("HP-SOS Screener")

# Embed the Chartink website
components.iframe("https://chartink.com/screener/hp-sos", height=800, scrolling=True)
