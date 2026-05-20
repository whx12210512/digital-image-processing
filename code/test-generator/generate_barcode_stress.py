#!/usr/bin/env python3
"""
一维条形码 (1D Barcode) 物理污损与几何畸变压力测试数据集生成器
================================================================
数字图像处理课程大作业 — 任务四：条形码/二维码识别
南方科技大学 电子与电气工程系 · 2026

核心思路:
    使用 python-barcode 动态生成干净条形码，再通过传统 DIP 算子
    施加物理污损和几何畸变，检验解码算法的鲁棒性。

条形码与 QR 码的关键差异:
    - 一维编码: 信息仅沿水平方向分布，垂直方向具有完全物理冗余
    - 解码依赖: 黑白条宽度比例的精确检测
    - 静区 (Quiet Zone): 左右必须有空白区，否则无法定位起止符

三种破坏策略:
    - Task A: 墨水污染 — 测试垂直冗余度与多线扫描机制
    - Task B: 物理划痕 — 测试定向形态学闭运算的修复能力
    - Task C: 几何畸变 — 测试宽度比例被破坏后的解码能力

输出:
    images/stress_test/
    ├── barcode_ink/          # Task A: 墨水污染 (≥100)
    ├── barcode_scratches/    # Task B: 物理划痕 (≥100)
    └── barcode_geometric/    # Task C: 几何畸变 (≥100)

使用:
    python generate_barcode_stress.py
    python generate_barcode_stress.py --count 120
"""

import cv2
import numpy as np
import barcode
from barcode.writer import ImageWriter
from barcode import Code128, EAN13, EAN8, Code39, UPCA
from PIL import Image as PILImage, ImageDraw, ImageFont
import random
import os
import math
import string
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import io


# ============================================================================
# 全局常量
# ============================================================================
BARCODE_WIDTH = 500         # 条形码输出宽度 (px)
BARCODE_HEIGHT = 200        # 条形码输出高度 (px)
MODULE_WIDTH = 10           # 最小模块宽度 (px)
QUIET_ZONE_RATIO = 0.12     # 静区占宽度的比例
PNG_COMPRESSION = 6         # PNG 压缩级别


# ============================================================================
# 工具函数
# ============================================================================

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def random_barcode_data(bc_type='code128'):
    """生成随机条形码数据。"""
    if bc_type == 'code128':
        # Code128 支持全 ASCII
        length = random.randint(8, 20)
        return ''.join(random.choices(string.ascii_letters + string.digits + ' _-', k=length))
    elif bc_type == 'ean13':
        return ''.join(random.choices(string.digits, k=12))
    elif bc_type == 'ean8':
        return ''.join(random.choices(string.digits, k=7))
    elif bc_type == 'code39':
        length = random.randint(6, 15)
        return ''.join(random.choices(string.ascii_uppercase + string.digits + '.- $/+%', k=length))
    elif bc_type == 'upca':
        return ''.join(random.choices(string.digits, k=11))
    else:
        return ''.join(random.choices(string.digits, k=random.randint(8, 16)))


def generate_barcode_image(data, bc_type='code128', width=BARCODE_WIDTH, height=BARCODE_HEIGHT):
    """
    使用 python-barcode 生成干净的条形码图像。

    返回 BGR numpy 数组。
    """
    # 选择条形码类型
    bc_classes = {
        'code128': Code128,
        'ean13': EAN13,
        'ean8': EAN8,
        'code39': Code39,
        'upca': UPCA,
    }
    bc_cls = bc_classes.get(bc_type, Code128)

    try:
        # 生成条形码
        bc = bc_cls(data, writer=ImageWriter())

        # 渲染到 PIL Image
        options = {
            'module_width': MODULE_WIDTH,
            'module_height': height * 0.6,
            'quiet_zone': int(width * QUIET_ZONE_RATIO),
            'write_text': True,
            'text_distance': 5,
            'font_size': 10,
        }
        # ImageWriter 返回的是 BytesIO
        fp = io.BytesIO()
        bc.write(fp, options)
        fp.seek(0)
        pil_img = PILImage.open(fp).convert('RGB')

        # 缩放到目标尺寸
        pil_img = pil_img.resize((width, height), PILImage.LANCZOS)
        img = np.array(pil_img)
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    except Exception as e:
        # 如果数据无效(如 EAN 校验位问题), 重试
        return None


