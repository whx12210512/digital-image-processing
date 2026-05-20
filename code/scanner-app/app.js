/**
 * Barcode/QR Code Scanner App
 * Digital Image Processing Course Project
 * Southern University of Science and Technology (SUSTech), 2026
 */

// ============ State ============
const state = {
    scanner: null,
    isScanning: false,
    scanFormat: 'all',       // 'all' | 'qr' | 'barcode'
    facingMode: 'environment',
    soundEnabled: true,
    autoRedirect: true,
    cameraResults: [],
    history: [],
    currentResult: null,
};

// ============ Constants ============
const QR_FORMATS = [Html5QrcodeScanType.SCAN_TYPE_CAMERA];
const BARCODE_FORMATS = [
    'ean_13', 'ean_8', 'upc_a', 'upc_e',
    'code_128', 'code_39', 'code_93',
    'codabar', 'itf', 'rss_14', 'rss_expanded',
];

// ============ Stress Test Gallery — one sample per category (26 types) ============
const TEST_IMAGES = [
    // QR geometric distortions (6)
    { src: 'test_images/stress_test/geometric_perspective_perspective_0000.png', label: 'QR 透视畸变' },
    { src: 'test_images/stress_test/geometric_rotation_rotation_0000_a022.png', label: 'QR 旋转变换' },
    { src: 'test_images/stress_test/geometric_curved_curved_combo_0008.png', label: 'QR 柱面/波纹' },
    { src: 'test_images/stress_test/linear_perspective_linear_persp_0000.png', label: 'QR 线性透视' },
    { src: 'test_images/stress_test/linear_shear_linear_shear_0000.png', label: 'QR 线性剪切' },
    { src: 'test_images/stress_test/linear_combo_linear_combo_0000.png', label: 'QR 复合几何' },
    // QR image quality flaws (4)
    { src: 'test_images/stress_test/flaw_motion_blur_motionblur_0000_l05_a012.png', label: 'QR 运动模糊' },
    { src: 'test_images/stress_test/flaw_highlight_highlight_0000.png', label: 'QR 镜面反光' },
    { src: 'test_images/stress_test/flaw_low_contrast_lowcontrast_0000_m083_p227.png', label: 'QR 低对比度' },
    { src: 'test_images/stress_test/illumination_illumination_0000.png', label: 'QR 光照不均' },
    // QR physical damage (4)
    { src: 'test_images/stress_test/damage_noise_damage_0000.png', label: 'QR 物理污损' },
    { src: 'test_images/stress_test/ink_corner_destruction_corner_dual_0001.png', label: 'QR 角部墨迹' },
    { src: 'test_images/stress_test/ink_data_pollution_data_pollution_0000_cov08.png', label: 'QR 数据区污染' },
    { src: 'test_images/stress_test/edge_quiet_zone_qz_0000_bc.png', label: 'QR 静区侵犯' },
    { src: 'test_images/stress_test/edge_tear_tear_0000_bc.png', label: 'QR 撕裂碎片' },
    // Liquid stains (3)
    { src: 'test_images/stress_test/liquid_blue_ink_blueink_0000.png', label: 'QR 蓝色墨水' },
    { src: 'test_images/stress_test/liquid_coffee_coffee_0000.png', label: 'QR 咖啡污渍' },
    { src: 'test_images/stress_test/liquid_water_drops_waterdrop_0000.png', label: 'QR 水滴折射' },
    // Barcode stress (7)
    { src: 'test_images/stress_test/barcode_geometric_barcode_geo_combo_0002_CODE128.png', label: '条码 几何畸变' },
    { src: 'test_images/stress_test/barcode_ink_barcode_ink_fatal_0000_EAN8.png', label: '条码 墨水污染' },
    { src: 'test_images/stress_test/barcode_scratches_barcode_scratches_0000_EAN13.png', label: '条码 物理划痕' },
    { src: 'test_images/stress_test/barcode_motion_blur_barcode_mblur_0000_CODE128.png', label: '条码 运动模糊' },
    { src: 'test_images/stress_test/barcode_highlight_barcode_highlight_0000_CODE39.png', label: '条码 镜面高光' },
    { src: 'test_images/stress_test/barcode_lowcontrast_barcode_lowcontrast_0000_CODE128.png', label: '条码 低对比度' },
    { src: 'test_images/stress_test/barcode_cylinder_barcode_cylinder_0000_CODE128.png', label: '条码 柱面弯曲' },
    // Multi-code (1)
    { src: 'test_images/stress_test/multi_qr_multi_qr_0000.jpg', label: '多码同框' },
];

