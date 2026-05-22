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
    flashlightOn: false,
    hasFlashlight: false,
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
    document.getElementById('btnFlashlight').addEventListener('click', toggleFlashlight);
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

        // Check flashlight availability after camera starts
        try {
            const capabilities = state.scanner.getRunningTrackCapabilities();
            if (capabilities && capabilities.torch) {
                state.hasFlashlight = true;
                document.getElementById('btnFlashlight').style.display = 'flex';
            }
        } catch {
            // Flashlight not available on this device
        }
    } catch (err) {
        console.error('Camera start error:', err);
        showToast('无法打开摄像头: ' + (err.message || '权限不足'));
        resetScanUI();
    }
}

async function toggleFlashlight() {
    if (!state.isScanning || !state.hasFlashlight) return;
    try {
        state.flashlightOn = !state.flashlightOn;
        await state.scanner.applyVideoConstraints({
            advanced: [{ torch: state.flashlightOn }]
        });
        const btn = document.getElementById('btnFlashlight');
        if (state.flashlightOn) {
            btn.classList.add('active');
            btn.title = '关闭手电筒';
        } else {
            btn.classList.remove('active');
            btn.title = '打开手电筒';
        }
    } catch {
        showToast('手电筒不可用');
        state.flashlightOn = false;
    }
}

// Normalize decoded text: trim whitespace, collapse newlines, remove BOM
function normalizeText(text) {
    if (!text) return '';
    return text.replace(/^\s+|\s+$/g, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\n+/g, '\n').trim();
}

function sameText(a, b) {
    return normalizeText(a) === normalizeText(b);
}

function hasText(arr, text) {
    return arr.some(m => sameText(m.text, text));
}

// Filter garbled / invalid decoded text
function isValidDecodedText(text) {
    if (!text || text.length < 2) return false;
    // Reject results with too many control characters or non-printable chars
    const clean = text.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]/g, '');
    if (clean.length < text.length * 0.5) return false;
    // Reject extremely high-entropy short strings (random garbage)
    if (text.length <= 6 && /[^\x20-\x7e]/.test(text)) return false;
    // Reject strings that are purely non-ASCII garbage
    if (text.length <= 10 && /^[^\x20-\x7e]+$/.test(text)) return false;
    return true;
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

    const normalized = normalizeText(decodedText);

    // Skip invalid/garbled results
    if (!isValidDecodedText(normalized)) return;

    const formatName = decodedResult.result.format?.formatName || 'unknown';
    const type = formatName === 'qr_code' ? 'QR Code' : 'Barcode';

    // Skip duplicates (check normalized text)
    if (hasText(state.cameraResults, normalized)) return;

    if (state.soundEnabled) playBeep();

    state.cameraResults.push({ text: normalized, type: type });
    addToHistory(decodedText, type);

    const card = document.getElementById('resultCard');
    card.style.display = 'block';

    // Limit camera results to 8 to prevent spam
    if (state.cameraResults.length > 8) {
        state.cameraResults.shift();
    }

    if (state.cameraResults.length === 1) {
        displayResult(normalized, type, 'resultCard', 'resultType', 'resultContent', 'resultConfidence');
        showToast('已扫描 1 个, 继续扫描中...');
    } else {
        card.innerHTML = buildMultiSelectHtml(state.cameraResults);
        showToast(`已扫描 ${state.cameraResults.length} 个, 点击查看详情`);
    }
}

function selectMultiResult(index) {
    const r = state.cameraResults[index];
    if (!r) return;
    const card = document.getElementById('resultCard');
    displayResultHtml(card, r.text, r.type, 'resultType', 'resultContent', 'resultConfidence');
    // Add a "back to list" button
    const backBtn = document.createElement('button');
    backBtn.className = 'btn-sm';
    backBtn.style.cssText = 'margin-top:8px;';
    backBtn.textContent = '← 返回列表';
    backBtn.onclick = () => {
        card.innerHTML = buildMultiSelectHtml(state.cameraResults);
    };
    card.querySelector('.result-actions')?.appendChild(backBtn);
}

function displayResultHtml(card, text, type, typeId, contentId, confidenceId) {
    const url = isUrl(text);
    card.innerHTML = `
        <div class="result-header">
            <span class="badge ${type === 'QR Code' ? '' : 'barcode'}">${type}</span>
            <span class="confidence"></span>
            <button onclick="this.closest('.result-card').style.display='none'" class="icon-btn-sm">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
        </div>
        <div class="result-content" style="font-size:20px;font-family:monospace;word-break:break-all;">${escapeHtml(text)}</div>
        <div class="result-actions">
            <button id="btnCopy" class="btn-sm" onclick="navigator.clipboard.writeText('${escapeHtml(text).replace(/'/g, "\\'")}');showToast('已复制')">复制</button>
            ${url ? `<button id="btnOpenUrl" class="btn-sm" onclick="window.open('${escapeHtml(text)}','_blank')">打开链接</button>` : ''}
        </div>
    `;
    state.currentResult = text;
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
    document.getElementById('btnFlashlight').style.display = 'none';
    document.getElementById('btnFlashlight').classList.remove('active');
    state.flashlightOn = false;
    state.hasFlashlight = false;
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
    return buildMultiSelectHtml(results);
}

function buildMultiSelectHtml(results) {
    return `
        <div class="result-header">
            <span class="badge" style="background:#1a73e8;">${results.length} 个结果</span>
            <span style="font-size:12px;color:#888;">点击查看详情</span>
            <button onclick="this.closest('.result-card').style.display='none'" class="icon-btn-sm">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
        </div>
        ${results.map((r, i) => `
            <div class="multi-result-item" onclick="selectMultiResult(${i})" style="cursor:pointer;">
                <div class="mri-header">
                    <span class="mri-index">● ${i + 1}</span>
                    <span class="badge ${r.type === 'QR Code' ? '' : 'barcode'}">${r.type}</span>
                </div>
                <div class="result-content" style="font-size:14px;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(r.text)}</div>
                <div style="text-align:right;color:#1a73e8;font-size:12px;">点击查看 →</div>
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
    try { return jsQR(data, w, h, { inversionAttempts: 'dontInvert' }); }
    catch { return null; }
}

