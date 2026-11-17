# AI Crypto Trading Terminal 🚀

Tento repozitár beží na tvojej GitHub doméne:  
👉 **[https://martinvojtus.github.io](https://martinvojtus.github.io)**

Aplikácia je kompletne navrhnutá tak, aby fungovala **100% v cloude priamo cez GitHub Pages bez nutnosti spúšťať akýkoľvek lokálny server (localhost)**.

---

## ⚡ Ako to funguje (Stačí len zadať API kľúč)

1. Otvor v prehliadači svoju doménu: **[https://martinvojtus.github.io](https://martinvojtus.github.io)**
2. V hornej lište klikni na tlačidlo **`API & SETUP`** (alebo na odznak `GEMINI SETUP`).
3. Vlož svoj bezplatný **Google Gemini API kľúč** zo [Google AI Studio](https://aistudio.google.com/app/apikey) a klikni na **`ULOŽIŤ A POUŽIŤ`**.
   - *Poznámka:* Kľúč je bezpečne uložený iba v tvojom prehliadači (`localStorage`), nikde sa neposiela a volania do Gemini idú priamo z tvojho prehliadača.
4. Klikni na zelené tlačidlo **`START BOT`**.
5. Hotovo! AI bot okamžite analyzuje trh, vyhodnocuje indikátory a zapisuje svoje úvahy a obchody v reálnom čase do terminálu.

---

## 🛠️ Čo všetko terminál obsahuje

- **Živý trhový feed z Binance (bez CORS obmedzení):** Real-time sviečky a 24h štatistiky pre BTC/USDT, ETH/USDT, SOL/USDT.
- **TradingView Lightweight Charts:** Interaktívny sviečkový graf s časovými rámcami (`1m`, `5m`, `15m`, `1h`) a vykresľovaním nákupných/predajných šípok (`AI BUY` / `AI EXIT`).
- **Technické indikátory v JS:** RSI(14), EMA(20) a MACD počítané v reálnom čase priamo v prehliadači.
- **Gemini AI Rozhodovací Modul:** Posiela trhové dáta do Google Gemini 2.5 Flash a prijíma štruktúrované JSON rozhodnutia (`BUY`, `SELL`, `HOLD`) spolu s odôvodnením a percentom istoty.
- **Kvantitatívny Fail-safe Fallback:** Ak API kľúč ešte nie je zadaný, bot automaticky beží v kvantitatívnom algoritmickom režime, takže terminal je okamžite interaktívny.
- **Paper Trading Engine & Risk Management:**
  - Virtuálny štartovací zostatok **$10,000 USDT**.
  - Pevné pravidlo **max. 2% risk na obchod**.
  - Automatický Stop Loss (2%) a Take Profit (4%) s automatickým uzavretím pri zásahu ceny.
  - Tlačidlo **`Close Now`** pre manuálne okamžité uzavretie pozície.
- **Web3 Wallet Integrácia:** Tlačidlo `Connect Wallet` načíta MetaMask / Rabby peňaženku a zobrazí reálny on-chain zostatok v ETH.
