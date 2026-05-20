#!/usr/bin/env python3
"""
液体污渍 (Liquid Stains) QR 码压力测试数据集生成器
=====================================================
数字图像处理课程大作业 — 任务四：条形码/二维码识别
南方科技大学 电子与电气工程系 · 2026

两个测试子集:
    Task A: 咖啡/泥水渍 — 褐色半透明不规则液体, 带"咖啡环"边缘效应
    Task B: 蓝色记号笔渗色 — 蓝/紫半透明线条涂抹, 模拟纸张渗色

核心算法:
    - Coffee Ring Effect: GaussianBlur + 形态学梯度 → 内疏外密的环形蒙版
    - Alpha Blending: result = stain * alpha + original * (1 - alpha)
"""

import cv2
import numpy as np
import qrcode
from PIL import Image
import random
import os
import string
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

QR_SIZE = 256
PNG_COMPRESSION = 6

def random_qr_data():
    rtype = random.choice(['url', 'text', 'numeric'])
    if rtype == 'url':
        domain = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
        return f"https://{domain}.com/{random.randint(1000,9999)}"
    elif rtype == 'text':
        return ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(8, 30)))
    else:
        return ''.join(random.choices(string.digits, k=random.randint(10, 16)))

def generate_qr():
    """生成 H 级纠错 QR 码。"""
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
                        box_size=10, border=2)
    qr.add_data(random_qr_data())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    img = img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


# ============================================================================
# Task A: 咖啡/泥水渍 (Coffee Ring Stain)
# ============================================================================

