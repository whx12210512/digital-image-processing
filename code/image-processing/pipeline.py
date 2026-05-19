"""Main recognition pipeline integrating all modules.

Usage:
    python pipeline.py <image_path>
    python pipeline.py --camera
"""

import sys
import os
import time
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from preprocess import preprocess
from localize import localize
from correct import correct_region
from decode import decode_all


def run_pipeline(img, adaptive=True, visualize=False):
    """Run the complete barcode/QR recognition pipeline.

    Args:
        img: input image (BGR or grayscale)
        adaptive: use adaptive thresholding (True) or Otsu (False)
        visualize: return intermediate results for display

    Returns:
        results: list of {'text': ..., 'type': ..., 'confidence': ...}
        vis_data: dict of intermediate images (if visualize=True)
    """
    start_time = time.time()

    # Stage 1: Preprocessing
    gray, binary, enhanced = preprocess(img, adaptive=adaptive)
    t1 = time.time()

    # Stage 2: Localization
    loc_result = localize(img, binary, enhanced)
    t2 = time.time()

    # Stage 3: Geometric Correction
    corrected = correct_region(img, loc_result)
    t3 = time.time()

    # Stage 4: Decoding
    results = decode_all(corrected)

    # Stage 5: pyzbar fallback with multi-angle + denoise attempts
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

            # Try original gray
            results = try_pyzbar(gray)

            # Try with median filter (salt-and-pepper noise removal)
            if not results:
                for ks in [3, 5, 7]:
                    denoised = cv2.medianBlur(gray, ks)
                    results = try_pyzbar(denoised)
                    if results:
                        break

            # Try with bilateral filter (edge-preserving)
            if not results:
                bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
                results = try_pyzbar(bilateral)

            # Try morph close to reconnect broken bar patterns
            if not results:
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
                closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
                results = try_pyzbar(closed)

            # Try un-rotating for tilted barcodes
            if not results:
                h, w = gray.shape[:2]
                center = (w // 2, h // 2)
                for angle in [15, -15, 30, -30]:
                    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
                    rotated = cv2.warpAffine(gray, rot_mat, (w, h),
                                             borderMode=cv2.BORDER_CONSTANT, borderValue=255)
                    results = try_pyzbar(rotated)
                    if results:
                        break

            # Try CLAHE enhancement (improves local contrast for faded bars)
            if not results:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced_gray = clahe.apply(gray)
                results = try_pyzbar(enhanced_gray)
                if not results:
                    results = try_pyzbar(cv2.GaussianBlur(enhanced_gray, (3, 3), 0))

            # Try adaptive threshold binarization (handles uneven shading)
            if not results:
                for block in [21, 31, 41]:
                    for c in [5, 9, 13]:
                        binary = cv2.adaptiveThreshold(gray, 255,
                            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, c)
                        results = try_pyzbar(binary)
                        if results:
                            break
                    if results:
                        break

            # Try binary inverse (white-on-black barcodes)
            if not results:
                inverted = cv2.adaptiveThreshold(gray, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 9)
                results = try_pyzbar(inverted)
        except ImportError:
            pass

    t4 = time.time()

    elapsed = {
        'preprocess': t1 - start_time,
        'localize': t2 - t1,
        'correct': t3 - t2,
        'decode': t4 - t3,
        'total': t4 - start_time,
    }

    if visualize:
        vis_data = {
            'gray': gray,
            'binary': binary,
            'enhanced': enhanced,
            'edges': loc_result.get('edges'),
            'finder_patterns': loc_result.get('finder_patterns', []),
            'barcode_rects': loc_result.get('barcode_rects', []),
            'qr_corners': loc_result.get('qr_corners', []),
            'results': results,
            'elapsed': elapsed,
        }
        return results, vis_data

    return results, {'results': results, 'elapsed': elapsed}


def draw_results(img, vis_data):
    """Draw detection and recognition results on the image."""
    display = img.copy()
    if len(display.shape) == 2:
        display = cv2.cvtColor(display, cv2.COLOR_GRAY2BGR)

    h, w = display.shape[:2]

    # Draw barcode rectangles
    for rect, conf in vis_data.get('barcode_rects', []):
        box = cv2.boxPoints(rect)
        box = np.int32(box)
        cv2.drawContours(display, [box], 0, (0, 255, 0), 2)

    # Draw QR corners
    for corners, mod_size in vis_data.get('qr_corners', []):
        cv2.polylines(display, [np.int32(corners)], True, (255, 0, 0), 2)
        for pt in np.int32(corners):
            cv2.circle(display, tuple(pt), 4, (0, 0, 255), -1)

    # Draw finder patterns
    for cx, cy, module in vis_data.get('finder_patterns', []):
        cv2.circle(display, (int(cx), int(cy)), int(module * 3), (255, 255, 0), 1)

    # Draw results text
    y_offset = 30
    for result in vis_data.get('results', []):
        text = f"[{result['type']}] {result['text']} ({result['confidence']:.0%})"
        cv2.putText(display, text, (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        y_offset += 25

    # Draw timing info
    elapsed = vis_data.get('elapsed', {})
    if elapsed:
        timing_text = f"Total: {elapsed['total']*1000:.0f}ms"
        cv2.putText(display, timing_text, (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    return display


def process_image(image_path, output_dir=None):
    """Process a single image file and save results."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Cannot read image '{image_path}'")
        return

    print(f"Processing: {image_path}")
    print(f"  Size: {img.shape[1]}x{img.shape[0]}")

    results, vis_data = run_pipeline(img, visualize=True)

    print(f"\nResults ({len(results)} found):")
    for i, r in enumerate(results):
        print(f"  {i+1}. [{r['type']}] {r['text']} (confidence: {r['confidence']:.1%})")

    elapsed = vis_data['elapsed']
    print(f"\nTiming:")
    print(f"  Preprocess: {elapsed['preprocess']*1000:.1f}ms")
    print(f"  Localize:   {elapsed['localize']*1000:.1f}ms")
    print(f"  Correct:    {elapsed['correct']*1000:.1f}ms")
    print(f"  Decode:     {elapsed['decode']*1000:.1f}ms")
    print(f"  Total:      {elapsed['total']*1000:.1f}ms")

    # Save annotated image
    if output_dir is None:
        output_dir = os.path.dirname(image_path) or '.'
    os.makedirs(output_dir, exist_ok=True)

    result_img = draw_results(img, vis_data)
    basename = os.path.splitext(os.path.basename(image_path))[0]
    output_path = os.path.join(output_dir, f"{basename}_result.png")
    cv2.imwrite(output_path, result_img)
    print(f"\nResult saved to: {output_path}")

    # Show intermediate results
    cv2.imshow('Original', cv2.resize(img, (400, 400)) if max(img.shape) > 800 else img)
    cv2.imshow('Binary', vis_data['binary'])
    if vis_data['edges'] is not None:
        cv2.imshow('Edges', vis_data['edges'])
    cv2.imshow('Result', cv2.resize(result_img, (600, 500)) if max(result_img.shape) > 800 else result_img)
    print("\nPress any key to close windows...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <image_path>")
        print("       python pipeline.py --test  (run on test images)")
        sys.exit(1)

    if sys.argv[1] == '--test':
        test_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'images', 'test_images')
        if not os.path.isdir(test_dir):
            print(f"Test directory not found: {test_dir}")
            sys.exit(1)

        test_files = [f for f in os.listdir(test_dir) if f.endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
        test_files = sorted(test_files)[:10]  # Process first 10
        print(f"Running on {len(test_files)} test images...\n")

        for tf in test_files:
            filepath = os.path.join(test_dir, tf)
            process_image(filepath, output_dir=os.path.join(test_dir, '..', '..', 'results'))
            print("\n" + "=" * 50 + "\n")
    else:
        process_image(sys.argv[1])
