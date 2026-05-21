#!/usr/bin/env python3
"""
几何畸变与形态变化 QR 码压力测试数据集生成器
==================================================
数字图像处理课程大作业 — 任务四：条形码/二维码识别
南方科技大学 电子与电气工程系 · 2026

核心思路:
    使用传统 DIP 数学变换 (仿射/透视/重映射) 模拟真实世界中
    QR 码因拍摄角度和物理载体形变产生的几何畸变。

数学变换原理 (详见各函数注释):
    - Task A: 平面内旋转 (Roll) — 2×3 仿射矩阵 + warpAffine
    - Task B: 空间透视 (Pitch/Yaw) — 3×3 单应性矩阵 + warpPerspective
    - Task C: 曲面弯曲 — 柱面投影坐标重映射 + remap

输出:
    images/stress_test/
    ├── geometric_rotation/     # Task A: 旋转 (≥100)
    ├── geometric_perspective/  # Task B: 透视 (≥100)
    └── geometric_curved/       # Task C: 柱面弯曲 (≥100)

使用:
    python generate_geometric_test.py
    python generate_geometric_test.py --count 150
"""

import cv2
import numpy as np
import qrcode
from PIL import Image
import random
import os
import argparse
import math
import string
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================================
# 全局常量
# ============================================================================
QR_SIZE = 300              # QR 码原始尺寸
BORDER = 2                 # QR 码白边框模块数
PNG_COMPRESSION = 6        # PNG 压缩
OUTPUT_SIZE = (360, 360)   # 输出图像统一尺寸


# ============================================================================
# 工具函数
# ============================================================================

def random_qr_data():
    """生成随机二维码内容。"""
    rtype = random.choice(['url', 'text', 'numeric'])
    if rtype == 'url':
        domain = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
        return f"https://{domain}.com/{random.randint(1000,9999)}"
    elif rtype == 'text':
        return ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(8, 30)))
    else:
        return ''.join(random.choices(string.digits, k=random.randint(10, 16)))


def generate_qr_image(data, size=QR_SIZE, border=BORDER):
    """生成 QR 码 BGR 图像。"""
    ecc = random.choice([
        qrcode.constants.ERROR_CORRECT_L,
        qrcode.constants.ERROR_CORRECT_M,
        qrcode.constants.ERROR_CORRECT_Q,
        qrcode.constants.ERROR_CORRECT_H,
    ])
    qr = qrcode.QRCode(version=None, error_correction=ecc, box_size=10, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    img_pil = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    img_pil = img_pil.resize((size, size), Image.LANCZOS)
    img = np.array(img_pil)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def ensure_dir(path):
    """确保目录存在。"""
    Path(path).mkdir(parents=True, exist_ok=True)


def pad_to_size(img, target_w, target_h):
    """
    将图像居中填充到目标尺寸 (白底)。
    若图像比目标大则等比缩小。
    """
    h, w = img.shape[:2]
    scale = min(target_w / w, target_h / h)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        h, w = new_h, new_w

    canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)
    ox = (target_w - w) // 2
    oy = (target_h - h) // 2
    canvas[oy:oy + h, ox:ox + w] = img
    return canvas


# ============================================================================
# Task A: 平面内旋转 (In-Plane Rotation)
# ============================================================================

def rotate_image(img, angle_deg):
    """
    对图像施加平面内旋转，保持完整内容不被裁剪。

    数学原理:
        旋转矩阵 R = [cosθ  -sinθ]
                    [sinθ   cosθ]
        变换后四个顶点的新坐标由 R 计算，取 min/max 得到新边界。
        仿射矩阵需补偿平移量 tx, ty，确保所有像素不丢失。

    参数:
        img:      输入 BGR 图像
        angle_deg:旋转角度 (度)
    返回:
        旋转后图像 (BGR)
    """
    if angle_deg == 0:
        return img.copy()

    h, w = img.shape[:2]
    theta = math.radians(angle_deg)
    cos_t = abs(math.cos(theta))
    sin_t = abs(math.sin(theta))

    # 计算旋转后的新画布尺寸 (避免裁剪)
    new_w = int(w * cos_t + h * sin_t)
    new_h = int(w * sin_t + h * cos_t)

    # 构建旋转矩阵 (绕原图中心)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)

    # 调整平移分量，将旋转后的图像居中放置到新画布
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2

    rotated = cv2.warpAffine(
        img, M, (new_w, new_h),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )
    return rotated