// ============ Splash Screen ============
window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        document.getElementById('splash').classList.add('hide');
        document.getElementById('app').style.display = 'flex';
        init();
    }, 1500);
});

// ============ Initialization ============
function init() {
    loadHistory();
    renderGallery();
    setupTabs();
    setupButtons();
    setupFileInputs();
    setupSettings();
}

// ============ Tab Navigation ============
function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const tabId = 'tab-' + btn.dataset.tab;
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            if (btn.dataset.tab === 'history') renderHistory();
            if (btn.dataset.tab === 'gallery') renderGallery();
        });
    });
}

// ============ Buttons ============
function setupButtons() {
    document.getElementById('btnStartScan').addEventListener('click', startScan);
    document.getElementById('btnStopScan').addEventListener('click', stopScan);
    document.getElementById('btnUpload').addEventListener('click', () => {
        document.getElementById('fileInput').click();
    });
    document.getElementById('btnCloseResult').addEventListener('click', () => {
        document.getElementById('resultCard').style.display = 'none';
    });
    document.getElementById('btnCopy').addEventListener('click', copyResult);
    document.getElementById('btnOpenUrl').addEventListener('click', openResultUrl);
    document.getElementById('btnSettings').addEventListener('click', openSettings);
    document.getElementById('btnCloseSettings').addEventListener('click', closeSettings);
    document.getElementById('btnClearHistory').addEventListener('click', clearHistory);
    document.getElementById('btnGalleryUpload').addEventListener('click', () => {
        document.getElementById('galleryFileInput').click();
    });

    // Settings modal backdrop
    document.querySelector('#settingsModal .modal-backdrop').addEventListener('click', closeSettings);
}

// ============ File Inputs ============
function setupFileInputs() {
    const fileInput = document.getElementById('fileInput');
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            scanImageFile(e.target.files[0], 'resultCard', 'resultType', 'resultContent', 'resultConfidence');
            fileInput.value = '';
        }
    });

    const galleryInput = document.getElementById('galleryFileInput');
    galleryInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            scanImageFile(e.target.files[0], 'galleryResultCard', null, null, null, true);
            galleryInput.value = '';
        }
    });
}

// ============ Camera Scanner ============
async function startScan() {
    try {
        document.getElementById('scanPlaceholder').style.display = 'none';
        document.getElementById('scanOverlay').style.display = 'flex';
        document.getElementById('btnStartScan').style.display = 'none';
        document.getElementById('btnStopScan').style.display = 'flex';

        const formatsToSupport = getScanFormats();
        const config = {
            fps: 10,
            qrbox: { width: 250, height: 250 },
            aspectRatio: 1,
            formatsToSupport: formatsToSupport,
        };

        // Configure based on scan format
        if (state.scanFormat === 'barcode') {
            config.qrbox = { width: 300, height: 150 };
        }

        state.cameraResults = [];
        state.scanner = new Html5Qrcode('reader');
        state.isScanning = true;

        await state.scanner.start(
            { facingMode: state.facingMode },
            config,
            onScanSuccess,
            onScanFailure
        );
    } catch (err) {
        console.error('Camera start error:', err);
        showToast('无法打开摄像头: ' + (err.message || '权限不足'));
        resetScanUI();
    }
}

function getScanFormats() {
    switch (state.scanFormat) {
        case 'qr':
            return [{ format: 'qr_code' }];
        case 'barcode':
            return BARCODE_FORMATS.map(f => ({ format: f }));
        case 'all':
        default:
            return [
                { format: 'qr_code' },
                ...BARCODE_FORMATS.map(f => ({ format: f })),
            ];
    }
}