def coffee_ring_mask(h, w, num_blobs=None):
    """
    生成咖啡环效应的不规则污渍蒙版。

    核心算法:
        1. 随机多边形/椭圆墨团 → 基础蒙版
        2. GaussianBlur → 柔化边界
        3. 形态学梯度 = dilation - erosion → 提取边缘环
        4. 与原始蒙版加权混合 → 中心半透明 + 边缘深色

    返回: float32 mask [0, 1], shape=(h,w)
    """
    if num_blobs is None:
        num_blobs = random.randint(1, 4)

    base_mask = np.zeros((h, w), dtype=np.uint8)

    for _ in range(num_blobs):
        cx = random.randint(w // 4, 3 * w // 4)
        cy = random.randint(h // 4, 3 * h // 4)
        rx = random.randint(20, 80)
        ry = random.randint(20, 80)
        angle = random.uniform(0, 360)

        # 不规则形状: 椭圆 + 多边形混合
        if random.random() < 0.5:
            cv2.ellipse(base_mask, (cx, cy), (rx, ry), angle, 0, 360, 255, -1)
        else:
            n_pts = random.randint(6, 10)
            angles = np.linspace(0, 2 * np.pi, n_pts)
            radii_x = rx * (1 + 0.3 * np.random.uniform(-1, 1, n_pts))
            radii_y = ry * (1 + 0.3 * np.random.uniform(-1, 1, n_pts))
            pts = np.int32([
                [cx + int(radii_x[i] * np.cos(angles[i])),
                 cy + int(radii_y[i] * np.sin(angles[i]))]
                for i in range(n_pts)
            ])
            cv2.fillPoly(base_mask, [pts], 255)

    # 柔化 (模拟液体扩散)
    blur_k = random.choice([15, 21, 31])
    if blur_k % 2 == 0: blur_k += 1
    blurred = cv2.GaussianBlur(base_mask, (blur_k, blur_k), blur_k // 3)

    # 咖啡环效应: 形态学梯度提取边缘
    d_k = random.choice([5, 7, 9])
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d_k, d_k))
    dilated = cv2.dilate(blurred, kernel)
    eroded = cv2.erode(blurred, kernel)
    edge_ring = cv2.subtract(dilated, eroded)  # 边缘增强

    # 混合: 中心 0.4 透明度 + 边缘 0.8 透明度
    center_weight = blurred.astype(np.float32) / 255.0 * random.uniform(0.3, 0.5)
    edge_weight = edge_ring.astype(np.float32) / 255.0 * random.uniform(0.7, 0.9)
    mask = np.clip(center_weight + edge_weight, 0, 0.9)

    return mask.astype(np.float32)


def apply_coffee_stain(img, mask):
    """
    将咖啡渍蒙版叠加到 QR 码图像上。

    Alpha 混合: result = stain_color * alpha + original * (1 - alpha)
    """
    h, w = img.shape[:2]
    result = img.astype(np.float32)

    # 褐色 (101, 67, 33) BGR
    stain_color = np.array([33.0, 67.0, 101.0], dtype=np.float32)

    for c in range(3):
        result[:, :, c] = (stain_color[c] * mask +
                           result[:, :, c] * (1.0 - mask))

    return np.clip(result, 0, 255).astype(np.uint8)


def generate_coffee_stain(index):
    qr_img = generate_qr()
    h, w = qr_img.shape[:2]
    mask = coffee_ring_mask(h, w)
    result = apply_coffee_stain(qr_img, mask)
    return f"coffee_{index:04d}.png", result


# ============================================================================
# Task B: 蓝色记号笔渗色 (Blue Ink Bleeding)
# ============================================================================

def blue_ink_mask(h, w, num_strokes=None):
    """
    生成蓝色记号笔涂抹蒙版。

    模拟: 横向或对角线的粗线条笔触，笔触边缘有轻微渗色模糊。
    """
    if num_strokes is None:
        num_strokes = random.randint(1, 3)

    mask = np.zeros((h, w), dtype=np.uint8)

    for _ in range(num_strokes):
        # 笔触参数
        thickness = random.randint(15, 40)
        x1 = random.randint(-w // 4, w // 4)
        y1 = random.randint(0, h)

        # 方向: 偏水平或对角线
        angle = random.uniform(-np.pi / 4, np.pi / 4)  # ±45°
        if random.random() < 0.3:
            angle = random.uniform(np.pi / 3, 2 * np.pi / 3)  # 偏垂直

        length = w + h  # 确保覆盖全图
        x2 = int(x1 + length * np.cos(angle))
        y2 = int(y1 + length * np.sin(angle))

        cv2.line(mask, (x1, y1), (x2, y2), 255, thickness)
        cv2.line(mask, (x1, y1), (x2, y2), 255, thickness - 10)  # 中心更浓

    # 渗色模糊 (模拟墨水在纸上扩散)
    blur_k = random.choice([7, 11, 15])
    if blur_k % 2 == 0: blur_k += 1
    mask = cv2.GaussianBlur(mask, (blur_k, blur_k), blur_k // 2)

    # 半透明: alpha 0.5-0.7
    alpha = random.uniform(0.5, 0.7)
    return (mask.astype(np.float32) / 255.0 * alpha).astype(np.float32)


def apply_blue_ink(img, mask):
    """
    将蓝色墨水蒙版叠加到 QR 码图像上。

    效果: 白纸处 → 浅蓝, 黑块处 → 深蓝黑
    """
    h, w = img.shape[:2]
    result = img.astype(np.float32)

    # 深蓝色 (0, 0, 139) BGR = (139, 0, 0)
    ink_color = np.array([139.0, 0.0, 0.0], dtype=np.float32)

    for c in range(3):
        result[:, :, c] = (ink_color[c] * mask +
                           result[:, :, c] * (1.0 - mask))

    return np.clip(result, 0, 255).astype(np.uint8)


def generate_blue_ink(index):
    qr_img = generate_qr()
    h, w = qr_img.shape[:2]
    mask = blue_ink_mask(h, w)
    result = apply_blue_ink(qr_img, mask)
    return f"blueink_{index:04d}.png", result


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
    p.add_argument('--count', type=int, default=30)
    p.add_argument('--output', type=str, default='../../images/stress_test')
    args = p.parse_args()
    root = os.path.abspath(args.output)
    print("Liquid Stains Generator")
    batch_generate(generate_coffee_stain, os.path.join(root, 'liquid_coffee'),
                   args.count, 'Task A: Coffee stains')
    batch_generate(generate_blue_ink, os.path.join(root, 'liquid_blue_ink'),
                   args.count, 'Task B: Blue ink bleeding')

if __name__ == '__main__':
    main()