def generate_rotation_image(index):
    """
    生成平面内旋转测试图。

    旋转角: 0°~360° 均匀随机。
    0°=无旋转, 90°=正侧立, 180°=倒置, 270°=反侧立。
    """
    data = random_qr_data()
    qr_img = generate_qr_image(data)

    # 均匀覆盖全圆周
    angle = random.uniform(0, 360)

    rotated = rotate_image(qr_img, angle)

    # 统一输出尺寸
    result = pad_to_size(rotated, OUTPUT_SIZE[0], OUTPUT_SIZE[1])

    fname = f"rotation_{index:04d}_a{int(angle):03d}.png"
    return fname, result


# ============================================================================
# Task B: 空间透视变换 (Perspective Distortion)
# ============================================================================

def perspective_transform(img, corner_offset_ratio=None):
    """
    对图像施加透视变换，模拟侧视/俯仰角度。

    数学原理:
        原图四顶点 → 目标不规则凸四边形。
        单应性矩阵 H (3×3) 通过四对对应点求解:
            [x']   [h11 h12 h13] [x]
            [y'] = [h21 h22 h23] [y]
            [w']   [h31 h32 h33] [1]
        输出: x'' = x'/w', y'' = y'/w'

    约束: 目标四边形必须保持凸性 (各内角 < 180°)。

    参数:
        img:                输入 BGR 图像
        corner_offset_ratio:顶点偏移比例 (None = 随机 0.1~0.4)
    返回:
        透视变换后图像 (BGR)
    """
    if corner_offset_ratio is None:
        corner_offset_ratio = random.uniform(0.10, 0.40)

    h, w = img.shape[:2]

    # 原图四顶点 (顺序: TL, TR, BR, BL)
    src_pts = np.float32([[0, 0], [w - 1, 0],
                          [w - 1, h - 1], [0, h - 1]])

    # 对每个顶点施加随机二维偏移 (保持凸性)
    max_offset = max(w, h) * corner_offset_ratio
    attempts = 0
    while attempts < 100:
        dst_pts = np.float32([
            [random.uniform(0, max_offset), random.uniform(0, max_offset)],
            [w - 1 - random.uniform(0, max_offset), random.uniform(0, max_offset)],
            [w - 1 - random.uniform(0, max_offset), h - 1 - random.uniform(0, max_offset)],
            [random.uniform(0, max_offset), h - 1 - random.uniform(0, max_offset)],
        ])

        # 验证凸性: 叉积符号必须一致 (CCW)
        def cross_z(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        signs = []
        for i in range(4):
            s = cross_z(dst_pts[i], dst_pts[(i + 1) % 4], dst_pts[(i + 2) % 4])
            signs.append(s)
        if all(s > 0 for s in signs) or all(s < 0 for s in signs):
            break  # 凸四边形 ✓
        attempts += 1
    else:
        # 回退: 仅做微小偏移确保不出错
        dst_pts = np.float32([
            [max_offset * 0.1, max_offset * 0.1],
            [w - 1 - max_offset * 0.1, max_offset * 0.1],
            [w - 1 - max_offset * 0.1, h - 1 - max_offset * 0.1],
            [max_offset * 0.1, h - 1 - max_offset * 0.1],
        ])

    # 计算单应性矩阵
    H = cv2.getPerspectiveTransform(src_pts, dst_pts)

    # 透视变换后的边界: 对四顶点 + 边中点做变换
    boundary_pts = np.float32([
        [0, 0], [w / 2, 0], [w - 1, 0],
        [w - 1, h / 2], [w - 1, h - 1],
        [w / 2, h - 1], [0, h - 1], [0, h / 2],
    ])
    transformed = cv2.perspectiveTransform(boundary_pts.reshape(-1, 1, 2), H)
    transformed = transformed.reshape(-1, 2)

    min_x = max(0, int(np.floor(transformed[:, 0].min())))
    min_y = max(0, int(np.floor(transformed[:, 1].min())))
    max_x = int(np.ceil(transformed[:, 0].max()))
    max_y = int(np.ceil(transformed[:, 1].max()))

    # 调整 H 使结果画布左上角对齐 (避免负坐标导致裁剪)
    H_adj = np.array([[1, 0, -min_x], [0, 1, -min_y], [0, 0, 1]], dtype=np.float64)
    H_final = H_adj @ H

    out_w = max_x - min_x
    out_h = max_y - min_y

    result = cv2.warpPerspective(
        img, H_final, (out_w, out_h),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )
    return result


def generate_perspective_image(index):
    """
    生成空间透视测试图。

    模拟: 手机从侧面/上方/下方扫描平面 QR 码时的透视变形。
    """
    data = random_qr_data()
    qr_img = generate_qr_image(data)

    offset_ratio = random.uniform(0.08, 0.35)
    warped = perspective_transform(qr_img, offset_ratio)

    # 随机旋转 0~30° 叠加 (模拟复合视角)
    if random.random() < 0.4:
        warped = rotate_image(warped, random.uniform(-30, 30))

    result = pad_to_size(warped, OUTPUT_SIZE[0], OUTPUT_SIZE[1])

    fname = f"perspective_{index:04d}.png"
    return fname, result


# ============================================================================
# Task C: 曲面弯曲与褶皱 (Curved & Rippled Deformation)
# ============================================================================

def build_cylinder_maps(w, h, curvature=None):
    """
    构建柱面弯曲的坐标映射图。

    数学原理:
        将平面图像映射到圆柱表面。
        设圆柱半径为 R, 像素水平坐标为 x, 垂直坐标为 y。
        柱面投影: x' = R * sin((x - cx) / R)
                 y' = (y - cy) * R / distance_to_cylinder
        其中 distance = sqrt(R² + (x - cx)²)

        简化模型: x_new = cx + R * arcsin((x - cx) / R)
        这在数学上等价于将平面"包裹"到圆柱上。

    参数:
        w, h:      图像宽高
        curvature: 曲率 [0,1], 0=平面, 1=最大弯曲 (None=随机)
    返回:
        (map_x, map_y) float32
    """
    if curvature is None:
        curvature = random.uniform(0.15, 0.9)

    # 曲率映射到有效半径 R (曲率越大 R 越小, 弯曲越明显)
    R = max(50, (w / 2) / (curvature * math.pi + 0.01))

    y, x = np.mgrid[0:h, 0:w].astype(np.float32)

    # 以图像中心为参考点
    cx = w / 2.0
    cy = h / 2.0

    # 柱面投影: 水平坐标按三角函数重映射
    # x' - cx = R * sin((x - cx) / R)  →  x' = cx + R * sin((x - cx) / R)
    # 垂直方向按深度缩放: y' - cy = (y - cy) * R / sqrt(R² + (x - cx)²)
    dx = (x - cx) / R  # 归一化水平角
    depth = np.sqrt(R * R + (x - cx) * (x - cx))

    map_x = cx + R * np.sin(dx)
    # 垂直: 根据深度远近做透视缩放
    map_y = cy + (y - cy) * R / (depth + 1e-6)

    return map_x.astype(np.float32), map_y.astype(np.float32)


def build_ripple_maps(w, h, amplitude=None, wavelength=None, direction='vertical'):
    """
    构建正弦波浪褶皱的坐标映射图。

    数学原理:
        在垂直/水平/双向叠加正弦波位移:
        map_y += A_y * sin(2π * x / λ_x + φ)
        map_x += A_x * cos(2π * y / λ_y + φ)

    参数:
        w, h:      图像宽高
        amplitude: 振幅 (px), None=随机 3~20
        wavelength:波长 (px), None=随机 w/8~w/2
        direction: 'vertical'(纵向波) | 'horizontal'(横向波) | 'both'(双向)
    返回:
        (map_x, map_y) float32
    """
    if amplitude is None:
        amplitude = random.uniform(3.0, 20.0)
    if wavelength is None:
        wavelength = random.uniform(w / 8.0, w / 2.0)

    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    phase = random.uniform(0, 2 * math.pi)

    map_x = x.copy()
    map_y = y.copy()

    if direction in ('vertical', 'both'):
        displacement = amplitude * np.sin(2 * math.pi * x / wavelength + phase)
        map_y += displacement

    if direction in ('horizontal', 'both'):
        displacement = amplitude * np.cos(2 * math.pi * y / wavelength + phase)
        map_x += displacement

    return map_x.astype(np.float32), map_y.astype(np.float32)


def apply_remap(img, map_x, map_y):
    """
    应用自定义坐标映射图进行图像重映射。

    使用双线性插值 (cv2.INTER_LINEAR) 确保平滑形变。
    边界填充白色模拟纸张背景。
    """
    return cv2.remap(
        img, map_x, map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )


def generate_curved_image(index):
    """
    生成柱面弯曲测试图。

    实际生活中QR码贴于瓶罐等圆柱表面时仅受柱面弯曲影响，
    不存在波浪褶皱(ripple)。因此仅使用纯柱面投影模型。

    柱面投影数学模型:
        x' = cx + R * sin((x - cx) / R)
        y' = cy + (y - cy) * R / sqrt(R² + (x - cx)²)
    其中R由曲率参数控制,曲率越大R越小弯曲越明显。
    """
    data = random_qr_data()
    qr_img = generate_qr_image(data)
    h, w = qr_img.shape[:2]

    curvature = random.uniform(0.08, 0.35)
    map_x, map_y = build_cylinder_maps(w, h, curvature)
    result = apply_remap(qr_img, map_x, map_y)
    fname = f"curved_cyl_{index:04d}.png"

    # 可选: 再叠加一个小角度旋转 (10%)
    if random.random() < 0.1:
        result = rotate_image(result, random.uniform(-15, 15))

    # 裁剪四个边可能出现的黑色或异常区域
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(thresh)
    if coords is not None:
        x, y_c, w_r, h_r = cv2.boundingRect(coords)
        x = max(0, x - 5)
        y_c = max(0, y_c - 5)
        w_r = min(result.shape[1] - x, w_r + 10)
        h_r = min(result.shape[0] - y_c, h_r + 10)
        result = result[y_c:y_c + h_r, x:x + w_r]

    result = pad_to_size(result, OUTPUT_SIZE[0], OUTPUT_SIZE[1])
    return fname, result


# ============================================================================
# 批量生成
# ============================================================================

def batch_generate(generator_func, output_dir, count, desc, parallel=True):
    """批量调用生成函数并保存图片。"""
    ensure_dir(output_dir)
    print(f"\n{'='*60}")
    print(f"  {desc}: {count} 张 -> {output_dir}")
    print(f"{'='*60}")

    if parallel and count >= 10:
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
            futures = {ex.submit(generator_func, i): i for i in range(count)}
            for future in as_completed(futures):
                try:
                    fname, img = future.result()
                    out_path = os.path.join(output_dir, fname)
                    cv2.imwrite(out_path, img,
                                [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
                except Exception as e:
                    print(f"  [!] #{futures[future]}: {e}")
    else:
        for i in range(count):
            try:
                fname, img = generator_func(i)
                out_path = os.path.join(output_dir, fname)
                cv2.imwrite(out_path, img,
                            [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
            except Exception as e:
                print(f"  [!] #{i}: {e}")
            if (i + 1) % max(1, count // 10) == 0:
                print(f"  ... {i + 1}/{count}")

    actual = len([f for f in os.listdir(output_dir)
                  if f.endswith('.png')])
    print(f"  [OK] {actual} images generated")


def main():
    parser = argparse.ArgumentParser(
        description='几何畸变 QR 码压力测试数据集生成器')
    parser.add_argument('--count', type=int, default=110,
                        help='每个任务生成数量 (默认 110)')
    parser.add_argument('--output', type=str,
                        default='../../images/stress_test',
                        help='输出根目录')
    parser.add_argument('--no-rotation', action='store_true',
                        help='跳过 Task A 旋转')
    parser.add_argument('--no-perspective', action='store_true',
                        help='跳过 Task B 透视')
    parser.add_argument('--no-curved', action='store_true',
                        help='跳过 Task C 曲面')
    parser.add_argument('--no-parallel', action='store_true',
                        help='禁用多线程')
    args = parser.parse_args()

    root = os.path.abspath(args.output)
    count = max(args.count, 100)
    parallel = not args.no_parallel

    print("=" * 60)
    print("  几何畸变 QR 码压力测试数据集生成器")
    print(f"  每个任务: {count} 张")
    print(f"  输出目录: {root}")
    print("=" * 60)

    if not args.no_rotation:
        batch_generate(generate_rotation_image,
                       os.path.join(root, 'geometric_rotation'),
                       count, 'Task A: 平面内旋转 (0-360°)',
                       parallel=parallel)

    if not args.no_perspective:
        batch_generate(generate_perspective_image,
                       os.path.join(root, 'geometric_perspective'),
                       count, 'Task B: 空间透视 (单应性变换)',
                       parallel=parallel)

    if not args.no_curved:
        batch_generate(generate_curved_image,
                       os.path.join(root, 'geometric_curved'),
                       count, 'Task C: 柱面弯曲 (cylinder projection)',
                       parallel=parallel)

    print(f"\n{'='*60}")
    print(f"  全部完成!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