function onScanSuccess(decodedText, decodedResult) {
    if (!state.isScanning) return;

    const formatName = decodedResult.result.format?.formatName || 'unknown';
    const type = formatName === 'qr_code' ? 'QR Code' : 'Barcode';

    // Skip duplicates during this scan session
    if (state.cameraResults.some(r => r.text === decodedText)) return;

    if (state.soundEnabled) playBeep();

    state.cameraResults.push({ text: decodedText, type: type });
    addToHistory(decodedText, type);

    const card = document.getElementById('resultCard');
    card.style.display = 'block';

    if (state.cameraResults.length === 1) {
        displayResult(decodedText, type, 'resultCard', 'resultType', 'resultContent', 'resultConfidence');
        showToast('扫描到 1 个, 继续扫描中...');
    } else {
        card.innerHTML = buildMultiResultHtml(state.cameraResults);
        showToast(`扫描到 ${state.cameraResults.length} 个结果`);
    }
}

function onScanFailure(error) {
    // Scanning failures are normal (no barcode in view) — silent
}

async function stopScan() {
    if (state.scanner && state.isScanning) {
        try {
            await state.scanner.stop();
            state.scanner.clear();
        } catch (err) {
            console.warn('Scanner stop error:', err);
        }
        state.isScanning = false;
    }

    if (state.cameraResults.length === 1 && state.autoRedirect && isUrl(state.cameraResults[0].text)) {
        showToast('检测到链接，即将跳转...');
        setTimeout(() => window.open(state.cameraResults[0].text, '_blank'), 1200);
    }

    resetScanUI();
}

function resetScanUI() {
    document.getElementById('scanOverlay').style.display = 'none';
    document.getElementById('scanPlaceholder').style.display = 'flex';
    document.getElementById('btnStartScan').style.display = 'flex';
    document.getElementById('btnStopScan').style.display = 'none';
}

// ============ Image File Scanner ============
async function scanImageFile(file, cardId, typeId, contentId, confidenceId, isGallery = false) {
    showToast('正在识别...');

    try {
        const results = await decodeImageFile(file, state.scanFormat);

        if (results.length === 0) {
            showToast('未识别到条码/二维码');
            return;
        }

        const card = document.getElementById(cardId);
        card.style.display = 'block';

        if (isGallery) {
            card.innerHTML = buildMultiResultHtml(results);
        } else if (results.length === 1) {
            const r = results[0];
            document.getElementById(typeId).textContent = r.type;
            document.getElementById(typeId).className = 'badge ' + (r.type === 'QR Code' ? '' : 'barcode');
            document.getElementById(contentId).textContent = r.text;
            document.getElementById(confidenceId).textContent = r.confidence || '';
            document.getElementById('btnOpenUrl').style.display = isUrl(r.text) ? 'flex' : 'none';
            state.currentResult = r.text;
        } else {
            card.innerHTML = buildMultiResultHtml(results);
        }

        for (const r of results) {
            addToHistory(r.text, r.type);
        }
        if (state.soundEnabled) playBeep();

        if (results.length === 1 && state.autoRedirect && !isGallery && isUrl(results[0].text)) {
            showToast('检测到链接，即将跳转...');
            setTimeout(() => window.open(results[0].text, '_blank'), 1200);
        }
    } catch (err) {
        console.error('Image scan error:', err);
        showToast('识别失败: ' + err.message);
    }
}

