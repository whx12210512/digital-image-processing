#!/usr/bin/env python
"""Fast stress test — only the 4 categories still below 80% from previous tests."""
import os, sys, time, json, csv, warnings
warnings.filterwarnings('ignore')
import cv2, numpy as np
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'code', 'image-processing'))
from advanced_cv_scanner import (AdvancedCVScanner, PerspectiveBarcodeNormalizer, CylindricalUnwarper)

CATEGORIES = ['barcode_geometric', 'damage_noise', 'edge_tear', 'multi_qr']

def engine_pyzbar_enhanced(bgr):
    """Comprehensive pyzbar with heavy preprocessing."""
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
    except:
        return []

    def td(img):
        if len(img.shape) == 2:
            pil = Image.fromarray(img).convert('RGB')
        else:
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        res = pyzbar_decode(pil)
        if not res: return []
        out = []
        for r in res:
            try:
                text = r.data.decode('utf-8', errors='replace').strip()
            except:
                text = str(r.data)
            out.append((text, r.type))
        return out

    r = td(bgr)
    if r: return r

    # Denoising pipeline
    for ks in [3, 5, 7]:
        r = td(cv2.cvtColor(cv2.medianBlur(gray, ks), cv2.COLOR_GRAY2BGR))
        if r: return r
    r = td(cv2.cvtColor(cv2.bilateralFilter(gray, 9, 75, 75), cv2.COLOR_GRAY2BGR))
    if r: return r
    m5 = cv2.medianBlur(gray, 5)
    r = td(cv2.cvtColor(cv2.bilateralFilter(m5, 7, 50, 50), cv2.COLOR_GRAY2BGR))
    if r: return r

    # CLAHE
    for clip in [2.0, 3.0, 4.0]:
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
        r = td(cv2.cvtColor(clahe.apply(gray), cv2.COLOR_GRAY2BGR))
        if r: return r

    # Adaptive threshold sweep
    for bs in [21, 31, 41, 51]:
        for c in [3, 5, 7, 9, 13]:
            binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bs, c)
            r = td(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR))
            if r: return r

    # Otsu
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    r = td(cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR))
    if r: return r

    # Morphological
    for ks_w, ks_h in [(3, 1), (5, 1), (7, 1), (3, 3), (5, 5), (7, 7)]:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (ks_w, ks_h))
        closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, k)
        r = td(cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR))
        if r: return r

    # Morphological opening for noise removal
    for ks in [3, 5]:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
        opened = cv2.morphologyEx(gray, cv2.MORPH_OPEN, k)
        r = td(cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR))
        if r: return r

    # Perspective normalization for barcode-like images
    if w > h * 1.3:
        try:
            norm = PerspectiveBarcodeNormalizer.normalize_perspective(bgr)
            if norm is not None:
                r = td(norm)
                if r: return r
                ng = cv2.cvtColor(norm, cv2.COLOR_BGR2GRAY)
                for bs in [15, 21, 31]:
                    nb = cv2.adaptiveThreshold(ng, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bs, 4)
                    r = td(cv2.cvtColor(nb, cv2.COLOR_GRAY2BGR))
                    if r: return r
        except: pass

    # Cylindrical unwarping
    try:
        unw = CylindricalUnwarper.unwarp(bgr)
        r = td(unw)
        if r: return r
    except: pass

    # Inverted
    inv = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 9)
    r = td(cv2.cvtColor(inv, cv2.COLOR_GRAY2BGR))
    if r: return r

    return []


def engine_cv2qr(bgr):
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        det = cv2.QRCodeDetector()
        data, _, _ = det.detectAndDecode(gray)
        if data: return [data.strip()]
        for bs in [21, 31]:
            for c in [5, 9]:
                binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bs, c)
                data2, _, _ = det.detectAndDecode(binary)
                if data2: return [data2.strip()]
    except: pass
    return []

