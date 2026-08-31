import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup

st.set_page_config(page_title="Chartink Screener", page_icon="📊", layout="wide")

st.title("HP-SOS Screener Data")

@st.cache_data(ttl=60) # Refreshes data every 60 seconds
def fetch_chartink_data():
    url = 'https://chartink.com/screener/hp-sos'
    condition = {"scan_clause": "( {33489} ( latest close > latest sma( latest close , 20 ) ) )"} # You will need the exact scan clause for hp-sos
    
    with requests.Session() as s:
        # 1. Get the CSRF token from the main page
        r = s.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        csrf_meta = soup.select_option('meta[name="csrf-token"]')
        if not csrf_meta:
            return pd.DataFrame()
            
        csrf_token = csrf_meta['content']
        
        # 2. Send the request to the backend API to get the data
        headers = {
            'x-csrf-token': csrf_token,
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # Chartink's backend endpoint for processing screeners
        process_url = 'https://chartink.com/screener/process'
        
        # Note: You must replace 'condition' with the exact text formula from your specific scanner
        response = s.post(process_url, headers=headers, data=condition)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                return pd.DataFrame(data['data'])
    return pd.DataFrame()

df = fetch_chartink_data()

if not df.empty:
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.error("Could not fetch data from Chartink.")