function buildMultiResultHtml(results) {
    return `
        <div class="result-header">
            <span class="badge" style="background:#1a73e8;">${results.length} 个结果</span>
            <button onclick="this.parentElement.parentElement.style.display='none'" class="icon-btn-sm">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
        </div>
        ${results.map((r, i) => `
            <div class="multi-result-item">
                <div class="mri-header">
                    <span class="badge ${r.type === 'QR Code' ? '' : 'barcode'}">${r.type}</span>
                    <span class="mri-index">#${i + 1}</span>
                </div>
                <div class="result-content" style="font-size:15px;font-family:monospace;">${escapeHtml(r.text)}</div>
                <div class="result-actions">
                    <button onclick="event.stopPropagation();navigator.clipboard.writeText('${escapeHtml(r.text).replace(/'/g, "\\'")}');showToast('已复制')" class="btn-sm">复制</button>
                    ${isUrl(r.text) ? `<button onclick="event.stopPropagation();window.open('${escapeHtml(r.text)}','_blank')" class="btn-sm">打开链接</button>` : ''}
                </div>
            </div>
        `).join('')}
    `;
}

function loadImage(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error('Image load error'));
            img.src = reader.result;
        };
        reader.onerror = () => reject(new Error('File read error'));
        reader.readAsDataURL(file);
    });
}

function blankRegion(data, w, h, location) {
    const margin = 10;
    const minX = Math.max(0, Math.floor(Math.min(
        location.topLeftCorner.x, location.bottomLeftCorner.x)) - margin);
    const minY = Math.max(0, Math.floor(Math.min(
        location.topLeftCorner.y, location.topRightCorner.y)) - margin);
    const maxX = Math.min(w, Math.ceil(Math.max(
        location.topRightCorner.x, location.bottomRightCorner.x)) + margin);
    const maxY = Math.min(h, Math.ceil(Math.max(
        location.bottomLeftCorner.y, location.bottomRightCorner.y)) + margin);
    for (let y = minY; y < maxY; y++) {
        for (let x = minX; x < maxX; x++) {
            const idx = (y * w + x) * 4;
            data[idx] = 255;
            data[idx + 1] = 255;
            data[idx + 2] = 255;
            data[idx + 3] = 255;
        }
    }
}

function grayscaleEnhance(imageData) {
    const out = new Uint8ClampedArray(imageData.data.length);
    let minVal = 255, maxVal = 0;
    for (let i = 0; i < imageData.data.length; i += 4) {
        const g = Math.round(imageData.data[i] * 0.299 +
                             imageData.data[i + 1] * 0.587 +
                             imageData.data[i + 2] * 0.114);
        out[i] = out[i + 1] = out[i + 2] = g;
        out[i + 3] = 255;
        if (g < minVal) minVal = g;
        if (g > maxVal) maxVal = g;
    }
    const range = maxVal - minVal || 1;
    for (let i = 0; i < out.length; i += 4) {
        const stretched = Math.round(((out[i] - minVal) / range) * 255);
        out[i] = out[i + 1] = out[i + 2] = stretched;
    }
    return { data: out, width: imageData.width, height: imageData.height };
}

// Crash-safe jsQR wrapper — never use 'attemptBoth' because it crashes
// on white-border images (inverted all-white → all-black → jsQR binarizer fails).
function safeJsQR(data, w, h, opts) {
    // Only use 'dontInvert' — any inversion we need is done manually
    try { return jsQR(data, w, h, { inversionAttempts: 'dontInvert' }); }
    catch { return null; }
}

function scanQrIterative(pixelData, w, h, label, maxIter) {
    const out = [];
    const data = new Uint8ClampedArray(pixelData);
    while (maxIter-- > 0) {
        const qrCode = safeJsQR(data, w, h, { inversionAttempts: 'dontInvert' });
        if (!qrCode || !qrCode.data) break;
        out.push({ text: qrCode.data, type: 'QR Code', confidence: label });
        blankRegion(data, w, h, qrCode.location);
    }
    return out;
}

// Scan regions of the image independently (fallback for when full-image scan gives 0)
async function scanRegions(canvas, w, h) {
    const results = [];
    // Split into 2x2 grid and scan each quadrant
    const cols = 2;
    const rows = 2;
    const rw = Math.floor(w / cols);
    const rh = Math.floor(h / rows);
    for (let i = 0; i < (cols * rows); i++) {
        const cx = (i % cols) * rw;
        const cy = Math.floor(i / cols) * rh;
        const rc = document.createElement('canvas');
        rc.width = rw; rc.height = rh;
        const rctx = rc.getContext('2d');
        rctx.drawImage(canvas, cx, cy, rw, rh, 0, 0, rw, rh);
        const idata = rctx.getImageData(0, 0, rw, rh);
        const enhanced = grayscaleEnhance(idata);
        for (const r of scanQrIterative(enhanced.data, rw, rh, 'jsQR(reg)', 5)) {
            if (!results.some(m => m.text === r.text)) results.push(r);
        }
    }
    return results;
}

