import sys
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict

import requests
import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG & LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Stavová pamäť pre bota: { "SYMBOL_INTERVAL": {"state": "NORMAL", "in_zone_since": None} }
bot_state: Dict[str, dict] = {}

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
    return {"status": "VBSX Engine V2.7 - Bot Active!"}

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

def calculate_trading_score(df):
    if len(df) < 200: return pd.Series([50]*len(df), index=df.index)
    
    c = df['Close']
    o = df['Open']
    h = df['High']
    l = df['Low']
    v = df['Vol']

    rsi = calculate_rsi(c, 14)
    stoch_k, _ = calculate_stoch_rsi(rsi, 14, 3, 3)
    
    sma20 = c.rolling(20, min_periods=10).mean()
    std20 = c.rolling(20, min_periods=10).std()
    upper_bb = sma20 + (2 * std20)
    lower_bb = sma20 - (2 * std20)
    bb_pct = ((c - lower_bb) / (upper_bb - lower_bb + 1e-8) * 100).clip(0, 100).fillna(50)
    
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal
    
    macd_min = macd_hist.rolling(100, min_periods=10).min()
    macd_max = macd_hist.rolling(100, min_periods=10).max()
    macd_norm = ((macd_hist - macd_min) / (macd_max - macd_min + 1e-8) * 100).clip(0, 100).fillna(50)
    
    ema50 = c.ewm(span=50, adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()
    
    prev_c = c.shift(1)
    tr1 = h - l
    tr2 = (h - prev_c).abs()
    tr3 = (l - prev_c).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=1).mean().bfill()
    vol_sma = v.rolling(20, min_periods=1).mean().bfill()

    base_score = (0.35 * rsi) + (0.20 * stoch_k.fillna(50)) + (0.25 * bb_pct) + (0.20 * macd_norm)
    final_scores = []
    
    for i in range(len(df)):
        if i < 200:
            final_scores.append(base_score.iloc[i])
            continue
        score = base_score.iloc[i]
        curr_c = c.iloc[i]; curr_o = o.iloc[i]; curr_h = h.iloc[i]; curr_l = l.iloc[i]; curr_v = v.iloc[i]
        upper_wick = curr_h - max(curr_o, curr_c)
        lower_wick = min(curr_o, curr_c) - curr_l
        curr_atr = atr.iloc[i]; curr_vol_sma = vol_sma.iloc[i]
        
        if curr_l < lower_bb.iloc[i] and lower_wick > (0.8 * curr_atr) and curr_v > curr_vol_sma: score *= 0.40 
        if curr_h > upper_bb.iloc[i] and upper_wick > (0.8 * curr_atr) and curr_v > curr_vol_sma: score += (100 - score) * 0.60 

        if ema50.iloc[i] > ema200.iloc[i] and curr_c > ema200.iloc[i]:
            if abs(curr_l - ema50.iloc[i]) < curr_atr and stoch_k.iloc[i] < 30: score *= 0.75
        
        if ema50.iloc[i] < ema200.iloc[i] and curr_c < ema200.iloc[i]:
            if abs(curr_h - ema50.iloc[i]) < curr_atr and stoch_k.iloc[i] > 70: score += (100 - score) * 0.30

        if macd_hist.iloc[i] > 0 and macd_hist.iloc[i-1] <= 0 and curr_v > curr_vol_sma: score *= 0.85
        elif macd_hist.iloc[i] < 0 and macd_hist.iloc[i-1] >= 0 and curr_v > curr_vol_sma: score += (100 - score) * 0.20

        final_scores.append(max(0.0, min(100.0, score)))

    return pd.Series(final_scores, index=df.index).bfill().fillna(50)

def calculate_h_line_synergy(symbol):
    with ThreadPoolExecutor() as executor:
        f1 = executor.submit(get_crypto_data, symbol, "1h")
        f2 = executor.submit(get_crypto_data, symbol, "2h")
        f4 = executor.submit(get_crypto_data, symbol, "4h")
        f24 = executor.submit(get_crypto_data, symbol, "1d")
    
    df_1h, df_2h, df_4h, df_1d = f1.result(), f2.result(), f4.result(), f24.result()
    if df_1h.empty or df_2h.empty or df_4h.empty or df_1d.empty:
        return None, None

    s_1h = calculate_trading_score(df_1h)
    s_2h_a = calculate_trading_score(df_2h).reindex(df_1h.index, method='ffill').fillna(50)
    s_4h_a = calculate_trading_score(df_4h).reindex(df_1h.index, method='ffill').fillna(50)
    s_1d_a = calculate_trading_score(df_1d).reindex(df_1h.index, method='ffill').fillna(50)

    final_h_scores = []
    for i in range(len(df_1h)):
        sc_1, sc_2, sc_4, sc_1d = s_1h.iloc[i], s_2h_a.iloc[i], s_4h_a.iloc[i], s_1d_a.iloc[i]
        w_1 = 0.35 + (abs(sc_1 - 50) / 50) * 0.15
        w_2 = 0.25 + (abs(sc_2 - 50) / 50) * 0.05
        w_4, w_1d = 0.25, 0.15
        score = ((sc_1 * w_1) + (sc_2 * w_2) + (sc_4 * w_4) + (sc_1d * w_1d)) / (w_1 + w_2 + w_4 + w_1d)
        
        if sc_1 < 30 and sc_2 < 35 and sc_4 < 40:
            score *= 0.65
            if sc_1 < 20: score *= 0.70
        elif sc_1 > 70 and sc_2 > 65 and sc_4 > 60:
            score += (100 - score) * 0.50
            if sc_1 > 80: score += (100 - score) * 0.30
        elif (sc_1d > 70 and sc_1 < 30) or (sc_1d < 30 and sc_1 > 70):
            score = (score * 0.7) + (50 * 0.3)

        final_h_scores.append(max(0.0, min(100.0, score)))

    return df_1h, pd.Series(final_h_scores, index=df_1h.index)