def generate_valid_barcode(width=BARCODE_WIDTH, height=BARCODE_HEIGHT):
    """生成一张有效的条形码图像，容错重试。"""
    bc_types = ['code128', 'ean13', 'ean8', 'code39']
    max_retries = 10
    for _ in range(max_retries):
        bc_type = random.choice(bc_types)
        data = random_barcode_data(bc_type)
        img = generate_barcode_image(data, bc_type, width, height)
        if img is not None:
            return img, bc_type, data
    # 最终回退
    img = generate_barcode_image('12345678', 'code128', width, height)
    return img, 'code128', '12345678'


def pad_to_height(img, target_h):
    """垂直居中填充到目标高度 (白底)。"""
    h, w = img.shape[:2]
    if h >= target_h:
        return img
    canvas = np.full((target_h, w, 3), 255, dtype=np.uint8)
    oy = (target_h - h) // 2
    canvas[oy:oy + h, :] = img
    return canvas


# ============================================================================
# Task A: 局部遮挡与墨水污染
# ============================================================================

def generate_ink_blob_mask(h, w, num_blobs=None, blob_radius_range=None):
    """
    生成不规则墨水团块蒙版。

    算法: 随机种子点 → 多个重叠椭圆 → 高斯模糊 → 阈值 → 墨迹边缘效果。

    参数:
        h, w:               蒙版尺寸
        num_blobs:          墨团数量 (None=随机)
        blob_radius_range:  墨团半径范围 (None=默认)
    返回:
        uint8 mask, 0=无墨, 255=有墨
    """
    if num_blobs is None:
        num_blobs = random.randint(2, 8)
    if blob_radius_range is None:
        blob_radius_range = (8, 35)

    mask = np.zeros((h, w), dtype=np.uint8)

    for _ in range(num_blobs):
        cx = random.randint(0, w - 1)
        cy = random.randint(0, h - 1)
        rx = random.randint(*blob_radius_range)
        ry = random.randint(*blob_radius_range)
        angle = random.uniform(0, 360)
        # 绘制旋转椭圆
        cv2.ellipse(mask, (cx, cy), (rx, ry), angle, 0, 360, 255, -1)

    # 柔化边缘 + 阈值 → 不规则墨迹
    blur_k = random.choice([5, 7, 9])
    mask = cv2.GaussianBlur(mask, (blur_k, blur_k), blur_k // 2)
    _, mask = cv2.threshold(mask, 50, 255, cv2.THRESH_BINARY)

    # 形态学操作增加自然感
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    # 随机膨胀/腐蚀增加变化
    if random.random() < 0.4:
        d_k = random.choice([3, 5])
        d_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d_k, d_k))
        if random.random() < 0.5:
            mask = cv2.dilate(mask, d_kernel, iterations=1)
        else:
            mask = cv2.erode(mask, d_kernel, iterations=1)

    return mask


def generate_ink_survivable(index):
    """
    生成可恢复墨水污染图。

    约束: 墨团不贯穿条形码高度，保留顶部或底部 ≥10% 高度的干净通道。
    """
    img, bc_type, data = generate_valid_barcode()
    h, w = img.shape[:2]
    clean_margin = int(h * 0.12)  # 至少 12% 的高度保持干净

    # 随机选择保留顶部或底部
    protect_top = random.random() < 0.5
    ink_mask = np.zeros((h, w), dtype=np.uint8)

    if protect_top:
        # 底部污染，保留顶部通道
        roi_top = 0
        roi_bottom = h - clean_margin
        protected = (0, roi_bottom, w, h)
        allowed = (clean_margin, h)
    else:
        # 顶部污染，保留底部通道
        roi_top = clean_margin
        roi_bottom = h
        protected = (0, 0, w, clean_margin)
        allowed = (0, h - clean_margin)

    # 在允许污染的区域生成墨团
    region_h = roi_bottom - roi_top
    region_mask = generate_ink_blob_mask(region_h, w,
                                         num_blobs=random.randint(3, 10),
                                         blob_radius_range=(5, 30))
    ink_mask[roi_top:roi_bottom, :] = region_mask

    # 叠加: 墨区像素替换为近黑色
    result = img.copy()
    # 墨水颜色: 深黑到深灰
    ink_color = np.random.randint(0, 40, size=(1, 1, 3), dtype=np.uint8)
    result[ink_mask > 0] = ink_color

    bc_short = bc_type.upper()
    fname = f"barcode_ink_survive_{index:04d}_{bc_short}.png"
    return fname, result


