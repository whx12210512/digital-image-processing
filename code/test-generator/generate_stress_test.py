#!/usr/bin/env python3
"""
QR 码压力测试数据集自动生成器
=================================
数字图像处理课程大作业 — 任务四：条形码/二维码识别
南方科技大学 电子与电气工程系 · 2026

用途: 生成三类压力测试数据集，用于检验传统图像处理算法在
      "多码同框"和"污损/低质量二维码"场景下的鲁棒性。

输出:
    images/stress_test/
    ├── multi_qr/         # 任务1: 多码同框 (≥100张)
    ├── illumination/     # 任务2: 局部阴影与光照不均 (≥100张)
    └── damage_noise/     # 任务3: 物理污损与噪点 (≥100张)

使用:
    python generate_stress_test.py
    python generate_stress_test.py --count 150 --output ../../images/stress_test
"""

import cv2
import numpy as np
from PIL import Image
import qrcode
import random
import os
import argparse
import string
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================================
# 全局常量
# ============================================================================
CANVAS_WIDTH = 1280       # 多码同框画布宽度
CANVAS_HEIGHT = 720       # 多码同框画布高度
QR_SIZE = 200             # 单码默认分辨率 (会被缩放)
BORDER = 2                # QR 码白色边框 (模块数)
PNG_COMPRESSION = 6       # PNG 压缩级别 (0-9, 9=最小文件)
JPEG_QUALITY = 92         # JPEG 质量 (用于多码图, 减少存储)

# ============================================================================
# 工具函数
# ============================================================================

def random_qr_data():
    """生成随机二维码内容 (URL / 文本 / 数字混用)。"""
    rtype = random.choice(['url', 'text', 'numeric', 'vcard_like'])
    if rtype == 'url':
        domain = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
        path = ''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 8)))
        return f"https://{domain}.com/{path}"
    elif rtype == 'text':
        length = random.randint(8, 35)
        return ''.join(random.choices(string.ascii_letters + string.digits + ' _-', k=length))
    elif rtype == 'numeric':
        length = random.randint(10, 16)
        return ''.join(random.choices(string.digits, k=length))
    else:
        # 模拟名片信息
        name = ''.join(random.choices(string.ascii_uppercase, k=random.randint(2, 4)))
        phone = ''.join(random.choices(string.digits, k=11))
        return f"BEGIN:VCARD\nN:{name}\nTEL:{phone}\nEND:VCARD"


