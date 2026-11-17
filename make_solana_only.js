const fs = require('fs');
let html = fs.readFileSync('index.html', 'utf8');

// 1. Remove Ethers.js
html = html.replace(/<!-- Ethers\.js for EVM Wallets -->\s*<script src="https:\/\/cdnjs\.cloudflare\.com\/ajax\/libs\/ethers\/6\.11\.1\/ethers\.umd\.min\.js"><\/script>\n/g, '');

// 2. Remove pair toggles from Desktop header
html = html.replace(/<!-- Desktop Coin Toggle \(hidden on mobile, shown on md\+\) -->\s*<div class="hidden md:flex items-center bg-dark-card rounded-lg p-0\.5 border border-dark-border text-xs font-mono">\s*<button onclick="changePair\('BTCUSDT'\)" id="pair-btn-BTCUSDT-d" class="px-2\.5 py-1 rounded-md text-white bg-dark-cardSub font-semibold transition-all">BTC<\/button>\s*<button onclick="changePair\('ETHUSDT'\)" id="pair-btn-ETHUSDT-d" class="px-2\.5 py-1 rounded-md text-gray-400 hover:text-white transition-all">ETH<\/button>\s*<button onclick="changePair\('SOLUSDT'\)" id="pair-btn-SOLUSDT-d" class="px-2\.5 py-1 rounded-md text-gray-400 hover:text-white transition-all">SOL<\/button>\s*<\/div>/, '');

// 3. Remove pair toggles from Mobile sub-bar
html = html.replace(/<div class="flex items-center bg-dark-card rounded-lg p-0\.5 border border-dark-border text-xs font-mono flex-1">\s*<button onclick="changePair\('BTCUSDT'\)" id="pair-btn-BTCUSDT-m" class="px-2 py-0\.5 rounded-md text-white bg-dark-cardSub font-semibold transition-all flex-1 text-center text-\[11px\]">BTC<\/button>\s*<button onclick="changePair\('ETHUSDT'\)" id="pair-btn-ETHUSDT-m" class="px-2 py-0\.5 rounded-md text-gray-400 hover:text-white transition-all flex-1 text-center text-\[11px\]">ETH<\/button>\s*<button onclick="changePair\('SOLUSDT'\)" id="pair-btn-SOLUSDT-m" class="px-2 py-0\.5 rounded-md text-gray-400 hover:text-white transition-all flex-1 text-center text-\[11px\]">SOL<\/button>\s*<\/div>/, '<div class="flex-1 text-white font-bold text-xs tracking-widest pl-2">SOLANA NETWORK</div>');

// 4. Default pair to SOLUSDT
html = html.replace(/pair: 'BTCUSDT',/g, "pair: 'SOLUSDT',");
html = html.replace(/<span class="font-bold text-white font-mono text-sm" id="chart-pair-text">BTC\/USDT<\/span>/g, '<span class="font-bold text-white font-mono text-sm" id="chart-pair-text">SOL/USDT</span>');
html = html.replace(/\[FEED\] Pripojený na živý trhový stream \(BTC, ETH, SOL\)\.\.\./g, '[FEED] Pripojený na živý trhový stream (SOL)...');

// 5. Update settings modal (Live Obchod SOL/ETH -> SOL)
html = html.replace(/Live Obchod \(SOL\/ETH\)/g, 'Live Obchod (SOL)');

// 6. Remove MetaMask button from Wallet Modal
html = html.replace(/<!-- MetaMask \/ EVM -->[\s\S]*?Pripojiť<\/span>\s*<\/button>/, '');

// 7. Remove EVM execution and logic from JS
html = html.replace(/\} else \{\s*await executeEVMLiveTrade\(action, dec\);\s*\}/g, '}');

html = html.replace(/async function executeEVMLiveTrade[\s\S]*?}\s*}\s*(?=\/\/ --- POSITIONS MANAGEMENT ---)/, '');

html = html.replace(/\(Phantom, Solflare, MetaMask\)/g, '(Phantom, Solflare)');

html = html.replace(/\/\/ MetaMask[\s\S]*?hasMetaMask \? 'Pripojiť' : \(isMobile \? 'Otvoriť App' : 'Inštalovať'\);/g, '');

html = html.replace(/async function connectMetaMask[\s\S]*?}\s*}\s*(?=\n\s*async function fetchSolBalance)/, '');

html = html.replace(/} else if \(autoConnect === 'metamask'\) \{\s*window\.history\.replaceState\(\{\}, document\.title, window\.location\.pathname\);\s*setTimeout\(connectMetaMask, 500\);\s*/g, '');

html = html.replace(/function changePair[\s\S]*?fetchMarketData\(\);\s*}/, '');

// Update the algorithmic fallback to be scalping-friendly
html = html.replace(
    /if \(rsi < 35\) \{[\s\S]*?\} else \{/,
    `if (rsi < 45 && ema < price) {
                    decision = { action: "BUY", confidence: 85, reasoning: \`Rýchly scalping: RSI (\${rsi.toFixed(1)}), cena nad EMA. Cielime na 0.5% zisk.\` };
                } else if (rsi > 60 && State.positions.length > 0) {
                    decision = { action: "SELL", confidence: 80, reasoning: \`Scalp exit: RSI (\${rsi.toFixed(1)}). Zabezpečenie rýchleho zisku.\` };
                } else {`
);

// Update AI Prompt for scalping
html = html.replace(
    /Return JSON: \{"action":"BUY"\|"SELL"\|"HOLD","confidence":85,"reasoning":"short reason in slovak"\}/g,
    'You are a high-frequency scalping bot targeting Solana meme coins and SOL tokens. Target 0.5% - 1.5% micro-profits per trade. Keep risk tight. Return JSON: {"action":"BUY"|"SELL"|"HOLD","confidence":85,"reasoning":"short reason in slovak"}'
);

// Change TP/SL for aggressive scalping
html = html.replace(/sl: State\.currentPrice \* 0\.98,/g, 'sl: State.currentPrice * 0.99, // 1% SL');
html = html.replace(/tp: State\.currentPrice \* 1\.04,/g, 'tp: State.currentPrice * 1.015, // 1.5% TP');

fs.writeFileSync('index.html', html);
console.log('Solana-only scalping modifications applied successfully!');