def generate_ink_fatal(index):
    """
    生成致命断裂污染图。

    效果: 画一条或多条粗黑水平线，从左到右完全切断所有黑白条。
    任何单根水平扫描线都会穿过污染区。
    """
    img, bc_type, data = generate_valid_barcode()
    h, w = img.shape[:2]

    result = img.copy()
    num_lines = random.randint(1, 3)

    for _ in range(num_lines):
        line_y = random.randint(int(h * 0.2), int(h * 0.8))
        line_thickness = random.randint(3, 12)

        # 添加轻微不规则性: 波浪线
        pts_x = np.arange(0, w, dtype=np.int32)
        pts_y = line_y + (np.sin(pts_x / random.uniform(30, 80)) *
                          random.uniform(1, 3)).astype(np.int32)

        # 绘制粗线条
        for t in range(-line_thickness // 2, line_thickness // 2 + 1):
            y_shifted = np.clip(pts_y + t, 0, h - 1)
            result[y_shifted, pts_x] = (0, 0, 0)

    bc_short = bc_type.upper()
    fname = f"barcode_ink_fatal_{index:04d}_{bc_short}.png"
    return fname, result


# ============================================================================
# Task B: 物理划痕与断裂
# ============================================================================

def add_scratches(img, num_scratches=None, scratch_color_range=None,
                  thickness_range=(1, 4), length_range=None):
    """
    在条形码图像上添加物理划痕。

    划痕模拟: 硬物刮擦导致的白色/灰色细线，切断黑色竖条。

    参数:
        img:                 BGR 图像
        num_scratches:       划痕数量
        scratch_color_range: 划痕颜色范围 (BGR 列表)
        thickness_range:     线宽范围
        length_range:        长度范围 (相对图像宽度的比例)
    返回:
        带划痕的图像
    """
    if num_scratches is None:
        num_scratches = random.randint(4, 15)
    if scratch_color_range is None:
        # 白色到浅灰的划痕
        scratch_color_range = [
            (255, 255, 255),
            (240, 240, 240),
            (220, 220, 220),
            (200, 200, 200),
            (180, 180, 180),
        ]
    if length_range is None:
        length_range = (0.2, 0.7)

    h, w = img.shape[:2]
    result = img.copy()

    for _ in range(num_scratches):
        color = random.choice(scratch_color_range)
        thickness = random.randint(*thickness_range)

        # 随机起点和方向
        start_x = random.randint(0, w - 1)
        start_y = random.randint(0, h - 1)
        # 方向偏水平或对角
        angle = random.uniform(-math.pi / 3, math.pi / 3)  # ±60°
        if random.random() < 0.3:
            angle = random.uniform(math.pi / 4, 3 * math.pi / 4)  # 偏垂直

        length = int(w * random.uniform(*length_range))
        end_x = int(np.clip(start_x + length * math.cos(angle), 0, w - 1))
        end_y = int(np.clip(start_y + length * math.sin(angle), 0, h - 1))

        cv2.line(result, (start_x, start_y), (end_x, end_y), color, thickness, cv2.LINE_AA)

    return result


def add_gaussian_noise(img, sigma=5.0):
    """添加轻微高斯白噪声 (模拟劣质打印)。"""
    noise = np.random.normal(0, sigma, img.shape).astype(np.float32)
    noisy = img.astype(np.float32) + noise
    return np.clip(noisy, 0, 255).astype(np.uint8)


def generate_scratches_image(index):
    """
    生成物理划痕测试图。

    效果: 白色/灰色划线 + 可选高斯噪声。
    """
    img, bc_type, data = generate_valid_barcode()

    # 划痕
    result = add_scratches(img)

    # 50% 概率叠加高斯噪声
    if random.random() < 0.5:
        result = add_gaussian_noise(result, sigma=random.uniform(2.0, 8.0))

    bc_short = bc_type.upper()
    fname = f"barcode_scratches_{index:04d}_{bc_short}.png"
    return fname, result


# ============================================================================
# Task C: 透视与柱面压缩
# ============================================================================

def apply_perspective_barcode(img, shrink_ratio=None, shrink_side=None):
    """
    对条形码施加侧视透视变换。

    模拟: 从左侧或右侧斜视条形码产生的近大远小效果。

    变换矩阵推导:
        原图四顶点 → 目标四边形 (一边高度被压缩)
        H (3×3 单应性) = getPerspectiveTransform(src, dst)

    参数:
        img:           BGR 图像
        shrink_ratio:  高度压缩比 (None=随机 0.2~0.7)
        shrink_side:   'left'|'right'|'random'
    返回:
        透视变换后图像
    """
    if shrink_ratio is None:
        shrink_ratio = random.uniform(0.2, 0.7)
    if shrink_side is None:
        shrink_side = random.choice(['left', 'right'])

    h, w = img.shape[:2]

    # 原图四顶点 (TL, TR, BR, BL)
    src_pts = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])

    # 压缩一侧的高度
    new_height = int(h * shrink_ratio)
    if shrink_side == 'left':
        # 左侧压缩
        dst_pts = np.float32([
            [0, (h - new_height) // 2],           # TL 下移
            [w - 1, 0],                           # TR 不变
            [w - 1, h - 1],                       # BR 不变
            [0, (h + new_height) // 2],           # BL 上移
        ])
    else:
        # 右侧压缩
        dst_pts = np.float32([
            [0, 0],                                          # TL 不变
            [w - 1, (h - new_height) // 2],                  # TR 下移
            [w - 1, (h + new_height) // 2],                  # BR 上移
            [0, h - 1],                                      # BL 不变
        ])

    H = cv2.getPerspectiveTransform(src_pts, dst_pts)

    # 计算输出边界
    boundary = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(boundary, H).reshape(-1, 2)
    min_x = int(max(0, np.floor(transformed[:, 0].min())))
    min_y = int(max(0, np.floor(transformed[:, 1].min())))
    max_x = int(np.ceil(transformed[:, 0].max()))
    max_y = int(np.ceil(transformed[:, 1].max()))

    # 调整 H 使结果左上对齐
    H_adj = np.array([[1, 0, -min_x], [0, 1, -min_y], [0, 0, 1]], dtype=np.float64)
    H_final = H_adj @ H

    result = cv2.warpPerspective(img, H_final, (max_x - min_x, max_y - min_y),
                                  borderMode=cv2.BORDER_CONSTANT,
                                  borderValue=(255, 255, 255))
    return result


def apply_cylinder_warp_horizontal(img, curvature=None):
    """
    对条形码施加横向柱面弯曲。

    数学原理:
        条形码水平贴在圆柱表面 → 左右两侧被压缩。
        x_new = cx + R * arcsin((x - cx) / R)
        当 x 靠近边缘时, arcsin 梯度增大 → 条宽被压缩。

        映射: x' = cx + R * sin((x - cx) / R)
               y' = y (垂直不变)

    参数:
        img:        BGR 图像
        curvature:  曲率 [0,1], 0=平面, 1=强弯曲 (None=随机)
    返回:
        弯曲后图像
    """
    if curvature is None:
        curvature = random.uniform(0.3, 0.9)

    h, w = img.shape[:2]
    cx = w / 2.0
    # 曲率越大 R 越小
    R = max(w * 0.3, w / (curvature * math.pi * 2 + 0.01))

    y, x = np.mgrid[0:h, 0:w].astype(np.float32)

    # 柱面水平映射
    dx = (x - cx) / R
    # 限制在有效范围防止映射坐标溢出
    dx = np.clip(dx, -math.pi / 2 + 0.1, math.pi / 2 - 0.1)
    map_x = cx + R * np.sin(dx)
    map_y = y  # 垂直不变

    result = cv2.remap(img, map_x, map_y,
                       interpolation=cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT,
                       borderValue=(255, 255, 255))
    return result


def generate_geometric_image(index):
    """
    生成几何畸变测试图。

    随机选择: 纯透视 / 纯柱面 / 透视+柱面复合。
    """
    img, bc_type, data = generate_valid_barcode()
    h, w = img.shape[:2]

    variant = random.choices(
        ['perspective', 'cylinder', 'combo'],
        weights=[35, 35, 30]
    )[0]

    if variant == 'perspective':
        shrink_ratio = random.uniform(0.25, 0.7)
        side = random.choice(['left', 'right'])
        result = apply_perspective_barcode(img, shrink_ratio, side)
        fname = f"barcode_geo_persp_{index:04d}_{bc_type.upper()}.png"

    elif variant == 'cylinder':
        curvature = random.uniform(0.3, 0.85)
        result = apply_cylinder_warp_horizontal(img, curvature)
        fname = f"barcode_geo_cyl_{index:04d}_{bc_type.upper()}.png"

    else:  # combo
        # 先透视后柱面
        shrink_ratio = random.uniform(0.4, 0.8)
        side = random.choice(['left', 'right'])
        result = apply_perspective_barcode(img, shrink_ratio, side)
        curvature = random.uniform(0.2, 0.6)
        result = apply_cylinder_warp_horizontal(result, curvature)
        fname = f"barcode_geo_combo_{index:04d}_{bc_type.upper()}.png"

    # 确保输出尺寸合理
    rh, rw = result.shape[:2]
    if rw < 100 or rh < 30:
        result = cv2.resize(result, (max(rw, 300), max(rh, 100)),
                            interpolation=cv2.INTER_LANCZOS4)

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


class InkWrapper:
    """Task A 包装器: 可恢复/致命 各半。"""

    def __init__(self, total):
        self.total = total

    def generate(self, index):
        if index < self.total // 2:
            return generate_ink_survivable(index)
        else:
            return generate_ink_fatal(index - self.total // 2)


# ============================================================================
# Task D: 运动模糊 (Motion Blur)
# ============================================================================

def motion_blur_kernel(length, angle_deg):
    kernel = np.zeros((length, length), dtype=np.float32)
    center = length // 2
    angle_rad = np.deg2rad(angle_deg)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    for i in range(length):
        dx = int(center + (i - center) * cos_a)
        dy = int(center + (i - center) * sin_a)
        if 0 <= dx < length and 0 <= dy < length:
            kernel[dy, dx] = 1.0
    kernel /= kernel.sum()
    return kernel


def generate_motion_blur_image(index):
    img, bc_type, data = generate_valid_barcode()
    length = random.choice([7, 9, 11, 13, 15])
    angle = random.uniform(0, 180)
    kernel = motion_blur_kernel(length, angle)
    blurred = cv2.filter2D(img, -1, kernel)
    fname = f"barcode_mblur_{index:04d}_{bc_type.upper()}.png"
    return fname, blurred


# ============================================================================
# Task E: 镜面高光 (Specular Highlight)
# ============================================================================

def generate_highlight_image(index):
    img, bc_type, data = generate_valid_barcode()
    h, w = img.shape[:2]
    result = img.astype(np.float32)
    num_spots = random.randint(1, 3)
    for _ in range(num_spots):
        cx = random.randint(w // 6, 5 * w // 6)
        cy = random.randint(h // 4, 3 * h // 4)
        rx = random.randint(30, 80)
        ry = random.randint(20, 50)
        angle = random.uniform(0, 360)
        mask = np.zeros((h, w), dtype=np.float32)
        cv2.ellipse(mask, (cx, cy), (rx, ry), angle, 0, 360, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (31, 31), 15)
        intensity = random.uniform(0.3, 0.7)
        for c in range(3):
            result[:, :, c] = result[:, :, c] * (1 - mask * intensity) + 255 * mask * intensity
    result = np.clip(result, 0, 255).astype(np.uint8)
    fname = f"barcode_highlight_{index:04d}_{bc_type.upper()}.png"
    return fname, result


# ============================================================================
# Task F: 低对比度 (Low Contrast)
# ============================================================================

def generate_lowcontrast_image(index):
    img, bc_type, data = generate_valid_barcode()
    h, w = img.shape[:2]
    fade_level = random.randint(60, 140)
    paper_darken = random.randint(180, 235)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    ratio = gray / 255.0
    # Keep black bars dark, white background light
    new_gray = fade_level + (paper_darken - fade_level) * ratio
    new_gray = np.clip(new_gray, 0, 255).astype(np.uint8)
    result = cv2.cvtColor(new_gray, cv2.COLOR_GRAY2BGR)
    fname = f"barcode_lowcontrast_{index:04d}_{bc_type.upper()}.png"
    return fname, result


# ============================================================================
# Task G: 柱面弯曲 (Cylinder Warp — dedicated)
# ============================================================================

def generate_cylinder_image(index):
    img, bc_type, data = generate_valid_barcode()
    curvature = random.uniform(0.3, 0.9)
    result = apply_cylinder_warp_horizontal(img, curvature)
    fname = f"barcode_cylinder_{index:04d}_{bc_type.upper()}.png"
    return fname, result


# ============================================================================
# 主入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='一维条形码压力测试数据集生成器')
    parser.add_argument('--count', type=int, default=110,
                        help='每个任务生成数量 (默认 110)')
    parser.add_argument('--output', type=str,
                        default='../../images/stress_test',
                        help='输出根目录')
    parser.add_argument('--no-ink', action='store_true',
                        help='跳过 Task A 墨水污染')
    parser.add_argument('--no-scratches', action='store_true',
                        help='跳过 Task B 物理划痕')
    parser.add_argument('--no-geometric', action='store_true',
                        help='跳过 Task C 几何畸变')
    parser.add_argument('--no-blur', action='store_true',
                        help='跳过 Task D 运动模糊')
    parser.add_argument('--no-highlight', action='store_true',
                        help='跳过 Task E 镜面高光')
    parser.add_argument('--no-lowcontrast', action='store_true',
                        help='跳过 Task F 低对比度')
    parser.add_argument('--no-cylinder', action='store_true',
                        help='跳过 Task G 柱面弯曲')
    parser.add_argument('--no-parallel', action='store_true',
                        help='禁用多线程')
    args = parser.parse_args()

    root = os.path.abspath(args.output)
    count = max(args.count, 100)
    parallel = not args.no_parallel

    ink_count = (count // 2) * 2

    print("=" * 60)
    print("  一维条形码压力测试数据集生成器")
    print(f"  Task A 墨水污染: {ink_count} 张 (可恢复/致命各 {ink_count // 2})")
    print(f"  Task B 物理划痕: {count} 张")
    print(f"  Task C 几何畸变: {count} 张")
    print(f"  Task D 运动模糊: {count} 张")
    print(f"  Task E 镜面高光: {count} 张")
    print(f"  Task F 低对比度: {count} 张")
    print(f"  Task G 柱面弯曲: {count} 张")
    print(f"  输出目录: {root}")
    print("=" * 60)

    if not args.no_ink:
        wrapper = InkWrapper(ink_count)
        batch_generate(wrapper.generate,
                       os.path.join(root, 'barcode_ink'),
                       ink_count,
                       'Task A: 墨水污染 (可恢复/致命)',
                       parallel=parallel)

    if not args.no_scratches:
        batch_generate(generate_scratches_image,
                       os.path.join(root, 'barcode_scratches'),
                       count,
                       'Task B: 物理划痕 + 高斯噪声',
                       parallel=parallel)

    if not args.no_geometric:
        batch_generate(generate_geometric_image,
                       os.path.join(root, 'barcode_geometric'),
                       count,
                       'Task C: 透视 + 柱面弯曲',
                       parallel=parallel)

    if not args.no_blur:
        batch_generate(generate_motion_blur_image,
                       os.path.join(root, 'barcode_motion_blur'),
                       count,
                       'Task D: 运动模糊',
                       parallel=parallel)

    if not args.no_highlight:
        batch_generate(generate_highlight_image,
                       os.path.join(root, 'barcode_highlight'),
                       count,
                       'Task E: 镜面高光',
                       parallel=parallel)

    if not args.no_lowcontrast:
        batch_generate(generate_lowcontrast_image,
                       os.path.join(root, 'barcode_lowcontrast'),
                       count,
                       'Task F: 低对比度',
                       parallel=parallel)

    if not args.no_cylinder:
        batch_generate(generate_cylinder_image,
                       os.path.join(root, 'barcode_cylinder'),
                       count,
                       'Task G: 柱面弯曲',
                       parallel=parallel)

    print(f"\n{'='*60}")
    print(f"  全部完成!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
