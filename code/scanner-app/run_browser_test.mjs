// Browser-based APP pipeline test using Playwright
import { chromium } from 'playwright';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT = path.resolve(__dirname, '../..');
const STRESS = path.join(PROJECT, 'images/stress_test');

const CATEGORIES = {
    'illumination': 1,
    'geometric_rotation': 1,
    'geometric_perspective': 1,
    'linear_perspective': 1,
    'linear_shear': 1,
    'linear_combo': 1,
    'damage_noise': 1,
    'ink_data_pollution': 1,
    'ink_corner_destruction': 1,
    'multi_qr': 2,
    'barcode_ink': 1,
    'barcode_scratches': 1,
    'barcode_geometric': 1,
};

// Start HTTP server from project root
const server = http.createServer((req, res) => {
    const urlPath = req.url.split('?')[0];
    const filePath = path.join(PROJECT, urlPath === '/' ? 'code/scanner-app/test_runner.html' : urlPath);
    try {
        const data = fs.readFileSync(filePath);
        const ext = path.extname(filePath);
        const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
            '.png': 'image/png', '.jpg': 'image/jpeg', '.json': 'application/json',
            '.mjs': 'text/javascript' }[ext] || 'application/octet-stream';
        res.writeHead(200, { 'Content-Type': mime, 'Access-Control-Allow-Origin': '*' });
        res.end(data);
    } catch {
        res.writeHead(404);
        res.end('Not found');
    }
});

await new Promise(resolve => server.listen(8765, resolve));
console.log('Server on http://localhost:8765');

const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe'
});
const page = await browser.newPage();
page.on('console', msg => {
    const text = msg.text();
    if (!text.includes('Test page ready') && !text.includes('Fast test ready'))
        process.stdout.write('.');
});

await page.goto('http://localhost:8765/code/scanner-app/test_runner_fast.html', { waitUntil: 'networkidle' });
console.log('\nPage loaded. Starting tests...\n');

console.log('='.repeat(70));
console.log('  APP BROWSER PIPELINE TEST (BarcodeDetector + jsQR, no html5-qrcode)');
console.log('='.repeat(70));

let grandTotal = 0, grandPass = 0;
const results = {};

for (const [cat, expected] of Object.entries(CATEGORIES)) {
    const dir = path.join(STRESS, cat);
    if (!fs.existsSync(dir)) { console.log(`  SKIP ${cat}: not found`); continue; }
    const files = fs.readdirSync(dir).filter(f => f.endsWith('.png') || f.endsWith('.jpg'));
    // Sample up to 110
    const sample = files.slice(0, 110);
    let pass = 0, fail = 0, errs = 0;

    process.stdout.write(`  ${cat.padEnd(35)} `);
    for (const f of sample) {
        const url = `/images/stress_test/${cat}/${f}`;
        try {
            const count = await page.evaluate(async (imgUrl) => {
                return await window.decodeOne(imgUrl);
            }, url);
            if (count >= expected) pass++;
            else if (count >= 0) fail++;
            else errs++;
        } catch (e) { errs++; }
    }
    const rate = (pass / sample.length * 100).toFixed(1);
    const bar = '#'.repeat(Math.round(pass / sample.length * 30));
    const line = '\r  ' + cat.padEnd(35) + ' ' + String(pass).padStart(4) + '/' + String(sample.length).padStart(4) + '  ' + rate + '% ' + bar + '\n';
    process.stdout.write(line);
    results[cat] = { pass, total: sample.length, rate: parseFloat(rate), fail, errs };
    grandTotal += sample.length;
    grandPass += pass;
}

console.log('-'.repeat(70));
console.log('  BROWSER APP TOTAL: ' + grandPass + '/' + grandTotal + '  ' + (grandPass/grandTotal*100).toFixed(1) + '%');
console.log();

// Comparison table
console.log('  COMPARISON: pyzbar vs BROWSER APP (real pipeline)');
console.log('  ' + '-'.repeat(65));
console.log('  ' + 'Category'.padEnd(35) + '  pyzbar  BROWSER   Delta');
console.log('  ' + '-'.repeat(65));

const pyzbarResults = {
    'illumination': 110, 'geometric_rotation': 102, 'geometric_perspective': 86,
    'linear_perspective': 110, 'linear_shear': 110, 'linear_combo': 110,
    'damage_noise': 68, 'ink_data_pollution': 14, 'ink_corner_destruction': 57,
    'multi_qr': 28, 'barcode_ink': 110, 'barcode_scratches': 99, 'barcode_geometric': 13,
};
let pp = 0, bp = 0;
for (const [cat, r] of Object.entries(results)) {
    const p = pyzbarResults[cat] || 0;
    const delta = r.pass - p;
    const sign = delta >= 0 ? '+' : '';
    console.log('  ' + cat.padEnd(35) + ' ' + String(p).padStart(3) + '/' + String(r.total).padStart(3) + ' ' + String(r.pass).padStart(3) + '/' + String(r.total).padStart(3) + ' ' + sign + delta);
    pp += p; bp += r.pass;
}
console.log('  ' + '-'.repeat(65));
const totalSign = bp - pp >= 0 ? '+' : '';
console.log('  ' + 'TOTAL'.padEnd(35) + ' ' + String(pp).padStart(3) + '/' + grandTotal + ' ' + String(bp).padStart(3) + '/' + grandTotal + ' ' + totalSign + (bp - pp));

await browser.close();
server.close();
process.exit(0);
