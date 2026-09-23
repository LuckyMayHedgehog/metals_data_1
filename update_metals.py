import os
import json
import datetime
import requests
import pandas as pd
import yfinance as yf
import firebase_admin
from firebase_admin import credentials, db

FIREBASE_URL = "https://metals-24324-default-rtdb.firebaseio.com/"
LOCAL_KEY_FILE = "metals-24324-firebase-adminsdk-fbsvc-0da1c70392.json"

# Підключення: або через Secret у GitHub Actions, або через локальний файл
if not firebase_admin._apps:
    if os.environ.get("FIREBASE_CREDENTIALS"):
        cred_dict = json.loads(os.environ["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
    elif os.path.exists(LOCAL_KEY_FILE):
        cred = credentials.Certificate(LOCAL_KEY_FILE)
    else:
        raise FileNotFoundError("Сертифікат доступу до Firebase не знайдено!")
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_URL})

def fetch_recent_yahoo():
    tickers = {
        "GLD": {"name": "Gold", "category": "metal"},
        "SLV": {"name": "Silver", "category": "metal"},
        "^GSPC": {"name": "S&P 500", "category": "index"},
        "^FTSE": {"name": "FTSE 100", "category": "index"}
    }
    df = yf.download(list(tickers.keys()), period="7d", progress=False)
    close_df = df["Close"] if "Close" in df.columns else df
    yahoo_dict = {}
    for date_idx, row in close_df.iterrows():
        d_str = date_idx.strftime("%Y-%m-%d")
        yahoo_dict[d_str] = {}
        for ticker, meta in tickers.items():
            val = row.get(ticker)
            if pd.notna(val):
                yahoo_dict[d_str][ticker] = {
                    "name": meta["name"],
                    "category": meta["category"],
                    "value": round(float(val), 2),
                    "source": "Yahoo Finance"
                }
    return yahoo_dict

def fetch_recent_matthey():
    start_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%d-%m-%Y")
    end_date = datetime.date.today().strftime("%d-%m-%Y")
    url = 'https://matthey.com/products-and-markets/pgms-and-circularity/pgm-management?p_p_id=jm_metal_price_portlet_JmMetalPricePortlet&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_cacheability=cacheLevelPage'
    metals = ['Pt', 'Pd', 'Rh', 'Ir', 'Ru']
    payload = {
        '_jm_metal_price_portlet_JmMetalPricePortlet_IntervalType': 'DAILY',
        '_jm_metal_price_portlet_JmMetalPricePortlet_start_Date': start_date,
        '_jm_metal_price_portlet_JmMetalPricePortlet_end_Date': end_date
    }
    for i, m in enumerate(metals):
        payload[f'_jm_metal_price_portlet_JmMetalPricePortlet_selectedMetal{i}'] = m
        
    res = requests.post(url=url, data=payload, timeout=15)
    csv_url = json.loads(res.text)['url']
    df_jm = pd.read_csv(csv_url, header=[1])
    df_jm['Date'] = pd.to_datetime(df_jm['Date'], format='mixed')
    
    jm_dict = {}
    for _, row in df_jm.iterrows():
        d_str = row['Date'].strftime("%Y-%m-%d")
        jm_dict[d_str] = {}
        for col in ['Platinum', 'Palladium', 'Rhodium', 'Iridium', 'Ruthenium']:
            if col in row and pd.notna(row[col]):
                jm_dict[d_str][col] = {
                    "name": col,
                    "category": "metal",
                    "value": round(float(row[col]), 2),
                    "source": "Johnson Matthey"
                }
    return jm_dict

def main():
    yahoo_data = fetch_recent_yahoo()
    jm_data = fetch_recent_matthey()
    all_dates = sorted(list(set(list(yahoo_data.keys()) + list(jm_data.keys()))))
    updates = {}
    for d in all_dates:
        rates = {}
        if d in yahoo_data:
            rates.update(yahoo_data[d])
        if d in jm_data:
            rates.update(jm_data[d])
        if rates:
            updates[d] = {"timestamp": f"{d} 00:00:00", "rates": rates}
    if updates:
        db.reference("/metals_history").update(updates)
        print(f"Оновлено {len(updates)} дат.")
    else:
        print("Нових даних не виявлено.")

if __name__ == "__main__":
    main()
