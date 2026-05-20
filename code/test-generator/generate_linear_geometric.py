#!/usr/bin/env python3
"""
线性几何畸变 (Linear Geometric Distortion) 压力测试数据集生成器
==================================================================
数字图像处理课程大作业 — 任务四：条形码/二维码识别
南方科技大学 电子与电气工程系 · 2026

核心思路:
    模拟现实中最常见的三种扫码几何畸变场景 —
    侧角扫码、纸张拉伸、复合旋转视角。
    所有变换基于线性单应性/仿射矩阵, 使用 cv2 标准 API 实现。

三个任务:
    Task A: 极度透视畸变 — 3×3 单应性矩阵 (warpPerspective)
    Task B: 仿射错切形变 — 2×3 错切矩阵 (warpAffine)
    Task C: 组合视角畸变 — 旋转 + 透视 (warpAffine + warpPerspective)

关键防裁剪:
    透视/错切后像素可能变负 → 使用 perspecitveTransform 预计算边界
    → 在矩阵中叠加平移 → 动态扩展输出画布 → 100% 保留码图内容

输出:
    images/stress_test/
    ├── linear_perspective/   # Task A: 透视畸变 (110)
    ├── linear_shear/          # Task B: 错切形变 (110)
    └── linear_combo/          # Task C: 组合畸变 (110)

使用:
    python generate_linear_geometric.py
    python generate_linear_geometric.py --count 150
"""

import cv2
import numpy as np
import qrcode
import barcode
from barcode.writer import ImageWriter
from barcode import Code128, EAN13, EAN8, Code39
from PIL import Image as PILImage
import random
import os
import math
import string
import io
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================================
# 全局常量
# ============================================================================
QR_SIZE = 256
BARCODE_W = 500
BARCODE_H = 200
OUTPUT_SIZE = (320, 320)
PNG_COMPRESSION = 6


# ============================================================================
# 工具函数
# ============================================================================

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


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
    ecc = random.choice([qrcode.constants.ERROR_CORRECT_L,
                          qrcode.constants.ERROR_CORRECT_M,
                          qrcode.constants.ERROR_CORRECT_Q,
                          qrcode.constants.ERROR_CORRECT_H])
    qr = qrcode.QRCode(version=None, error_correction=ecc, box_size=10, border=2)
    qr.add_data(random_qr_data())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    img = img.resize((QR_SIZE, QR_SIZE), PILImage.LANCZOS)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def generate_barcode():
    """生成 Code128 或 EAN-13 条形码。"""
    bc_type = random.choice(['code128', 'ean13'])
    try:
        if bc_type == 'code128':
            data = ''.join(random.choices(string.ascii_letters+string.digits, k=random.randint(8, 16)))
            bc = Code128(data, writer=ImageWriter())
        else:
            data = ''.join(random.choices(string.digits, k=12))
            bc = EAN13(data, writer=ImageWriter())
        fp = io.BytesIO()
        options = {'module_width': 8, 'module_height': 100, 'quiet_zone': 40,
                   'write_text': True, 'text_distance': 5, 'font_size': 10}
        bc.write(fp, options)
        fp.seek(0)
        img = PILImage.open(fp).convert('RGB')
        img = img.resize((BARCODE_W, BARCODE_H), PILImage.LANCZOS)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except:
        return generate_qr()


def pad_to_size(img, tw, th):
    """居中白底填充到目标尺寸。"""
    h, w = img.shape[:2]
    scale = min(tw/w, th/h)
    if scale < 1.0:
        img = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LANCZOS4)
        h, w = img.shape[:2]
    canvas = np.full((th, tw, 3), 255, dtype=np.uint8)
    ox, oy = (tw-w)//2, (th-h)//2
    canvas[oy:oy+h, ox:ox+w] = img
    return canvas


# ============================================================================
# 防裁剪透视变换 (任务 A 核心)
# ============================================================================

def safe_warp_perspective(img, dst_pts, border_value=(255,255,255)):
    """
    执行透视变换并确保 100% 内容保留。

    数学推导:
        1. 原图四顶点 src = TL(0,0), TR(w-1,0), BR(w-1,h-1), BL(0,h-1)
        2. 目标四边形 dst_pts (用户指定)
        3. H = getPerspectiveTransform(src, dst_pts)  (3×3 单应性)
        4. 计算变换后四顶点 + 边中点共 8 点的位置
        5. 取 min/max → 新边界
        6. 叠加平移矩阵 H_adj = [[1,0,-min_x],[0,1,-min_y],[0,0,1]]
        7. H_final = H_adj @ H
        8. warpPerspective(img, H_final, (max_x-min_x, max_y-min_y))
    """
    h, w = img.shape[:2]
    src_pts = np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])

    H = cv2.getPerspectiveTransform(src_pts, dst_pts)

    # 预计算变换后所有关键点的位置
    boundary = np.float32([
        [0, 0], [w/2, 0], [w-1, 0],
        [w-1, h/2], [w-1, h-1],
        [w/2, h-1], [0, h-1], [0, h/2]
    ]).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(boundary, H).reshape(-1, 2)

    min_x = int(np.floor(transformed[:, 0].min()))
    min_y = int(np.floor(transformed[:, 1].min()))
    max_x = int(np.ceil(transformed[:, 0].max()))
    max_y = int(np.ceil(transformed[:, 1].max()))

    # 平移补偿: 确保所有坐标 >= 0
    H_adj = np.array([[1, 0, -min_x], [0, 1, -min_y], [0, 0, 1]], dtype=np.float64)
    H_final = H_adj @ H

    out_w = max_x - min_x
    out_h = max_y - min_y

    return cv2.warpPerspective(img, H_final, (out_w, out_h),
                                borderMode=cv2.BORDER_CONSTANT,
                                borderValue=border_value)


