#!/usr/bin/env python
"""
Multi-Engine Stress Test Suite v2.0.0 — Tiered Approach
========================================================
Digital Image Processing — QR/Barcode Recognition

Tier 1: pyzbar (fast) — all categories
Tier 2: cv2.QRCodeDetector — categories with pyzbar < 90%
Tier 3: AdvancedCVScanner — categories with Tier1+2 < 80%
"""
import cv2
import numpy as np
from pyzbar.pyzbar import decode as pyzbar_decode
from PIL import Image
import os, sys, json, time, csv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'code', 'image-processing'))
from advanced_cv_scanner import (AdvancedCVScanner, PerspectiveBarcodeNormalizer,
                                  CylindricalUnwarper)


def engine_pyzbar(bgr):
    """Tier 1: pyzbar with comprehensive preprocessing for both QR and barcode."""
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
    except:
        return []

    def try_decode(img):
        if len(img.shape) == 2:
            pil = Image.fromarray(img).convert('RGB')
        else:
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        res = pyzbar_decode(pil)
        return [(r.data.decode('utf-8', errors='replace').strip(), r.type) for r in res]

    r = try_decode(bgr)
    if r: return [('pyzbar', r[0][0], r[0][1])]

    # Median denoise
    for ks in [3, 5]:
        r = try_decode(cv2.cvtColor(cv2.medianBlur(gray, ks), cv2.COLOR_GRAY2BGR))
        if r: return [('pyzbar_median', r[0][0], r[0][1])]

    # CLAHE
    for clip in [2.0, 3.0]:
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
        r = try_decode(cv2.cvtColor(clahe.apply(gray), cv2.COLOR_GRAY2BGR))
        if r: return [('pyzbar_clahe', r[0][0], r[0][1])]

    # Adaptive threshold — wide range
    for bs in [21, 31, 41, 51]:
        for c in [3, 5, 9, 13]:
            binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bs, c)
            r = try_decode(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR))
            if r: return [('pyzbar_adap', r[0][0], r[0][1])]

    # Otsu
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    r = try_decode(cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR))
    if r: return [('pyzbar_otsu', r[0][0], r[0][1])]

    # Bilateral filter
    bilat = cv2.bilateralFilter(gray, 9, 75, 75)
    r = try_decode(cv2.cvtColor(bilat, cv2.COLOR_GRAY2BGR))
    if r: return [('pyzbar_bilateral', r[0][0], r[0][1])]

    # Heavy denoise: median + bilateral combo
    m5 = cv2.medianBlur(gray, 5)
    bi2 = cv2.bilateralFilter(m5, 7, 50, 50)
    r = try_decode(cv2.cvtColor(bi2, cv2.COLOR_GRAY2BGR))
    if r: return [('pyzbar_heavy_denoise', r[0][0], r[0][1])]

    # Aggressive morphological opening (remove noise dots)
    for ks in [3, 5]:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
        opened = cv2.morphologyEx(gray, cv2.MORPH_OPEN, k)
        r = try_decode(cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR))
        if r: return [('pyzbar_open', r[0][0], r[0][1])]

    # Morph close for reconnecting broken bars (barcode)
    for ks_h in [1, 3, 5]:
        for ks_w in [3, 5, 7]:
            k = cv2.getStructuringElement(cv2.MORPH_RECT, (ks_w, ks_h))
            closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, k)
            r = try_decode(cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR))
            if r: return [('pyzbar_morph', r[0][0], r[0][1])]

    # If image is wider than tall (potential barcode), try perspective normalization
    if w > h * 1.5:
        try:
            norm = PerspectiveBarcodeNormalizer.normalize_perspective(bgr)
            if norm is not None and norm.shape != bgr.shape:
                r = try_decode(norm)
                if r: return [('pyzbar_persp_norm', r[0][0], r[0][1])]
                ng = cv2.cvtColor(norm, cv2.COLOR_BGR2GRAY)
                nb = cv2.adaptiveThreshold(ng, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 4)
                r = try_decode(cv2.cvtColor(nb, cv2.COLOR_GRAY2BGR))
                if r: return [('pyzbar_persp_bin', r[0][0], r[0][1])]
        except: pass

    # Try cylindrical unwarping for curved barcodes
    try:
        unwarped = CylindricalUnwarper.unwarp(bgr)
        r = try_decode(unwarped)
        if r: return [('pyzbar_unwarped', r[0][0], r[0][1])]
    except: pass

    # Inverted binary (white-on-black)
    inv = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 9)
    r = try_decode(cv2.cvtColor(inv, cv2.COLOR_GRAY2BGR))
    if r: return [('pyzbar_inv', r[0][0], r[0][1])]

    return []


