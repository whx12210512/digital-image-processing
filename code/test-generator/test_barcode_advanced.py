"""Headless batch test for the 54 new barcode degradation images."""
import sys, os, time
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'image-processing'))

from preprocess import preprocess
from localize import localize
from correct import correct_region
from decode import decode_all

TEST_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'images', 'test_images')

# Collect only new barcode degradation images
PATTERNS = ['_perspective_', '_occluded', '_lighting_', '_complex_bg']

def run_pipeline(img):
    gray, binary, enhanced = preprocess(img, adaptive=True)
    loc_result = localize(img, binary, enhanced)
    corrected = correct_region(img, loc_result)
    results = decode_all(corrected)

    if not results:
        try:
            from pyzbar.pyzbar import decode as pyzbar_decode
            gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            def try_pyzbar(image):
                res = pyzbar_decode(image)
                if res:
                    return [{'text': r.data.decode('utf-8', errors='replace'),
                             'type': r.type, 'confidence': 0.75} for r in res]
                return []

            results = try_pyzbar(gray)
            if not results:
                for ks in [3, 5, 7]:
                    results = try_pyzbar(cv2.medianBlur(gray, ks))
                    if results: break
            if not results:
                results = try_pyzbar(cv2.bilateralFilter(gray, 9, 75, 75))
            if not results:
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
                results = try_pyzbar(cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel))
            if not results:
                h, w = gray.shape[:2]
                center = (w // 2, h // 2)
                for angle in [15, -15, 30, -30]:
                    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
                    rotated = cv2.warpAffine(gray, rot_mat, (w, h),
                                             borderMode=cv2.BORDER_CONSTANT, borderValue=255)
                    results = try_pyzbar(rotated)
                    if results: break
            if not results:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced_gray = clahe.apply(gray)
                results = try_pyzbar(enhanced_gray)
                if not results:
                    results = try_pyzbar(cv2.GaussianBlur(enhanced_gray, (3, 3), 0))
            if not results:
                for block in [21, 31, 41]:
                    for c in [5, 9, 13]:
                        bina = cv2.adaptiveThreshold(gray, 255,
                            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, c)
                        results = try_pyzbar(bina)
                        if results: break
                    if results: break
            if not results:
                inv = cv2.adaptiveThreshold(gray, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 9)
                results = try_pyzbar(inv)
        except ImportError:
            pass
    return results

def main():
    files = sorted([
        f for f in os.listdir(TEST_DIR)
        if f.startswith('barcode_') and any(p in f for p in PATTERNS) and f.endswith('.png')
    ])

    print(f"Testing {len(files)} barcode degradation images...\n")

    stats = {}
    total_pass, total_fail = 0, 0
    t0 = time.time()

    for fname in files:
        img = cv2.imread(os.path.join(TEST_DIR, fname))
        results = run_pipeline(img)

        # Parse category
        for p in PATTERNS:
            if p in fname:
                cat = p.strip('_')
                break
        else:
            cat = 'other'

        btype = fname.split('_')[1]  # ean13, code128, code39
        key = f"{btype}/{cat}"

        if key not in stats:
            stats[key] = {'pass': 0, 'fail': 0, 'failed_files': []}

        if results:
            stats[key]['pass'] += 1
            total_pass += 1
            status = 'PASS'
            detail = results[0]['text'][:40]
        else:
            stats[key]['fail'] += 1
            total_fail += 1
            status = 'FAIL'
            detail = '---'
            stats[key]['failed_files'].append(fname)

        print(f"  [{status}] {key:30s} | {fname:45s} | {detail}")

    elapsed = time.time() - t0

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY: {total_pass}/{total_pass+total_fail} passed ({total_fail} failed) in {elapsed:.1f}s")
    print(f"{'='*70}")

    for key in sorted(stats.keys()):
        s = stats[key]
        pct = s['pass'] / (s['pass'] + s['fail']) * 100 if (s['pass'] + s['fail']) > 0 else 0
        bar = '#' * int(pct / 10) + ' ' * (10 - int(pct / 10))
        print(f"  {key:30s} | [{bar}] {pct:5.1f}%  ({s['pass']}/{s['pass']+s['fail']})")

    if total_fail > 0:
        print(f"\nFailed files:")
        for key in sorted(stats.keys()):
            for f in stats[key]['failed_files']:
                print(f"  {f}")

if __name__ == '__main__':
    main()
