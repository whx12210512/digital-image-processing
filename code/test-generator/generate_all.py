#!/usr/bin/env python3
"""Generate test barcode and QR code images (50+ samples).

Covers:
  - Clean QR codes (10 contents, various sizes)
  - Rotation variants: 10°, 20°, 30°, 40°
  - Degradation: noise, blur, uneven lighting
  - Partial occlusion
  - Perspective distortion
  - Barcodes: EAN-13, Code-128, Code-39
  - Complex backgrounds
  - Multi-barcode composites
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import qrcode
import barcode
from barcode.writer import ImageWriter

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'images', 'test_images')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def add_noise(img, intensity=20):
    arr = np.array(img).copy()
    h, w = arr.shape[:2]
    mask = np.random.random((h, w)) < (intensity / 255)
    if arr.ndim == 3:
        for c in range(arr.shape[2]):
            arr[:, :, c][mask] = np.where(np.random.random(mask.sum()) > 0.5, 255, 0)
    else:
        arr[mask] = np.where(np.random.random(mask.sum()) > 0.5, 255, 0)
    return Image.fromarray(arr)


def add_gaussian_noise(img, sigma=10):
    arr = np.array(img).astype(np.float32)
    noise = np.random.normal(0, sigma, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def apply_blur(img, radius=1.5):
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def rotate_image(img, angle):
    return img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor='white')


def apply_uneven_lighting(img, factor=0.5):
    arr = np.array(img).astype(np.float32)
    h, w = arr.shape[:2]
    y, x = np.ogrid[:h, :w]
    gradient = 1.0 - factor * (x / w) * (y / h)
    gradient = np.clip(gradient, 0.3, 1.0)
    if arr.ndim == 3:
        gradient = gradient[:, :, np.newaxis]
    arr = np.clip(arr * gradient, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def add_partial_occlusion(img, x, y, w, h):
    """Draw a black rectangle over part of the image."""
    img = img.copy()
    draw = ImageDraw.Draw(img)
    draw.rectangle([x, y, x + w, y + h], fill='black')
    return img


def perspective_distort(img, intensity=0.3):
    """Apply a mild perspective distortion using PIL transforms."""
    w, h = img.size
    # Shift top corners inward
    coeffs = [
        1 - intensity * 0.3, 0, intensity * w * 0.1,
        0.05, 1 - intensity * 0.1, intensity * h * 0.05,
        0, 0,
    ]
    return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor='white')


# ============ Main Generation ============

def generate_all():
    count = 0
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr_contents = [
        "https://github.com/whx12210512",
        "Hello, Digital Image Processing!",
        "1234567890",
        "SUSTech DIP 2026 Project",
        "QR Code Scanner Test",
        "ITEM:BOOK:9787040456514",
        "https://www.sustech.edu.cn",
        "Digital Image Processing @ SUSTech",
        "0123456789ABCDEF",
        "https://example.com/test",
    ]

    # --- Clean QR codes ---
    print("--- Clean QR codes ---")
    for i, content in enumerate(qr_contents):
        qr.clear()
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        filename = f"qr_clean_{i+1:02d}.png"
        img.save(os.path.join(OUTPUT_DIR, filename))
        count += 1
        print(f"  [{count}] {filename}")

    # --- Rotation variants (10°, 20°, 30°, 40°) ---
    print("--- Rotation variants ---")
    for i in range(6):  # First 6 QR codes get rotation variants
        qr.clear()
        qr.add_data(qr_contents[i])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        for angle in [10, 20, 30, 40]:
            rot_img = rotate_image(img, angle)
            filename = f"qr_rotated_{angle:02d}_{i+1:02d}.png"
            rot_img.save(os.path.join(OUTPUT_DIR, filename))
            count += 1
            print(f"  [{count}] {filename}")

    # --- Noise variants (salt & pepper + gaussian) ---
    print("--- Noise variants ---")
    for i in range(6):
        qr.clear()
        qr.add_data(qr_contents[i])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        # Salt & pepper
        for intensity in [10, 20]:
            noisy = add_noise(img, intensity)
            filename = f"qr_noisy_{intensity}_{i+1:02d}.png"
            noisy.save(os.path.join(OUTPUT_DIR, filename))
            count += 1
            print(f"  [{count}] {filename}")
        # Gaussian noise (mild)
        gn = add_gaussian_noise(img, 10)
        filename = f"qr_gnoise_{i+1:02d}.png"
        gn.save(os.path.join(OUTPUT_DIR, filename))
        count += 1
        print(f"  [{count}] {filename}")

    # --- Blur variants ---
    print("--- Blur variants ---")
    for i in range(5):
        qr.clear()
        qr.add_data(qr_contents[i])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        for radius in [1.0, 1.8]:
            blur = apply_blur(img, radius)
            filename = f"qr_blurred_{radius:.1f}_{i+1:02d}.png"
            blur.save(os.path.join(OUTPUT_DIR, filename))
            count += 1
            print(f"  [{count}] {filename}")

    # --- Uneven lighting ---
    print("--- Uneven lighting ---")
    for i in range(5):
        qr.clear()
        qr.add_data(qr_contents[i])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        for factor in [0.4, 0.6]:
            lit = apply_uneven_lighting(img, factor)
            filename = f"qr_lighting_{int(factor*100)}_{i+1:02d}.png"
            lit.save(os.path.join(OUTPUT_DIR, filename))
            count += 1
            print(f"  [{count}] {filename}")

    # --- Partial occlusion ---
    print("--- Partial occlusion ---")
    for i in range(5):
        qr.clear()
        qr.add_data(qr_contents[i])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        w, h = img.size
        # Occlude bottom-right finder pattern area
        occ = add_partial_occlusion(img, int(w * 0.7), int(h * 0.7), int(w * 0.25), int(h * 0.25))
        filename = f"qr_occluded_{i+1:02d}.png"
        occ.save(os.path.join(OUTPUT_DIR, filename))
        count += 1
        print(f"  [{count}] {filename}")

    # --- Perspective distortion ---
    print("--- Perspective distortion ---")
    for i in range(5):
        qr.clear()
        qr.add_data(qr_contents[i])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        for intensity in [0.25, 0.4]:
            persp = perspective_distort(img, intensity)
            filename = f"qr_perspective_{int(intensity*100)}_{i+1:02d}.png"
            persp.save(os.path.join(OUTPUT_DIR, filename))
            count += 1
            print(f"  [{count}] {filename}")

    # --- Complex backgrounds ---
    print("--- Complex backgrounds ---")
    for i in range(4):
        canvas = Image.new('RGB', (400, 400), 'white')
        draw = ImageDraw.Draw(canvas)
        np.random.seed(42 + i)
        for _ in range(30):
            x1, y1 = np.random.randint(0, 400), np.random.randint(0, 400)
            x2, y2 = np.random.randint(0, 400), np.random.randint(0, 400)
            draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200), width=2)
        qr.clear()
        qr.add_data(qr_contents[i])
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        canvas.paste(qr_img, (70, 70))
        filename = f"qr_complex_bg_{i+1:02d}.png"
        canvas.save(os.path.join(OUTPUT_DIR, filename))
        count += 1
        print(f"  [{count}] {filename}")

    # --- Multi QR codes ---
    print("--- Multi QR codes ---")
    for n_codes in [2, 3, 4]:
        canvas = Image.new('RGB', (600, 600), 'white')
        positions = {
            2: [(30, 150), (320, 150)],
            3: [(30, 30), (320, 30), (175, 320)],
            4: [(30, 30), (320, 30), (30, 320), (320, 320)],
        }
        for j, (x, y) in enumerate(positions[n_codes]):
            qr.clear()
            qr.add_data(f"Multi-{n_codes} QR #{j+1}")
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            qr_img = qr_img.resize((250, 250))
            canvas.paste(qr_img, (x, y))
        filename = f"multi_{n_codes}_qr.png"
        canvas.save(os.path.join(OUTPUT_DIR, filename))
        count += 1
        print(f"  [{count}] {filename}")

    # --- Barcodes ---
    print("--- Barcodes ---")
    ean_codes = ['5901234123457', '9780201379624', '6901234567890', '9787302517599', '9787111638445']
    c128_codes = ['CODE128-TEST', 'SUSTech2026', 'DIP-Project', 'BARCODE-SCAN', 'IMG-PROCESS']
    c39_codes = ['ABC123', 'TEST39', 'DIP2026', 'SCAN01', 'CODE39X']

    for fmt, codes in [('ean13', ean_codes), ('code128', c128_codes), ('code39', c39_codes)]:
        for i, data in enumerate(codes):
            try:
                if fmt == 'ean13':
                    bc = barcode.get('ean13', data, writer=ImageWriter())
                elif fmt == 'code128':
                    bc = barcode.get('code128', data, writer=ImageWriter())
                elif fmt == 'code39':
                    bc = barcode.get('code39', data, writer=ImageWriter())
                else:
                    continue

                filename = f"barcode_{fmt}_{i+1:02d}.png"
                filepath = os.path.join(OUTPUT_DIR, filename)
                bc.write(filepath)
                count += 1
                print(f"  [{count}] {filename}")

                # Rotation variants for first 3 of each
                if i < 3:
                    img = Image.open(filepath).convert('RGB')
                    for angle in [15, 30]:
                        rot_img = rotate_image(img, angle)
                        rot_filename = f"barcode_{fmt}_rotated_{angle:02d}_{i+1:02d}.png"
                        rot_img.save(os.path.join(OUTPUT_DIR, rot_filename))
                        count += 1
                        print(f"  [{count}] {rot_filename}")

                    # Noise and blur for first
                    if i == 0:
                        noisy = add_noise(img, 12)
                        noisy.save(os.path.join(OUTPUT_DIR, f"barcode_{fmt}_noisy_01.png"))
                        count += 1
                        blur = apply_blur(img, 1.0)
                        blur.save(os.path.join(OUTPUT_DIR, f"barcode_{fmt}_blurred_01.png"))
                        count += 1
            except Exception as e:
                print(f"  Warning: {fmt} '{data}': {e}")

    # --- Barcode advanced degradation: perspective, occlusion, lighting, complex bg ---
    print("--- Barcode advanced degradation ---")
    barcode_files_map = {}
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith('barcode_') and f.endswith('.png') and '_rotated_' not in f and '_noisy_' not in f and '_blurred_' not in f:
            fmt_key = f.split('_')[1]
            if fmt_key not in barcode_files_map:
                barcode_files_map[fmt_key] = []
            barcode_files_map[fmt_key].append(f)

    for fmt_key in sorted(barcode_files_map.keys()):
        files = sorted(barcode_files_map[fmt_key])[:3]
        for fname in files:
            base = fname.replace('.png', '')
            img = Image.open(os.path.join(OUTPUT_DIR, fname)).convert('RGB')

            # Perspective distortion
            for intensity in [0.25, 0.4]:
                persp = perspective_distort(img, intensity)
                out = f"{base}_perspective_{int(intensity*100)}.png"
                persp.save(os.path.join(OUTPUT_DIR, out))
                count += 1
                print(f"  [{count}] {out}")

            # Occlusion (block middle section)
            w, h = img.size
            occ = add_partial_occlusion(img, int(w * 0.35), int(h * 0.1), int(w * 0.3), int(h * 0.8))
            out = f"{base}_occluded.png"
            occ.save(os.path.join(OUTPUT_DIR, out))
            count += 1
            print(f"  [{count}] {out}")

            # Uneven lighting
            for factor in [0.4, 0.6]:
                lit = apply_uneven_lighting(img, factor)
                out = f"{base}_lighting_{int(factor*100)}.png"
                lit.save(os.path.join(OUTPUT_DIR, out))
                count += 1
                print(f"  [{count}] {out}")

            # Complex background
            w, h = img.size
            canvas = Image.new('RGB', (w + 80, h + 80), 'white')
            draw = ImageDraw.Draw(canvas)
            np.random.seed(hash(base) % 10000)
            for _ in range(25):
                x1, y1 = np.random.randint(0, canvas.width), np.random.randint(0, canvas.height)
                x2, y2 = np.random.randint(0, canvas.width), np.random.randint(0, canvas.height)
                draw.line([(x1, y1), (x2, y2)], fill=(180, 180, 180), width=2)
            canvas.paste(img, (40, 40))
            out = f"{base}_complex_bg.png"
            canvas.save(os.path.join(OUTPUT_DIR, out))
            count += 1
            print(f"  [{count}] {out}")

    # --- Mixed barcode + QR ---
    print("--- Mixed types ---")
    for combo_i in range(3):
        canvas = Image.new('RGB', (700, 400), 'white')
        # QR on left
        qr.clear()
        qr.add_data(f"Mixed combo #{combo_i+1} QR")
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        qr_img = qr_img.resize((200, 200))
        canvas.paste(qr_img, (30, 100))
        # Barcode on right
        bc = barcode.get('ean13', ean_codes[combo_i], writer=ImageWriter())
        tmp_path = os.path.join(OUTPUT_DIR, f'_tmp_mixed_{combo_i}.png')
        bc.write(tmp_path)
        bc_img = Image.open(tmp_path).convert('RGB')
        bc_img = bc_img.resize((350, 120))
        canvas.paste(bc_img, (320, 140))
        os.remove(tmp_path)
        filename = f"mixed_combo_{combo_i+1:02d}.png"
        canvas.save(os.path.join(OUTPUT_DIR, filename))
        count += 1
        print(f"  [{count}] {filename}")

    # --- Small QR codes (lower resolution) ---
    print("--- Small / low-res QR codes ---")
    for i in range(5):
        qr.clear()
        qr.add_data(qr_contents[i])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        small = img.resize((150, 150), Image.LANCZOS)
        canvas = Image.new('RGB', (300, 300), 'white')
        canvas.paste(small, (75, 75))
        filename = f"qr_small_{i+1:02d}.png"
        canvas.save(os.path.join(OUTPUT_DIR, filename))
        count += 1
        print(f"  [{count}] {filename}")

    print(f"\nTotal generated: {count} images")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == '__main__':
    generate_all()
