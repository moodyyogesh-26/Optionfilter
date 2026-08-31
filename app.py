import streamlit as st
import pandas as pd
import requests
import math
import os
import time
import gzip
import shutil
import json
import re
from datetime import datetime, timedelta, timezone
import concurrent.futures
import zipfile
import io

# IST Offset
IST_OFFSET = timedelta(hours=5, minutes=30)
IST = timezone(IST_OFFSET)

def get_ist_now():
    return datetime.now(IST)

# Set page configuration
st.set_page_config(
    page_title="Option Filter",
    page_icon="📈",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    hr {
        margin-top: 0.5em !important; 
        margin-bottom: 0.5em !important;
    }
    .block-container {
        padding-top: 3.0rem !important;
        padding-bottom: 0.75rem !important;
    }
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        z-index: 99 !important;
    }
    .reportview-container { background: #f0f2f6 }
    .stTable { font-size: 14px; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
    h1 { color: #1e3a8a; }
    h2 { color: #1e40af; }
    h3 { color: #1d4ed8; }
    
    /* Prevent graying out during refresh */
    .stApp {
        transition: none !important;
    }
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        opacity: 1 !important;
        transition: none !important;
    }
    
    /* Force Dataframe Font Weight */
    div[data-testid="stDataFrame"] {
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# Data Directory
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

TOKEN_FILE = os.path.join(DATA_DIR, 'token.json')
META_FILE = os.path.join(DATA_DIR, 'meta.json')
LTP_CACHE_FILE = os.path.join(DATA_DIR, 'ltp_cache.json')
JSTT_H_CACHE_FILE = os.path.join(DATA_DIR, 'JSTT_H_cache.json')

# Updated FILES dictionary
FILES = {
    'JSTT_H': os.path.join(DATA_DIR, 'JSTT_H.csv'),
    'Strike_Selection': os.path.join(DATA_DIR, 'strike_selection.csv'),
    'Prev_Bhavcopy': os.path.join(DATA_DIR, 'prev_bhavcopy.csv'),
    'Lot_Size': os.path.join(DATA_DIR, 'lot_size.csv')
}

def get_base64_image(image_path):
    possible_paths = [
        image_path,
        os.path.join(os.path.dirname(__file__), image_path)
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                import base64
                with open(path, "rb") as img_file:
                    return base64.b64encode(img_file.read()).decode('utf-8')
            except Exception:
                pass
    return ""

def render_header(target_exp=None):
    """Renders the top header with logo, title, and right-aligned expiry badge."""
    logo_base64 = get_base64_image('jstt_logo.png')
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="height: 52px; max-height: 52px; width: auto; object-fit: contain; vertical-align: middle; flex-shrink: 0;" />' if logo_base64 else ''
    
    expiry_html = ''
    if target_exp:
        exp_str = target_exp.strftime('%d-%b-%Y') if hasattr(target_exp, 'strftime') else str(target_exp)
        expiry_html = f'<div style="background-color: #e0f2fe; color: #0369a1; padding: 6px 14px; border-radius: 8px; font-weight: 600; font-size: 0.95rem; border: 1px solid #bae6fd; display: flex; align-items: center; gap: 6px; white-space: nowrap; margin-left: auto;"><span>📅 Expiry:</span> <strong style="color: #0284c7;">{exp_str}</strong></div>'
        
    st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-top: 0.5rem; margin-bottom: 1.2rem; flex-wrap: wrap; gap: 16px;">
    <div style="display: flex; align-items: center; gap: 16px;">
        {logo_html}
        <h1 style="margin: 0; padding: 0; color: #1e3a8a; font-size: 1.9rem; font-weight: 700; line-height: 1.3; display: inline-block;">
            Option Filter
        </h1>
    </div>
    {expiry_html}
</div>
""", unsafe_allow_html=True)

def load_meta():
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_meta(key, date_str):
    try:
        meta = load_meta()
        meta[key] = date_str
        with open(META_FILE, 'w') as f:
            json.dump(meta, f)
    except:
        pass

def load_ltp_cache():
    if os.path.exists(LTP_CACHE_FILE):
        try:
            with open(LTP_CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_ltp_cache(new_data):
    try:
        cache = load_ltp_cache()
        cache.update(new_data)
        with open(LTP_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except:
        pass

def load_JSTT_H_cache():
    if os.path.exists(JSTT_H_CACHE_FILE):
        try:
            with open(JSTT_H_CACHE_FILE, 'r') as f:
                data = json.load(f)
                today_str = get_ist_now().strftime('%Y-%m-%d')
                if data.get('date') == today_str:
                    return data.get('highs', {})
        except:
            pass
    return {}

def save_JSTT_H_cache(new_highs):
    try:
        cache = load_JSTT_H_cache()
        cache.update(new_highs)
        today_str = get_ist_now().strftime('%Y-%m-%d')
        save_data = {
            'date': today_str,
            'highs': cache
        }
        with open(JSTT_H_CACHE_FILE, 'w') as f:
            json.dump(save_data, f)
    except:
        pass

def extract_date_from_filename(filename):
    match = re.search(r'(\d{8})', filename)
    if match:
        d = match.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None

def extract_csv_from_zip(zip_file):
    try:
        with zipfile.ZipFile(zip_file) as z:
            csv_files = [f for f in z.namelist() if f.lower().endswith('.csv') and not f.startswith('__MACOSX')]
            if not csv_files:
                st.error("No CSV file found in the ZIP archive.")
                return None, None
            
            if len(csv_files) == 1:
                csv_filename = csv_files[0]
                with z.open(csv_filename) as f:
                    d_str = extract_date_from_filename(csv_filename)
                    return f.read(), d_str or csv_filename
            else:
                dfs = []
                dates = []
                for fname in sorted(csv_files):
                    with z.open(fname) as f:
                        try:
                            df_temp = pd.read_csv(f)
                            dfs.append(df_temp)
                            d_str = extract_date_from_filename(fname)
                            if d_str:
                                dates.append(d_str)
                        except Exception:
                            pass
                
                if not dfs:
                    return None, None
                
                combined_df = pd.concat(dfs, ignore_index=True)
                dates = sorted(list(set(dates)))
                if len(dates) > 1:
                    date_display = f"{', '.join(dates)} ({len(dates)} days)"
                elif len(dates) == 1:
                    date_display = dates[0]
                else:
                    date_display = extract_date_from_filename(getattr(zip_file, 'name', '')) or "Uploaded Data"
                    
                csv_bytes = combined_df.to_csv(index=False).encode('utf-8')
                return csv_bytes, date_display
    except Exception as e:
        st.error(f"Error extracting ZIP file: {e}")
        return None, None

def process_uploaded_files(uploaded_files):
    if not uploaded_files:
        return None, None
        
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]
        
    dfs = []
    dates = []
    
    for f in uploaded_files:
        filename = getattr(f, 'name', '').lower()
        if hasattr(f, 'seek'):
            try:
                f.seek(0)
            except Exception:
                pass
                
        if filename.endswith('.zip'):
            csv_bytes, date_display = extract_csv_from_zip(f)
            if csv_bytes:
                try:
                    df_temp = pd.read_csv(io.BytesIO(csv_bytes))
                    dfs.append(df_temp)
                    if date_display:
                        found_dates = re.findall(r'\d{4}-\d{2}-\d{2}', date_display)
                        if found_dates:
                            dates.extend(found_dates)
                        else:
                            d_str = extract_date_from_filename(getattr(f, 'name', ''))
                            if d_str:
                                dates.append(d_str)
                except Exception:
                    pass
        elif filename.endswith('.csv'):
            try:
                content = f.read()
                if content:
                    df_temp = pd.read_csv(io.BytesIO(content))
                    dfs.append(df_temp)
                    d_str = extract_date_from_filename(getattr(f, 'name', ''))
                    if d_str:
                        dates.append(d_str)
                    else:
                        for d_col in ['TradDt', 'Date', 'TRADEDATE', 'TIMESTAMP']:
                            if d_col in df_temp.columns:
                                try:
                                    u_dates = pd.to_datetime(df_temp[d_col]).dt.strftime('%Y-%m-%d').unique().tolist()
                                    dates.extend(u_dates)
                                except Exception:
                                    pass
            except Exception:
                pass

    if not dfs:
        return None, None
        
    combined_df = pd.concat(dfs, ignore_index=True)
    dates = sorted(list(set(dates)))
    if dates:
        if len(dates) > 1:
            date_display = f"{', '.join(dates)} ({len(dates)} days)"
        else:
            date_display = dates[0]
    else:
        date_display = "Uploaded Data"
        
    csv_bytes = combined_df.to_csv(index=False).encode('utf-8')
    return csv_bytes, date_display

def load_token():
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                data = json.load(f)
                if data.get('date') == get_ist_now().strftime('%Y-%m-%d'):
                    return data.get('token', '')
        except:
            pass
    return ''

def save_token(token):
    try:
        data = {
            'date': get_ist_now().strftime('%Y-%m-%d'),
            'token': token
        }
        with open(TOKEN_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass

# Constant for NSE JSON
NSE_JSON_PATH = 'NSE.json'

@st.cache_data
def load_nse_json():
    if os.path.exists(NSE_JSON_PATH):
        try:
            df = pd.read_json(NSE_JSON_PATH)
            if 'segment' in df.columns:
                df = df[df['segment'] == 'NSE_FO']
            df['expiry_dt'] = pd.to_datetime(df['expiry'], unit='ms').dt.normalize()
            return df
        except Exception as e:
            st.error(f"Error loading NSE.json: {e}")
            return pd.DataFrame()
    else:
        st.error(f"NSE.json not found at {NSE_JSON_PATH}")
        return pd.DataFrame()

def process_bhavcopy(bhav_file, df_json, target_expiry_index=0, strike_bhav_file=None, prev_bhav_file=None):
    try:
        df_bhav = pd.read_csv(bhav_file)
        
        required_cols = ['FinInstrmTp', 'TckrSymb', 'XpryDt', 'ClsPric', 'StrkPric', 'OptnTp', 'HghPric', 'LwPric', 'LastPric']
        if not all(col in df_bhav.columns for col in required_cols):
            st.error(f"Uploaded file missing required columns: {required_cols}")
            return pd.DataFrame(), None, []

        df_selection = df_bhav
        if strike_bhav_file and os.path.exists(strike_bhav_file):
            try:
                df_strike = pd.read_csv(strike_bhav_file)
                if all(col in df_strike.columns for col in ['FinInstrmTp', 'TckrSymb', 'XpryDt', 'ClsPric', 'StrkPric', 'OptnTp']):
                    df_selection = df_strike
            except Exception:
                pass

        futures = df_selection[df_selection['FinInstrmTp'].isin(['STF', 'IDF'])].copy()
        if futures.empty:
            futures = df_bhav[df_bhav['FinInstrmTp'].isin(['STF', 'IDF'])].copy()
            if futures.empty:
                st.warning("No Futures data found in uploaded file.")
                return pd.DataFrame(), None, []

        futures['XpryDt'] = pd.to_datetime(futures['XpryDt'])
        
        ist_now = get_ist_now()
        today = ist_now.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
        
        future_expiries = futures[futures['XpryDt'] >= today]
        if not future_expiries.empty:
            futures = future_expiries
        
        if futures.empty:
            st.warning("No expiry dates found in the uploaded file.")
            return pd.DataFrame(), None, []

        futures = futures.sort_values('XpryDt')
        available_expiries = sorted(futures['XpryDt'].unique())
        
        if not available_expiries:
            st.warning("No future expiry dates found in the uploaded file.")
            return pd.DataFrame(), None, []

        if target_expiry_index >= len(available_expiries):
            target_expiry = available_expiries[-1]
        else:
            target_expiry = available_expiries[target_expiry_index]

        near_futures = futures[futures['XpryDt'] == target_expiry].copy()
        near_futures = near_futures[['TckrSymb', 'ClsPric', 'XpryDt']]
        near_futures = near_futures.rename(columns={'ClsPric': 'FuturePrice', 'XpryDt': 'FutureExpiryDate'})

        options_sel = df_selection[df_selection['OptnTp'].isin(['CE', 'PE'])].copy()
        if options_sel.empty:
            options_sel = df_bhav[df_bhav['OptnTp'].isin(['CE', 'PE'])].copy()

        options_sel['XpryDt'] = pd.to_datetime(options_sel['XpryDt'])
        merged_sel = pd.merge(options_sel, near_futures, on='TckrSymb')
        merged_sel = merged_sel[merged_sel['XpryDt'] == merged_sel['FutureExpiryDate']]
        merged_sel['Diff'] = abs(merged_sel['StrkPric'] - merged_sel['FuturePrice'])
        
        best_strikes = merged_sel[['TckrSymb', 'StrkPric', 'Diff']].drop_duplicates()
        best_strikes = best_strikes.sort_values(by=['TckrSymb', 'Diff', 'StrkPric'])
        best_strikes = best_strikes.groupby('TckrSymb').first().reset_index()

        options = df_bhav[df_bhav['OptnTp'].isin(['CE', 'PE'])].copy()
        if options.empty:
            st.warning("No Options data found in uploaded file.")
            return pd.DataFrame(), target_expiry, available_expiries

        options['XpryDt'] = pd.to_datetime(options['XpryDt'])
        merged = pd.merge(options, near_futures, on='TckrSymb')
        merged = merged[merged['XpryDt'] == merged['FutureExpiryDate']]
        
        atm_options = pd.merge(merged, best_strikes[['TckrSymb', 'StrkPric']], on=['TckrSymb', 'StrkPric'])
        atm_rows = atm_options[['TckrSymb', 'XpryDt', 'StrkPric', 'OptnTp', 'FuturePrice', 'ClsPric', 'FinInstrmNm', 'HghPric', 'LwPric', 'LastPric']].copy()
        
        atm_rows['XpryDt'] = atm_rows['XpryDt'].dt.normalize()

        atm_rows = atm_rows.groupby(['TckrSymb', 'XpryDt', 'StrkPric', 'OptnTp'], as_index=False).agg({
            'FuturePrice': 'last',
            'ClsPric': 'last',
            'FinInstrmNm': 'first',
            'HghPric': 'max',
            'LwPric': 'min',
            'LastPric': 'last'
        })

        result = pd.merge(
            atm_rows,
            df_json,
            left_on=['TckrSymb', 'StrkPric', 'OptnTp', 'XpryDt'],
            right_on=['underlying_symbol', 'strike_price', 'instrument_type', 'expiry_dt'],
            how='inner'
        )

        if result.empty and not atm_rows.empty:
            st.error("Data mismatch: Found options in Bhavcopy but couldn't find them in NSE.json. Please update NSE.json via the sidebar.")

        final_df = result[[
            'TckrSymb', 'XpryDt', 'StrkPric', 'OptnTp', 
            'FuturePrice', 'ClsPric', 'instrument_key',
            'HghPric', 'LwPric', 'LastPric'
        ]].copy()

        final_df = final_df.rename(columns={
            'TckrSymb': 'Symbol',
            'XpryDt': 'ExpiryDate',
            'StrkPric': 'StrikePrice',
            'OptnTp': 'OptionType',
            'HghPric': 'HighPrice',
            'LwPric': 'LowPrice',
            'LastPric': 'LastPrice'
        })

        # --- Merge Previous Day Bhavcopy for %P ---
        if prev_bhav_file and os.path.exists(prev_bhav_file):
            try:
                df_prev = pd.read_csv(prev_bhav_file)
                opts_prev = df_prev[df_prev['OptnTp'].isin(['CE', 'PE'])].copy()
                opts_prev['XpryDt'] = pd.to_datetime(opts_prev['XpryDt']).dt.normalize()
                opts_prev = opts_prev[['TckrSymb', 'XpryDt', 'StrkPric', 'OptnTp', 'ClsPric']]
                opts_prev = opts_prev.rename(columns={'ClsPric': 'PrevClose'})
                opts_prev = opts_prev.drop_duplicates(subset=['TckrSymb', 'XpryDt', 'StrkPric', 'OptnTp'])

                final_df = pd.merge(
                    final_df, 
                    opts_prev,
                    left_on=['Symbol', 'ExpiryDate', 'StrikePrice', 'OptionType'],
                    right_on=['TckrSymb', 'XpryDt', 'StrkPric', 'OptnTp'],
                    how='left'
                )
                final_df = final_df.drop(columns=['TckrSymb', 'XpryDt', 'StrkPric', 'OptnTp'])
                final_df['PrevClose'] = final_df['PrevClose'].fillna(0.0)
            except Exception as e:
                final_df['PrevClose'] = 0.0
        else:
            final_df['PrevClose'] = 0.0

        # Shared strike formatting: remove trailing '.0'
        strike_str = final_df['StrikePrice'].astype(str).str.replace(r'\.0$', '', regex=True)

        # 1. Tradingview Scrip
        formatted_date_tv = final_df['ExpiryDate'].dt.strftime('%y%m%d')
        opt_type_tv = final_df['OptionType'].str[0]
        final_df['Tradingview Scrip'] = final_df['Symbol'] + formatted_date_tv + opt_type_tv + strike_str + ","

        # 2. Trade Point Scrip
        formatted_date_tp = final_df['ExpiryDate'].dt.strftime('%d-%b-%Y')
        final_df['Trade Point Scrip'] = (
            final_df['Symbol'] + " " + 
            formatted_date_tp + " " + 
            final_df['OptionType'] + " " + 
            strike_str
        )

        return final_df, target_expiry, available_expiries

    except Exception as e:
        st.error(f"Error processing Bhavcopy: {e}")
        return pd.DataFrame(), None, []

def fetch_ltp(instrument_keys, access_token):
    if not access_token or not instrument_keys:
        return {}
    
    url = "https://api.upstox.com/v2/market-quote/ltp"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    
    results = {}
    chunk_size = 100
    
    for i in range(0, len(instrument_keys), chunk_size):
        chunk = instrument_keys[i:i + chunk_size]
        params = {'instrument_key': ','.join(chunk)}
        
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get('status') == 'success':
                    for k, v in data.get('data', {}).items():
                        price = float(v.get('last_price', 0.0))
                        clean_k = k.replace(':', '|')
                        results[clean_k] = price
                        token = v.get('instrument_token')
                        if token:
                            clean_token = token.replace(':', '|')
                            results[clean_token] = price
        except Exception:
            pass
            
    return results

def display_option_chain(df, access_token):
    st.caption(f"Last Updated: {get_ist_now().strftime('%H:%M:%S')} IST")
    if df.empty:
        st.info("No data to display. Please upload JSTT Bhavcopy files in the sidebar.")
        return

    if access_token:
        all_keys = df['instrument_key'].dropna().unique().tolist()
        fetched_data = fetch_ltp(all_keys, access_token)
        if fetched_data:
            save_ltp_cache(fetched_data)
            ltp_cache = fetched_data
        else:
            ltp_cache = load_ltp_cache()
        
        ltp_data = {k: ltp_cache.get(k, 0.0) for k in all_keys}
        df['ltp'] = df['instrument_key'].map(ltp_data).fillna(0.0)
    else:
        df['ltp'] = 0.0
        st.warning("Enter Access Token in sidebar to see live LTP.")

    def clean_ltp(row):
        ltp = row.get('ltp', 0.0)
        if ltp > 0:
            return ltp
        last_price = row.get('LastPrice', 0.0)
        cls_price = row.get('ClsPric', 0.0)
        return last_price if last_price > 0 else cls_price

    df['ltp'] = df.apply(clean_ltp, axis=1)

    # --- Load and Map Lot Size ---
    def get_lot_sizes():
        lot_file = FILES.get('Lot_Size')
        if lot_file and os.path.exists(lot_file):
            try:
                ldf = pd.read_csv(lot_file)
                ldf.columns = ldf.columns.str.strip().str.upper()
                sym_col = next((c for c in ldf.columns if c in ['SYMBOL', 'UNDERLYING', 'TCKRSYMB']), None)
                lot_col = next((c for c in ldf.columns if 'LOT' in c or 'SIZE' in c), None)
                if sym_col and lot_col:
                    month_col = next((c for c in ldf.columns if 'MONTH' in c or 'EXPIRY' in c), None)
                    if month_col:
                        ldf = ldf.sort_values(month_col)
                    ldf = ldf.drop_duplicates(subset=[sym_col], keep='first')
                    return dict(zip(ldf[sym_col], ldf[lot_col]))
            except Exception:
                pass
        return {}

    lot_size_map = get_lot_sizes()
    df['Lot Size'] = df['Symbol'].map(lot_size_map).fillna(0).astype(int)

    # Trigger logic
    if 'HighPrice' in df.columns and (df['HighPrice'] > 0).any():
        df['Trigger'] = df['HighPrice']
    else:
        df['Trigger'] = 0.0
        high_cache = load_JSTT_H_cache()
        if high_cache:
            df['Trigger'] = df['instrument_key'].map(high_cache).fillna(df['Trigger'])
            
    if 'ClsPric' in df.columns:
        df['JSTT-C'] = df['ClsPric']
    else:
        df['JSTT-C'] = 0.0

    if 'LowPrice' in df.columns:
        df['JSTT-L'] = df['LowPrice']
    else:
        df['JSTT-L'] = 0.0

    df['Diff'] = df['JSTT-C'] - df['JSTT-L']

    def calculate_numeric_change(row):
        try:
            trigger = float(row.get('Trigger', 0.0))
            ltp = float(row.get('ltp', 0.0))
            if trigger > 0 and ltp > 0:
                return round((ltp / trigger) * 100, 2)
        except Exception:
            pass
        return 0.0

    def calculate_c_percent(row):
        try:
            close_val = float(row.get('JSTT-C', 0.0))
            ltp = float(row.get('ltp', 0.0))
            if close_val > 0 and ltp > 0:
                return round((ltp / close_val) * 100, 2)
        except Exception:
            pass
        return 0.0

    def calculate_l_percent(row):
        try:
            low_val = float(row.get('JSTT-L', 0.0))
            ltp = float(row.get('ltp', 0.0))
            if low_val > 0 and ltp > 0:
                return round((ltp / low_val) * 100, 2)
        except Exception:
            pass
        return 0.0
        
    def calculate_p_percent(row):
        try:
            prev_close = float(row.get('PrevClose', 0.0))
            ltp = float(row.get('ltp', 0.0))
            if prev_close > 0 and ltp > 0:
                return round(((ltp - prev_close) / prev_close) * 100, 2)
        except Exception:
            pass
        return 0.0

    df['change_val'] = df.apply(calculate_numeric_change, axis=1)
    df['%H'] = df['change_val']
    
    df['%C_val'] = df.apply(calculate_c_percent, axis=1)
    df['%C'] = df['%C_val']
    
    df['%L_val'] = df.apply(calculate_l_percent, axis=1)
    df['%L'] = df['%L_val']

    df['%P'] = df.apply(calculate_p_percent, axis=1)

    trigger_col_name = 'JSTT-H'
    df = df.rename(columns={'Trigger': trigger_col_name})

    # --- DASHBOARD CONTROLS ---
    st.markdown("---")
    
    col_f0, col_f1, col_f2, col_f3, col_f4, col_f5, col_f6 = st.columns([1.2, 2.2, 0.9, 0.8, 0.8, 0.6, 0.9])
    
    with col_f0:
        search_query = st.text_input("🔍 Search:", value="", placeholder="Search anything...", key="search_query_input")
        
    with col_f1:
        sc1, sc2, sc3 = st.columns(3)
        # Filter View defaults to %C (index 1) and is STRICTLY for the range filters.
        filter_metric = sc1.selectbox("Filter View:", options=["%H", "%C", "%L", "%P"], index=1, key="filter_metric_select")
        min_pct_input = sc2.text_input("🔺 Min % :", value="", placeholder="e.g. >=90")
        max_pct_input = sc3.text_input("🔻 Max % :", value="", placeholder="e.g. <=140")
        
    with col_f2:
        min_strike_input = st.text_input("Min Price:", value="1000", placeholder=">= Price")
        
    with col_f3:
        max_lot_input = st.text_input("📦 Max Lot:", value="", placeholder="<= Lot Size")

    with col_f4:
        # Sort is strictly handled via this Dropdown independent of the filter above
        sort_by = st.selectbox("↕️ Sort:", options=["%P", "%H", "%C", "%L", "Diff", "Lot Size", "Symbol", "Sr."], index=0, key="sort_by_select")
    
    with col_f5:
        color_toggle = st.radio("🎨 Color:", options=["On", "Off"], key="color_toggle_radio")
       
    with col_f6:
        layout_view = st.radio(
            "Layout:",
            options=["↔️ Split", "📈 CE Max", "📉 PE Max"],
            key="table_layout_radio"
        )
        
    st.markdown("---")
    # ----------------------------------------

    # Apply Global Search Filter
    if search_query.strip():
        q = search_query.strip().lower()
        search_mask = df.astype(str).apply(
            lambda col: col.str.lower().str.contains(q, regex=False)
        ).any(axis=1)
        df = df[search_mask]

    # Apply % Range Filter (Uses the Filter View purely for row filtration)
    if min_pct_input.strip():
        try:
            min_pct_val = float(min_pct_input.strip())
            df = df[df[filter_metric] >= min_pct_val]
        except ValueError:
            pass
            
    if max_pct_input.strip():
        try:
            max_pct_val = float(max_pct_input.strip())
            df = df[df[filter_metric] <= max_pct_val]
        except ValueError:
            pass

    # Apply Strike Price Filter
    if min_strike_input.strip():
        try:
            min_strike_val = float(min_strike_input.strip())
            df = df[df['StrikePrice'] >= min_strike_val]
        except ValueError:
            pass

    # Apply Lot Size Filter
    if max_lot_input.strip():
        try:
            max_lot_val = float(max_lot_input.strip())
            df = df[df['Lot Size'] <= max_lot_val]
        except ValueError:
            pass

    calls_df = df[df['OptionType'] == 'CE'].copy()
    puts_df = df[df['OptionType'] == 'PE'].copy()

    # Apply Sorting (STRICTLY uses the "Sort" Dropdown)
    sort_column = sort_by
    sort_ascending = False 

    if sort_by == 'Sr.':
        sort_column = 'Symbol'
        sort_ascending = True
    elif sort_by == 'Symbol':
        sort_ascending = True

    if sort_column in calls_df.columns:
        calls_df = calls_df.sort_values(by=sort_column, ascending=sort_ascending)
    if sort_column in puts_df.columns:
        puts_df = puts_df.sort_values(by=sort_column, ascending=sort_ascending)

    # Overwrite the DataFrame index AFTER sorting, guaranteeing 1 to N order.
    calls_df.index = range(1, len(calls_df) + 1)
    calls_df.index.name = 'Sr.'
    
    puts_df.index = range(1, len(puts_df) + 1)
    puts_df.index.name = 'Sr.'

    display_cols = [
        'Symbol', 'StrikePrice', 'ltp', '%P', trigger_col_name, '%H', 'JSTT-C', '%C', 
        'JSTT-L', '%L', 'Diff', 'Lot Size', 'Tradingview Scrip', 'Trade Point Scrip'
    ]
    
    display_cols = [col for col in display_cols if col in calls_df.columns]
    
    # ---------------- DYNAMIC COLOR LOGIC ----------------
    
    # New green-only dynamic gradient shading exclusively for %H, %C, %L (starts at > 85%)
    def color_hcl_percent(s):
        if color_toggle == "Off":
            return [''] * len(s)
            
        styles = []
        s_numeric = pd.to_numeric(s, errors='coerce').fillna(0)
        
        # Determine the maximum value above 85 to scale the gradient
        max_pos = s_numeric[s_numeric > 85].max() if not s_numeric[s_numeric > 85].empty else 86
        range_pos = max_pos - 85 if max_pos > 85 else 1  # Guard against division by zero
        
        for val in s_numeric:
            if val <= 85:
                styles.append('')
            else:
                intensity = min((val - 85) / range_pos, 1.0)
                alpha = 0.15 + (0.85 * intensity) 
                text_color = 'white' if alpha > 0.55 else 'black'
                styles.append(f'background-color: rgba(0, 128, 0, {alpha}); color: {text_color};')
                
        return styles

    # Existing red/green dynamic gradient shading exclusively for %P
    def color_p_percent(s):
        if color_toggle == "Off":
            return [''] * len(s)
            
        styles = []
        s_numeric = pd.to_numeric(s, errors='coerce').fillna(0)
        
        max_pos = s_numeric[s_numeric > 0].max() if not s_numeric[s_numeric > 0].empty else 1
        min_neg = s_numeric[s_numeric < 0].min() if not s_numeric[s_numeric < 0].empty else -1
        
        for val in s_numeric:
            if val == 0:
                styles.append('')
            elif val > 0:
                intensity = val / max_pos
                alpha = 0.15 + (0.85 * intensity) 
                text_color = 'white' if alpha > 0.55 else 'black'
                styles.append(f'background-color: rgba(0, 128, 0, {alpha}); color: {text_color};')
            else:
                intensity = val / min_neg
                alpha = 0.15 + (0.85 * intensity)
                text_color = 'white' if alpha > 0.55 else 'black'
                styles.append(f'background-color: rgba(255, 0, 0, {alpha}); color: {text_color};')
                
        return styles
        
    # -----------------------------------------------------

    format_dict = {
        '%H': '{:.2f}%',
        '%C': '{:.2f}%',
        '%L': '{:.2f}%',
        '%P': '{:.2f}%',
        trigger_col_name: '{:.2f}',
        'JSTT-C': '{:.2f}',
        'JSTT-L': '{:.2f}',
        'Diff': '{:.2f}',
        'ltp': '{:.2f}',
        'StrikePrice': '{:.2f}',
        'Lot Size': '{:d}'
    }

    # Render layout - No hide_index parameter so the 'Sr.' index is displayed natively.
    if layout_view == "↔️ Split":
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"Calls (CE) ({len(calls_df)})")
            st.dataframe(
                calls_df[display_cols].style
                .apply(color_hcl_percent, subset=['%H', '%C', '%L'])
                .apply(color_p_percent, subset=['%P'])
                .format(format_dict)
                .set_properties(**{'font-weight': '600', 'text-align': 'center', 'font-size': '16px'}),
                use_container_width=True,
                height=1800
            )

        with col2:
            st.subheader(f"Puts (PE) ({len(puts_df)})")
            st.dataframe(
                puts_df[display_cols].style
                .apply(color_hcl_percent, subset=['%H', '%C', '%L'])
                .apply(color_p_percent, subset=['%P'])
                .format(format_dict)
                .set_properties(**{'font-weight': '600', 'text-align': 'center', 'font-size': '16px'}),
                use_container_width=True,
                height=1800
            )
            
    elif layout_view == "📈 CE Max":
        st.subheader(f"Calls (CE) ({len(calls_df)})")
        st.dataframe(
            calls_df[display_cols].style
            .apply(color_hcl_percent, subset=['%H', '%C', '%L'])
            .apply(color_p_percent, subset=['%P'])
            .format(format_dict)
            .set_properties(**{'font-weight': '600', 'text-align': 'center', 'font-size': '16px'}),
            use_container_width=True,
            height=1800
        )
        
    elif layout_view == "📉 PE Max":
        st.subheader(f"Puts (PE) ({len(puts_df)})")
        st.dataframe(
            puts_df[display_cols].style
            .apply(color_hcl_percent, subset=['%H', '%C', '%L'])
            .apply(color_p_percent, subset=['%P'])
            .format(format_dict)
            .set_properties(**{'font-weight': '600', 'text-align': 'center', 'font-size': '16px'}),
            use_container_width=True,
            height=1800
        )

# Secret Handling (Client View Mode)
is_client_view = "UPSTOX_ACCESS_TOKEN" in st.secrets

if is_client_view:
    access_token = st.secrets["UPSTOX_ACCESS_TOKEN"]
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none;}
        .block-container {
            padding-top: 3.5rem !important;
        }
    </style>
    """, unsafe_allow_html=True)
    auto_refresh = True
    refresh_interval = 15
    target_expiry_idx = 0
else:
    with st.sidebar:
        st.title("Settings & Uploads")
        
        saved_token = load_token()
        access_token = st.text_input("Upstox Access Token", value=saved_token, type="password")
        if access_token != saved_token:
            save_token(access_token)
            
        expiry_type = st.radio("Select Expiry", ["Current Month", "Next Month"], index=0)
        target_expiry_idx = 0 if expiry_type == "Current Month" else 1

        st.markdown("---")
        st.header("Data Management")
        
        if st.button("⚡ Refresh LTP Now", use_container_width=True):
            st.session_state['force_refresh_ltp'] = True
            st.rerun()

        st.subheader("NSE Instrument JSON")
        if st.button("🔄 Download Latest"):
            try:
                with st.spinner("Downloading latest NSE.json from Upstox..."):
                    url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                    response = requests.get(url, headers=headers, stream=True)
                    if response.status_code == 200:
                        with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz:
                            data = json.load(gz)
                        with open(NSE_JSON_PATH, 'w') as f:
                            json.dump(data, f)
                        st.success("Successfully updated NSE.json!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Failed to download NSE.json (Status: {response.status_code})")
            except Exception as e:
                st.error(f"Error updating NSE.json: {e}")

        # Strike Selection Uploader
        st.subheader("1. Strike Selection (ATM)")
        uploaded_strike = st.file_uploader("Upload Strike Selection Bhavcopy (CSV/ZIP)", type=['csv', 'zip'], key='strike_sel')
        if uploaded_strike is not None:
            csv_bytes, csv_name = process_uploaded_files(uploaded_strike)
            if csv_bytes and csv_name:
                with open(FILES['Strike_Selection'], 'wb') as f:
                    f.write(csv_bytes)
                save_meta('Strike_Selection', csv_name)
                st.success(f"Strike Selection file updated from {csv_name}!")

        meta = load_meta()
        if 'Strike_Selection' in meta and os.path.exists(FILES['Strike_Selection']):
            st.caption(f"📅 Data Date: {meta['Strike_Selection']}")

        # Previous Day Bhavcopy Uploader
        st.subheader("2. Previous Day Bhavcopy")
        # Checkbox defaults to False (Off). Toggles custom file vs ATM file handling.
        use_custom_prev_bhav = st.checkbox("Upload custom Previous Day Bhavcopy", value=False, key="use_prev_bhav_check")
        
        if use_custom_prev_bhav:
            uploaded_prev = st.file_uploader("Upload Previous Day Bhavcopy (CSV/ZIP)", type=['csv', 'zip'], key='prev_sel')
            if uploaded_prev is not None:
                csv_content, csv_name = process_uploaded_files(uploaded_prev)
                if csv_content:
                    with open(FILES['Prev_Bhavcopy'], 'wb') as f:
                        f.write(csv_content)
                    if csv_name:
                        save_meta('Prev_Bhavcopy', csv_name)
                    st.success(f"Previous Bhavcopy file updated from {csv_name}!")

            if 'Prev_Bhavcopy' in meta and os.path.exists(FILES['Prev_Bhavcopy']):
                st.caption(f"📅 Data Date: {meta['Prev_Bhavcopy']}")
        else:
            st.info("Using Strike Selection (ATM) as Previous Day Bhavcopy.")

        # JSTT Uploader
        st.subheader("3. JSTT Bhavcopy")
        uploaded_wh = st.file_uploader("Upload JSTT Bhavcopy (Multiple CSVs or ZIP)", type=['csv', 'zip'], accept_multiple_files=True, key='wh_sel')
        if uploaded_wh:
            csv_content, csv_name = process_uploaded_files(uploaded_wh)
            if csv_content:
                with open(FILES['JSTT_H'], 'wb') as f:
                    f.write(csv_content)
                if csv_name:
                    save_meta('JSTT_H', csv_name)
                st.success(f"JSTT file updated from {csv_name}!")

        if 'JSTT_H' in meta and os.path.exists(FILES['JSTT_H']):
            st.caption(f"📅 Data Date: {meta['JSTT_H']}")
            
        # Lot Size Uploader
        st.subheader("4. Lot Size File")
        uploaded_lot = st.file_uploader("Upload Dhan Lot Size File (CSV)", type=['csv'], key='lot_size_upload')
        if uploaded_lot is not None:
            try:
                csv_bytes = uploaded_lot.read()
                if csv_bytes:
                    with open(FILES['Lot_Size'], 'wb') as f:
                        f.write(csv_bytes)
                    save_meta('Lot_Size', getattr(uploaded_lot, 'name', 'lot_size.csv'))
                    st.success(f"Lot Size file updated from {getattr(uploaded_lot, 'name', 'lot_size.csv')}!")
            except Exception as e:
                st.error(f"Error reading Lot Size file: {e}")

        if 'Lot_Size' in meta and os.path.exists(FILES['Lot_Size']):
            st.caption(f"📅 Data File: {meta['Lot_Size']}")

        st.markdown("---")
        st.header("Auto Refresh")
        auto_refresh = st.checkbox("Enable Auto-Refresh", value=True)
        refresh_interval = st.slider("Refresh Interval (seconds)", min_value=5, max_value=60, value=30)

nse_json_df = load_nse_json()

if not nse_json_df.empty:
    run_every = refresh_interval if auto_refresh else None
    strike_file = FILES.get('Strike_Selection') if os.path.exists(FILES.get('Strike_Selection', '')) else None
    
    # Resolve the correct previous day bhavcopy source based on the user's toggle setting
    use_custom_prev = st.session_state.get("use_prev_bhav_check", False)
    if use_custom_prev:
        prev_file_path = FILES.get('Prev_Bhavcopy') if os.path.exists(FILES.get('Prev_Bhavcopy', '')) else None
    else:
        prev_file_path = strike_file

    if os.path.exists(FILES['JSTT_H']):
        @st.fragment(run_every=run_every)
        def show_JSTT_H():
            df_wh, target_exp, all_exps = process_bhavcopy(
                FILES['JSTT_H'], 
                nse_json_df, 
                target_expiry_index=target_expiry_idx, 
                strike_bhav_file=strike_file,
                prev_bhav_file=prev_file_path
            )
            render_header(target_exp)
            display_option_chain(df_wh, access_token)
        show_JSTT_H()
    else:
        render_header()
        st.warning("JSTT Bhavcopy file not found. Please upload 'JSTT Bhavcopy' (CSV/ZIP) in the sidebar.")
else:
    render_header()
    st.error("Critical Error: NSE.json could not be loaded.")