def generate_qr_image(data, size=QR_SIZE, border=BORDER, ecc=qrcode.constants.ERROR_CORRECT_M):
    """
    生成单张 QR 码，返回 BGR numpy 数组。

    参数:
        data:  二维码编码内容
        size:  输出图像尺寸 (px)
        border:白色边框模块数
        ecc:   纠错等级 (L/M/Q/H)
    返回:
        BGR numpy 数组, shape=(size, size, 3)
    """
    qr = qrcode.QRCode(version=None, error_correction=ecc, box_size=10, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    img_pil = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    img_pil = img_pil.resize((size, size), Image.LANCZOS)
    img = np.array(img_pil)  # RGB
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def random_ecc():
    """随机返回一个纠错等级，H 概率略低 (更贴近实际使用中 M/Q 居多)。"""
    return random.choices(
        [qrcode.constants.ERROR_CORRECT_L,
         qrcode.constants.ERROR_CORRECT_M,
         qrcode.constants.ERROR_CORRECT_Q,
         qrcode.constants.ERROR_CORRECT_H],
        weights=[10, 40, 35, 15]
    )[0]


def safe_paste(canvas, patch, x, y):
    """
    将 patch 安全粘贴到 canvas 的 (x, y) 位置。
    自动裁剪越界部分，防止 IndexError。
    """
    h_c, w_c = canvas.shape[:2]
    h_p, w_p = patch.shape[:2]

    # 计算有效重叠区域
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(w_c, x + w_p)
    y2 = min(h_c, y + h_p)

    px1 = x1 - x
    py1 = y1 - y
    px2 = px1 + (x2 - x1)
    py2 = py1 + (y2 - y1)

    if x2 <= x1 or y2 <= y1:
        return  # 完全越界，跳过

    if patch.shape[2] == 4:  # 带 alpha 通道
        alpha = patch[py1:py2, px1:px2, 3:4] / 255.0
        canvas[y1:y2, x1:x2] = (
            patch[py1:py2, px1:px2, :3] * alpha +
            canvas[y1:y2, x1:x2] * (1 - alpha)
        ).astype(np.uint8)
    else:
        canvas[y1:y2, x1:x2] = patch[py1:py2, px1:px2]


def ensure_dir(path):
    """确保目录存在。"""
    Path(path).mkdir(parents=True, exist_ok=True)


# ============================================================================
# 任务 1: 多码同框测试集 (Multi-QR Dataset)
# ============================================================================

def apply_affine_transform(img, angle_deg, scale, tx, ty):
    """
    对图像施加仿射变换 (旋转 + 缩放 + 平移)。

    参数:
        img:      输入图像 (BGR numpy)
        angle_deg:旋转角度 (°)
        scale:    缩放比例 (1.0 = 原始大小)
        tx, ty:   平移量 (px)
    返回:
        变换后的图像 (保持原始尺寸)
    """
    h, w = img.shape[:2]
    center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle_deg, scale)
    M[0, 2] += tx
    M[1, 2] += ty
    # 扩大输出画布避免裁剪
    bw = int(w * abs(scale) * 1.5)
    bh = int(h * abs(scale) * 1.5)
    M[0, 2] += bw / 2 - center[0]
    M[1, 2] += bh / 2 - center[1]
    result = cv2.warpAffine(img, M, (bw, bh),
                             borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(255, 255, 255))
    return result


def generate_multi_qr_background(w, h):
    """
    生成复杂背景画布。
    随机选择: 纯白 / 浅色渐变 / 模拟纸张纹理 / 彩色噪点。
    """
    bg_type = random.choice(['white', 'gradient', 'paper', 'noise'])
    canvas = np.zeros((h, w, 3), dtype=np.uint8)

    if bg_type == 'white':
        canvas[:] = (255, 255, 255)
    elif bg_type == 'gradient':
        for y in range(h):
            t = y / h
            r = int(220 + 35 * t)
            g = int(220 + 35 * (1 - t))
            b = int(230 + 25 * random.random())
            canvas[y, :] = (b, g, r)
    elif bg_type == 'paper':
        canvas[:] = (245, 243, 235)
        noise = np.random.randint(-8, 9, (h, w, 3), dtype=np.int16)
        canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    elif bg_type == 'noise':
        canvas[:] = (255, 255, 255)
        speckle = np.random.randint(-15, 16, (h, w, 3), dtype=np.int16)
        canvas = np.clip(canvas.astype(np.int16) + speckle, 0, 255).astype(np.uint8)

    return canvas


def generate_multi_qr_image(index, num_codes=None):
    """
    生成一张多码同框测试图。

    参数:
        index:     图片编号 (用于文件名)
        num_codes: QR 码数量 (None = 随机 2~5)
    返回:
        (filename, numpy BGR image)
    """
    if num_codes is None:
        num_codes = random.randint(2, 5)

    canvas = generate_multi_qr_background(CANVAS_WIDTH, CANVAS_HEIGHT)
    used_positions = []  # 记录已占用的边界框，用于避免过度重叠

    for i in range(num_codes):
        data = random_qr_data()
        ecc = random_ecc()
        qr_clean = generate_qr_image(data, size=QR_SIZE, ecc=ecc)

        # 随机仿射参数
        angle = random.uniform(-45, 45)
        scale = random.uniform(0.4, 1.2)
        # 平移量 (确保不超出画布太远)
        tx = random.randint(-80, 80)
        ty = random.randint(-80, 80)

        qr_transformed = apply_affine_transform(qr_clean, angle, scale, tx, ty)

        # 随机放置位置 (均匀分布画布)
        h_qr, w_qr = qr_transformed.shape[:2]
        max_x = max(0, CANVAS_WIDTH - w_qr)
        max_y = max(0, CANVAS_HEIGHT - h_qr)
        px = random.randint(0, max(1, max_x))
        py = random.randint(0, max(1, max_y))

        # 轻微避让: 避免与已放置码完全重叠
        attempts = 0
        while attempts < 10 and used_positions:
            overlap = False
            for (ux, uy, uw, uh) in used_positions:
                iou_x = max(0, min(px + w_qr, ux + uw) - max(px, ux))
                iou_y = max(0, min(py + h_qr, uy + uh) - max(py, uy))
                iou = (iou_x * iou_y) / min(w_qr * h_qr, uw * uh)
                if iou > 0.3:
                    overlap = True
                    break
            if not overlap:
                break
            attempts += 1
            px = random.randint(0, max(1, max_x))
            py = random.randint(0, max(1, max_y))

        used_positions.append((px, py, w_qr, h_qr))
        safe_paste(canvas, qr_transformed, px, py)

    fname = f"multi_qr_{index:04d}.jpg"
    return fname, canvas