async function decodeImageFile(file, scanFormat) {
    const img = await loadImage(file);
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const w = imageData.width;
    const h = imageData.height;
    const wantQr = scanFormat === 'all' || scanFormat === 'qr';
    const wantBarcode = scanFormat === 'all' || scanFormat === 'barcode';
    const merged = [];

    // ====== BarcodeDetector: 3-level fallback ======
    if ((wantQr || wantBarcode) && 'BarcodeDetector' in window) {
        let detected = [];
        // Level 1: all requested formats
        try {
            const fmts = [];
            if (wantQr) fmts.push('qr_code');
            if (wantBarcode) fmts.push('ean_13','ean_8','upc_a','upc_e','code_128','code_39','code_93','codabar','itf');
            detected = await new BarcodeDetector({ formats: fmts }).detect(canvas);
        } catch (e1) {
            // Level 2: validate with getSupportedFormats
            try {
                const sup = await BarcodeDetector.getSupportedFormats();
                const fmts = [];
                if (wantQr && sup.includes('qr_code')) fmts.push('qr_code');
                if (wantBarcode) {
                    for (const f of ['ean_13','ean_8','upc_a','upc_e','code_128','code_39','code_93','codabar','itf']) {
                        if (sup.includes(f)) fmts.push(f);
                    }
                }
                if (fmts.length > 0) detected = await new BarcodeDetector({ formats: fmts }).detect(canvas);
            } catch (e2) {
                // Level 3: qr_code only (most widely supported)
                try {
                    if (wantQr) detected = await new BarcodeDetector({ formats: ['qr_code'] }).detect(canvas);
                } catch (e3) { /* all failed */ }
            }
        }
        for (const b of detected) {
            const isQr = b.format === 'qr_code' || b.format === 'QR Code';
            merged.push({ text: b.rawValue, type: isQr ? 'QR Code' : 'Barcode',
                          confidence: 'BarcodeDetector ✓' });
        }
    }

    // ====== jsQR crusafe passes (no attemptBoth — we handle inversion manually) ======
    if (wantQr) {
        const enhanced = grayscaleEnhance(imageData);

        // Normal enhanced
        insertUnique(merged, scanQrIterative(enhanced.data, w, h, 'jsQR ✓', 25));

        // Raw colour
        insertUnique(merged, scanQrIterative(imageData.data, w, h, 'jsQR (raw)', 25));

        // Inverted enhanced
        insertUnique(merged, scanQrIterative(inverted(enhanced.data), w, h, 'jsQR (inv)', 15));

        // Inverted raw
        insertUnique(merged, scanQrIterative(inverted(imageData.data), w, h, 'jsQR (raw inv)', 15));
    }

    // ====== Speckle removal: morphological opening to clear 1-4px ink dots ======
    if (wantQr) {
        try {
            const specCanvas = document.createElement('canvas');
            specCanvas.width = w; specCanvas.height = h;
            const specCtx = specCanvas.getContext('2d');
            specCtx.putImageData(imageData, 0, 0);
            // Get pixel data, do opening (erode->dilate) manually
            const specData = specCtx.getImageData(0, 0, w, h);
            const gray = new Uint8ClampedArray(w * h);
            for (let i = 0; i < specData.data.length; i += 4) {
                gray[i >> 2] = Math.round(specData.data[i] * 0.299 + specData.data[i + 1] * 0.587 + specData.data[i + 2] * 0.114);
            }
            // Simple binary threshold
            const binary = new Uint8ClampedArray(w * h);
            for (let i = 0; i < gray.length; i++) binary[i] = gray[i] < 128 ? 0 : 255;
            // Erode: if any neighbor is white, become white (remove small black dots)
            const eroded = new Uint8ClampedArray(w * h);
            for (let y = 1; y < h - 1; y++) {
                for (let x = 1; x < w - 1; x++) {
                    const idx = y * w + x;
                    if (binary[idx] === 0) {
                        let hasWhite = false;
                        for (let dy = -1; dy <= 1; dy++)
                            for (let dx = -1; dx <= 1; dx++)
                                if (binary[(y + dy) * w + (x + dx)] === 255) hasWhite = true;
                        eroded[idx] = hasWhite ? 255 : 0;
                    } else eroded[idx] = 255;
                }
            }
            // Dilate: if any neighbor is black, become black (restore module edges)
            const dilated = new Uint8ClampedArray(w * h);
            for (let y = 1; y < h - 1; y++) {
                for (let x = 1; x < w - 1; x++) {
                    const idx = y * w + x;
                    if (eroded[idx] === 255) {
                        let hasBlack = false;
                        for (let dy = -1; dy <= 1; dy++)
                            for (let dx = -1; dx <= 1; dx++)
                                if (eroded[(y + dy) * w + (x + dx)] === 0) hasBlack = true;
                        dilated[idx] = hasBlack ? 0 : 255;
                    } else dilated[idx] = 0;
                }
            }
            // Apply to enhanced data and scan
            const cleanedData = new Uint8ClampedArray(w * h * 4);
            for (let i = 0; i < dilated.length; i++) {
                const val = dilated[i];
                cleanedData[i * 4] = val;
                cleanedData[i * 4 + 1] = val;
                cleanedData[i * 4 + 2] = val;
                cleanedData[i * 4 + 3] = 255;
            }
            insertUnique(merged, scanQrIterative(cleanedData, w, h, 'jsQR(speckle)', 25));
        } catch (e) { /* speckle filter failed */ }
    }

    // ====== Finder-pattern repair: detect and fix ink-damaged corners ======
    if (wantQr && merged.length < 2) {
        try {
            const fpSize = Math.floor(Math.min(w, h) * 0.22);
            const corners = [
                { name: 'TL', x: 0, y: 0 },
                { name: 'TR', x: w - fpSize, y: 0 },
                { name: 'BL', x: 0, y: h - fpSize },
            ];
            let damaged = 0;
            const repCanvas = document.createElement('canvas');
            repCanvas.width = w; repCanvas.height = h;
            const repCtx = repCanvas.getContext('2d');
            repCtx.putImageData(imageData, 0, 0);

            for (const c of corners) {
                // Sample corner region: if >40% pixels are dark (ink damage), repair it
                let darkCount = 0, total = 0;
                for (let dy = 0; dy < fpSize; dy += 3) {
                    for (let dx = 0; dx < fpSize; dx += 3) {
                        const idx = ((c.y + dy) * w + (c.x + dx)) * 4;
                        const gray = imageData.data[idx] * 0.299 + imageData.data[idx + 1] * 0.587 + imageData.data[idx + 2] * 0.114;
                        if (gray < 100) darkCount++;
                        total++;
                    }
                }
                if (total > 0 && darkCount / total > 0.4) {
                    damaged++;
                    // Erase ink in this corner (fill white) then draw clean finder pattern
                    repCtx.fillStyle = '#FFFFFF';
                    repCtx.fillRect(c.x, c.y, fpSize, fpSize);
                    // Draw 7x7 module finder pattern (black-white-black concentric)
                    const cx = c.x + fpSize / 2;
                    const cy = c.y + fpSize / 2;
                    const half = fpSize / 2;
                    repCtx.fillStyle = '#000000';
                    repCtx.fillRect(cx - half, cy - half, fpSize, fpSize);
                    const inner1 = fpSize * 5 / 14;
                    repCtx.fillStyle = '#FFFFFF';
                    repCtx.fillRect(cx - inner1, cy - inner1, inner1 * 2, inner1 * 2);
                    const inner2 = fpSize * 3 / 14;
                    repCtx.fillStyle = '#000000';
                    repCtx.fillRect(cx - inner2, cy - inner2, inner2 * 2, inner2 * 2);
                }
            }

            if (damaged > 0) {
                // Re-scan the repaired image with jsQR + BarcodeDetector
                const repImageData = repCtx.getImageData(0, 0, w, h);
                const repEnhanced = grayscaleEnhance(repImageData);
                insertUnique(merged, scanQrIterative(repEnhanced.data, w, h, 'jsQR(repair)', 25));
                // Also try BarcodeDetector on repaired canvas
                if ('BarcodeDetector' in window) {
                    try {
                        const detected = await new BarcodeDetector({ formats: ['qr_code'] }).detect(repCanvas);
                        for (const b of detected) {
                            insertUnique(merged, [{ text: b.rawValue, type: 'QR Code', confidence: 'BD(repair)' }]);
                        }
                    } catch (e) { /* ok */ }
                }
            }
        } catch (e) { /* repair failed, continue */ }
    }

    // ====== Region-based fallback for sparse/large images ======
    if (wantQr && merged.length < 2) {
        try {
            const regionResults = await scanRegions(canvas, w, h);
            insertUnique(merged, regionResults);
        } catch (e) { /* region scan failed, continue */ }
    }

    // ====== html5-qrcode: zxing WASM with 6s timeout ======
    if (wantQr) {
        try {
            const tempId = 'temp-scan-' + Date.now();
            const div = document.createElement('div');
            div.id = tempId;
            div.style.display = 'none';
            document.body.appendChild(div);
            const scanner = new Html5Qrcode(tempId);
            try {
                // 6-second timeout prevents hanging on corrupted images
                const result = await Promise.race([
                    scanner.scanFile(file, false),
                    new Promise((_, reject) =>
                        setTimeout(() => reject(new Error('timeout')), 6000))
                ]);
                if (result && typeof result === 'string' && result.trim()) {
                    insertUnique(merged, [{ text: result, type: 'QR Code', confidence: 'html5-qrcode' }]);
                }
            } finally {
                try { await scanner.clear(); } catch {}
                div.remove();
            }
        } catch (e) { /* html5-qrcode failed or timed out */ }
    }

    return merged;
}

