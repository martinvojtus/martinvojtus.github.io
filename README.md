# AI Crypto Trading Terminal

Tento repozitár obsahuje plne funkčný, produkčne pripravený **AI Crypto Trading Terminal** poháňaný umelou inteligenciou Gemini a Python/FastAPI backendom s reálnym trading a paper-trading modulom.

## Architektúra

- **Backend:** Python, FastAPI (poskytuje WebSocket pre real-time dáta, integráciu s burzami pomocou `ccxt`, On-chain dáta pomocou `web3` a analýzu trhu cez `pandas_ta`). Rozhodovací modul využíva **Google Gemini 2.5 Flash** cez knižnicu `google-genai` a vracia plne štruktúrované JSON odpovede.
- **Frontend:** Moderné, kyber-finančné tmavé používateľské rozhranie vytvorené v čistom HTML a Tailwind CSS, s interaktívnym sviečkovým grafom (`lightweight-charts`) a živým terminálom pre zobrazenie myšlienkových pochodov AI bota.

## Nastavenie prostredia

1. Premenuj alebo skopíruj súbor `.env.example` na `.env` a vyplň požadované premenné:
   ```bash
   cp .env.example .env
   ```

2. **Dôležité premenné v `.env`:**
   - `GEMINI_API_KEY`: Tvoj API kľúč od Google Gemini (nutné pre AI rozhodovanie).
   - `EXCHANGE_ID`: (napr. `binance`, `kraken`, `bybit`)
   - `TRADING_MODE`: Nastav na `PAPER` pre simulačný režim alebo `LIVE` pre skutočné obchodovanie (v `LIVE` režime musia byť vyplnené kľúče burzy).
   - `EXCHANGE_API_KEY` a `EXCHANGE_SECRET`: Tvoje API kľúče z burzy.
   - `RPC_URL`: Endpoint pre pripojenie do siete Ethereum/EVM (napr. `https://cloudflare-eth.com`).
   - `WALLET_ADDRESS`: (Voliteľné) Verejná adresa peňaženky pre zobrazenie on-chain zostatku.

## Spustenie aplikácie

Inštalácia závislostí a spustenie servera jedným príkazom z koreňového priečinka projektu:

```bash
pip install -r backend/requirements.txt && python backend/main.py
```

Po spustení bude aplikácia dostupná na adrese: `http://localhost:10000` (prípadne iný port podľa nastavenia prostredia). Frontend je priamo servovaný backendom a pripája sa na WebSocket pre živé dáta.