# ============================================================================
# 防裁剪仿射变换 (任务 B 核心)
# ============================================================================

def safe_warp_affine(img, M_2x3, border_value=(255,255,255)):
    """
    执行仿射变换并确保 100% 内容保留。

    数学推导:
        仿射变换 M = [a b tx; c d ty]  (2×3)
        新顶点 = M @ 原顶点 (齐次坐标)
        取 min/max → 新边界 → 平移补偿
    """
    h, w = img.shape[:2]
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    transformed = cv2.transform(corners, M_2x3).reshape(-1, 2)

    min_x = int(np.floor(transformed[:, 0].min()))
    min_y = int(np.floor(transformed[:, 1].min()))
    max_x = int(np.ceil(transformed[:, 0].max()))
    max_y = int(np.ceil(transformed[:, 1].max()))

    M_adj = M_2x3.copy()
    M_adj[0, 2] -= min_x
    M_adj[1, 2] -= min_y

    return cv2.warpAffine(img, M_adj, (max_x - min_x, max_y - min_y),
                           borderMode=cv2.BORDER_CONSTANT,
                           borderValue=border_value)


# ============================================================================
# 任务 A: 极度透视畸变
# ============================================================================

def generate_perspective_extreme(index, image_type='qr'):
    """
    生成极度透视畸变图。

    模拟: 以极大倾斜角从侧面/上方/下方扫描平面码图。
    偏移量: 原边长的 20%~40%。

    防裁剪: safe_warp_perspective 自动计算扩展画布。
    """
    img = generate_qr() if image_type == 'qr' else generate_barcode()
    h, w = img.shape[:2]
    max_offset = max(w, h) * random.uniform(0.20, 0.40)

    # 选择畸变方向
    direction = random.choice(['left_lean', 'right_lean', 'top_lean', 'bottom_lean'])

    if direction == 'left_lean':
        # 左侧正常，右侧大幅收缩 → 从右边看
        dst = np.float32([
            [random.uniform(0, max_offset*0.3), random.uniform(0, max_offset*0.3)],
            [w-1 - max_offset, random.uniform(0, max_offset*0.3)],
            [w-1 - max_offset*0.8, h-1 - random.uniform(0, max_offset*0.3)],
            [random.uniform(0, max_offset*0.3), h-1 - random.uniform(0, max_offset*0.3)],
        ])
    elif direction == 'right_lean':
        dst = np.float32([
            [max_offset, random.uniform(0, max_offset*0.3)],
            [w-1 - random.uniform(0, max_offset*0.3), random.uniform(0, max_offset*0.3)],
            [w-1 - random.uniform(0, max_offset*0.3), h-1 - random.uniform(0, max_offset*0.3)],
            [max_offset*0.8, h-1 - random.uniform(0, max_offset*0.3)],
        ])
    elif direction == 'top_lean':
        dst = np.float32([
            [random.uniform(0, max_offset*0.3), max_offset],
            [w-1 - random.uniform(0, max_offset*0.3), max_offset*0.8],
            [w-1 - random.uniform(0, max_offset*0.3), h-1 - random.uniform(0, max_offset*0.3)],
            [random.uniform(0, max_offset*0.3), h-1 - random.uniform(0, max_offset*0.3)],
        ])
    else:  # bottom_lean
        dst = np.float32([
            [random.uniform(0, max_offset*0.3), random.uniform(0, max_offset*0.3)],
            [w-1 - random.uniform(0, max_offset*0.3), random.uniform(0, max_offset*0.3)],
            [w-1 - random.uniform(0, max_offset*0.3), h-1 - max_offset*0.8],
            [random.uniform(0, max_offset*0.3), h-1 - max_offset],
        ])

    result = safe_warp_perspective(img, dst)
    result = pad_to_size(result, OUTPUT_SIZE[0], OUTPUT_SIZE[1])
    return f"linear_persp_{index:04d}.png", result


# ============================================================================
# 任务 B: 仿射错切形变
# ============================================================================