function inverted(data) {
    const out = new Uint8ClampedArray(data.length);
    for (let i = 0; i < data.length; i += 4) {
        out[i] = 255 - data[i];
        out[i + 1] = 255 - data[i + 1];
        out[i + 2] = 255 - data[i + 2];
        out[i + 3] = data[i + 3];
    }
    return out;
}

function insertUnique(dest, items) {
    for (const r of items) {
        if (!dest.some(m => m.text === r.text)) {
            dest.push(r);
        }
    }
}

// ============ Result Display ============
function displayResult(text, type, cardId, typeId, contentId, confidenceId) {
    document.getElementById(cardId).style.display = 'block';
    document.getElementById(typeId).textContent = type;
    document.getElementById(typeId).className = 'badge ' + (type === 'QR Code' ? '' : 'barcode');
    document.getElementById(contentId).textContent = text;
    document.getElementById(confidenceId).textContent = '';
    document.getElementById('btnOpenUrl').style.display = isUrl(text) ? 'flex' : 'none';
    state.currentResult = text;
}

function copyResult() {
    if (state.currentResult) {
        navigator.clipboard.writeText(state.currentResult).then(() => showToast('已复制到剪贴板'));
    }
}

function openResultUrl() {
    if (state.currentResult && isUrl(state.currentResult)) {
        window.open(state.currentResult, '_blank');
    }
}

