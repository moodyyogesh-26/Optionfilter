import requests
import gzip
import shutil
import os

# --- Upstox Master ---
UPSTOX_JSON_PATH = 'NSE.json'
upstox_url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def update_upstox():
    try:
        print(f"Downloading Upstox Master: {upstox_url}...")
        response = requests.get(upstox_url, headers=headers, stream=True)
        if response.status_code == 200:
            with open(UPSTOX_JSON_PATH, "wb") as f_out:
                with gzip.GzipFile(fileobj=response.raw) as f_in:
                    shutil.copyfileobj(f_in, f_out)
            print(f"✅ Updated {UPSTOX_JSON_PATH} successfully!")
        else:
            print(f"❌ Failed to download Upstox. Status: {response.status_code}")
    except Exception as e:
        print(f"Error updating Upstox: {e}")

if __name__ == "__main__":
    print("--- Master Instrument Updater ---")
    update_upstox()
    print("--- Update Complete ---")

