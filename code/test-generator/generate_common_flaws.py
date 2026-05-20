#!/usr/bin/env python3
"""
常见扫码失败场景压力测试数据集生成器
===========================================
数字图像处理课程大作业 — 任务四：条形码/二维码识别
南方科技大学 电子与电气工程系 · 2026

三个高频现实失败场景:
    Task A: 运动模糊 (Motion Blur) — 手抖/快速移动
    Task B: 镜面反光 (Specular Highlight) — 光面杂志/屏幕反光
    Task C: 低对比度 (Low Contrast) — 褪色/旧打印/传真件
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
    img = img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


# ============================================================================
# Task A: 运动模糊 (Motion Blur)
# ============================================================================

def motion_blur_kernel(length, angle_deg):
    """
    生成线性运动模糊核。

    数学:
        核 = 沿 angle_deg 方向、长度为 length 的平均值线。
        作用在图像上 = 每个像素与运动方向上的 length 个邻近像素取平均。
    """
    kernel = np.zeros((length, length), dtype=np.float32)
    center = length // 2
    angle_rad = np.deg2rad(angle_deg)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    for i in range(length):
        dx = int(center + (i - center) * cos_a)
        dy = int(center + (i - center) * sin_a)
        if 0 <= dx < length and 0 <= dy < length:
            kernel[dy, dx] = 1.0
    kernel /= kernel.sum()  # 归一化
    return kernel


def apply_motion_blur(img, length=None, angle=None):
    """施加运动模糊。"""
    if length is None:
        length = random.choice([7, 9, 11, 13, 15, 17, 21])
    if angle is None:
        angle = random.uniform(0, 180)
    kernel = motion_blur_kernel(length, angle)
    return cv2.filter2D(img, -1, kernel)


def generate_motion_blur(index):
    qr = generate_qr()
    length = random.choice([5, 7, 9, 11, 15, 19])
    angle = random.uniform(0, 180)
    result = apply_motion_blur(qr, length, angle)
    return f"motionblur_{index:04d}_l{length:02d}_a{int(angle):03d}.png", result


# ============================================================================
# Task B: 镜面反光 (Specular Highlight)
# ============================================================================

def generate_highlight_mask(h, w, num_spots=None):
    """
    生成镜面反光的高光蒙版。

    模拟: 光滑杂志/手机屏幕上的灯光反射。
    特点: 椭圆形/不规则形, 亮度从中心向边缘递减 (高斯衰减)。
    """
    if num_spots is None:
        num_spots = random.randint(1, 3)

    mask = np.zeros((h, w), dtype=np.float32)

    for _ in range(num_spots):
        cx = random.randint(w // 5, 4 * w // 5)
        cy = random.randint(h // 5, 4 * h // 5)
        rx = random.randint(30, 110)
        ry = random.randint(20, 80)
        angle = random.uniform(0, 180)
        intensity = random.uniform(0.6, 1.0)

        # 椭圆形渐变高光
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        dx = (x - cx) * np.cos(np.deg2rad(angle)) + (y - cy) * np.sin(np.deg2rad(angle))
        dy = -(x - cx) * np.sin(np.deg2rad(angle)) + (y - cy) * np.cos(np.deg2rad(angle))
        ellipse = (dx / max(rx, 1)) ** 2 + (dy / max(ry, 1)) ** 2

        # 高斯衰减: 中心亮度最高, 边缘递减
        spot = np.exp(-ellipse / 2.0) * intensity
        mask = np.maximum(mask, spot)

    return np.clip(mask, 0, 1)


def apply_highlight(img, mask):
    """将高光蒙版叠加到图像上 — 高光区像素被直接替换为白色 (擦除下方内容)。"""
    result = img.astype(np.float32)
    # 高光区: 像素值 → 白色 (模拟完全过曝)
    for c in range(3):
        result[:, :, c] = result[:, :, c] * (1 - mask) + 255 * mask
    return np.clip(result, 0, 255).astype(np.uint8)


def generate_highlight(index):
    qr = generate_qr()
    h, w = qr.shape[:2]
    mask = generate_highlight_mask(h, w)
    result = apply_highlight(qr, mask)
    return f"highlight_{index:04d}.png", result


# ============================================================================
# Task C: 低对比度 (Low Contrast / Faded)
# ============================================================================

def apply_low_contrast(img, module_fade=None, paper_darken=None):
    """
    模拟褪色/旧打印/传真件。

    两种效果随机组合:
        1. 黑色模块变灰 (module_fade): RGB 0→N, 模拟墨水淡化
        2. 白色纸张变黄灰 (paper_darken): RGB 255→N, 模拟纸张老化
    """
    if module_fade is None:
        module_fade = random.randint(110, 160)  # 黑色提升
    if paper_darken is None:
        paper_darken = random.randint(140, 175)  # 白色降低 → 对比度仅 20-50

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # 线性映射: [0, 255] → [module_fade, paper_darken]
    faded = module_fade + (paper_darken - module_fade) * (gray / 255.0)

    return cv2.cvtColor(faded.astype(np.uint8), cv2.COLOR_GRAY2BGR)


def generate_low_contrast(index):
    qr = generate_qr()
    module_val = random.randint(40, 120)
    paper_val = random.randint(180, 240)
    result = apply_low_contrast(qr, module_val, paper_val)
    return f"lowcontrast_{index:04d}_m{module_val:03d}_p{paper_val:03d}.png", result


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
    print("Common Scan-Failure Stress Test Generator")
    batch_generate(generate_motion_blur, os.path.join(root, 'flaw_motion_blur'),
                   n, 'Task A: Motion Blur')
    batch_generate(generate_highlight, os.path.join(root, 'flaw_highlight'),
                   n, 'Task B: Specular Highlight')
    batch_generate(generate_low_contrast, os.path.join(root, 'flaw_low_contrast'),
                   n, 'Task C: Low Contrast')

if __name__ == '__main__':
    main()
