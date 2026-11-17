const fs = require('fs');
let html = fs.readFileSync('index.html', 'utf8');

// Outer cards
html = html.replace(/p-5 rounded-\[32px\]/g, 'p-3 rounded-[24px]');

// WRAPPERS: theme-segmented-box, coin-toggle-box, macro-buttons
const wrappers = ['theme-segmented-box', 'coin-toggle-box', 'macro-buttons'];
wrappers.forEach(id => {
    html = html.replace(new RegExp(`id="${id}" class="([^"]*)"`), (match, cls) => {
        let newCls = cls.replace(/\bh-10\b/g, '').replace(/\bh-8\b/g, '').replace(/\bp-1\b/g, '').replace(/\bp-0\.5\b/g, '').replace(/\brounded-xl\b/g, '').replace(/\brounded-lg\b/g, '').replace(/\s+/g, ' ').trim();
        return `id="${id}" class="${newCls} h-8 p-1 rounded-lg"`;
    });
});

// INNER BUTTONS HTML
const btnIds = ['theme-btn-solar', 'theme-btn-light', 'theme-btn-dark', 'coin-btn-BTC', 'coin-btn-ZEC', 'btn-1Y', 'btn-2Y', 'btn-5Y'];
btnIds.forEach(id => {
    html = html.replace(new RegExp(`id="${id}"([^>]*?)class="([^"]*?)"`, 'g'), (match, attrs, cls) => {
        let newCls = cls.replace(/\bh-full\b/g, '').replace(/\bh-10\b/g, '').replace(/\bh-8\b/g, '').replace(/\bpx-4\b/g, '').replace(/\bpx-3\b/g, '').replace(/\brounded-xl\b/g, '').replace(/\brounded-lg\b/g, '').replace(/\brounded-md\b/g, '').replace(/\brounded\b/g, '').replace(/\s+/g, ' ').trim();
        return `id="${id}"${attrs}class="${newCls} h-full px-3 rounded"`;
    });
});

// INNER BUTTONS JS
html = html.replace(/"h-full px-4 rounded-lg /g, '"h-full px-3 rounded ');
html = html.replace(/"h-10 px-4 rounded-xl /g, '"h-full px-3 rounded ');
html = html.replace(/"h-full px-3 rounded-md /g, '"h-full px-3 rounded ');
const jsBtnRegexes = [
    /"h-full px-\d+ rounded-[a-z]+ text-white/g,
    /"h-full px-\d+ rounded-[a-z]+ text-neutral-900/g,
    /"h-full px-\d+ rounded-[a-z]+ text-neutral-400/g,
    /"h-full px-\d+ rounded-[a-z]+ text-neutral-500/g,
];
jsBtnRegexes.forEach(reg => {
    html = html.replace(reg, (m) => m.replace(/px-\d+/, 'px-3').replace(/rounded-[a-z]+/, 'rounded'));
});

// BADGES HTML & JS
// 24H Badge
html = html.replace(/px-4 h-10 rounded-xl font-semibold flex/g, 'px-3 h-8 rounded-lg font-semibold flex');
html = html.replace(/px-3 h-8 rounded-xl font-semibold flex/g, 'px-3 h-8 rounded-lg font-semibold flex');
// Theme Badge right
html = html.replace(/px-4 h-10 flex items-center rounded-xl bg-black\/5/g, 'px-3 h-8 flex items-center rounded-lg bg-black/5');
html = html.replace(/px-3 h-8 flex items-center rounded-xl bg-black\/5/g, 'px-3 h-8 flex items-center rounded-lg bg-black/5');
// Indicator Badge
html = html.replace(/px-4 h-10 flex items-center rounded-xl bg-black\/5/g, 'px-3 h-8 flex items-center rounded-lg bg-black/5');
html = html.replace(/px-3 h-8 flex items-center rounded-xl bg-black\/5/g, 'px-3 h-8 flex items-center rounded-lg bg-black/5');

// Refresh Button
html = html.replace(/w-10 h-10 flex items-center justify-center rounded-xl/g, 'w-8 h-8 flex items-center justify-center rounded-lg');
html = html.replace(/w-8 h-8 flex items-center justify-center rounded-xl/g, 'w-8 h-8 flex items-center justify-center rounded-lg');

// 24H Wrapper
html = html.replace(/gap-2 h-10 whitespace-nowrap/g, 'gap-1.5 h-8 whitespace-nowrap');
html = html.replace(/gap-1\.5 h-10 whitespace-nowrap/g, 'gap-1.5 h-8 whitespace-nowrap');

// Chart Header
html = html.replace(/h-10 gap-2">/g, 'h-8 gap-1.5">');

// Dynamic Score
html = html.replace(/w-\[4\.5rem\] h-10 px-1 rounded-xl/g, 'w-16 h-8 px-1 rounded-lg');
html = html.replace(/w-16 h-10 px-1 rounded-xl/g, 'w-16 h-8 px-1 rounded-lg');
html = html.replace(/w-16 h-8 px-1 rounded-xl/g, 'w-16 h-8 px-1 rounded-lg');
html = html.replace(/w-\[4\.5rem\] h-8 px-1 rounded-xl/g, 'w-16 h-8 px-1 rounded-lg');
html = html.replace(/w-\[4\.5rem\] h-8 px-1 rounded-lg/g, 'w-16 h-8 px-1 rounded-lg');

// Dynamic Title
html = html.replace(/px-4 h-10 flex justify-center items-center rounded-xl/g, 'px-3 h-8 flex justify-center items-center rounded-lg');
html = html.replace(/px-3 h-8 flex justify-center items-center rounded-xl/g, 'px-3 h-8 flex justify-center items-center rounded-lg');
html = html.replace(/w-14 justify-center"/g, 'w-12 justify-center"');

// Phase Badge (HODL)
html = html.replace(/px-4 h-10 w-\[5\.5rem\] flex items-center justify-center rounded-xl/g, 'px-3 h-8 w-20 flex items-center justify-center rounded-lg');
html = html.replace(/px-4 h-10 w-\[5rem\] flex items-center justify-center rounded-xl/g, 'px-3 h-8 w-20 flex items-center justify-center rounded-lg');
html = html.replace(/px-4 h-10 flex items-center justify-center rounded-xl/g, 'px-3 h-8 flex items-center justify-center rounded-lg');
html = html.replace(/w-\[5rem\]/g, 'w-20');
html = html.replace(/w-\[5\.5rem\]/g, 'w-20');
// In JS phase badge
html = html.replace(/px-4 h-10 flex items-center justify-center rounded-lg/g, 'px-3 h-8 flex items-center justify-center rounded-lg');
html = html.replace(/px-3 h-8 flex items-center justify-center rounded-xl/g, 'px-3 h-8 flex items-center justify-center rounded-lg');

// Score large
html = html.replace(/w-\[5\.5rem\] flex justify-end"/g, 'w-20 flex justify-end"');
html = html.replace(/w-\[5rem\] flex justify-end"/g, 'w-20 flex justify-end"');

// Theme icon box
html = html.replace(/w-10 h-10 rounded-xl bg-gradient/g, 'w-8 h-8 rounded-lg bg-gradient');

fs.writeFileSync('index.html', html);
