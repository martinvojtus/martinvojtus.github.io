import os
import time
import json
import logging
import requests
import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai

load_dotenv()

# --- CONFIG & LOGGING ---
logging.basicConfig(level=logging.INFO)
logging.getLogger("google_genai.models").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

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

def _fetch_from_binance_url(url):
    r = requests.get(url, headers=HEADERS, timeout=8)
    r.raise_for_status()
    df = pd.DataFrame(r.json(), columns=['Time', 'Open', 'High', 'Low', 'Close', 'Vol', 'CloseTime', 'QuoteVol', 'Trades', 'TakerBuyVol', 'TakerBuyQuoteVol', 'Ignore'])
    for col in ['Open', 'High', 'Low', 'Close', 'Vol']:
        df[col] = df[col].astype(float)
    df['Time'] = pd.to_datetime(df['Time'], unit='ms')
    df = df.set_index('Time')
    if len(df) >= 200:
        return df
    raise ValueError(f"Insufficient candles: {len(df)}")

def _fetch_from_gateio(pair="BTC_USDT", interval="7d"):
    url = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={pair}&interval={interval}&limit=1000"
    r = requests.get(url, headers=HEADERS, timeout=8)
    r.raise_for_status()
    raw = r.json()
    if not isinstance(raw, list) or len(raw) < 200:
        raise ValueError("Invalid or insufficient Gate.io candles")
    df = pd.DataFrame(raw, columns=['Time', 'QuoteVol', 'Close', 'High', 'Low', 'Open', 'Vol', 'WindowEnd'])
    for col in ['Open', 'High', 'Low', 'Close', 'Vol']:
        df[col] = df[col].astype(float)
    df['Time'] = pd.to_datetime(df['Time'].astype(int), unit='s')
    return df.set_index('Time').sort_index()

