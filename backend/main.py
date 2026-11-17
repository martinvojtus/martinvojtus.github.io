import os
import json
import asyncio
import logging
from datetime import datetime
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import ccxt.async_support as ccxt
from web3 import Web3
import pandas as pd
import pandas_ta as ta
from google import genai
from google.genai import types

load_dotenv()

# Setup
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

# Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EXCHANGE_ID = os.getenv("EXCHANGE_ID", "binance")
TRADING_MODE = os.getenv("TRADING_MODE", "PAPER")
RPC_URL = os.getenv("RPC_URL", "https://cloudflare-eth.com")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "") # Optional config

if GEMINI_API_KEY:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = None

# Global State
class TradingEngineState:
    def __init__(self):
        self.is_running = False
        self.paper_balance = 10000.0
        self.positions = []
        self.history = []
        self.current_price = 0.0
        self.wallet_balance = 0.0
        self.wallet_sol_balance = 0.0
        self.wallet_usdc_balance = 0.0
        self.sol_fee_reserve = 0.02
        
engine_state = TradingEngineState()
connected_websockets = []

class AIDecision(BaseModel):
    action: str = Field(description="BUY, SELL, or HOLD")
    pair: str = Field(description="Trading pair, e.g., SOL/USDC")
    amount_pct: float = Field(description="Percentage of portfolio to use (0-100)")
    stop_loss: float = Field(description="Stop loss price")
    take_profit: float = Field(description="Take profit price")
    confidence: int = Field(description="Confidence level (0-100)")
    reasoning: str = Field(description="Reasoning behind the decision")

async def broadcast_log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] [AI-CORE] {msg}"
    logger.info(log_msg)
    await broadcast_ws({"type": "log", "data": log_msg})

async def broadcast_ws(message: dict):
    disconnected = []
    for ws in connected_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_websockets.remove(ws)

async def fetch_market_data(exchange):
    try:
        ohlcv = await exchange.fetch_ohlcv('SOL/USDC', timeframe='1m', limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Indicators
        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)
        df.ta.ema(length=20, append=True)
        
        current_price = df.iloc[-1]['close']
        engine_state.current_price = current_price
        
        rsi = df.iloc[-1]['RSI_14']
        macd = df.iloc[-1]['MACD_12_26_9']
        ema = df.iloc[-1]['EMA_20']
        
        # Also return last 50 candles for the frontend chart if needed
        chart_data = df.tail(50)[['timestamp', 'close']].to_dict(orient='records')
        
        return {
            "price": current_price,
            "rsi": rsi,
            "macd": macd,
            "ema": ema,
            "chart_data": chart_data
        }
    except Exception as e:
        await broadcast_log(f"Market data fetch error: {str(e)}")
        return None

