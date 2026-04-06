import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_bot.bybit_executor import BybitExecutor
import os
import requests
import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- GLOBÁLNA PAMÄŤ PRE POSLEDNÉ SIGNÁLY ---
LAST_TRADER_SIGNALS = {"BTC": None, "SOL": None}

# --- TRADING BOT LOGIC ---
class TelegramBot:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text):
        if not self.token or not self.chat_id:
            return
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"Telegram error: {e}")

    def notify_hook(self, signal, leverage, score_ema, interval_scores, asset="SOL"):
        emoji = "🚀 LONG" if signal == "BUY" else "🔻 SHORT"
        msg = f"*{emoji} {asset} SIGNAL CONFIRMED!* (Leverage: {leverage}x)\n\n"
        msg += f"MTF Master EMA: `{score_ema}%`\n"
        msg += f"1d: `{interval_scores.get('1d')}%` | 4h: `{interval_scores.get('4h')}%`\n"
        msg += f"2h: `{interval_scores.get('2h')}%` | 1h: `{interval_scores.get('1h')}%`"
        self.send_message(msg)
        
        # Uložíme do globálnej pamäte pre web
        LAST_TRADER_SIGNALS[asset] = {
            "signal": "LONG" if signal == "BUY" else "SHORT",
            "time": datetime.now().strftime("%d %b %H:%M"),
            "score": score_ema
        }

class VBSXStrategy:
    def __init__(self, ema_period=5):
        self.ema_period = ema_period
        self.ema_value = None
        self.k = 2 / (ema_period + 1)
        self.history = []
        self.raw_history = []

    def calculate_weighted_score(self, scores):
        w1d = scores.get("1d", 50.0) * 0.4
        w4h = scores.get("4h", 50.0) * 0.3
        w2h = scores.get("2h", 50.0) * 0.2
        w1h = scores.get("1h", 50.0) * 0.1
        return round(w1d + w4h + w2h + w1h, 2)

    def update_ema(self, new_score):
        # Save raw score for emergency signals
        self.raw_history.append(new_score)
        if len(self.raw_history) > 50: self.raw_history.pop(0)

        # Update EMA
        if self.ema_value is None:
            self.ema_value = new_score
        else:
            self.ema_value = (new_score * self.k) + (self.ema_value * (1 - self.k))
        self.ema_value = round(self.ema_value, 2)
        self.history.append(self.ema_value)
        if len(self.history) > 50: self.history.pop(0)
        return self.ema_value

    def check_hook(self):
        if len(self.history) < 2 or len(self.raw_history) < 2: return None, None
        
        prev_raw = self.raw_history[-2]
        curr_raw = self.raw_history[-1]
        
        # 1. EMERGENCY SIGNALS (3x Leverage) - Absolute Extremes
        if prev_raw >= 95 and curr_raw < prev_raw:
            return "SELL", 3.0
        if prev_raw <= 5 and curr_raw > prev_raw:
            return "BUY", 3.0

        # 2. STANDARD SWING SIGNALS (2x Leverage) - EMA Hooks
        prev_ema = self.history[-2]
        curr_ema = self.history[-1]
        
        if prev_ema < 20 and curr_ema > prev_ema:
            # Check if it was very deep for 3x
            lev = 3.0 if prev_ema < 10 else 2.0
            return "BUY", lev
            
        if prev_ema > 80 and curr_ema < prev_ema:
            lev = 3.0 if prev_ema > 90 else 2.0
            return "SELL", lev
        
        return None, None

async def trading_bot_loop():
    print("Starting background VBSX Bot Loop...")
    strategies = {"SOL": VBSXStrategy()}
    executor = BybitExecutor()
    tg_bot = TelegramBot()
    tg_bot.send_message("🤖 *VBSX Bot Active on Render*\nMonitoring: SOL (1d, 4h, 2h, 1h)")
    
    intervals = ["1d", "4h", "2h", "1h"]

    while True:
        try:
            for asset in ["SOL"]:
                symbol = f"{asset}USDT"
                scores = {}
                for interval in intervals:
                    df = get_crypto_data(symbol, interval)
                    if not df.empty:
                        score_series = calculate_trading_score(df)
                        scores[interval] = round(float(score_series.iloc[-1]), 1)
                    else:
                        scores[interval] = 50.0
                
                strategy = strategies[asset]
                master_score = strategy.calculate_weighted_score(scores)
                ema = strategy.update_ema(master_score)
                signal, leverage = strategy.check_hook()
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Bot Loop -> {asset} Master: {master_score}, EMA: {ema}")
                
                if signal:
                    tg_bot.notify_hook(signal, leverage, ema, scores, asset)
                    # EXECUTE ON BYBIT
                    try:
                        executor.execute_signal(signal, leverage)
                    except Exception as e:
                        print(f"Bybit Execution Error: {e}")
                
                # Check for scale-in (Momentum Trigger) every loop
                try:
                    executor.check_scale_in()
                except Exception as e:
                    print(f"Bybit Scale-in Check Error: {e}")
                
        except Exception as e:
            print(f"Bot Loop Error: {e}")
            
        await asyncio.sleep(300)  # Check every 5 minutes (300 seconds)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(trading_bot_loop())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(lifespan=lifespan)

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
    return {"status": "VBSX Engine V2.7 - Macro & Advanced Swing Trading Active!"}

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
        print(f"Data Fetch Error: {e}")
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