# --- BOT LOGIC ---
def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: logger.error(f"Telegram Error: {e}")

def check_market_signals():
    logger.info("Checking market signals...")
    symbols = ["BTCUSDT", "SOLUSDT"]
    
    for symbol in symbols:
        df, scores = calculate_h_line_synergy(symbol)
        if df is None: continue
        
        curr_score = scores.iloc[-1]
        prev_score = scores.iloc[-2]
        price = df['Close'].iloc[-1]
        
        # EMA200 filter (1h timeframe)
        ema200 = df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
        trend = "UP" if price > ema200 else "DOWN"
        
        state_key = f"{symbol}_HLINE"
        if state_key not in bot_state: bot_state[state_key] = {"state": "NORMAL", "in_zone_since": None}
        
        # LOGIKA SIGNÁLOV S POTVRDENÍM NÁVRATU
        # 1. LONG: Bol pod 20 a teraz vyšiel nad 20 + Trend Filter
        if bot_state[state_key]["state"] == "OVERSOLD" and curr_score > 20:
            if trend == "UP": # Len do trendu
                msg = f"🚀 *LONG SIGNAL: {symbol}*\n\n" \
                      f"Score: {round(curr_score, 1)}% (Návrat z prepredania)\n" \
                      f"Price: ${price:,.2f}\n" \
                      f"Trend: 🟢 UPTREND (nad EMA200)\n" \
                      f"Mode: H-LINE SYNERGY"
                send_telegram_msg(msg)
            bot_state[state_key]["state"] = "NORMAL"
            
        # 2. SHORT: Bol nad 80 a teraz klesol pod 80 + Trend Filter
        elif bot_state[state_key]["state"] == "OVERBOUGHT" and curr_score < 80:
            if trend == "DOWN": # Len do trendu
                msg = f"🔻 *SHORT SIGNAL: {symbol}*\n\n" \
                      f"Score: {round(curr_score, 1)}% (Návrat z prekúpenia)\n" \
                      f"Price: ${price:,.2f}\n" \
                      f"Trend: 🔴 DOWNTREND (pod EMA200)\n" \
                      f"Mode: H-LINE SYNERGY"
                send_telegram_msg(msg)
            bot_state[state_key]["state"] = "NORMAL"
            
        # Nastavenie stavu zóny
        if curr_score <= 20: bot_state[state_key]["state"] = "OVERSOLD"
        elif curr_score >= 80: bot_state[state_key]["state"] = "OVERBOUGHT"

@app.on_event("startup")
def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_market_signals, 'interval', minutes=5)
    scheduler.start()
    app.state.scheduler = scheduler
    
    # Uvítacia správa po úspešnom nasadení
    send_telegram_msg("🤖 *VBSX Engine Online*\nBot bol úspešne aktivovaný a každých 5 minút skenuje H-LINE signály pre BTC a SOL.")

@app.post("/analyze")
def analyze(req: AnalyzeRequest = None):
    mode = req.mode.upper() if req else "MACRO"
    interval = req.interval.lower() if req else "1w"
    symbol = "BTCUSDT" if mode == "MACRO" else "SOLUSDT"
    name = "Bitcoin" if mode == "MACRO" else "Solana"
    ticker = "BTC" if mode == "MACRO" else "SOL"

    if interval == "h-line":
        df, score_series = calculate_h_line_synergy(symbol)
        if df is None: return {"error": "API Error: Binance unreachable for H-LINE."}
        analysis_tag = "VBSX TRADING (H-LINE ISM v2.0)"
    else:
        df = get_crypto_data(symbol, interval)
        if df.empty: return {"error": "API Error: Binance unreachable."}
        if mode == "TRADING":
            score_series = calculate_trading_score(df)
            analysis_tag = f"VBSX TRADING ({interval.upper()})"
        else:
            score_series = calculate_macro_score(df['Close'])
            analysis_tag = "VBSX MACRO (1W)"

    curr_score = round(float(score_series.iloc[-1]), 1)
    return {
        "price": float(df['Close'].iloc[-1]),
        "change": round(get_24h_change(symbol), 2),
        "analysis": analysis_tag,
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
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)