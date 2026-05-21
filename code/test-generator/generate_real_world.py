#!/usr/bin/env python3
"""
真实场景压力测试数据集 — 3 个新增类别
=========================================
数字图像处理课程大作业 — 任务四：条形码/二维码识别
南方科技大学 电子与电气工程系 · 2026

新增类别:
    Task A: JPEG 压缩伪影 (JPEG Compression Artifacts)
    Task B: 散焦模糊 (Defocus Blur)
    Task C: 手指部分遮挡 (Finger Occlusion)

使用:
    python generate_real_world.py --count 110
"""

import cv2
import numpy as np
import qrcode
import barcode
from barcode.writer import ImageWriter
from barcode import Code128, EAN13, EAN8, Code39
from PIL import Image as PILImage
import random, os, io, string, argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================================
# 全局常量
# ============================================================================
QR_SIZE = 300
BARCODE_W = 800
BARCODE_H = 300
PNG_COMPRESSION = 6
OUTPUT_SIZE = (400, 400)  # QR output
JPEG_QUALITIES = [8, 12, 18, 25, 35, 50]  # JPEG quality levels

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)

def random_qr_data():
    rtype = random.choice(['url', 'text', 'numeric'])
    if rtype == 'url':
        d = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5,10)))
        return f"https://{d}.com/{random.randint(1000,9999)}"
    elif rtype == 'text':
        return ''.join(random.choices(string.ascii_letters+string.digits, k=random.randint(8,30)))
    else:
        return ''.join(random.choices(string.digits, k=random.randint(10,16)))

def generate_qr():
    ecc = random.choice([qrcode.constants.ERROR_CORRECT_L, qrcode.constants.ERROR_CORRECT_M,
                         qrcode.constants.ERROR_CORRECT_Q, qrcode.constants.ERROR_CORRECT_H])
    qr = qrcode.QRCode(version=None, error_correction=ecc, box_size=10, border=2)
    qr.add_data(random_qr_data())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    img = img.resize((QR_SIZE, QR_SIZE), PILImage.LANCZOS)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def generate_barcode():
    bc_classes = {'code128': Code128, 'ean13': EAN13, 'ean8': EAN8, 'code39': Code39}
    bc_type = random.choice(list(bc_classes.keys()))
    if bc_type == 'code128':
        data = ''.join(random.choices(string.ascii_letters+string.digits+' _-', k=random.randint(8,20)))
    elif bc_type == 'ean13':
        data = ''.join(random.choices(string.digits, k=12))
    elif bc_type == 'ean8':
        data = ''.join(random.choices(string.digits, k=7))
    else:
        data = ''.join(random.choices(string.ascii_uppercase+string.digits+'.$/+%', k=random.randint(6,15)))
    try:
        bc = bc_classes[bc_type](data, writer=ImageWriter())
        fp = io.BytesIO()
        bc.write(fp, {'module_width': 10, 'module_height': 120, 'quiet_zone': 60,
                      'write_text': True, 'text_distance': 5, 'font_size': 10})
        fp.seek(0)
        pil_img = PILImage.open(fp).convert('RGB')
        pil_img = pil_img.resize((BARCODE_W, BARCODE_H), PILImage.LANCZOS)
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except:
        return generate_qr()

def pad_to_size(img, target_w, target_h):
    h, w = img.shape[:2]
    scale = min(target_w/w, target_h/h)
    if scale < 1.0:
        new_w, new_h = int(w*scale), int(h*scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        h, w = new_h, new_w
    canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)
    ox, oy = (target_w-w)//2, (target_h-h)//2
    canvas[oy:oy+h, ox:ox+w] = img
    return canvas

# ============================================================================
# Task A: JPEG 压缩伪影
# ============================================================================

def generate_jpeg_artifact(index):
    """JPEG compression → blocking artifacts around QR/barcode modules."""
    is_bc = random.random() < 0.35
    img = generate_barcode() if is_bc else generate_qr()
    quality = random.choice(JPEG_QUALITIES)
    tag = 'bc' if is_bc else 'qr'

    # Encode → decode at low quality
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    degraded = cv2.imdecode(buf, cv2.IMREAD_COLOR)

    if not is_bc:
        degraded = pad_to_size(degraded, *OUTPUT_SIZE)

    fname = f"jpeg_{index:04d}_q{quality:02d}_{tag}.png"
    return fname, degraded

# ============================================================================
# Task B: 散焦模糊 (Gaussian Defocus)
# ============================================================================