# === PÔVODNÝ MACRO ENGINE (TÝŽDENNÝ GRAF - STRICTLY UNTOUCHED) ===
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
            elif p_curr >= f_max + ((f_max - f_min) * 0.618): score += (100 - score) * 0.08

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


# === SOFISTIKOVANÝ SWING TRADING ENGINE (V2.7) ===
def calculate_trading_score(df):
    if len(df) < 200: return pd.Series([50]*len(df), index=df.index)
    
    c = df['Close']
    o = df['Open']
    h = df['High']
    l = df['Low']
    v = df['Vol']

    # 1. Momentum & Oscilátory
    rsi = calculate_rsi(c, 14)
    stoch_k, _ = calculate_stoch_rsi(rsi, 14, 3, 3)
    
    # 2. Volatilita a Bollinger Bands
    sma20 = c.rolling(20, min_periods=10).mean()
    std20 = c.rolling(20, min_periods=10).std()
    upper_bb = sma20 + (2 * std20)
    lower_bb = sma20 - (2 * std20)
    bb_pct = ((c - lower_bb) / (upper_bb - lower_bb + 1e-8) * 100).clip(0, 100).fillna(50)
    
    # 3. MACD Normalizované Momentum
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal
    
    macd_min = macd_hist.rolling(100, min_periods=10).min()
    macd_max = macd_hist.rolling(100, min_periods=10).max()
    macd_norm = ((macd_hist - macd_min) / (macd_max - macd_min + 1e-8) * 100).clip(0, 100).fillna(50)
    
    # 4. Trend Filtre (EMA)
    ema50 = c.ewm(span=50, adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()
    
    # 5. ATR (Average True Range) a Volume MA pre detekciu anomálií
    prev_c = c.shift(1)
    tr1 = h - l
    tr2 = (h - prev_c).abs()
    tr3 = (l - prev_c).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=1).mean().bfill()
    vol_sma = v.rolling(20, min_periods=1).mean().bfill()

    # ZÁKLADNÉ TRADING SKÓRE (Kombinácia štruktúry)
    base_score = (0.35 * rsi) + (0.20 * stoch_k.fillna(50)) + (0.25 * bb_pct) + (0.20 * macd_norm)
    
    final_scores = []
    
    for i in range(len(df)):
        if i < 200:
            final_scores.append(base_score.iloc[i])
            continue
            
        score = base_score.iloc[i]
        
        curr_c = c.iloc[i]
        curr_o = o.iloc[i]
        curr_h = h.iloc[i]
        curr_l = l.iloc[i]
        curr_v = v.iloc[i]
        
        upper_wick = curr_h - max(curr_o, curr_c)
        lower_wick = min(curr_o, curr_c) - curr_l
        
        curr_atr = atr.iloc[i]
        curr_vol_sma = vol_sma.iloc[i]
        
        # --- SWING TRADING MODIFIKÁTORY ---
        
        # 1. INSTITUTIONAL LIQUIDITY GRAB (BUY)
        # Sviečka prepichla Lower BB, objem je nadpriemerný a spodný chvost je dlhší ako 80% ATR
        if curr_l < lower_bb.iloc[i] and lower_wick > (0.8 * curr_atr) and curr_v > curr_vol_sma:
            score *= 0.40 

        # 2. INSTITUTIONAL EXHAUSTION (SELL)
        # Sviečka prepichla Upper BB, objem je nadpriemerný a horný chvost je dlhší ako 80% ATR
        if curr_h > upper_bb.iloc[i] and upper_wick > (0.8 * curr_atr) and curr_v > curr_vol_sma:
            score += (100 - score) * 0.60 

        # 3. TREND PULLBACK (Golden Swing Buy)
        # Sme v Uptrende (EMA50 > EMA200). Cena klesla k EMA50 (vzdialenosť < 1 ATR) a indikátory sú prepredané
        if ema50.iloc[i] > ema200.iloc[i] and curr_c > ema200.iloc[i]:
            if abs(curr_l - ema50.iloc[i]) < curr_atr and stoch_k.iloc[i] < 30:
                score *= 0.75
        
        # 4. TREND EXHAUSTION (Swing Sell)
        # Sme v Downtrende (EMA50 < EMA200). Cena vyskočila k EMA50 a indikátory sú prekúpené
        if ema50.iloc[i] < ema200.iloc[i] and curr_c < ema200.iloc[i]:
            if abs(curr_h - ema50.iloc[i]) < curr_atr and stoch_k.iloc[i] > 70:
                score += (100 - score) * 0.30

        # 5. MACD CROSSOVER REAKCIA NA OBJEME
        if macd_hist.iloc[i] > 0 and macd_hist.iloc[i-1] <= 0 and curr_v > curr_vol_sma:
            score *= 0.85 # Potvrdený nákupný setup
        elif macd_hist.iloc[i] < 0 and macd_hist.iloc[i-1] >= 0 and curr_v > curr_vol_sma:
            score += (100 - score) * 0.20 # Potvrdený výpredajný setup

        final_scores.append(max(0.0, min(100.0, score)))

    return pd.Series(final_scores, index=df.index).bfill().fillna(50)