// ============================================================================
// Preprocess v2.0.3 — Ported from Python advanced_cv_scanner.py
// CLAHE, Otsu, median filter, adaptive threshold sweep, morphological close
// ============================================================================

const Preprocess = {
    /**
     * Median filter on grayscale ImageData.
     * Equivalent to cv2.medianBlur(gray, ks).
     */
    medianBlur(imageData, ks) {
        const w = imageData.width, h = imageData.height, src = imageData.data;
        const gray = new Float32Array(w * h);
        for (let i = 0; i < w * h; i++) {
            gray[i] = src[i * 4] * 0.299 + src[i * 4 + 1] * 0.587 + src[i * 4 + 2] * 0.114;
        }
        const out = new ImageData(w, h);
        const dst = out.data;
        const r = Math.floor(ks / 2);
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const vals = [];
                for (let dy = -r; dy <= r; dy++) {
                    for (let dx = -r; dx <= r; dx++) {
                        const ny = clamp(y + dy, 0, h - 1), nx = clamp(x + dx, 0, w - 1);
                        vals.push(gray[ny * w + nx]);
                    }
                }
                vals.sort((a, b) => a - b);
                const v = vals[Math.floor(vals.length / 2)];
                const di = (y * w + x) * 4;
                dst[di] = dst[di + 1] = dst[di + 2] = v;
                dst[di + 3] = 255;
            }
        }
        return out;
    },

    /**
     * Contrast Limited Adaptive Histogram Equalization (simplified).
     * Splits image into tiles, equalizes each, bilinear interpolation.
     * Equivalent to cv2.createCLAHE(clipLimit, tileGridSize).
     */
    clahe(imageData, clipLimit, tileW, tileH) {
        const w = imageData.width, h = imageData.height, src = imageData.data;
        const gray = new Uint8Array(w * h);
        for (let i = 0; i < w * h; i++) {
            gray[i] = Math.round(src[i * 4] * 0.299 + src[i * 4 + 1] * 0.587 + src[i * 4 + 2] * 0.114);
        }

        const tw = tileW || 32, th = tileH || 32;
        const nx = Math.ceil(w / tw), ny = Math.ceil(h / th);
        const tiles = [];
        for (let ty = 0; ty < ny; ty++) {
            for (let tx = 0; tx < nx; tx++) {
                const hist = new Array(256).fill(0);
                const x0 = tx * tw, y0 = ty * th;
                const x1 = Math.min(w, x0 + tw), y1 = Math.min(h, y0 + th);
                let count = 0;
                for (let y = y0; y < y1; y++) {
                    for (let x = x0; x < x1; x++) {
                        hist[gray[y * w + x]]++;
                        count++;
                    }
                }
                // Clip and redistribute
                const clip = clipLimit || 2.0;
                const clipThreshold = Math.floor((count / 256) * clip);
                let excess = 0;
                for (let i = 0; i < 256; i++) {
                    if (hist[i] > clipThreshold) { excess += hist[i] - clipThreshold; hist[i] = clipThreshold; }
                }
                const redist = Math.floor(excess / 256);
                for (let i = 0; i < 256; i++) hist[i] += redist;
                // CDF
                const cdf = new Float32Array(256);
                cdf[0] = hist[0] / count;
                for (let i = 1; i < 256; i++) cdf[i] = cdf[i - 1] + hist[i] / count;
                tiles.push({ x0, y0, x1, y1, cdf });
            }
        }

        const out = new ImageData(w, h);
        const dst = out.data;
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const v = gray[y * w + x];
                // Find surrounding tiles and bilinear interpolate
                const txf = (x + 0.5) / tw - 0.5, tyf = (y + 0.5) / th - 0.5;
                const tx0 = clamp(Math.floor(txf), 0, nx - 1), ty0 = clamp(Math.floor(tyf), 0, ny - 1);
                const tx1 = Math.min(tx0 + 1, nx - 1), ty1 = Math.min(ty0 + 1, ny - 1);
                const fx = txf - tx0, fy = tyf - ty0;

                const c00 = tiles[ty0 * nx + tx0].cdf[v];
                const c10 = tiles[ty0 * nx + tx1].cdf[v];
                const c01 = tiles[ty1 * nx + tx0].cdf[v];
                const c11 = tiles[ty1 * nx + tx1].cdf[v];
                const eq = Math.round(((c00 * (1 - fx) + c10 * fx) * (1 - fy) + (c01 * (1 - fx) + c11 * fx) * fy) * 255);

                const di = (y * w + x) * 4;
                dst[di] = dst[di + 1] = dst[di + 2] = eq;
                dst[di + 3] = 255;
            }
        }
        return out;
    },

    /**
     * Otsu's method for global thresholding.
     * Finds threshold that maximizes between-class variance.
     */
    otsuThreshold(imageData) {
        const w = imageData.width, h = imageData.height, src = imageData.data;
        const gray = new Float32Array(w * h);
        for (let i = 0; i < w * h; i++) {
            gray[i] = src[i * 4] * 0.299 + src[i * 4 + 1] * 0.587 + src[i * 4 + 2] * 0.114;
        }

        const hist = new Array(256).fill(0);
        for (let i = 0; i < w * h; i++) hist[Math.round(gray[i])]++;

        let sum = 0, sumB = 0, wB = 0, wF = 0, maxVar = 0, threshold = 128;
        for (let i = 0; i < 256; i++) sum += i * hist[i];
        const total = w * h;

        for (let t = 0; t < 256; t++) {
            wB += hist[t];
            if (wB === 0) continue;
            wF = total - wB;
            if (wF === 0) break;
            sumB += t * hist[t];
            const mB = sumB / wB, mF = (sum - sumB) / wF;
            const betweenVar = wB * wF * (mB - mF) * (mB - mF);
            if (betweenVar > maxVar) { maxVar = betweenVar; threshold = t; }
        }

        const out = new ImageData(w, h);
        const dst = out.data;
        for (let i = 0; i < w * h; i++) {
            const v = gray[i] > threshold ? 255 : 0;
            const di = i * 4;
            dst[di] = dst[di + 1] = dst[di + 2] = v;
            dst[di + 3] = 255;
        }
        return out;
    },

    /**
     * Adaptive threshold with Gaussian kernel.
     * For each pixel, compares to weighted mean of neighbors.
     */
    adaptiveThreshold(imageData, blockSize, C) {
        const w = imageData.width, h = imageData.height, src = imageData.data;
        const gray = new Float32Array(w * h);
        for (let i = 0; i < w * h; i++) {
            gray[i] = src[i * 4] * 0.299 + src[i * 4 + 1] * 0.587 + src[i * 4 + 2] * 0.114;
        }

        // Gaussian kernel
        const r = Math.floor(blockSize / 2);
        const kernel = [];
        const sigma = blockSize / 6;
        let kernelSum = 0;
        for (let dy = -r; dy <= r; dy++) {
            for (let dx = -r; dx <= r; dx++) {
                const wgt = Math.exp(-(dx * dx + dy * dy) / (2 * sigma * sigma));
                kernel.push(wgt);
                kernelSum += wgt;
            }
        }
        for (let i = 0; i < kernel.length; i++) kernel[i] /= kernelSum;

        const out = new ImageData(w, h);
        const dst = out.data;
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                let sum = 0;
                for (let dy = -r; dy <= r; dy++) {
                    for (let dx = -r; dx <= r; dx++) {
                        const ny = clamp(y + dy, 0, h - 1), nx = clamp(x + dx, 0, w - 1);
                        sum += gray[ny * w + nx] * kernel[(dy + r) * blockSize + (dx + r)];
                    }
                }
                const v = gray[y * w + x] > (sum - C) ? 255 : 0;
                const di = (y * w + x) * 4;
                dst[di] = dst[di + 1] = dst[di + 2] = v;
                dst[di + 3] = 255;
            }
        }
        return out;
    },

    /**
     * Morphological opening: erode then dilate.
     * Removes small dark spots (ink specks) while preserving large features.
     * Critical for ink_data_pollution category.
     */
    morphOpen(imageData, kernelSize) {
        const w = imageData.width, h = imageData.height, src = imageData.data;
        const bin = new Uint8Array(w * h);
        for (let i = 0; i < w * h; i++) {
            bin[i] = (src[i * 4] * 0.299 + src[i * 4 + 1] * 0.587 + src[i * 4 + 2] * 0.114) < 128 ? 0 : 255;
        }
        const r = Math.floor((kernelSize || 3) / 2);

        // Erode: if any neighbor is white, become white (remove small black dots)
        const eroded = new Uint8Array(w * h);
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                let hasWhite = false;
                for (let dy = -r; dy <= r; dy++) {
                    for (let dx = -r; dx <= r; dx++) {
                        const ny = clamp(y + dy, 0, h - 1), nx = clamp(x + dx, 0, w - 1);
                        if (bin[ny * w + nx] === 255) { hasWhite = true; break; }
                    }
                    if (hasWhite) break;
                }
                eroded[y * w + x] = hasWhite ? 255 : 0;
            }
        }

        // Dilate: restore module edges
        const opened = new Uint8Array(w * h);
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                let hasBlack = false;
                for (let dy = -r; dy <= r; dy++) {
                    for (let dx = -r; dx <= r; dx++) {
                        const ny = clamp(y + dy, 0, h - 1), nx = clamp(x + dx, 0, w - 1);
                        if (eroded[ny * w + nx] === 0) { hasBlack = true; break; }
                    }
                    if (hasBlack) break;
                }
                opened[y * w + x] = hasBlack ? 0 : 255;
            }
        }

        const out = new ImageData(w, h);
        const dst = out.data;
        for (let i = 0; i < w * h; i++) {
            dst[i * 4] = dst[i * 4 + 1] = dst[i * 4 + 2] = opened[i];
            dst[i * 4 + 3] = 255;
        }
        return out;
    },

    /**
     * Simplified bilateral filter — spatial + range weighting.
     * Smooths noise while preserving edges.
     */
    bilateralFilter(imageData, d, sigmaColor, sigmaSpace) {
        const w = imageData.width, h = imageData.height, src = imageData.data;
        const gray = new Float32Array(w * h);
        for (let i = 0; i < w * h; i++) {
            gray[i] = src[i * 4] * 0.299 + src[i * 4 + 1] * 0.587 + src[i * 4 + 2] * 0.114;
        }

        const dia = d || 7, sc = sigmaColor || 50, ss = sigmaSpace || 50;
        const r = Math.floor(dia / 2);

        const out = new ImageData(w, h);
        const dst = out.data;
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const centerVal = gray[y * w + x];
                let sum = 0, weightSum = 0;
                for (let dy = -r; dy <= r; dy++) {
                    for (let dx = -r; dx <= r; dx++) {
                        const ny = clamp(y + dy, 0, h - 1), nx = clamp(x + dx, 0, w - 1);
                        const val = gray[ny * w + nx];
                        const spatialW = Math.exp(-(dx * dx + dy * dy) / (2 * ss * ss));
                        const rangeW = Math.exp(-((val - centerVal) * (val - centerVal)) / (2 * sc * sc));
                        const wgt = spatialW * rangeW;
                        sum += val * wgt;
                        weightSum += wgt;
                    }
                }
                const v = Math.round(sum / (weightSum + 1e-6));
                const di = (y * w + x) * 4;
                dst[di] = dst[di + 1] = dst[di + 2] = v;
                dst[di + 3] = 255;
            }
        }
        return out;
    },

    /**
     * Morphological close: dilate then erode.
     * Reconnects broken bars in 1D barcodes.
     */
    morphClose(imageData, kernelW, kernelH) {
        const w = imageData.width, h = imageData.height, src = imageData.data;
        const bin = new Uint8Array(w * h);
        for (let i = 0; i < w * h; i++) {
            bin[i] = (src[i * 4] * 0.299 + src[i * 4 + 1] * 0.587 + src[i * 4 + 2] * 0.114) < 128 ? 0 : 255;
        }
        const kw = kernelW || 7, kh = kernelH || 1;
        const rx = Math.floor(kw / 2), ry = Math.floor(kh / 2);

        // Dilate
        const dilated = new Uint8Array(w * h);
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                let hasBlack = false;
                for (let dy = -ry; dy <= ry; dy++) {
                    for (let dx = -rx; dx <= rx; dx++) {
                        const ny = clamp(y + dy, 0, h - 1), nx = clamp(x + dx, 0, w - 1);
                        if (bin[ny * w + nx] === 0) { hasBlack = true; break; }
                    }
                    if (hasBlack) break;
                }
                dilated[y * w + x] = hasBlack ? 0 : 255;
            }
        }

        // Erode
        const closed = new Uint8Array(w * h);
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                let allBlack = true;
                for (let dy = -ry; dy <= ry; dy++) {
                    for (let dx = -rx; dx <= rx; dx++) {
                        const ny = clamp(y + dy, 0, h - 1), nx = clamp(x + dx, 0, w - 1);
                        if (dilated[ny * w + nx] !== 0) { allBlack = false; break; }
                    }
                    if (!allBlack) break;
                }
                closed[y * w + x] = allBlack ? 0 : 255;
            }
        }

        const out = new ImageData(w, h);
        const dst = out.data;
        for (let i = 0; i < w * h; i++) {
            dst[i * 4] = dst[i * 4 + 1] = dst[i * 4 + 2] = closed[i];
            dst[i * 4 + 3] = 255;
        }
        return out;
    },

    /**
     * Fast tier: most impactful variants ordered by diagnostic hit rate.
     * median3 rescues the most images (92/210 for ink pollution) — must be first.
     */
    generateFastVariants(imageData) {
        const variants = [];
        const w = imageData.width, h = imageData.height;

        // #1: Median denoise — highest hit rate across all damage types
        variants.push({ tag: 'median3', data: this.medianBlur(imageData, 3) });

        // #2: Median(5) + Bilateral heavy denoise — critical for ink pollution (31 extra images)
        const med5 = this.medianBlur(imageData, 5);
        const med5Gray = new Float32Array(w * h);
        const m5d = med5.data;
        for (let i = 0; i < w * h; i++) {
            med5Gray[i] = m5d[i * 4] * 0.299 + m5d[i * 4 + 1] * 0.587 + m5d[i * 4 + 2] * 0.114;
        }
        // Build ImageData from med5 gray for bilateral input
        const med5ImgData = new ImageData(w, h);
        const m5di = med5ImgData.data;
        for (let i = 0; i < w * h; i++) {
            const v = Math.round(med5Gray[i]);
            m5di[i * 4] = m5di[i * 4 + 1] = m5di[i * 4 + 2] = v;
            m5di[i * 4 + 3] = 255;
        }
        variants.push({ tag: 'med5+bilat', data: this.bilateralFilter(med5ImgData, 7, 50, 50) });

        // #3: CLAHE — for low contrast / noise
        variants.push({ tag: 'clahe-c2', data: this.clahe(imageData, 2.0) });

        // #4: Otsu — for data pollution
        variants.push({ tag: 'otsu', data: this.otsuThreshold(imageData) });

        // #5: Morphological opening — removes small ink specks (critical for QR ink pollution)
        if (w < h * 2.0 && h < w * 2.0) {  // Square-ish → QR code
            variants.push({ tag: 'morphOpen-3', data: this.morphOpen(imageData, 3) });
            variants.push({ tag: 'morphOpen-5', data: this.morphOpen(imageData, 5) });
        }

        // #6: Wide adaptive threshold sweep (8 key combos — Python uses 16)
        for (const [bs, c] of [[21, 5], [31, 9], [41, 13], [51, 9], [21, 13], [31, 5], [41, 9], [51, 13]]) {
            variants.push({ tag: `adap-${bs}-${c}`, data: this.adaptiveThreshold(imageData, bs, c) });
        }

        // #7: Median3+CLAHE combo (for heavy noise)
        const med3ForClahe = this.medianBlur(imageData, 3);
        variants.push({ tag: 'med3+clahe', data: this.clahe(med3ForClahe, 2.0) });

        // #8: median5 standalone (28 ink_pollution images)
        variants.push({ tag: 'median5', data: this.medianBlur(imageData, 5) });

        // #9: Morphological close — critical for ink pollution (41 images), all types
        variants.push({ tag: 'morphClose-5x1', data: this.morphClose(imageData, 5, 1) });
        if (w > h * 1.2) {
            variants.push({ tag: 'morphClose-7x1', data: this.morphClose(imageData, 7, 1) });
        }
        variants.push({ tag: 'morphClose-3x3', data: this.morphClose(imageData, 3, 3) });

        return variants;
    },

    /**
     * Full sweep: comprehensive variants for stubborn images.
     * Only called if fast tier didn't find anything.
     */
    generateFullVariants(imageData) {
        const variants = [];
        const w = imageData.width, h = imageData.height;

        // Remaining CLAHE and combos
        variants.push({ tag: 'clahe-c3', data: this.clahe(imageData, 3.0) });
        const med3 = this.medianBlur(imageData, 3);
        const med3Gray = new Float32Array(w * h);
        const m3d = med3.data;
        for (let i = 0; i < w * h; i++) med3Gray[i] = m3d[i * 4];
        const med3Img = new ImageData(w, h);
        const m3di = med3Img.data;
        for (let i = 0; i < w * h; i++) {
            const v = Math.round(med3Gray[i]);
            m3di[i*4]=m3di[i*4+1]=m3di[i*4+2]=v; m3di[i*4+3]=255;
        }
        variants.push({ tag: 'med3+clahe', data: this.clahe(med3Img, 2.0) });

        // Full adaptive threshold sweep
        for (const bs of [21, 31, 41, 51]) {
            for (const c of [3, 5, 9, 13]) {
                const tag = `adap-${bs}-${c}`;
                if (!variants.some(v => v.tag === tag)) {
                    variants.push({ tag, data: this.adaptiveThreshold(imageData, bs, c) });
                }
            }
        }

        // Extended morphological close (barcodes)
        if (w > h * 1.2) {
            for (const [kw, kh] of [[3, 1], [7, 3], [7, 5]]) {
                variants.push({ tag: `morphClose-${kw}x${kh}`, data: this.morphClose(imageData, kw, kh) });
            }
        }

        // Inverted adaptive threshold (catches white-on-black prints)
        variants.push({ tag: 'adap-inv-31-9', data: this.invert(this.adaptiveThreshold(imageData, 31, 9)) });

        return variants;
    },

    /** Invert binary ImageData (255 ↔ 0). */
    invert(imageData) {
        const out = new ImageData(imageData.width, imageData.height);
        const src = imageData.data, dst = out.data;
        for (let i = 0; i < src.length; i += 4) {
            const v = 255 - src[i];
            dst[i] = dst[i + 1] = dst[i + 2] = v;
            dst[i + 3] = 255;
        }
        return out;
    }
};

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