_scanner = None
def engine_advcv(image_path_or_bgr):
    global _scanner
    if _scanner is None: _scanner = AdvancedCVScanner()
    try:
        if isinstance(image_path_or_bgr, str):
            results = _scanner.process_and_decode(image_path_or_bgr)
        else:
            h, w = image_path_or_bgr.shape[:2]
            results = _scanner.process_and_decode(image_path_or_bgr)
        out = []
        for r in results:
            text = r[0] if isinstance(r, (list, tuple)) else str(r)
            if text and len(text) >= 2:
                out.append(text)
        return out
    except: return []


def test_image(img_path, engines):
    bgr = cv2.imread(img_path)
    if bgr is None: return {'file': img_path, 'error': True, 'success': False}

    success = False
    engines_used = []
    decoded_text = None

    if 'pyzbar' in engines:
        r = engine_pyzbar_enhanced(bgr)
        if r:
            success = True
            decoded_text = r[0][0]
            engines_used.append('pyzbar')

    if not success and 'cv2qr' in engines:
        r = engine_cv2qr(bgr)
        if r:
            success = True
            decoded_text = r[0]
            engines_used.append('cv2qr')

    if not success and 'advcv' in engines:
        r = engine_advcv(img_path)
        if r:
            success = True
            decoded_text = r[0]
            engines_used.append('advcv')

    return {'file': img_path, 'success': success, 'engines': engines_used, 'text': decoded_text}


def run_category(cat_name, engines):
    cat_path = os.path.join('images', 'stress_test', cat_name)
    files = sorted([f for f in os.listdir(cat_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    total = len(files)
    results = []
    ok = 0
    for i, fn in enumerate(files):
        r = test_image(os.path.join(cat_path, fn), engines)
        results.append(r)
        if r['success']: ok += 1
        if (i+1) % max(1, total//5) == 0:
            print(f"  [{cat_name}] {i+1}/{total} — ok={ok} ({ok/(i+1)*100:.1f}%)")
    pct = ok/total*100 if total > 0 else 0
    print(f"  [{cat_name}] FINAL: {ok}/{total} = {pct:.1f}%")
    return results, pct


def main():
    print("=" * 60)
    print("  TARGETED STRESS TEST — 4 Low-Performance Categories")
    print("=" * 60)

    tier1 = {}
    tier2 = {}
    tier3 = {}
    final_pct = {}

    # Tier 1: pyzbar enhanced
    print("\n[TIER 1] Enhanced pyzbar\n")
    for cat in CATEGORIES:
        results, pct = run_category(cat, {'pyzbar'})
        tier1[cat] = pct
        tier2[cat] = pct

    # Tier 2: +cv2QR where pyzbar < 90%
    print("\n[TIER 2] +cv2.QRCodeDetector\n")
    for cat in CATEGORIES:
        if tier1[cat] < 90.0:
            results, pct = run_category(cat, {'pyzbar', 'cv2qr'})
            tier2[cat] = pct
            if pct > tier1[cat]:
                print(f"    delta: {pct-tier1[cat]:+.1f}%")

    # Tier 3: +AdvCV where still < 80%
    print("\n[TIER 3] +AdvancedCVScanner\n")
    for cat in CATEGORIES:
        current = tier2[cat]
        if current < 80.0:
            results, pct = run_category(cat, {'pyzbar', 'cv2qr', 'advcv'})
            tier3[cat] = pct
            if pct > current:
                print(f"    delta: {pct-current:+.1f}%")
        else:
            tier3[cat] = current

    for cat in CATEGORIES:
        final_pct[cat] = tier3[cat]

    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    for cat in CATEGORIES:
        t1, t2, t3 = tier1[cat], tier2[cat], tier3[cat]
        status = "PASS" if t3 >= 80 else "FAIL"
        print(f"  {cat:<30}: pyzbar={t1:.1f}% +cv2QR={t2:.1f}% +AdvCV={t3:.1f}% [{status}]")

    # Save summary
    summary = {'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'), 'categories': {}}
    for cat in CATEGORIES:
        summary['categories'][cat] = {'tier1': tier1[cat], 'tier2': tier2[cat], 'tier3': tier3[cat]}
    with open('results/targeted_test.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("\nSaved: results/targeted_test.json")


if __name__ == '__main__':
    main()
