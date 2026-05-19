#!/usr/bin/env python3
"""Generate test barcode and QR code images for testing the scanner app.

Generates:
  - Clean QR codes (various content)
  - Clean barcodes (EAN-13, Code-128, Code-39)
  - Rotated versions
  - Noisy/blurred versions
  - Multi-barcode composite images
"""

import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import qrcode
import barcode
from barcode.writer import ImageWriter

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'images', 'test_images')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def add_noise(img, intensity=25):
    """Add salt-and-pepper noise to image."""
    arr = np.array(img).copy()
    h, w = arr.shape[:2]
    mask = np.random.random((h, w)) < (intensity / 255)
    if arr.ndim == 3:
        for c in range(arr.shape[2]):
            channel = arr[:, :, c]
            channel[mask] = np.where(np.random.random((h, w))[mask] > 0.5, 255, 0)
            arr[:, :, c] = channel
    else:
        arr[mask] = np.where(np.random.random((h, w))[mask] > 0.5, 255, 0)
    return Image.fromarray(arr)


def add_gaussian_noise(img, sigma=15):
    """Add Gaussian noise."""
    arr = np.array(img).astype(np.float32)
    noise = np.random.normal(0, sigma, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def apply_blur(img, radius=2):
    """Apply Gaussian blur."""
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def rotate_image(img, angle):
    """Rotate image by angle degrees."""
    return img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor='white')