@app.post("/analyze")
def analyze(req: AnalyzeRequest = None):
    mode = req.mode.upper() if req else "MACRO"
    interval = req.interval.lower() if req else "1w"
    
    if mode == "MACRO":
        symbol = "BTCUSDT"
        name = "Bitcoin"
        ticker = "BTC"
    else:
        symbol = "SOLUSDT"
        name = "Solana"
        ticker = "SOL"

    df = get_crypto_data(symbol, interval)
    if df.empty:
        return {"error": "API Error: Binance unreachable."}

    # SEPARÁTNE SMEROVANIE LOGIKY
    if mode == "TRADING":
        score_series = calculate_trading_score(df)
        analysis_tag = f"VBSX TRADING ({interval.upper()})"
    else:
        prices = df['Close']
        score_series = calculate_macro_score(prices)
        analysis_tag = "VBSX MACRO (1W)"

    curr_score = round(float(score_series.iloc[-1]), 1)
    
    # Calculate Warning Label for Trader
    warning_text = "STANDBY"
    warning_color = "#525252"
    
    if mode == "MACRO":
        if curr_score <= 20:
            warning_text = "DCA BUYING OPPORTUNITY"
            warning_color = "#22c55e"
        elif curr_score >= 80:
            warning_text = "DCA EXIT OPPORTUNITY"
            warning_color = "#EC4899"
        else:
            warning_text = "HOLDING PHASE"
            warning_color = "#FFFF00"
            
    elif mode == "TRADING":
        intervals_to_fetch = ["1d", "4h", "2h", "1h"]
        
        def get_score_for_inv(inv):
            if inv == interval:
                return curr_score
            d = get_crypto_data(symbol, inv)
            if not d.empty:
                s_series = calculate_trading_score(d)
                return round(float(s_series.iloc[-1]), 1)
            return 50.0

        with ThreadPoolExecutor(max_workers=4) as executor:
            res_scores = list(executor.map(get_score_for_inv, intervals_to_fetch))
        
        # Calculate best possible outcome (most extreme score from 50)
        best_score = 50.0
        max_dev = -1
        for s in res_scores:
            dev = abs(s - 50.0)
            if dev > max_dev:
                max_dev = dev
                best_score = s
                
        if best_score <= 30:
            warning_text = "INCOMING LONG"
            warning_color = "#22c55e"
        elif best_score >= 70:
            warning_text = "INCOMING SHORT"
            warning_color = "#EC4899"
        else:
            warning_text = "NEUTRAL ZONE"
            warning_color = "#FFFF00"
    
    return {
        "price": float(df['Close'].iloc[-1]),
        "change": round(get_24h_change(symbol), 2),
        "analysis": analysis_tag,
        "name": name,
        "ticker": ticker,
        "chart_dates": [int(d.timestamp() * 1000) for d in df.index],
        "chart_score": score_series.values.tolist(),
        "cycle_score": curr_score,
        "phase": "DCA IN" if curr_score <= 20 else ("HODL" if curr_score <= 79 else "DCA OUT"),
        "last_signal": LAST_TRADER_SIGNALS.get(ticker),
        "warning_text": warning_text,
        "warning_color": warning_color
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