def generate_defocus_blur(index):
    """Gaussian blur simulating out-of-focus camera."""
    is_bc = random.random() < 0.35
    img = generate_barcode() if is_bc else generate_qr()
    tag = 'bc' if is_bc else 'qr'

    # Simulate various defocus levels
    sigma = random.uniform(1.5, 6.0)
    kernel_size = int(sigma * 4 + 1) | 1  # odd
    kernel_size = min(kernel_size, 31)

    blurred = cv2.GaussianBlur(img, (kernel_size, kernel_size), sigma)

    if not is_bc:
        blurred = pad_to_size(blurred, *OUTPUT_SIZE)

    fname = f"defocus_{index:04d}_s{sigma:.1f}_{tag}.png"
    return fname, blurred

# ============================================================================
# Task C: 手指部分遮挡
# ============================================================================

def generate_finger_occlusion(index):
    """Simulate finger partially covering the code when holding phone + product."""
    is_bc = random.random() < 0.35
    img = generate_barcode() if is_bc else generate_qr()
    tag = 'bc' if is_bc else 'qr'
    h, w = img.shape[:2]

    result = img.copy()
    num_fingers = random.choices([1, 2], weights=[80, 20])[0]

    for _ in range(num_fingers):
        side = random.choice(['left', 'right', 'bottom'])
        skin_color = np.random.randint(150, 210, 3).tolist()

        if side == 'left':
            cx = random.randint(-5, w//6)
            cy = random.randint(h//4, 3*h//4)
            rx = random.randint(20, w//5)
            ry = random.randint(40, h//3)
        elif side == 'right':
            cx = random.randint(5*w//6, w+5)
            cy = random.randint(h//4, 3*h//4)
            rx = random.randint(20, w//5)
            ry = random.randint(40, h//3)
        else:  # bottom
            cx = random.randint(w//4, 3*w//4)
            cy = random.randint(5*h//6, h+5)
            rx = random.randint(40, w//3)
            ry = random.randint(20, h//5)

        angle = random.uniform(-30, 30)
        cv2.ellipse(result, (cx, cy), (rx, ry), angle, 0, 360,
                    (int(skin_color[0]), int(skin_color[1]), int(skin_color[2])), -1)
        # Add slight edge blur for realism
        cv2.ellipse(result, (cx, cy), (rx+3, ry+3), angle, 0, 360,
                    (int(skin_color[0]), int(skin_color[1]), int(skin_color[2])), 2)

    if not is_bc:
        result = pad_to_size(result, *OUTPUT_SIZE)

    fname = f"finger_{index:04d}_{tag}.png"
    return fname, result


# ============================================================================
# 批量生成
# ============================================================================

def batch_generate(generator_func, output_dir, count, desc, parallel=True):
    ensure_dir(output_dir)
    print(f"\n{'='*60}")
    print(f"  {desc}: {count} images -> {output_dir}")
    print(f"{'='*60}")

    if parallel and count >= 10:
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
            futures = {ex.submit(generator_func, i): i for i in range(count)}
            for future in as_completed(futures):
                try:
                    fname, img = future.result()
                    out_path = os.path.join(output_dir, fname)
                    cv2.imwrite(out_path, img, [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
                except Exception as e:
                    print(f"  [!] #{futures[future]}: {e}")
    else:
        for i in range(count):
            try:
                fname, img = generator_func(i)
                out_path = os.path.join(output_dir, fname)
                cv2.imwrite(out_path, img, [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
            except Exception as e:
                print(f"  [!] #{i}: {e}")

    actual = len([f for f in os.listdir(output_dir) if f.endswith('.png')])
    print(f"  [OK] {actual} images generated")


def main():
    parser = argparse.ArgumentParser(description='Real-world stress test generators')
    parser.add_argument('--count', type=int, default=110)
    parser.add_argument('--output', type=str, default='../../images/stress_test')
    parser.add_argument('--no-jpeg', action='store_true')
    parser.add_argument('--no-defocus', action='store_true')
    parser.add_argument('--no-finger', action='store_true')
    parser.add_argument('--no-parallel', action='store_true')
    args = parser.parse_args()

    root = os.path.abspath(args.output)
    count = args.count
    parallel = not args.no_parallel

    print("=" * 60)
    print("  Real-World Stress Test Generators")
    print(f"  {count} images per task")
    print(f"  Output: {root}")
    print("=" * 60)

    if not args.no_jpeg:
        batch_generate(generate_jpeg_artifact,
                       os.path.join(root, 'artifact_jpeg'), count,
                       'Task A: JPEG Compression Artifacts', parallel=parallel)

    if not args.no_defocus:
        batch_generate(generate_defocus_blur,
                       os.path.join(root, 'artifact_defocus'), count,
                       'Task B: Defocus Blur', parallel=parallel)

    if not args.no_finger:
        batch_generate(generate_finger_occlusion,
                       os.path.join(root, 'artifact_finger'), count,
                       'Task C: Finger Occlusion', parallel=parallel)

    print(f"\n{'='*60}")
    print("  All done!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
