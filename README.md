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
   - Simuluje obchody s virtuálnym kapitálom $10,000 USDC v páre **SOL/USDC**.
   - Presné sledovanie P&L, dynamické Stop-Loss a Take-Profit úrovne s vizuálnym indikátorom.
   - Ideálne na sledovanie a testovanie úspešnosti AI stratégií bez rizika.

2. **`LIVE ON-CHAIN TRADING` (Reálne mikroobchody v páre SOL/USDC):**
   - Po kliknutí na **`👛 Peňaženka`** pripojíš svoju peňaženku:
     - 👻 **Phantom** (Solana)
     - 🔥 **Solflare** (Solana)
   - **Zobrazenie zostatkov:** Terminál zobrazuje zostatok **SOL** aj **USDC** v reálnom čase.
   - **Ochrana rezervy na poplatky (Gas fees):** Terminál striktne chráni minimálnu rezervu SOL na poplatky (predvolene `0.02 SOL`, nastaviteľné v ⚙️). Predaj SOL za USDC nikdy nesiahne do tejto rezervy, aby peňaženka nikdy neostala zablokovaná bez plynu na transakcie.
   - **Mikroobchody v páre SOL/USDC:**
     - Pri signáli `BUY`: bot nakupuje SOL za USDC cez Jupiter DEX Aggregator.
     - Pri signáli `SELL`: bot realizuje zisk predajom voľného SOL do USDC so zachovaním rezervy na poplatky.
     - K dispozícii je aj funkcia **Rýchly mikro-swap** priamo v peňaženke pre jednoduchú konverziu medzi SOL a USDC.
   - Po každom obchode sa transakcia okamžite zapíše na blockchain a terminál ti vypíše priamy odkaz na **Solscan**.

---

## 🛠️ Funkcie systému

- **Živý Binance WebSocket Stream:** Sub-sekundové real-time sviečky a pulzujúci cenový feed pre Solana USDC páry (`SOL/USDC`, `JUP/USDC`, `RAY/USDC`, `WIF/USDC`, `BONK/USDC`).
- **Ochrana dostatku SOL na fees:** Automatická kontrola a zachovanie minimálnej rezervy SOL na poplatky siete pred každým obchodom.
- **Duálne zobrazenie SOL & USDC:** Okamžitý prehľad o voľných aj rezervovaných prostriedkoch na peňaženke.
- **TradingView Lightweight Charts:** Interaktívny sviečkový graf s časovými rámcami (`1m`, `5m`, `15m`), vykresľovaním trendových kriviek **EMA(9)** a **EMA(21)** priamo v grafe a nákupnými/predajnými signálmi (`BUY` / `EXIT`).
- **Technické indikátory v JS:** RSI(14), EMA(9), EMA(21) a vyhodnocovanie trendových crossoverov počítané v reálnom čase priamo v prehliadači.
- **Web Audio Sound Effects:** Zvukové notifikácie pre vstupy do obchodov, úspešné Take-Profit obchody a Stop-Loss výstupy (s možnosťou stíšenia 🔊/🔇).
- **Vizuálny PnL & SL/TP Tracker:** Interaktívny farebný progress bar pozícií ukazujúci presnú vzdialenosť ceny od Stop-Lossu a Take-Profitu.
- **Export histórie do CSV:** Možnosť jedným kliknutím stiahnuť kompletnú históriu obchodov v CSV formáte.
- **Gemini AI Rozhodovací Modul:** Posiela trhové dáta do Google Gemini 2.5 Flash a prijíma štruktúrované JSON rozhodnutia (`BUY`, `SELL`, `HOLD`) spolu s odôvodnením a percentom istoty.
- **Mobilné & Minimalistické UI:** Optimalizované pre smartfóny, tablety aj počítače s okamžitým prepínaním tokenov v lište.
