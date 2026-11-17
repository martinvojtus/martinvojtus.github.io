# AI Crypto Trading Terminal 🚀

Tento repozitár beží na tvojej GitHub doméne:  
👉 **[https://martinvojtus.github.io](https://martinvojtus.github.io)**

Aplikácia je kompletne navrhnutá tak, aby fungovala **100% v cloude priamo cez GitHub Pages bez nutnosti spúšťať akýkoľvek lokálny server (localhost)**.

---

## ⚡ Ako to funguje

1. Otvor v prehliadači svoju doménu: **[https://martinvojtus.github.io](https://martinvojtus.github.io)**
2. V hornej lište klikni na ikonu ⚙️ (**Nastavenia**).
3. Vlož svoj bezplatný **Google Gemini API kľúč** zo [Google AI Studio](https://aistudio.google.com/app/apikey) a klikni na **`ULOŽIŤ`**.
   - *Poznámka:* Kľúč je bezpečne uložený iba v tvojom prehliadači (`localStorage`), nikde sa neposiela a volania do Gemini idú priamo z tvojho prehliadača.
4. Klikni na tlačidlo **`START`**.
5. Hotovo! AI bot okamžite analyzuje trh, vyhodnocuje indikátory a zapisuje svoje úvahy a obchody v reálnom čase do terminálu.

---

## 👛 Pripojenie Peňaženky & Reálne On-Chain Obchodovanie

V termináli môžeš prepínať medzi dvoma režimami:
1. **`PAPER TRADING` (Predvolený - Bez rizika):**
   - Simuluje obchody s virtuálnym kapitálom $10,000 USDT.
   - Ideálne na sledovanie a testovanie úspešnosti AI stratégií.

2. **`LIVE ON-CHAIN TRADING` (Reálne obchody cez peňaženku):**
   - Po kliknutí na **`👛 Peňaženka`** pripojíš svoju peňaženku:
     - 👻 **Phantom** (Solana)
     - 🔥 **Solflare** (Solana)
     - 🦊 **MetaMask / Web3** (Ethereum & EVM)
   - Prepnite v hornej lište tlačidlo z `PAPER` na `LIVE ON-CHAIN`.
   - V nastaveniach (⚙️) si vieš nastaviť veľkosť jedného obchodu (napr. `0.05 SOL`).
   - Keď AI vygeneruje nákupný alebo predajný signál, bot automaticky pripraví on-chain DEX transakciu (Solana Jupiter DEX Aggregator / Web3) a požiada tvoju peňaženku o podpis.
   - Po potvrdení sa transakcia okamžite zapíše na blockchain a terminál ti vypíše priamy odkaz na **Solscan** alebo **Etherscan**.

---

## 🛠️ Funkcie systému

- **Živý trhový feed:** Real-time sviečky a 24h štatistiky pre BTC/USDT, ETH/USDT, SOL/USDT.
- **TradingView Lightweight Charts:** Interaktívny sviečkový graf s časovými rámcami (`1m`, `5m`, `15m`) a vykresľovaním nákupných/predajných šípok (`BUY` / `EXIT`).
- **Technické indikátory v JS:** RSI(14) a EMA(20) počítané v reálnom čase priamo v prehliadači.
- **Gemini AI Rozhodovací Modul:** Posiela trhové dáta do Google Gemini 2.5 Flash a prijíma štruktúrované JSON rozhodnutia (`BUY`, `SELL`, `HOLD`) spolu s odôvodnením a percentom istoty.
- **Mobilné & Minimalistické UI:** Optimalizované pre smartfóny, tablety aj počítače.