def _fetch_from_bybit(symbol="BTCUSDT", interval="W"):
    url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval={interval}&limit=1000"
    r = requests.get(url, headers=HEADERS, timeout=8)
    r.raise_for_status()
    raw = r.json().get('result', {}).get('list', [])
    if not isinstance(raw, list) or len(raw) < 200:
        raise ValueError("Invalid or insufficient Bybit candles")
    df = pd.DataFrame(raw, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Vol', 'Turnover'])
    for col in ['Open', 'High', 'Low', 'Close', 'Vol']:
        df[col] = df[col].astype(float)
    df['Time'] = pd.to_datetime(df['Time'].astype(int), unit='ms')
    return df.set_index('Time').sort_index()

def _fetch_from_kraken(pair="XBTUSDT", interval=10080):
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    r = requests.get(url, headers=HEADERS, timeout=8)
    r.raise_for_status()
    res = r.json().get('result', {})
    key = [k for k in res.keys() if k != 'last'][0]
    raw = res[key]
    if not isinstance(raw, list) or len(raw) < 200:
        raise ValueError("Invalid or insufficient Kraken candles")
    df = pd.DataFrame(raw, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Vwap', 'Vol', 'Count'])
    for col in ['Open', 'High', 'Low', 'Close', 'Vol']:
        df[col] = df[col].astype(float)
    df['Time'] = pd.to_datetime(df['Time'].astype(int), unit='s')
    return df.set_index('Time').sort_index()

def get_crypto_data(symbol="BTCUSDT", interval="1w"):
    sources = [
        ("Binance Vision", lambda: _fetch_from_binance_url(f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit=1000")),
        ("Binance Official", lambda: _fetch_from_binance_url(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=1000")),
        ("Gate.io", lambda: _fetch_from_gateio()),
        ("Bybit", lambda: _fetch_from_bybit()),
        ("Binance US", lambda: _fetch_from_binance_url(f"https://api.binance.us/api/v3/klines?symbol={symbol}&interval={interval}&limit=1000")),
        ("Kraken", lambda: _fetch_from_kraken()),
    ]
    for name, fetch_func in sources:
        try:
            df = fetch_func()
            if not df.empty:
                logger.info(f"Successfully fetched {len(df)} candles from {name}")
                return df
        except Exception as e:
            logger.warning(f"Data Fetch from {name} failed: {e}")

    logger.error("All crypto data sources failed.")
    return pd.DataFrame()

def get_24h_change(symbol="BTCUSDT"):
    sources = [
        ("Binance Vision", f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={symbol}", lambda r: float(r.json()['priceChangePercent'])),
        ("Binance Official", f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", lambda r: float(r.json()['priceChangePercent'])),
        ("Gate.io", "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT", lambda r: float(r.json()[0]['change_percentage'])),
        ("Bybit", f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}", lambda r: float(r.json()['result']['list'][0]['price24hPcnt']) * 100.0),
        ("Binance US", f"https://api.binance.us/api/v3/ticker/24hr?symbol={symbol}", lambda r: float(r.json()['priceChangePercent'])),
        ("Kraken", "https://api.kraken.com/0/public/Ticker?pair=XBTUSDT", lambda r: ((float(r.json()['result'][next(iter(r.json()['result']))]['c'][0]) - float(r.json()['result'][next(iter(r.json()['result']))]['o'])) / float(r.json()['result'][next(iter(r.json()['result']))]['o'])) * 100.0),
    ]
    for name, url, parser in sources:
        try:
            r = requests.get(url, headers=HEADERS, timeout=5)
            if r.status_code == 200:
                return float(parser(r))
        except Exception as e:
            logger.warning(f"Ticker Fetch from {name} failed: {e}")
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

_ai_cache = {
    "data": None,
    "timestamp": 0,
    "price": None,
    "score": None,
}

def generate_ai_macro_insight(price: float, change_24h: float, cycle_score: float, phase: str, rsi_val: float, ma200_val: float, drawdown: float) -> dict | None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not configured. Skipping AI insight generation.")
        return None

    now = time.time()
    if _ai_cache["data"] and (now - _ai_cache["timestamp"] < 600):
        if _ai_cache["score"] is not None and abs(_ai_cache["score"] - cycle_score) < 1.0:
            logger.info("Serving AI macro insight from cache.")
            return _ai_cache["data"]

    ma200_rel = round(((price - ma200_val) / ma200_val) * 100, 1) if ma200_val else 0

    prompt = f"""You are a quantitative macro analyst specializing in Bitcoin cycle analysis.
Analyze the following live Bitcoin macro metrics:
- Current Price: ${price:,.2f}
- 24h Change: {change_24h:+.2f}%
- Macro Cycle Score: {cycle_score:.1f}% (Scale: 0-100%. 0-20% DCA IN, 21-79% HODL, 80-100% DCA OUT)
- Current Cycle Phase: {phase}
- 14-week RSI: {rsi_val:.1f}
- Price vs 200-Week Moving Average: {ma200_rel:+.1f}%
- Drawdown from Rolling ATH: {drawdown:.1f}%

Provide a high-signal institutional macro brief.
Respond strictly in JSON format with exactly these keys:
{{
  "regime": "A 2-4 word macro regime label (e.g. 'Mid-Cycle Consolidation', 'Accumulation Zone', 'Distribution Warning', etc.)",
  "summary": "2 concise sentences synthesizing the market regime, momentum, and cycle position.",
  "strategy": "1 sentence actionable perspective aligned with the macro score and phase."
}}"""

    models_to_try = ["gemini-flash-latest", "gemini-2.5-flash-lite"]
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini client: {e}")
        return _ai_cache.get("data")

    for model_name in models_to_try:
        try:
            logger.info(f"Generating AI macro insight with model: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            insight_data = json.loads(raw_text.strip())
            insight_data["model"] = "Gemini AI"
            insight_data["generated_at"] = int(now * 1000)

            _ai_cache["data"] = insight_data
            _ai_cache["timestamp"] = now
            _ai_cache["price"] = price
            _ai_cache["score"] = cycle_score
            return insight_data
        except Exception as e:
            logger.warning(f"Gemini generation with {model_name} failed: {e}")

    return _ai_cache.get("data")

@app.get("/ai-insight")
def get_ai_insight_endpoint():
    symbol = "BTCUSDT"
    interval = "1w"
    df = get_crypto_data(symbol, interval)
    if df.empty:
        return {"error": "API Error: All market data sources unreachable."}

    score_series = calculate_macro_score(df['Close'])
    curr_score = round(float(score_series.iloc[-1]), 1)
    price = float(df['Close'].iloc[-1])
    change_24h = round(get_24h_change(symbol), 2)
    rsi_series = calculate_rsi(df['Close'], 14)
    rsi_val = round(float(rsi_series.iloc[-1]), 1) if not rsi_series.empty else 50.0
    ma200_series = df['Close'].rolling(200, min_periods=10).mean().bfill()
    ma200_val = float(ma200_series.iloc[-1]) if not ma200_series.empty else price
    rolling_ath = float(df['Close'].cummax().iloc[-1])
    drawdown = round(((price - rolling_ath) / rolling_ath) * 100, 1) if rolling_ath else 0.0
    phase = "DCA IN" if curr_score <= 20 else ("HODL" if curr_score <= 79 else "DCA OUT")

    insight = generate_ai_macro_insight(price, change_24h, curr_score, phase, rsi_val, ma200_val, drawdown)
    return {"ai_insight": insight}

@app.post("/analyze")
def analyze(req: AnalyzeRequest = None):
    symbol = "BTCUSDT"
    interval = "1w"
    name = "Bitcoin"
    ticker = "BTC"

    df = get_crypto_data(symbol, interval)
    if df.empty:
        return {"error": "API Error: All market data sources unreachable."}

    score_series = calculate_macro_score(df['Close'])
    curr_score = round(float(score_series.iloc[-1]), 1)
    price = float(df['Close'].iloc[-1])
    change_24h = round(get_24h_change(symbol), 2)
    rsi_series = calculate_rsi(df['Close'], 14)
    rsi_val = round(float(rsi_series.iloc[-1]), 1) if not rsi_series.empty else 50.0
    ma200_series = df['Close'].rolling(200, min_periods=10).mean().bfill()
    ma200_val = float(ma200_series.iloc[-1]) if not ma200_series.empty else price
    rolling_ath = float(df['Close'].cummax().iloc[-1])
    drawdown = round(((price - rolling_ath) / rolling_ath) * 100, 1) if rolling_ath else 0.0
    phase = "DCA IN" if curr_score <= 20 else ("HODL" if curr_score <= 79 else "DCA OUT")

    ai_insight = generate_ai_macro_insight(price, change_24h, curr_score, phase, rsi_val, ma200_val, drawdown)

    return {
        "price": price,
        "change": change_24h,
        "analysis": "MACRO (1W)",
        "name": name,
        "ticker": ticker,
        "chart_dates": [int(d.timestamp() * 1000) for d in df.index],
        "chart_score": score_series.values.tolist(),
        "cycle_score": curr_score,
        "phase": phase,
        "ai_insight": ai_insight
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