def apply_uneven_lighting(img, darkness_factor=0.5):
    """Simulate uneven lighting by darkening one corner."""
    arr = np.array(img).astype(np.float32)
    h, w = arr.shape[:2]
    y, x = np.ogrid[:h, :w]
    gradient = 1.0 - darkness_factor * (x / w) * (y / h)
    gradient = np.clip(gradient, 0.3, 1.0)
    if arr.ndim == 3:
        gradient = gradient[:, :, np.newaxis]
    arr = np.clip(arr * gradient, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def generate_qr_codes():
    """Generate various QR code images."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    test_contents = [
        "https://github.com/whx12210512/digital-image-processing",
        "Hello, Digital Image Processing!",
        "1234567890",
        "南方科技大学 数字图像处理 2026",
        "SUSTech DIP Project - QR Code Scanner",
        "ITEM:BOOK:9787040456514",
        "https://www.sustech.edu.cn",
    ]

    for i, content in enumerate(test_contents):
        qr.clear()
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        filename = f"qr_clean_{i+1:02d}.png"
        img.save(os.path.join(OUTPUT_DIR, filename))
        print(f"  Generated: {filename}")

        # Rotated versions
        for angle in [15, 30, 45]:
            rot_img = rotate_image(img, angle)
            filename = f"qr_rotated_{angle:02d}_{i+1:02d}.png"
            rot_img.save(os.path.join(OUTPUT_DIR, filename))
            print(f"  Generated: {filename}")

        # Noisy version
        noisy_img = add_noise(img, intensity=20)
        filename = f"qr_noisy_{i+1:02d}.png"
        noisy_img.save(os.path.join(OUTPUT_DIR, filename))
        print(f"  Generated: {filename}")

        # Blurred version
        blur_img = apply_blur(img, radius=1.5)
        filename = f"qr_blurred_{i+1:02d}.png"
        blur_img.save(os.path.join(OUTPUT_DIR, filename))
        print(f"  Generated: {filename}")

        # Uneven lighting
        lit_img = apply_uneven_lighting(img, 0.6)
        filename = f"qr_lighting_{i+1:02d}.png"
        lit_img.save(os.path.join(OUTPUT_DIR, filename))
        print(f"  Generated: {filename}")

        if i >= 2:
            break  # Only first 3 get all variations to keep manageable

    for i, content in enumerate(test_contents):
        qr.clear()
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        filename = f"qr_clean_{i+3:02d}.png" if i >= 3 else f"qr_clean_{i+1:02d}.png"
        if not os.path.exists(os.path.join(OUTPUT_DIR, filename)):
            img.save(os.path.join(OUTPUT_DIR, filename))
            print(f"  Generated: {filename}")


def generate_barcodes():
    """Generate various barcode images."""
    test_data = {
        'ean13': ['5901234123457', '9780201379624', '6901234567890'],
        'code128': ['CODE128-TEST', 'SUSTech2026', 'DIP-Project'],
        'code39': ['ABC123', 'TEST39', 'DIP2026'],
    }

    for fmt, data_list in test_data.items():
        for i, data in enumerate(data_list):
            try:
                BarcodeClass = barcode.get(fmt, data, writer=ImageWriter())
                img = BarcodeClass.render()
                # Render returns SVG by default; we need to use write method
            except Exception:
                pass

            try:
                options = {
                    'module_width': 0.3,
                    'module_height': 15.0,
                    'font_size': 10,
                    'text_distance': 5.0,
                    'quiet_zone': 6.5,
                }
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
                bc.write(filepath, options)
                print(f"  Generated: {filename}")

                # Rotation variants
                img = Image.open(filepath).convert('RGB')
                for angle in [15, 30]:
                    rot_img = rotate_image(img, angle)
                    rot_filename = f"barcode_{fmt}_rotated_{angle:02d}_{i+1:02d}.png"
                    rot_img.save(os.path.join(OUTPUT_DIR, rot_filename))
                    print(f"  Generated: {rot_filename}")

                # First barcode of each format gets more variants
                if i == 0:
                    noisy_img = add_noise(img, intensity=15)
                    noisy_img.save(os.path.join(OUTPUT_DIR, f"barcode_{fmt}_noisy_{i+1:02d}.png"))

                    blur_img = apply_blur(img, radius=1.0)
                    blur_img.save(os.path.join(OUTPUT_DIR, f"barcode_{fmt}_blurred_{i+1:02d}.png"))

            except Exception as e:
                print(f"  Warning: Could not generate {fmt} barcode '{data}': {e}")


def generate_multi_barcode():
    """Generate images containing multiple barcodes/QR codes."""
    # Create a canvas with multiple QR codes
    canvas = Image.new('RGB', (800, 600), 'white')

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=3)

    positions = [(50, 50), (450, 50), (50, 320), (450, 320)]
    contents = [
        "https://www.sustech.edu.cn",
        "SUSTech DIP 2026",
        "QR Code Multi-Test 1",
        "QR Code Multi-Test 2",
    ]

    for (x, y), content in zip(positions, contents):
        qr.clear()
        qr.add_data(content)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        canvas.paste(qr_img, (x, y))

    filename = "multi_qr_codes.png"
    canvas.save(os.path.join(OUTPUT_DIR, filename))
    print(f"  Generated: {filename}")

    # Mix of barcode and QR code
    canvas2 = Image.new('RGB', (800, 500), 'white')

    qr.clear()
    qr.add_data("Mixed test - QR Code")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    canvas2.paste(qr_img, (50, 80))

    try:
        ean = barcode.get('ean13', '9780201379624', writer=ImageWriter())
        ean_path = os.path.join(OUTPUT_DIR, '_temp_ean.png')
        ean.write(ean_path)
        ean_img = Image.open(ean_path).convert('RGB')
        ean_img = ean_img.resize((300, 100))
        canvas2.paste(ean_img, (420, 200))
        os.remove(ean_path)
    except Exception as e:
        print(f"  Warning: {e}")

    filename = "mixed_barcode_qr.png"
    canvas2.save(os.path.join(OUTPUT_DIR, filename))
    print(f"  Generated: {filename}")


def generate_complex_background():
    """Generate QR codes on complex/textured backgrounds."""
    canvas = Image.new('RGB', (400, 400), 'white')
    draw = ImageDraw.Draw(canvas)

    # Draw random lines as background
    np.random.seed(42)
    for _ in range(50):
        x1, y1 = np.random.randint(0, 400), np.random.randint(0, 400)
        x2, y2 = np.random.randint(0, 400), np.random.randint(0, 400)
        draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200), width=2)

    for _ in range(30):
        x, y = np.random.randint(0, 380), np.random.randint(0, 380)
        draw.ellipse([x, y, x + 20, y + 20], outline=(180, 180, 180), width=1)

    # Place QR code on top
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=6, border=3)
    qr.add_data("Complex background test")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # Semi-transparent overlay for realism
    bg_region = canvas.crop((80, 80, 80 + qr_img.width, 80 + qr_img.height))
    blended = Image.blend(bg_region, qr_img, 0.85)
    canvas.paste(blended, (80, 80))

    filename = "qr_complex_background.png"
    canvas.save(os.path.join(OUTPUT_DIR, filename))
    print(f"  Generated: {filename}")


if __name__ == '__main__':
    print("Generating test QR codes...")
    generate_qr_codes()
    print("\nGenerating test barcodes...")
    generate_barcodes()
    print("\nGenerating multi-barcode images...")
    generate_multi_barcode()
    print("\nGenerating complex background images...")
    generate_complex_background()
    print(f"\nAll test images saved to: {OUTPUT_DIR}")
