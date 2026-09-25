import os
import logging
import requests
import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG & LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    mode: str = "MACRO"
    interval: str = "1w"

@app.get("/")
def keep_alive():
    return {"status": "Trading Engine - Bot Active!"}

def get_crypto_data(symbol="BTCUSDT", interval="1w"):
    try:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit=1000"
        r = requests.get(url, timeout=10)
        df = pd.DataFrame(r.json(), columns=['Time', 'Open', 'High', 'Low', 'Close', 'Vol', 'CloseTime', 'QuoteVol', 'Trades', 'TakerBuyVol', 'TakerBuyQuoteVol', 'Ignore'])
        for col in ['Open', 'High', 'Low', 'Close', 'Vol']:
            df[col] = df[col].astype(float)
        df['Time'] = pd.to_datetime(df['Time'], unit='ms')
        return df.set_index('Time')
    except Exception as e:
        logger.error(f"Data Fetch Error: {e}")
        return pd.DataFrame()

def get_24h_change(symbol="BTCUSDT"):
    try:
        r = requests.get(f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={symbol}", timeout=5)
        return float(r.json()['priceChangePercent'])
    except:
        return 0.0

def calculate_rsi(series, window=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=window-1, adjust=False).mean()
    ema_down = down.ewm(com=window-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

def calculate_stoch_rsi(rsi, window=14, smooth_k=3, smooth_d=3):
    min_rsi = rsi.rolling(window=window).min()
    max_rsi = rsi.rolling(window=window).max()
    stoch = ((rsi - min_rsi) / (max_rsi - min_rsi + 1e-8)) * 100
    k = stoch.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()
    return k, d

def calculate_macro_score(prices):
    if len(prices) < 200: return pd.Series([50]*len(prices), index=prices.index)
    
    rsi = calculate_rsi(prices, 14)
    stoch_k, _ = calculate_stoch_rsi(rsi, 14, 3, 3)
    ma200 = prices.rolling(200, min_periods=10).mean().bfill()
    ma50 = prices.rolling(50, min_periods=10).mean().bfill() 
    rolling_ath = prices.cummax()
    drawdown = ((prices - rolling_ath) / rolling_ath) * 100

    log_ratio = np.log(prices / ma200).clip(lower=0)
    log_norm = (log_ratio / 1.3 * 100).clip(0, 100) 
    dd_norm = ((drawdown - (-75)) / (0 - (-75)) * 100).clip(0, 100)
    rsi_norm = ((rsi - 30) / (85 - 30) * 100).clip(0, 100)
    stoch_norm = stoch_k.fillna(50).clip(0, 100)
    base_score = (0.35 * log_norm) + (0.35 * rsi_norm) + (0.15 * dd_norm) + (0.15 * stoch_norm)
    
    final_scores = []
    ath_streak = 0 
    weeks_since_bottom = 0 
    
    for i in range(len(prices)):
        if i < 150:
            final_scores.append(base_score.iloc[i])
            continue
            
        p_curr = prices.iloc[i]; r_curr = rsi.iloc[i]; r_prev = rsi.iloc[i-1]; r_prev2 = rsi.iloc[i-2]; k_curr = stoch_k.iloc[i]
        score = base_score.iloc[i]
        rule_d_active = False 

        p_104w = prices.iloc[i-104:i+1]
        r_104w = rsi.iloc[i-104:i+1]
        p_52w = prices.iloc[i-52:i+1]
        p_26w = prices.iloc[i-26:i+1]

        fib_slice = prices.iloc[i-150:i-26]
        if not fib_slice.empty:
            f_max = fib_slice.max(); f_min = fib_slice.min()
            if p_curr >= f_max + ((f_max - f_min) * 1.618): score += (100 - score) * 0.20
            elif p_curr >= f_max + ((f_max - f_min) * 0.08): score += (100 - score) * 0.08

        if p_curr > ma200.iloc[i] and drawdown.iloc[i] <= -20 and k_curr < 20: score *= 0.60 

        recent_low = p_26w.min()
        if p_curr < ma200.iloc[i] and ((p_curr - recent_low) / recent_low) * 100 >= 20 and k_curr > 80: score += (100 - score) * 0.40

        if p_curr <= p_52w.min() * 1.05: weeks_since_bottom = 0; score *= 0.6  
        else: weeks_since_bottom += 1

        if p_curr >= p_104w.max() * 0.95:
            if (p_104w.iloc[52:].max() > p_104w.iloc[:52].max()) and (r_104w.iloc[52:].max() < r_104w.iloc[:52].max()) and r_curr > 65 and p_curr > ma200.iloc[i] * 2.0:
                score += (100 - score) * 0.6; rule_d_active = True 
                
        if p_curr > ma50.iloc[i] * 1.8 and r_curr > 75: score += (100 - score) * 0.5

        p_prev_max = rolling_ath.iloc[i-1] if i > 0 else rolling_ath.iloc[0]
        if p_curr >= p_prev_max: ath_streak += 1
        else: ath_streak = 0
        
        if ath_streak > 0:
            pr = min((0.112 + (ath_streak - 20) * 0.02) if ath_streak > 20 else ((0.016 + (ath_streak - 8) * 0.008) if ath_streak > 8 else ath_streak * 0.002), 0.30)
            score += (100 - score) * pr

        if weeks_since_bottom > 100 and p_curr > (ma200.iloc[i] * 1.25): score += (100 - score) * (min(weeks_since_bottom - 100, 70) * 0.0025)

        if p_curr >= p_26w.max() * 0.90 and (r_prev < 70) and (r_curr < r_prev) and (r_prev > r_prev2) and score > 79 and not rule_d_active: score *= 0.85  

        final_scores.append(max(0.0, min(100.0, score)))

    return pd.Series(final_scores, index=prices.index).bfill().fillna(50)

@app.post("/analyze")
def analyze(req: AnalyzeRequest = None):
    symbol = "BTCUSDT"
    interval = "1w"
    name = "Bitcoin"
    ticker = "BTC"

    df = get_crypto_data(symbol, interval)
    if df.empty:
        return {"error": "API Error: Binance unreachable."}

    score_series = calculate_macro_score(df['Close'])
    curr_score = round(float(score_series.iloc[-1]), 1)

    return {
        "price": float(df['Close'].iloc[-1]),
        "change": round(get_24h_change(symbol), 2),
        "analysis": "MACRO (1W)",
        "name": name,
        "ticker": ticker,
        "chart_dates": [int(d.timestamp() * 1000) for d in df.index],
        "chart_score": score_series.values.tolist(),
        "cycle_score": curr_score,
        "phase": "DCA IN" if curr_score <= 20 else ("HODL" if curr_score <= 79 else "DCA OUT")
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