// ============ Gallery ============
function renderGallery() {
    const grid = document.getElementById('galleryGrid');
    grid.innerHTML = TEST_IMAGES.map((img, idx) => `
        <div class="gallery-item" data-idx="${idx}">
            <img src="${img.src}" alt="${img.label}" loading="lazy"
                 onerror="this.parentElement.style.display='none'"
                 onload="this.parentElement.querySelector('.item-label').style.display='block'">
            <div class="item-label" style="display:none;">${img.label}</div>
        </div>
    `).join('');

    // Add click handlers
    grid.querySelectorAll('.gallery-item').forEach(item => {
        item.addEventListener('click', async () => {
            const idx = parseInt(item.dataset.idx);
            const imgData = TEST_IMAGES[idx];
            try {
                const resp = await fetch(imgData.src);
                const blob = await resp.blob();
                const file = new File([blob], imgData.src.split('/').pop(), { type: blob.type || 'image/png' });

                // Switch to scan tab to show result
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelector('.tab-btn[data-tab="scan"]').classList.add('active');
                document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                document.getElementById('tab-scan').classList.add('active');

                scanImageFile(file, 'resultCard', 'resultType', 'resultContent', 'resultConfidence');
            } catch (err) {
                showToast('图片加载失败');
            }
        });
    });
}