/**
 * Run BarcodeDetector on a canvas with 3-level fallback.
 * Returns array of { rawValue, format }.
 */
async function runBarcodeDetector(canvas, wantQr, wantBarcode) {
    let detected = [];
    if (!('BarcodeDetector' in window)) return detected;
    try {
        const fmts = [];
        if (wantQr) fmts.push('qr_code');
        if (wantBarcode) fmts.push('ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39', 'code_93', 'codabar', 'itf');
        detected = await new BarcodeDetector({ formats: fmts }).detect(canvas);
    } catch (e1) {
        try {
            const sup = await BarcodeDetector.getSupportedFormats();
            const fmts = [];
            if (wantQr && sup.includes('qr_code')) fmts.push('qr_code');
            if (wantBarcode) {
                for (const f of ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39', 'code_93', 'codabar', 'itf']) {
                    if (sup.includes(f)) fmts.push(f);
                }
            }
            if (fmts.length > 0) detected = await new BarcodeDetector({ formats: fmts }).detect(canvas);
        } catch (e2) {
            try {
                if (wantQr) detected = await new BarcodeDetector({ formats: ['qr_code'] }).detect(canvas);
            } catch (e3) {}
        }
    }
    return detected;
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

    // ====== v2.0.3 Preprocessing variants (CLAHE, Otsu, adaptive, morph) ======
    // Tiered approach: fast impactful variants first, full sweep only if needed
    const fastVariants = Preprocess.generateFastVariants(imageData);
    const fullVariants = Preprocess.generateFullVariants(imageData);

    // ====== v2.0.1 Geometric Correction ======
    // Generate corrected variants for cylinder/perspective distortion
    let correctedVariants = [];
    if (w > h * 1.2) {
        // Wide image: likely barcode — try cylinder unwarp + perspective normalize
        correctedVariants.push({ tag: 'persp-norm', data: GeoCorrect.normalizePerspective(imageData) });
        const cylVariants = GeoCorrect.unwarpBarcodeMulti(imageData);
        for (const v of cylVariants) {
            correctedVariants.push({ tag: `barcode-cyl-c${v.curvature.toFixed(2)}`, data: v.data });
            // Also try cylinder unwarp followed by perspective normalize (combo)
            correctedVariants.push({
                tag: `cyl-c${v.curvature.toFixed(2)}+persp`,
                data: GeoCorrect.normalizePerspective(v.data)
            });
        }
    }
    if (wantQr && h > 40 && w > 40) {
        const qrVariants = GeoCorrect.unwarpQRMulti(imageData);
        for (const v of qrVariants) {
            correctedVariants.push({ tag: `qr-cyl-c${v.curvature.toFixed(2)}`, data: v.data });
        }
    }

    // ====== Fragment extraction (for edge_tear / torn images) ======
    const fragments = GeoCorrect.extractFragments(imageData);
    for (const frag of fragments) {
        correctedVariants.push(frag);
    }

    // Fast jsQR-only decode on a variant (no BarcodeDetector — too slow on binarized images)
    function jsqrQuick(variant) {
        if (!wantQr) return false;
        const d = variant.data;
        const r = safeJsQR(d.data, d.width, d.height);
        if (r && r.data) {
            insertUnique(merged, { text: normalizeText(r.data), type: 'QR Code', confidence: `jsQR(${variant.tag})` });
            return true;
        }
        // Inverted quick pass
        const inv = inverted(d.data);
        const r2 = safeJsQR(inv, d.width, d.height);
        if (r2 && r2.data) {
            insertUnique(merged, { text: normalizeText(r2.data), type: 'QR Code', confidence: `jsQR(${variant.tag}/inv)` });
            return true;
        }
        return false;
    }

    // Run BarcodeDetector on a canvas (original or geometric variants only — clean images)
    async function bdOnCanvas(cv, tag) {
        if (!wantQr && !wantBarcode) return false;
        try {
            const detected = await runBarcodeDetector(cv, wantQr, wantBarcode);
            for (const b of detected) {
                const isQr = b.format === 'qr_code' || b.format === 'QR Code';
                if (!hasText(merged, b.rawValue)) {
                    merged.push({ text: normalizeText(b.rawValue), type: isQr ? 'QR Code' : 'Barcode',
                                  confidence: `BarcodeDetector(${tag})` });
                }
            }
            return detected.length > 0;
        } catch { return false; }
    }

    function toCanvas(imgData) {
        const cv = document.createElement('canvas');
        cv.width = imgData.width; cv.height = imgData.height;
        cv.getContext('2d').putImageData(imgData, 0, 0);
        return cv;
    }

    // ====== Phase 1: Original image (BarcodeDetector + jsQR, parallel) ======
    const bdPromise = bdOnCanvas(canvas, 'original');

    // jsQR on original (runs while BarcodeDetector is pending)
    if (wantQr) {
        const enhanced = grayscaleEnhance(imageData);
        for (const [label, data, maxIter] of [
            ['jsQR', enhanced.data, 20], ['raw', imageData.data, 15],
            ['inv', inverted(enhanced.data), 12], ['raw-inv', inverted(imageData.data), 10]
        ]) {
            const r = scanQrIterative(data, w, h, label, maxIter);
            if (r) { insertUnique(merged, r); break; }
        }
    }

    // ====== Phase 2: Fast preprocessing (jsQR only, ~15 variants < 300ms total) ======
    if (merged.length === 0) {
        for (const variant of fastVariants) {
            if (jsqrQuick(variant)) break;
        }
    }

    // ====== Phase 3: Geometric correction ======
    if (merged.length === 0) {
        if (wantQr) {
            // QR: jsQR useless on cylinder distortion → BD on ALL curvature values
            for (const variant of correctedVariants) {
                const cv = toCanvas(variant.data);
                if (await bdOnCanvas(cv, variant.tag)) break;
            }
        } else {
            // Barcode: jsQR first (works), BD on first 3 + perspective
            let geoBdCount = 0;
            for (const variant of correctedVariants) {
                if (jsqrQuick(variant)) break;
                if (geoBdCount < 3 || variant.tag.includes('persp')) {
                    const cv = toCanvas(variant.data);
                    if (await bdOnCanvas(cv, variant.tag)) break;
                    geoBdCount++;
                }
            }
        }
    }

    // ====== Phase 4: Original BarcodeDetector result (awaited from Phase 1) ======
    if (merged.length === 0) {
        await bdPromise;  // Already ran, just awaiting
    }

    // ====== Phase 5: Full sweep (stubborn images only) ======
    if (merged.length === 0) {
        for (const variant of fullVariants) {
            if (wantQr && jsqrQuick(variant)) break;
        }
        // If still nothing, try BD on full variants too
        if (merged.length === 0) {
            for (const variant of fullVariants.slice(0, 8)) {
                const cv = toCanvas(variant.data);
                if (await bdOnCanvas(cv, variant.tag)) break;
            }
        }
    }

    if (merged.length > 0) return merged;

    if (merged.length > 0) return merged;

    // ====== Final fallback: Speckle removal + region scan ======
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
        const text = normalizeText(r.text);
        if (!isValidDecodedText(text)) continue;
        if (!hasText(dest, text)) {
            r.text = text;
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

// ============================================================================
// Geometric Correction v2.0.1 — Cylinder Unwarp + Perspective Normalize
// Ported from Python advanced_cv_scanner.py to JavaScript for mobile app
// ============================================================================

const GeoCorrect = {
    /**
     * Estimate cylinder curvature from image content aspect ratio.
     * A square QR code compressed horizontally by cylinder projection
     * has aspect ratio = contentWidth / contentHeight ≈ sinc(c*PI).
     */
    estimateCurvature(imageData) {
        const w = imageData.width, h = imageData.height;
        const d = imageData.data;
        // Find content bounding box (non-white pixels)
        let minX = w, maxX = 0, minY = h, maxY = 0;
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const i = (y * w + x) * 4;
                const gray = d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114;
                if (gray < 240) {
                    if (x < minX) minX = x;
                    if (x > maxX) maxX = x;
                    if (y < minY) minY = y;
                    if (y > maxY) maxY = y;
                }
            }
        }
        const cw = maxX - minX + 1, ch = maxY - minY + 1;
        if (cw < 30 || ch < 30) return 0.15;
        const ratio = Math.min(cw / Math.max(ch, 1), 1.0);
        // Invert sinc(c*PI + 0.01) = ratio via lookup
        let bestC = 0.15, bestDiff = 999;
        for (let c = 0.04; c <= 0.45; c += 0.01) {
            const arg = c * Math.PI + 0.01;
            const expected = arg > 0.001 ? Math.sin(arg) / arg : 1.0;
            const diff = Math.abs(expected - ratio);
            if (diff < bestDiff) { bestDiff = diff; bestC = c; }
        }
        return Math.max(0.04, Math.min(0.45, bestC));
    },

    /**
     * Horizontal-only cylinder inverse unwarp for 1D barcodes.
     * Forward:  x' = cx + R * sin((x - cx) / R),  y' = y
     * Inverse:  x  = cx + R * arcsin((x' - cx) / R),  y = y'
     */
    unwarpBarcode(imageData, curvature) {
        const w = imageData.width, h = imageData.height;
        const src = imageData.data;
        const out = new ImageData(w, h);
        const dst = out.data;
        const cx = w / 2.0;
        const R = Math.max(w * 0.3, w / (curvature * Math.PI * 2 + 0.01));

        for (let y = 0; y < h; y++) {
            const row = y * w;
            for (let xDst = 0; xDst < w; xDst++) {
                const dxNorm = Math.max(-0.9999, Math.min(0.9999, (xDst - cx) / R));
                const xSrc = Math.round(cx + R * Math.asin(dxNorm));
                const sx = Math.max(0, Math.min(w - 1, xSrc));
                const si = (row + sx) * 4;
                const di = (row + xDst) * 4;
                dst[di] = src[si];
                dst[di + 1] = src[si + 1];
                dst[di + 2] = src[si + 2];
                dst[di + 3] = 255;
            }
        }
        return out;
    },

    /**
     * Full cylinder inverse unwarp for QR codes.
     * Forward:  x' = cx + R*sin((x-cx)/R), y' = cy + (y-cy)*R/sqrt(R²+(x-cx)²)
     * Inverse:  x  = cx + R*arcsin((x'-cx)/R), y = cy + (y'-cy)*sqrt(1+arcsin²)
     */
    unwarpQR(imageData, curvature) {
        const w = imageData.width, h = imageData.height;
        const src = imageData.data;
        const out = new ImageData(w, h);
        const dst = out.data;
        const cx = w / 2.0, cy = h / 2.0;
        const R = Math.max(50, (w / 2) / (curvature * Math.PI + 0.01));

        for (let yDst = 0; yDst < h; yDst++) {
            for (let xDst = 0; xDst < w; xDst++) {
                const dxNorm = Math.max(-0.9999, Math.min(0.9999, (xDst - cx) / R));
                const arcTerm = Math.asin(dxNorm);
                const xSrc = Math.round(cx + R * arcTerm);
                const depthFactor = Math.sqrt(1.0 + arcTerm * arcTerm);
                const ySrc = Math.round(cy + (yDst - cy) * depthFactor);
                const sx = Math.max(0, Math.min(w - 1, xSrc));
                const sy = Math.max(0, Math.min(h - 1, ySrc));
                const si = (sy * w + sx) * 4;
                const di = (yDst * w + xDst) * 4;
                dst[di] = src[si];
                dst[di + 1] = src[si + 1];
                dst[di + 2] = src[si + 2];
                dst[di + 3] = 255;
            }
        }
        return out;
    },

    /**
     * Detect and normalize perspective distortion in barcode images.
     * Uses row-variance to find barcode region boundaries, then applies
     * inverse perspective (homography) to flatten.
     */
    normalizePerspective(imageData) {
        const w = imageData.width, h = imageData.height;
        if (w < h * 1.2) return imageData;  // Only for wide (barcode-like) images

        const d = imageData.data;
        const topPts = [], botPts = [];
        const step = Math.max(1, Math.floor(w / 30));

        for (let x = 0; x < w; x += step) {
            // Compute row variances for this column slice
            const window = 15;
            const variances = [];
            for (let y = 0; y < h - window; y++) {
                let sum = 0, sumSq = 0;
                for (let dy = 0; dy < window; dy++) {
                    const idx = ((y + dy) * w + x) * 4;
                    const gray = d[idx] * 0.299 + d[idx + 1] * 0.587 + d[idx + 2] * 0.114;
                    sum += gray; sumSq += gray * gray;
                }
                const mean = sum / window;
                variances.push(sumSq / window - mean * mean);
            }
            const maxVar = Math.max(...variances);
            if (maxVar > 80) {
                const thresh = maxVar * 0.25;
                let first = -1, last = -1;
                for (let i = 0; i < variances.length; i++) {
                    if (variances[i] > thresh) { if (first < 0) first = i; last = i; }
                }
                if (first >= 0) {
                    topPts.push([x, first + Math.floor(window / 2)]);
                    botPts.push([x, last + Math.floor(window / 2)]);
                }
            }
        }

        if (topPts.length < 10) return imageData;

        // Fit quadratic polynomial to boundary points
        try {
            const topPoly = fitQuadratic(topPts);
            const botPoly = fitQuadratic(botPts);
            if (!topPoly || !botPoly) return imageData;

            const tl = clamp(topPoly(0), 0, h - 1), tr = clamp(topPoly(w - 1), 0, h - 1);
            const bl = clamp(botPoly(0), 0, h - 1), br = clamp(botPoly(w - 1), 0, h - 1);

            const lh = Math.abs(bl - tl), rh = Math.abs(br - tr);
            if (Math.min(lh, rh) < 10 || Math.max(lh, rh) / Math.max(Math.min(lh, rh), 1) < 1.25) {
                return imageData;
            }

            // Inverse perspective using 2D remap
            const out = new ImageData(w, h);
            const od = out.data;
            const targetH = Math.min(h, Math.floor(Math.max(lh, rh) * 1.3));

            // Build homography from src->dst: map irregular quad to rectangle
            const srcPts = [[0, tl], [w - 1, tr], [w - 1, br], [0, bl]];
            const dstPts = [[0, 0], [w - 1, 0], [w - 1, targetH - 1], [0, targetH - 1]];
            const H = computeHomography(dstPts, srcPts);  // inverse: dst->src

            for (let y = 0; y < targetH; y++) {
                for (let x = 0; x < w; x++) {
                    const [sx, sy] = applyHomography(H, x, y);
                    const isx = clamp(Math.round(sx), 0, w - 1);
                    const isy = clamp(Math.round(sy), 0, h - 1);
                    const si = (isy * w + isx) * 4;
                    const di = (y * w + x) * 4;
                    od[di] = d[si]; od[di + 1] = d[si + 1]; od[di + 2] = d[si + 2]; od[di + 3] = 255;
                }
            }
            // Fill remaining rows with white
            for (let y = targetH; y < h; y++) {
                for (let x = 0; x < w; x++) {
                    const di = (y * w + x) * 4;
                    od[di] = 255; od[di + 1] = 255; od[di + 2] = 255; od[di + 3] = 255;
                }
            }
            return out;
        } catch {
            return imageData;
        }
    },

    /**
     * Try multiple curvature values and return all unwarped images.
     */
    unwarpBarcodeMulti(imageData) {
        const results = [];
        const curvatures = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35];
        for (const c of curvatures) {
            results.push({ curvature: c, data: this.unwarpBarcode(imageData, c) });
        }
        return results;
    },

    unwarpQRMulti(imageData) {
        const results = [];
        // Full-range sweep (19 values) — curvature estimation unreliable for padded images
        // Generator uses curvature 0.08-0.35, sweep wider to cover edge cases
        for (let c = 0.04; c <= 0.40; c += 0.02) {
            results.push({ curvature: c, data: this.unwarpQR(imageData, c) });
        }
        return results;
    },

    /**
     * Extract content fragments from torn/split images.
     * Detects connected non-white regions and returns each as a separate ImageData.
     * Ported from Python AdvancedCVScanner V12 multi-fragment splitting.
     */
    extractFragments(imageData) {
        const w = imageData.width, h = imageData.height, src = imageData.data;
        // Binary: non-white (gray < 250) = content, white = background
        const bin = new Uint8Array(w * h);
        for (let i = 0; i < w * h; i++) {
            const gray = src[i * 4] * 0.299 + src[i * 4 + 1] * 0.587 + src[i * 4 + 2] * 0.114;
            bin[i] = gray < 250 ? 1 : 0;
        }

        // BFS connected components
        const labels = new Int32Array(w * h).fill(-1);
        let nextLabel = 0;
        const fragments = [];  // {x, y, w, h, label}

        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const idx = y * w + x;
                if (bin[idx] !== 1 || labels[idx] >= 0) continue;

                // BFS this component
                const queue = [[x, y]];
                labels[idx] = nextLabel;
                let minX = x, maxX = x, minY = y, maxY = y;
                let qi = 0;
                while (qi < queue.length) {
                    const [cx, cy] = queue[qi++];
                    for (const [dx, dy] of [[0, 1], [1, 0], [0, -1], [-1, 0], [1, 1], [-1, 1], [1, -1], [-1, -1]]) {
                        const nx = cx + dx, ny = cy + dy;
                        if (nx >= 0 && nx < w && ny >= 0 && ny < h) {
                            const ni = ny * w + nx;
                            if (bin[ni] === 1 && labels[ni] < 0) {
                                labels[ni] = nextLabel;
                                queue.push([nx, ny]);
                                if (nx < minX) minX = nx; if (nx > maxX) maxX = nx;
                                if (ny < minY) minY = ny; if (ny > maxY) maxY = ny;
                            }
                        }
                    }
                }

                const area = (maxX - minX + 1) * (maxY - minY + 1);
                if (area > 1000 && queue.length > 50) {
                    fragments.push({ x: minX, y: minY, w: maxX - minX + 1, h: maxY - minY + 1, label: nextLabel });
                }
                nextLabel++;
            }
        }

        if (fragments.length <= 1) return [];

        // Extract each fragment as ImageData
        const results = [];
        for (const frag of fragments) {
            if (frag.w < 25 || frag.h < 25) continue;
            const out = new ImageData(frag.w, frag.h);
            const dst = out.data;
            for (let fy = 0; fy < frag.h; fy++) {
                for (let fx = 0; fx < frag.w; fx++) {
                    const si = ((frag.y + fy) * w + (frag.x + fx)) * 4;
                    const di = (fy * frag.w + fx) * 4;
                    dst[di] = src[si]; dst[di + 1] = src[si + 1];
                    dst[di + 2] = src[si + 2]; dst[di + 3] = 255;
                }
            }
            results.push({ tag: `frag-${frag.label}`, data: out });
        }
        return results;
    }
};