# ============================================================================
# 任务 2: 局部阴影与光照不均测试集 (Illumination Dataset)
# ============================================================================

def gaussian_surface(w, h, cx=None, cy=None, sigma_x=None, sigma_y=None, amplitude=0.6):
    """
    生成二维高斯表面蒙版。

    参数:
        w, h:       画布宽高
        cx, cy:     高斯中心 (None = 随机位置)
        sigma_x, y: 标准差 (None = 随机)
        amplitude:  幅值 [0, 1], 越大越暗
    返回:
        float32 numpy, shape=(h,w), 值域 [0, 1]
    """
    if cx is None:
        cx = random.uniform(0.1 * w, 0.9 * w)
    if cy is None:
        cy = random.uniform(0.1 * h, 0.9 * h)
    if sigma_x is None:
        sigma_x = random.uniform(w * 0.15, w * 0.5)
    if sigma_y is None:
        sigma_y = random.uniform(h * 0.15, h * 0.5)

    y, x = np.mgrid[0:h, 0:w]
    g = np.exp(-((x - cx) ** 2 / (2 * sigma_x ** 2) + (y - cy) ** 2 / (2 * sigma_y ** 2)))
    # 归一化到 [0, amplitude]
    g = (g / g.max()) * amplitude
    return g.astype(np.float32)


def linear_gradient_mask(w, h, direction=None, intensity=0.5):
    """
    生成线性渐变蒙版。

    参数:
        w, h:      画布宽高
        direction: 'left','right','top','bottom','diagonal' (None = 随机)
        intensity: 渐变强度 [0, 1]
    返回:
        float32 numpy, shape=(h,w), 值域 [0, intensity]
    """
    if direction is None:
        direction = random.choice(['left', 'right', 'top', 'bottom', 'diagonal'])

    y, x = np.mgrid[0:h, 0:w]
    if direction == 'left':
        mask = x.astype(np.float32) / w
    elif direction == 'right':
        mask = (w - x).astype(np.float32) / w
    elif direction == 'top':
        mask = y.astype(np.float32) / h
    elif direction == 'bottom':
        mask = (h - y).astype(np.float32) / h
    elif direction == 'diagonal':
        mask = ((x / w) + (y / h)) / 2.0
    # 加轻微随机扰动
    noise = np.random.uniform(-0.05, 0.05, (h, w)).astype(np.float32)
    mask = np.clip(mask + noise, 0, 1) * intensity
    return mask.astype(np.float32)


def apply_shadow(img, mask):
    """
    将阴影蒙版叠加到图像上 (乘法暗化)。

    参数:
        img:  BGR uint8 图像
        mask: float32, 值域 [0,1], 0=全黑, 1=不变
    返回:
        暗化后的 BGR uint8 图像
    """
    img_f = img.astype(np.float32)
    mask_3ch = np.stack([mask, mask, mask], axis=-1)
    result = img_f * (1.0 - mask_3ch) + 255 * mask_3ch * 0.15  # 暗区带轻微底灰
    return np.clip(result, 0, 255).astype(np.uint8)