def engine_cv2_qr(bgr):
    """Tier 2: OpenCV QRCodeDetector."""
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        det = cv2.QRCodeDetector()
        data, points, _ = det.detectAndDecode(gray)
        if data: return [('cv2qr', data.strip(), 'QRCODE')]
        for bs in [21, 31]:
            for c in [5, 9]:
                binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bs, c)
                data2, _, _ = det.detectAndDecode(binary)
                if data2: return [('cv2qr_bin', data2.strip(), 'QRCODE')]
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        data3, _, _ = det.detectAndDecode(clahe.apply(gray))
        if data3: return [('cv2qr_clahe', data3.strip(), 'QRCODE')]
    except: pass
    return []


_scanner = None
def get_scanner():
    global _scanner
    if _scanner is None: _scanner = AdvancedCVScanner()
    return _scanner


def engine_advcv(bgr):
    """Tier 3: Custom AdvancedCVScanner."""
    try:
        scanner = get_scanner()
        results = scanner.process_and_decode(bgr)
        out = []
        for r in results:
            text = r[0] if isinstance(r, (list, tuple)) else str(r)
            if text and len(text) >= 2:
                out.append(('advcv', text, 'MIXED'))
        return out
    except: return []


def test_image(image_path, engines_to_use):
    """Test single image with specified engines."""
    bgr = cv2.imread(image_path)
    if bgr is None:
        return {'file': image_path, 'error': 'Cannot read', 'results': [], 'success': False}

    all_results = []
    if 'pyzbar' in engines_to_use:
        all_results.extend(engine_pyzbar(bgr))
    if 'cv2qr' in engines_to_use:
        all_results.extend(engine_cv2_qr(bgr))
    if 'advcv' in engines_to_use:
        all_results.extend(engine_advcv(bgr))

    return {
        'file': image_path,
        'results': all_results,
        'success': len(all_results) > 0,
        'num_engines': len(set(r[0] for r in all_results))
    }