// ---- Numerical helpers ----

function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }

function fitQuadratic(pts) {
    const n = pts.length;
    let sx = 0, sx2 = 0, sx3 = 0, sx4 = 0, sy = 0, sxy = 0, sx2y = 0;
    for (const [x, y] of pts) {
        const x2 = x * x;
        sx += x; sx2 += x2; sx3 += x2 * x; sx4 += x2 * x2;
        sy += y; sxy += x * y; sx2y += x2 * y;
    }
    const denom = n * (sx2 * sx4 - sx3 * sx3) - sx * (sx * sx4 - sx2 * sx3) + sx2 * (sx * sx3 - sx2 * sx2);
    if (Math.abs(denom) < 1e-9) return null;
    const a = (n * (sx2 * sx2y - sx3 * sxy) - sx * (sx * sx2y - sx2 * sxy) + sx2 * (sx * sxy - sx2 * sy)) / denom;
    const b = (n * (sx4 * sxy - sx3 * sx2y) - sx2 * (sx2 * sxy - sx * sx2y) + sx * (sx2 * sx2y - sx * sxy)) / denom;
    const c_val = (sy - a * sx2 - b * sx) / n;
    return x => a * x * x + b * x + c_val;
}

function computeHomography(srcPts, dstPts) {
    // Solve for H (3x3) mapping src (4 corners) -> dst (4 corners)
    // |x'|   |h11 h12 h13| |x|
    // |y'| = |h21 h22 h23| |y|   with h33=1
    // |w'|   |h31 h32  1 | |1|
    const A = [];
    const B = [];
    for (let i = 0; i < 4; i++) {
        const [sx, sy] = srcPts[i];
        const [dx, dy] = dstPts[i];
        A.push([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy]);
        A.push([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy]);
        B.push(dx, dy);
    }
    // Solve linear system A * h = B using Gaussian elimination
    const n = 8;
    const M = A.map((row, i) => [...row, B[i]]);
    for (let col = 0; col < n; col++) {
        let pivot = col;
        for (let row = col; row < n; row++) {
            if (Math.abs(M[row][col]) > Math.abs(M[pivot][col])) pivot = row;
        }
        [M[col], M[pivot]] = [M[pivot], M[col]];
        const pv = M[col][col];
        if (Math.abs(pv) < 1e-9) continue;
        for (let j = col; j <= n; j++) M[col][j] /= pv;
        for (let row = 0; row < n; row++) {
            if (row === col) continue;
            const f = M[row][col];
            for (let j = col; j <= n; j++) M[row][j] -= f * M[col][j];
        }
    }
    return [M[0][8], M[1][8], M[2][8], M[3][8], M[4][8], M[5][8], M[6][8], M[7][8], 1.0];
}

function applyHomography(H, x, y) {
    const h11 = H[0], h12 = H[1], h13 = H[2];
    const h21 = H[3], h22 = H[4], h23 = H[5];
    const h31 = H[6], h32 = H[7], h33 = H[8];
    const w = h31 * x + h32 * y + h33;
    const sx = (h11 * x + h12 * y + h13) / w;
    const sy = (h21 * x + h22 * y + h23) / w;
    return [sx, sy];
}

// ============ PWA Registration ============
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('sw.js').catch(() => {});
    });
}