def generate_illumination_image(index):
    """
    生成一张光照不均测试图。

    效果组合 (随机 1~2 种):
      - 高斯亮斑 (圆形强光反光)
      - 高斯暗斑 (手电筒阴影)
      - 线性渐变 (左暗右亮等)
    """
    data = random_qr_data()
    ecc = random_ecc()
    qr_img = generate_qr_image(data, ecc=ecc)
    h, w = qr_img.shape[:2]

    effects = random.randint(1, 2)
    for _ in range(effects):
        effect_type = random.choice(['bright_spot', 'dark_spot', 'gradient'])
        if effect_type == 'bright_spot':
            mask = gaussian_surface(w, h, amplitude=random.uniform(0.3, 0.8))
            qr_img = apply_shadow(qr_img, mask)
        elif effect_type == 'dark_spot':
            mask = gaussian_surface(w, h, amplitude=random.uniform(0.3, 0.7))
            # 反转：中心亮、边缘暗 → 用局部区域
            y_center = int(h * random.uniform(0.2, 0.8))
            x_center = int(w * random.uniform(0.2, 0.8))
            local_mask = np.zeros((h, w), dtype=np.float32)
            radius = random.randint(40, 120)
            cv2.circle(local_mask, (x_center, y_center), radius, 1.0, -1)
            local_mask = cv2.GaussianBlur(local_mask, (61, 61), 30)
            local_mask = local_mask * random.uniform(0.4, 0.75)
            qr_img = apply_shadow(qr_img, local_mask)
        elif effect_type == 'gradient':
            mask = linear_gradient_mask(w, h, intensity=random.uniform(0.3, 0.7))
            qr_img = apply_shadow(qr_img, mask)

    fname = f"illumination_{index:04d}.png"
    return fname, qr_img


# ============================================================================
# 任务 3: 物理污损与噪点测试集 (Damage & Noise Dataset)
# ============================================================================

def apply_scratches(img, num_scratches=None, thickness_range=(1, 4),
                    color_range=None, length_ratio_range=(0.1, 0.5)):
    """
    在图像上施加随机划痕 (模拟物理刮擦)。

    参数:
        img:                BGR uint8 图像
        num_scratches:      划痕数量 (None = 随机 2~8)
        thickness_range:    线宽范围
        color_range:        颜色范围 (None = 自动含白/灰/黑)
        length_ratio_range: 划痕长度相对图像尺寸的比例范围
    返回:
        带划痕的图像
    """
    if num_scratches is None:
        num_scratches = random.randint(2, 8)
    if color_range is None:
        colors = [(255, 255, 255), (200, 200, 200), (150, 150, 150),
                  (0, 0, 0), (50, 50, 50)]

    h, w = img.shape[:2]
    result = img.copy()

    for _ in range(num_scratches):
        # 随机起点和方向
        x1 = random.randint(0, w - 1)
        y1 = random.randint(0, h - 1)
        length = int(min(w, h) * random.uniform(*length_ratio_range))
        angle = random.uniform(0, 2 * np.pi)
        x2 = int(np.clip(x1 + length * np.cos(angle), 0, w - 1))
        y2 = int(np.clip(y1 + length * np.sin(angle), 0, h - 1))

        color = random.choice(colors)
        thickness = random.randint(*thickness_range)
        cv2.line(result, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)

    return result


def apply_salt_pepper_noise(img, amount=0.02, salt_vs_pepper=0.5):
    """
    施加椒盐噪声。

    参数:
        img:            BGR uint8 图像
        amount:         噪声比例 [0, 1]
        salt_vs_pepper: 盐噪声 (白) 占比
    返回:
        带噪声的图像
    """
    result = img.copy()
    h, w = result.shape[:2]
    num_pixels = int(h * w * amount)

    # Salt (白色)
    num_salt = int(num_pixels * salt_vs_pepper)
    salt_coords = (np.random.randint(0, h, num_salt),
                   np.random.randint(0, w, num_salt))
    result[salt_coords] = (255, 255, 255)

    # Pepper (黑色)
    num_pepper = num_pixels - num_salt
    pepper_coords = (np.random.randint(0, h, num_pepper),
                     np.random.randint(0, w, num_pepper))
    result[pepper_coords] = (0, 0, 0)

    return result