def generate_shear(index, image_type='qr'):
    """
    生成仿射错切形变图。

    数学原理:
        错切矩阵 M = [[1, sh_x, 0],
                     [sh_y, 1, 0]]
        sh_x: 水平错切系数 (x 坐标受 y 影响)
        sh_y: 垂直错切系数 (y 坐标受 x 影响)
        当 sh_x > 0, 图像向右倾斜; sh_x < 0, 向左倾斜。

    系数范围: -0.3 ~ 0.3
    """
    img = generate_qr() if image_type == 'qr' else generate_barcode()
    h, w = img.shape[:2]

    sh_x = random.uniform(-0.3, 0.3)
    sh_y = random.uniform(-0.3, 0.3)

    # 确保至少有一个方向的错切足够明显
    if abs(sh_x) < 0.05 and abs(sh_y) < 0.05:
        sh_x = random.choice([-0.2, 0.2])

    M = np.float32([[1, sh_x, 0], [sh_y, 1, 0]])
    result = safe_warp_affine(img, M)
    result = pad_to_size(result, OUTPUT_SIZE[0], OUTPUT_SIZE[1])
    return f"linear_shear_{index:04d}.png", result


# ============================================================================
# 任务 C: 组合视角畸变 (旋转 + 透视)
# ============================================================================

def generate_combo(index, image_type='qr'):
    """
    生成组合视角畸变图: 旋转 + 透视。

    模拟: 手机既侧倾角度, 同时旋转了镜头 (最随意的扫码姿势)。

    流程:
        1. 对原图做 -45°~45° 平面旋转 (warpAffine)
        2. 再叠加随机方向透视变换 (warpPerspective)
        3. 两次变换均使用 safe_* 系列函数防裁剪
    """
    img = generate_qr() if image_type == 'qr' else generate_barcode()
    h, w = img.shape[:2]

    # 步骤1: 旋转
    angle = random.uniform(-45, 45)
    center = (w/2, h/2)
    M_rot = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = safe_warp_affine(img, M_rot)

    # 步骤2: 透视
    rh, rw = rotated.shape[:2]
    max_offset = max(rw, rh) * random.uniform(0.10, 0.25)
    direction = random.choice(['left', 'right', 'top', 'bottom'])

    if direction == 'left':
        dst = np.float32([
            [0, random.uniform(0, max_offset*0.3)],
            [rw-1 - max_offset, 0],
            [rw-1 - max_offset*0.5, rh-1],
            [0, rh-1 - random.uniform(0, max_offset*0.3)],
        ])
    elif direction == 'right':
        dst = np.float32([
            [max_offset, 0],
            [rw-1, random.uniform(0, max_offset*0.3)],
            [rw-1, rh-1 - random.uniform(0, max_offset*0.3)],
            [max_offset*0.5, rh-1],
        ])
    elif direction == 'top':
        dst = np.float32([
            [0, max_offset],
            [rw-1, max_offset*0.4],
            [rw-1, rh-1],
            [0, rh-1],
        ])
    else:
        dst = np.float32([
            [0, 0],
            [rw-1, 0],
            [rw-1, rh-1 - max_offset*0.4],
            [0, rh-1 - max_offset],
        ])

    result = safe_warp_perspective(rotated, dst)
    result = pad_to_size(result, OUTPUT_SIZE[0], OUTPUT_SIZE[1])
    return f"linear_combo_{index:04d}.png", result


# ============================================================================
# 批量生成
# ============================================================================

def batch_generate(task_func, output_dir, count, image_type, desc, parallel=True):
    ensure_dir(output_dir)
    print(f"\n  {desc}: {count} 张 -> {output_dir}")

    def gen(i):
        return task_func(i, image_type)

    if parallel and count >= 10:
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
            futures = {ex.submit(gen, i): i for i in range(count)}
            for future in as_completed(futures):
                try:
                    fname, img = future.result()
                    cv2.imwrite(os.path.join(output_dir, fname), img,
                                [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
                except Exception as e:
                    print(f"  [!] #{futures[future]}: {e}")
    else:
        for i in range(count):
            try:
                fname, img = gen(i)
                cv2.imwrite(os.path.join(output_dir, fname), img,
                            [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
            except Exception as e:
                print(f"  [!] #{i}: {e}")

    actual = len([f for f in os.listdir(output_dir) if f.endswith('.png')])
    print(f"  [OK] {actual} images")


def main():
    parser = argparse.ArgumentParser(description='线性几何畸变测试集生成器')
    parser.add_argument('--count', type=int, default=110, help='每任务数量')
    parser.add_argument('--output', type=str, default='../../images/stress_test')
    parser.add_argument('--no-parallel', action='store_true')
    args = parser.parse_args()

    root = os.path.abspath(args.output)
    count = max(args.count, 110)
    parallel = not args.no_parallel

    print("=" * 60)
    print("  线性几何畸变压力测试数据集生成器")
    print(f"  每个任务: {count} 张 (QR {count//2} + Barcode {count - count//2})")
    print("=" * 60)

    for task_func, dirname, desc in [
        (generate_perspective_extreme, 'linear_perspective', 'Task A: 极度透视'),
        (generate_shear, 'linear_shear',            'Task B: 仿射错切'),
        (generate_combo, 'linear_combo',            'Task C: 组合畸变'),
    ]:
        batch_generate(task_func, os.path.join(root, dirname), count,
                       'qr', desc, parallel=parallel)

    print(f"\n  Done. {count*3} images generated.")


if __name__ == '__main__':
    main()
