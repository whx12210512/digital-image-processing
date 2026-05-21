#!/usr/bin/env python3
"""
边缘破坏场景压力测试数据集生成器
===========================================
数字图像处理课程大作业 — 任务四：条形码/二维码识别
南方科技大学 电子与电气工程系 · 2026

两个边缘破坏场景:
    Task A: 静区侵犯 (Quiet Zone Violation) — 文字/图形侵入条码/QR码静区
    Task B: 撕裂/碎片 (Tear & Fragment) — 物理撕裂导致部分图像缺失
"""

import cv2
import numpy as np
import qrcode
import barcode
from barcode.writer import ImageWriter
from barcode import Code128, EAN13
from PIL import Image as PILImage, ImageDraw, ImageFont
import random
import os
import string
import io
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

QR_SIZE = 256
BARCODE_W = 500
BARCODE_H = 200
PNG_COMPRESSION = 6

def random_qr_data():
    rtype = random.choice(['url', 'text', 'numeric'])
    if rtype == 'url':
        d = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
        return f"https://{d}.com/{random.randint(1000,9999)}"
    elif rtype == 'text':
        return ''.join(random.choices(string.ascii_letters+string.digits, k=random.randint(8, 30)))
    else:
        return ''.join(random.choices(string.digits, k=random.randint(10, 16)))

def generate_qr():
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
                        box_size=10, border=2)
    qr.add_data(random_qr_data())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    img = img.resize((QR_SIZE, QR_SIZE), PILImage.LANCZOS)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def generate_barcode_img():
    try:
        bc_type = random.choice(['code128', 'ean13'])
        if bc_type == 'code128':
            data = ''.join(random.choices(string.ascii_letters+string.digits, k=random.randint(8, 16)))
            bc = Code128(data, writer=ImageWriter())
        else:
            data = ''.join(random.choices(string.digits, k=12))
            bc = EAN13(data, writer=ImageWriter())
        fp = io.BytesIO()
        bc.write(fp, {'module_width': 8, 'module_height': 100, 'quiet_zone': 40,
                       'write_text': True, 'text_distance': 5, 'font_size': 10})
        fp.seek(0)
        img = PILImage.open(fp).convert('RGB')
        img = img.resize((BARCODE_W, BARCODE_H), PILImage.LANCZOS)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except:
        return generate_qr()

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


# ============================================================================
# Task A: 静区侵犯 (Quiet Zone Violation)
# ============================================================================

def violate_quiet_zone(img, is_barcode=False):
    """
    在图像静区（边缘空白带）生成侵入内容。

    模拟: 旁边文字、图标、污渍贴近或侵入条码/QR码的静区。
    静区被侵犯 → 解码器无法定位起始/终止符或QR码边界。

    侵入类型:
        - 字符: 随机字母/数字贴近边缘
        - 线段: 横线/竖线延伸到静区
        - 黑色块: 矩形色块贴边
    """
    h, w = img.shape[:2]
    result = img.copy()

    # 静区宽度: QR ~10% 边长, 条码 ~14% 宽度
    qz = int(w * 0.12) if not is_barcode else int(w * 0.16)

    # 随机 3-6 种侵入 (更密集)
    num_violations = random.randint(3, 6)

    for _ in range(num_violations):
        vtype = random.choice(['char', 'line', 'block'])
        side = random.choice(['left', 'right', 'top', 'bottom'])

        if vtype == 'char':
            # 在静区边缘绘制随机字符
            text = random.choice(string.ascii_uppercase + string.digits + '#@&%')
            font_scale = random.uniform(1.0, 2.0)  # 更大字体
            thickness = random.randint(2, 5)  # 更粗
            color = (0, 0, 0)

            if side == 'left':
                pos = (random.randint(2, qz - 10), random.randint(10, h - 10))
            elif side == 'right':
                pos = (w - qz + random.randint(2, qz - 10), random.randint(10, h - 10))
            elif side == 'top':
                pos = (random.randint(10, w - 10), random.randint(2, qz - 10))
            else:
                pos = (random.randint(10, w - 10), h - qz + random.randint(2, qz - 10))

            cv2.putText(result, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                        font_scale, color, thickness, cv2.LINE_AA)

        elif vtype == 'line':
            # 从图像外部延伸到静区
            thickness = random.randint(3, 7)
            if side in ('left', 'right'):
                x = random.randint(1, qz) if side == 'left' else w - random.randint(1, qz)
                y1 = random.randint(0, h)
                y2 = random.randint(0, h)
                cv2.line(result, (x, y1), (x + random.randint(-20, 20), y2),
                         (0, 0, 0), thickness, cv2.LINE_AA)
            else:
                y = random.randint(1, qz) if side == 'top' else h - random.randint(1, qz)
                x1 = random.randint(0, w)
                x2 = random.randint(0, w)
                cv2.line(result, (x1, y), (x2, y + random.randint(-20, 20)),
                         (0, 0, 0), thickness, cv2.LINE_AA)

        elif vtype == 'block':
            # 黑色矩形块贴边
            if side == 'left':
                bx, bw = 0, random.randint(5, qz)
                by, bh = random.randint(0, h - 30), 30
            elif side == 'right':
                bx, bw = w - random.randint(5, qz), random.randint(5, qz)
                by, bh = random.randint(0, h - 30), 30
            elif side == 'top':
                bx, bw = random.randint(0, w - 30), 30
                by, bh = 0, random.randint(5, qz)
            else:
                bx, bw = random.randint(0, w - 30), 30
                by, bh = h - random.randint(5, qz), random.randint(5, qz)
            cv2.rectangle(result, (bx, by), (bx + bw, by + bh), (0, 0, 0), -1)

    return result