def apply_local_blur(img, num_regions=None, kernel_range=(5, 15)):
    """
    对图像施加局部高斯模糊 (模拟对焦不准)。

    参数:
        img:          BGR uint8 图像
        num_regions:  模糊区域数量 (None = 随机 1~4)
        kernel_range: 高斯核大小范围 (奇数)
    返回:
        局部模糊的图像
    """
    if num_regions is None:
        num_regions = random.randint(1, 4)

    h, w = img.shape[:2]
    result = img.copy()

    for _ in range(num_regions):
        # 随机圆形模糊区域
        cx = random.randint(0, w - 1)
        cy = random.randint(0, h - 1)
        radius = random.randint(30, min(w, h) // 3)

        # 创建圆形 mask
        mask = np.zeros((h, w), dtype=np.float32)
        cv2.circle(mask, (cx, cy), radius, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (radius // 2 * 2 + 1, radius // 2 * 2 + 1),
                                radius // 3)

        # 对全图模糊，然后用 mask 混合
        ksize = random.randint(*kernel_range)
        if ksize % 2 == 0:
            ksize += 1  # 确保奇数
        blurred = cv2.GaussianBlur(result, (ksize, ksize), 0)

        mask_3ch = np.stack([mask, mask, mask], axis=-1)
        result = (result * (1 - mask_3ch) + blurred * mask_3ch).astype(np.uint8)

    return result


def apply_full_image_blur(img, kernel_size=None):
    """对整图施加轻微高斯模糊。"""
    if kernel_size is None:
        kernel_size = random.choice([3, 5, 7])
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)


def generate_damage_image(index):
    """
    生成一张物理污损测试图。

    效果随机组合:
      - 划痕
      - 椒盐噪声
      - 局部模糊
      - 全图轻微模糊
      - 随机遮挡块
    """
    data = random_qr_data()
    ecc = random_ecc()
    qr_img = generate_qr_image(data, ecc=ecc)

    # 随机选择 1~3 种破坏效果
    effects_pool = ['scratches', 'noise', 'local_blur', 'full_blur', 'occlusion']
    num_effects = random.randint(1, 3)
    effects = random.sample(effects_pool, min(num_effects, len(effects_pool)))

    if 'scratches' in effects:
        qr_img = apply_scratches(qr_img)
    if 'noise' in effects:
        amount = random.choice([0.005, 0.01, 0.02, 0.03, 0.05])
        qr_img = apply_salt_pepper_noise(qr_img, amount=amount)
    if 'local_blur' in effects:
        qr_img = apply_local_blur(qr_img)
    if 'full_blur' in effects:
        qr_img = apply_full_image_blur(qr_img)
    if 'occlusion' in effects:
        qr_img = apply_random_occlusion(qr_img)

    fname = f"damage_{index:04d}.png"
    return fname, qr_img


def apply_random_occlusion(img, num_blocks=None):
    """
    在图像上放置随机遮挡块 (模拟贴纸/污渍)。

    参数:
        img:        BGR uint8 图像
        num_blocks: 遮挡块数量 (None = 随机 1~4)
    返回:
        带遮挡的图像
    """
    if num_blocks is None:
        num_blocks = random.randint(1, 4)

    h, w = img.shape[:2]
    result = img.copy()

    for _ in range(num_blocks):
        bw = random.randint(15, w // 3)
        bh = random.randint(15, h // 3)
        bx = random.randint(0, max(0, w - bw))
        by = random.randint(0, max(0, h - bh))

        block_color = random.choice([
            (0, 0, 0),          # 纯黑
            (255, 255, 255),    # 纯白
            (180, 180, 180),    # 灰
            (120, 90, 70),      # 棕色
            (200, 220, 240),    # 浅蓝
        ])
        # 圆角矩形效果用 filled rectangle + 轻微边缘模糊
        cv2.rectangle(result, (bx, by), (bx + bw, by + bh), block_color, -1)
        # 轻微虚化边缘
        roi = result[max(0, by-2):min(h, by+bh+2), max(0, bx-2):min(w, bx+bw+2)]
        if roi.size > 0:
            result[max(0, by-2):min(h, by+bh+2),
                   max(0, bx-2):min(w, bx+bw+2)] = cv2.GaussianBlur(roi, (3, 3), 0)

    return result


# ============================================================================
# 批量生成主逻辑
# ============================================================================

def batch_generate(generator_func, output_dir, count, desc, parallel=True):
    """
    批量调用生成函数，保存图片到 output_dir。

    参数:
        generator_func:  单张生成函数 func(index) -> (filename, numpy_image)
        output_dir:      输出目录
        count:           生成数量
        desc:            描述文字 (用于打印)
        parallel:        是否多线程并行
    """
    ensure_dir(output_dir)
    print(f"\n{'='*60}")
    print(f"  生成 {desc}: {count} 张 -> {output_dir}")
    print(f"{'='*60}")

    if parallel and count >= 10:
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
            futures = {ex.submit(generator_func, i): i for i in range(count)}
            for future in as_completed(futures):
                try:
                    fname, img = future.result()
                    out_path = os.path.join(output_dir, fname)
                    if fname.endswith('.jpg'):
                        cv2.imwrite(out_path, img,
                                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                    else:
                        cv2.imwrite(out_path, img,
                                    [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
                except Exception as e:
                    print(f"  [!] 生成第 {futures[future]} 张时出错: {e}")
    else:
        for i in range(count):
            try:
                fname, img = generator_func(i)
                out_path = os.path.join(output_dir, fname)
                if fname.endswith('.jpg'):
                    cv2.imwrite(out_path, img,
                                [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                else:
                    cv2.imwrite(out_path, img,
                                [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
            except Exception as e:
                print(f"  [!] 生成第 {i} 张时出错: {e}")
            if (i + 1) % max(1, count // 10) == 0:
                print(f"  ... {i + 1}/{count}")

    # 验证
    actual = len([f for f in os.listdir(output_dir)
                  if f.endswith('.png') or f.endswith('.jpg')])
    print(f"  [OK] {actual} images generated")


def main():
    parser = argparse.ArgumentParser(
        description='QR 码压力测试数据集自动生成器')
    parser.add_argument('--count', type=int, default=110,
                        help='每个数据集生成数量 (默认 110)')
    parser.add_argument('--output', type=str,
                        default='../../images/stress_test',
                        help='输出根目录')
    parser.add_argument('--no-multi', action='store_true',
                        help='跳过 Task 1 多码同框')
    parser.add_argument('--no-illum', action='store_true',
                        help='跳过 Task 2 光照不均')
    parser.add_argument('--no-damage', action='store_true',
                        help='跳过 Task 3 物理污损')
    parser.add_argument('--no-parallel', action='store_true',
                        help='禁用多线程')
    args = parser.parse_args()

    root = os.path.abspath(args.output)
    parallel = not args.no_parallel
    count = max(args.count, 100)  # 至少 100 张

    print("=" * 60)
    print("  QR 码压力测试数据集自动生成器")
    print(f"  每个数据集: {count} 张")
    print(f"  输出目录: {root}")
    print("=" * 60)

    total = 0
    if not args.no_multi:
        batch_generate(generate_multi_qr_image,
                       os.path.join(root, 'multi_qr'), count,
                       'Task 1: 多码同框', parallel=parallel)
        total += 1

    if not args.no_illum:
        batch_generate(generate_illumination_image,
                       os.path.join(root, 'illumination'), count,
                       'Task 2: 光照不均', parallel=parallel)
        total += 1

    if not args.no_damage:
        batch_generate(generate_damage_image,
                       os.path.join(root, 'damage_noise'), count,
                       'Task 3: 物理污损', parallel=parallel)
        total += 1

    print(f"\n{'='*60}")
    print(f"  全部完成! 共生成 {total} 类 × {count} 张压力测试图片")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