async def trading_loop():
    exchange_class = getattr(ccxt, EXCHANGE_ID)
    exchange = exchange_class({'enableRateLimit': True})
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    await broadcast_log("Bot spustený. Sledujem pár SOL/USDC...")
    
    while engine_state.is_running:
        try:
            # 1. Fetch Market Data
            market_data = await fetch_market_data(exchange)
            if not market_data:
                await asyncio.sleep(10)
                continue
                
            price = market_data["price"]
            rsi = market_data["rsi"]
            
            # 2. Fetch Wallet Data
            if WALLET_ADDRESS and w3.is_connected():
                try:
                    bal_wei = w3.eth.get_balance(WALLET_ADDRESS)
                    engine_state.wallet_balance = w3.from_wei(bal_wei, 'ether')
                except Exception:
                    pass

            await broadcast_log(f"Analyzujem SOL/USDC... Cena: {price:.2f}$, RSI: {rsi:.1f}")
            
            # 3. AI Decision
            if not ai_client:
                await broadcast_log("Gemini API Key missing. Skipping AI decision.")
            else:
                prompt = f"""
                You are a crypto scalping AI trading SOL/USDC on Solana. Current market state:
                Pair: SOL/USDC
                Price: {price}
                RSI (14): {rsi}
                MACD: {market_data['macd']}
                EMA (20): {market_data['ema']}
                
                Portfolio: {engine_state.paper_balance} USDC
                Open Positions: {len(engine_state.positions)}
                
                Rules:
                - Target micro-scalps between SOL and USDC.
                - When buying: Spend USDC to buy SOL.
                - When selling: Sell SOL for USDC.
                - Maintain mandatory SOL reserve for gas fees.
                Decide the next action (BUY, SELL, HOLD). Limit risk to max 2% per trade.
                """
                
                try:
                    response = ai_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=AIDecision,
                            temperature=0.2,
                        ),
                    )
                    
                    decision_dict = json.loads(response.text)
                    decision = AIDecision(**decision_dict)
                    
                    log_reason = f"Rozhodnutie: {decision.action} (Istota: {decision.confidence}%) - Dôvod: {decision.reasoning}"
                    await broadcast_log(log_reason)
                    
                    # 4. Execute Trade (Paper Trading)
                    if decision.action == "BUY" and len(engine_state.positions) == 0:
                        risk_amount = engine_state.paper_balance * (decision.amount_pct / 100.0)
                        if risk_amount > engine_state.paper_balance * 0.02:
                            risk_amount = engine_state.paper_balance * 0.02 # Max 2%
                            
                        if risk_amount > 0:
                            position = {
                                "id": str(datetime.now().timestamp()),
                                "pair": decision.pair,
                                "type": "LONG",
                                "entry_price": price,
                                "amount": risk_amount / price,
                                "cost": risk_amount,
                                "stop_loss": decision.stop_loss or (price * 0.98),
                                "take_profit": decision.take_profit or (price * 1.05)
                            }
                            engine_state.positions.append(position)
                            engine_state.paper_balance -= risk_amount
                            await broadcast_log(f"Otvorená pozícia BUY na {price:.2f}$. Veľkosť: {risk_amount:.2f}$")
                            
                    elif decision.action == "SELL" and len(engine_state.positions) > 0:
                        for p in list(engine_state.positions):
                            if p['pair'] == decision.pair:
                                pnl = (price - p['entry_price']) * p['amount']
                                engine_state.paper_balance += (p['cost'] + pnl)
                                engine_state.history.append({"id": p['id'], "pnl": pnl})
                                engine_state.positions.remove(p)
                                await broadcast_log(f"Zatvorená pozícia SELL na {price:.2f}$. PNL: {pnl:.2f}$")
                except Exception as ai_e:
                    await broadcast_log(f"Chyba AI modulu: {str(ai_e)}")

            # Evaluate Stop Loss / Take Profit
            for p in list(engine_state.positions):
                if price <= p['stop_loss']:
                    pnl = (price - p['entry_price']) * p['amount']
                    engine_state.paper_balance += (p['cost'] + pnl)
                    engine_state.positions.remove(p)
                    engine_state.history.append({"id": p['id'], "pnl": pnl})
                    await broadcast_log(f"STOP LOSS hit pre pozíciu. PNL: {pnl:.2f}$")
                elif price >= p['take_profit']:
                    pnl = (price - p['entry_price']) * p['amount']
                    engine_state.paper_balance += (p['cost'] + pnl)
                    engine_state.positions.remove(p)
                    engine_state.history.append({"id": p['id'], "pnl": pnl})
                    await broadcast_log(f"TAKE PROFIT hit pre pozíciu. PNL: {pnl:.2f}$")

            # Broadcast State
            total_pnl = sum([h['pnl'] for h in engine_state.history])
            
            # current pnl for open positions
            open_pnl = 0
            for p in engine_state.positions:
                open_pnl += (price - p['entry_price']) * p['amount']
                p['current_pnl'] = (price - p['entry_price']) * p['amount']

            total_balance = engine_state.paper_balance + sum([p['cost'] for p in engine_state.positions]) + open_pnl

            await broadcast_ws({
                "type": "state",
                "data": {
                    "price": price,
                    "pair": "SOL/USDC",
                    "paper_balance": engine_state.paper_balance,
                    "total_balance": total_balance,
                    "wallet_balance": float(engine_state.wallet_balance),
                    "wallet_sol_balance": float(engine_state.wallet_sol_balance),
                    "wallet_usdc_balance": float(engine_state.wallet_usdc_balance),
                    "sol_fee_reserve": float(engine_state.sol_fee_reserve),
                    "open_positions": len(engine_state.positions),
                    "total_pnl": total_pnl,
                    "open_pnl": open_pnl,
                    "positions": engine_state.positions,
                    "mode": TRADING_MODE,
                    "chart_data": market_data["chart_data"]
                }
            })
            
        except Exception as e:
            await broadcast_log(f"Chyba v trading loope: {str(e)}")
            
        await asyncio.sleep(15) # run every 15 seconds for live feel
        
    await exchange.close()
    await broadcast_log("Bot stopped.")

bot_task = None

@app.get("/")
async def serve_index():
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")
    return FileResponse(index_path)

@app.post("/bot/start")
async def start_bot():
    global bot_task
    if engine_state.is_running:
        return {"status": "already running"}
    engine_state.is_running = True
    bot_task = asyncio.create_task(trading_loop())
    return {"status": "started"}

@app.post("/bot/stop")
async def stop_bot():
    engine_state.is_running = False
    return {"status": "stopped"}

@app.post("/bot/close_all")
async def close_all():
    if len(engine_state.positions) > 0:
        price = engine_state.current_price
        for p in list(engine_state.positions):
            pnl = (price - p['entry_price']) * p['amount']
            engine_state.paper_balance += (p['cost'] + pnl)
            engine_state.history.append({"id": p['id'], "pnl": pnl})
            engine_state.positions.remove(p)
            await broadcast_log(f"Manuálne zatvorená pozícia na {price:.2f}$. PNL: {pnl:.2f}$")
    return {"status": "closed"}

@app.get("/bot/status")
async def get_status():
    return {
        "is_running": engine_state.is_running,
        "mode": TRADING_MODE
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    # Send initial state
    await websocket.send_json({
        "type": "init",
        "data": {
            "mode": TRADING_MODE,
            "is_running": engine_state.is_running
        }
    })
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