def generate_quiet_zone_violation(index):
    is_bc = random.random() < 0.5
    img = generate_barcode_img() if is_bc else generate_qr()
    result = violate_quiet_zone(img, is_bc)
    tag = 'bc' if is_bc else 'qr'
    return f"qz_{index:04d}_{tag}.png", result


# ============================================================================
# Task B: 撕裂/碎片 (Tear & Fragment)
# ============================================================================

def apply_tear(img, num_tears=None):
    """
    模拟物理撕裂: 移除图像中的随机矩形/三角形区域, 白底填充。

    撕裂类型:
        - 边角撕掉: 移除一个角 (三角形或矩形)
        - 中间撕条: 移除一条水平或垂直长条
        - 不规则缺口: 移除随机位置的不规则多边形
    """
    if num_tears is None:
        num_tears = random.choices([1, 2], weights=[70, 30])[0]

    h, w = img.shape[:2]
    result = img.copy()

    for _ in range(num_tears):
        # Weight corner tear (most realistic) higher than strip/hole
        tear_type = random.choices(['corner', 'strip', 'hole'], weights=[50, 30, 20])[0]

        if tear_type == 'corner':
            # 撕掉一个角 (size reduced: was w//2 → w//4)
            corner = random.choice(['tl', 'tr', 'bl', 'br'])
            size_w = random.randint(w // 6, w // 3)
            size_h = random.randint(h // 6, h // 3)

            if corner == 'tl':
                pts = np.array([[0, 0], [size_w, 0], [0, size_h]], dtype=np.int32)
            elif corner == 'tr':
                pts = np.array([[w, 0], [w - size_w, 0], [w, size_h]], dtype=np.int32)
            elif corner == 'bl':
                pts = np.array([[0, h], [size_w, h], [0, h - size_h]], dtype=np.int32)
            else:
                pts = np.array([[w, h], [w - size_w, h], [w, h - size_h]], dtype=np.int32)

            cv2.fillPoly(result, [pts], (255, 255, 255))
            # 边缘加黑线模拟撕痕
            cv2.polylines(result, [pts], True, (100, 100, 100), 2, cv2.LINE_AA)

        elif tear_type == 'strip':
            # 撕掉一条水平或垂直长条
            if random.random() < 0.5:
                y1 = random.randint(h // 5, 3 * h // 5)
                y2 = y1 + random.randint(6, h // 10)
                x1, x2 = 0, w
            else:
                x1 = random.randint(w // 5, 3 * w // 5)
                x2 = x1 + random.randint(6, w // 10)
                y1, y2 = 0, h

            # 不规则边缘 (加轻微波浪)
            cv2.rectangle(result, (x1, y1), (x2, y2), (255, 255, 255), -1)
            cv2.rectangle(result, (x1, y1), (x2, y2), (120, 120, 120), 1)

        elif tear_type == 'hole':
            # 中间不规则洞 (radius reduced: was w//4 → w//5)
            cx = random.randint(w // 4, 3 * w // 4)
            cy = random.randint(h // 4, 3 * h // 4)
            rx = random.randint(15, w // 5)
            ry = random.randint(15, h // 5)
            angle = random.uniform(0, 360)

            # 不规则多边形洞
            n_pts = random.randint(5, 8)
            angles = np.linspace(0, 2 * np.pi, n_pts)
            radii_x = rx * (1 + 0.4 * np.random.uniform(-1, 1, n_pts))
            radii_y = ry * (1 + 0.4 * np.random.uniform(-1, 1, n_pts))
            pts = np.int32([
                [int(cx + radii_x[i] * np.cos(angles[i])),
                 int(cy + radii_y[i] * np.sin(angles[i]))]
                for i in range(n_pts)
            ])
            cv2.fillPoly(result, [pts], (255, 255, 255))
            cv2.polylines(result, [pts], True, (100, 100, 100), 2, cv2.LINE_AA)

    return result


def generate_tear(index):
    is_bc = random.random() < 0.35
    img = generate_barcode_img() if is_bc else generate_qr()
    result = apply_tear(img)
    tag = 'bc' if is_bc else 'qr'
    return f"tear_{index:04d}_{tag}.png", result


# ============================================================================
# 批量生成
# ============================================================================

def batch_generate(gen_func, output_dir, count, desc):
    ensure_dir(output_dir)
    print(f"  {desc}: {count} -> {output_dir}")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(gen_func, i): i for i in range(count)}
        for f in futures:
            try:
                fname, img = f.result()
                cv2.imwrite(os.path.join(output_dir, fname), img,
                            [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
            except Exception as e:
                print(f"  [!] {e}")
    print(f"  [OK] {len(os.listdir(output_dir))} images")

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--count', type=int, default=110)
    p.add_argument('--output', type=str, default='../../images/stress_test')
    args = p.parse_args()
    root = os.path.abspath(args.output)
    n = max(args.count, 110)
    print("Edge-Case Stress Test Generator")
    batch_generate(generate_quiet_zone_violation,
                   os.path.join(root, 'edge_quiet_zone'), n,
                   'Task A: Quiet Zone Violation')
    batch_generate(generate_tear,
                   os.path.join(root, 'edge_tear'), n,
                   'Task B: Tear & Fragment')

if __name__ == '__main__':
    main()