// ============ History ============
function loadHistory() {
    try {
        const stored = localStorage.getItem('scan_history');
        state.history = stored ? JSON.parse(stored) : [];
    } catch {
        state.history = [];
    }
}

function saveHistory() {
    localStorage.setItem('scan_history', JSON.stringify(state.history.slice(0, 50)));
}

function addToHistory(text, type) {
    state.history.unshift({
        text,
        type,
        time: new Date().toLocaleString('zh-CN'),
    });
    if (state.history.length > 50) state.history.pop();
    saveHistory();
}

function renderHistory() {
    const list = document.getElementById('historyList');
    if (state.history.length === 0) {
        list.innerHTML = '<p class="empty-hint">暂无扫描记录</p>';
        return;
    }
    list.innerHTML = state.history.map(h => `
        <div class="history-item" onclick="navigator.clipboard.writeText('${escapeHtml(h.text).replace(/'/g, "\\'")}');showToast('已复制')">
            <span class="hi-type ${h.type === 'QR Code' ? 'qr' : 'barcode'}">${h.type}</span>
            <div class="hi-content">${escapeHtml(h.text)}</div>
            <div class="hi-time">${h.time}</div>
        </div>
    `).join('');
}

function clearHistory() {
    if (confirm('确定清空扫描历史？')) {
        state.history = [];
        saveHistory();
        renderHistory();
        showToast('历史已清空');
    }
}

// ============ Settings ============
function setupSettings() {
    document.getElementById('scanFormat').addEventListener('change', (e) => {
        state.scanFormat = e.target.value;
        localStorage.setItem('scan_format', state.scanFormat);
    });
    document.getElementById('cameraSelect').addEventListener('change', (e) => {
        state.facingMode = e.target.value;
    });
    document.getElementById('soundToggle').addEventListener('change', (e) => {
        state.soundEnabled = e.target.checked;
    });
    document.getElementById('autoRedirectToggle').addEventListener('change', (e) => {
        state.autoRedirect = e.target.checked;
        localStorage.setItem('auto_redirect', e.target.checked);
    });

    // Load saved
    const savedFormat = localStorage.getItem('scan_format');
    if (savedFormat) {
        state.scanFormat = savedFormat;
        document.getElementById('scanFormat').value = savedFormat;
    }
    const savedAutoRedirect = localStorage.getItem('auto_redirect');
    if (savedAutoRedirect !== null) {
        state.autoRedirect = savedAutoRedirect === 'true';
        document.getElementById('autoRedirectToggle').checked = state.autoRedirect;
    }
}

function openSettings() {
    document.getElementById('settingsModal').style.display = 'block';
}

function closeSettings() {
    document.getElementById('settingsModal').style.display = 'none';
}

// ============ Utility Functions ============
function isUrl(text) {
    return /^(https?:\/\/|www\.)/i.test(text);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.style.display = 'block';
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => { toast.style.display = 'none'; }, 2000);
}

function playBeep() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.frequency.value = 880;
        oscillator.type = 'sine';
        gain.gain.value = 0.3;
        oscillator.start(ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
        oscillator.stop(ctx.currentTime + 0.15);
    } catch {
        // Audio not available
    }
}

// ============ PWA Registration ============
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('sw.js').catch(() => {});
    });
}