def run_category(category_path, category_name, engines):
    """Run test on a category with given engines."""
    files = sorted([f for f in os.listdir(category_path)
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))])
    total = len(files)
    results = []
    success_count = 0

    for i, fname in enumerate(files):
        fpath = os.path.join(category_path, fname)
        r = test_image(fpath, engines)
        results.append(r)
        if r['success']:
            success_count += 1
        if (i + 1) % max(1, total // 5) == 0:
            pct = (i+1)/total*100
            print(f"  [{category_name}] {i+1}/{total} ({pct:.0f}%) — ok={success_count} ({success_count/(i+1)*100:.1f}%)")

    pct = success_count / total * 100 if total > 0 else 0
    return results, pct


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    stress_dir = os.path.join(root_dir, 'images', 'stress_test')
    results_dir = os.path.join(root_dir, 'results')
    os.makedirs(results_dir, exist_ok=True)

    categories = sorted([d for d in os.listdir(stress_dir) if os.path.isdir(os.path.join(stress_dir, d))])
    print("=" * 70)
    print("  MULTI-ENGINE STRESS TEST — TIERED APPROACH")
    print(f"  Categories: {len(categories)}  |  Engines: pyzbar → cv2QR → AdvCV")
    print("=" * 70)

    all_stats = []
    start = time.time()

    # =====================================================================
    # TIER 1: pyzbar on ALL categories
    # =====================================================================
    print("\n[TIER 1] Running pyzbar on ALL categories...\n")
    tier1_results = {}
    tier1_stats = {}

    for cat in categories:
        cat_path = os.path.join(stress_dir, cat)
        n = len([f for f in os.listdir(cat_path) if f.lower().endswith(('.png','.jpg','.jpeg','.bmp'))])
        print(f"  {cat} ({n} images)")
        res, pct = run_category(cat_path, cat, {'pyzbar'})
        tier1_results[cat] = res
        tier1_stats[cat] = {'total': n, 'pyzbar_pct': pct, 'pyzbar_ok': int(n * pct / 100)}
        print(f"    → pyzbar: {pct:.1f}%")

    # =====================================================================
    # TIER 2: cv2.QRCodeDetector on categories with pyzbar < 90%
    # =====================================================================
    print("\n[TIER 2] Running cv2.QRCodeDetector on categories where pyzbar < 90%\n")
    tier2_added = {}

    for cat in categories:
        pyzbar_pct = tier1_stats[cat]['pyzbar_pct']
        if pyzbar_pct < 90.0:
            cat_path = os.path.join(stress_dir, cat)
            print(f"  {cat} (pyzbar={pyzbar_pct:.1f}%)")
            n = tier1_stats[cat]['total']
            res, pct = run_category(cat_path, cat, {'pyzbar', 'cv2qr'})
            tier1_results[cat] = res
            tier2_added[cat] = pct
            tier1_stats[cat]['tier2_pct'] = pct
            tier1_stats[cat]['tier2_ok'] = int(n * pct / 100)
            print(f"    → pyzbar+cv2QR: {pct:.1f}% (delta: {pct-pyzbar_pct:+.1f}%)")
        else:
            tier1_stats[cat]['tier2_pct'] = pyzbar_pct
            tier1_stats[cat]['tier2_ok'] = tier1_stats[cat]['pyzbar_ok']

    # =====================================================================
    # TIER 3: AdvancedCVScanner on categories still < 80%
    # =====================================================================
    print("\n[TIER 3] Running AdvancedCVScanner on categories still < 80%\n")
    tier3_added = {}

    for cat in categories:
        current_pct = tier1_stats[cat]['tier2_pct']
        if current_pct < 80.0:
            cat_path = os.path.join(stress_dir, cat)
            print(f"  {cat} (tier2={current_pct:.1f}%)")
            n = tier1_stats[cat]['total']
            res, pct = run_category(cat_path, cat, {'pyzbar', 'cv2qr', 'advcv'})
            tier1_results[cat] = res
            tier3_added[cat] = pct
            tier1_stats[cat]['tier3_pct'] = pct
            tier1_stats[cat]['tier3_ok'] = int(n * pct / 100)
            print(f"    → pyzbar+cv2QR+AdvCV: {pct:.1f}% (delta: {pct-current_pct:+.1f}%)")
        else:
            tier1_stats[cat]['tier3_pct'] = current_pct
            tier1_stats[cat]['tier3_ok'] = int(tier1_stats[cat]['total'] * current_pct / 100)

    elapsed = time.time() - start

    # =====================================================================
    # SUMMARY TABLE
    # =====================================================================
    print("\n" + "=" * 90)
    print("  FINAL RESULTS — Multi-Engine Stress Test")
    print("=" * 90)
    header = f"{'Category':<28} {'Total':>5} {'pyzbar':>8} {'+cv2QR':>8} {'+AdvCV':>8} {'Status'}"
    print(header)
    print("-" * 90)

    low_acc = []
    for cat in categories:
        s = tier1_stats[cat]
        final_pct = s['tier3_pct']
        if final_pct >= 90: status = "PASS"
        elif final_pct >= 80: status = "WARN"
        else:
            status = "FAIL"
            low_acc.append({'category': cat, 'accuracy': final_pct, 'total': s['total'],
                           'pyzbar': s['pyzbar_pct'], 'tier2': s['tier2_pct'], 'final': final_pct})

        print(f"{cat:<28} {s['total']:>5} {s['pyzbar_pct']:>7.1f}% {s['tier2_pct']:>7.1f}% {final_pct:>7.1f}% {status}")

    grand_total = sum(s['total'] for s in tier1_stats.values())
    grand_final = sum(s['tier3_ok'] for s in tier1_stats.values())
    print("-" * 90)
    print(f"{'OVERALL':<28} {grand_total:>5} {'':>8} {'':>8} {grand_final/grand_total*100:>7.1f}%")
    print(f"\nElapsed: {elapsed:.1f}s")

    if low_acc:
        print(f"\n⚠  BELOW 80% ACCURACY ({len(low_acc)} categories):")
        for s in low_acc:
            print(f"   - {s['category']}: {s['final']:.1f}% (pyzbar={s['pyzbar']:.1f}%, +cv2QR={s['tier2']:.1f}%)")

    # Save results
    json_path = os.path.join(results_dir, 'stress_test_results.json')
    summary = {
        'meta': {'version': '2.0.0', 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                 'elapsed': elapsed, 'engines': ['pyzbar', 'cv2.QRCodeDetector', 'AdvancedCVScanner'],
                 'total_images': grand_total, 'total_categories': len(categories)},
        'category_stats': {cat: tier1_stats[cat] for cat in categories},
        'low_accuracy': low_acc,
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nJSON saved: {json_path}")

    csv_path = os.path.join(results_dir, 'stress_test_summary.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['category', 'total', 'pyzbar_pct', 'tier2_pct', 'tier3_pct',
                     'pyzbar_ok', 'tier2_ok', 'tier3_ok'])
        for cat in categories:
            s = tier1_stats[cat]
            w.writerow([cat, s['total'], round(s['pyzbar_pct'],1), round(s['tier2_pct'],1),
                       round(s['tier3_pct'],1), s['pyzbar_ok'], s['tier2_ok'], s['tier3_ok']])
    print(f"CSV saved: {csv_path}")

    return tier1_stats, low_acc


if __name__ == '__main__':
    main()
