#!/usr/bin/env python3
"""
墨水污染（Ink Blot/Splatter）QR 码压力测试数据集生成器
========================================================
数字图像处理课程大作业 — 任务四：条形码/二维码识别
南方科技大学 电子与电气工程系 · 2026

核心思路:
    使用传统 DIP 方法 (cv2 + numpy 空间域矩阵掩膜) 在 QR 码上叠加
    真实墨水斑块，分为两个测试子集:
      - Task A (data_pollution/):  数据区污染，避开定位符，测试 RS 纠错
      - Task B (corner_destruction/): 定位符毁灭，测试几何推理

墨水斑块算法:
    随机种子点 → 多尺度圆形叠加 → 高斯模糊 → 阈值 → 形态学操作
    → 模拟真实墨水扩散/飞溅的不规则边缘效果。

输出:
    images/stress_test/
    ├── ink_data_pollution/    # Task A: ~200 张 (3 级均匀分布)
    └── ink_corner_destruction/ # Task B: ~100 张

使用:
    python generate_ink_test.py
    python generate_ink_test.py --data-count 300 --corner-count 150
"""

import cv2
import numpy as np
import qrcode
from PIL import Image
import random
import os
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import string

# ============================================================================
# 全局常量
# ============================================================================
QR_SIZE = 256              # QR 码图像边长 (px)
BORDER = 2                 # QR 码白色边框 (模块数)
FINDER_RATIO = 0.22        # 定位符占图像边长比例 (含安全边距)
PNG_COMPRESSION = 6        # PNG 压缩级别

# ============================================================================
# 工具函数
# ============================================================================

def random_qr_data():
    """生成随机二维码内容。"""
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
        name = ''.join(random.choices(string.ascii_uppercase, k=random.randint(2, 4)))
        phone = ''.join(random.choices(string.digits, k=11))
        return f"BEGIN:VCARD\nN:{name}\nTEL:{phone}\nEND:VCARD"


def generate_qr_image(data, size=QR_SIZE, border=BORDER):
    """
    生成单张 QR 码，返回 BGR numpy 数组。
    """
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
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR), ecc


def finder_bounding_boxes(img_size, fp_ratio=FINDER_RATIO):
    """
    计算三个定位符的包围盒坐标。

    QR 码的三个"回"字形定位符位于:
      - 左上角 (TL)
      - 右上角 (TR)
      - 左下角 (BL)

    参数:
        img_size:  图像边长 (正方形)
        fp_ratio:  定位符区域占图像的比例
    返回:
        {'TL': (x1,y1,x2,y2), 'TR': (x1,y1,x2,y2), 'BL': (x1,y1,x2,y2)}
    """
    fp = int(img_size * fp_ratio)
    margin = int(img_size * 0.02)  # 安全边距 (2%)
    return {
        'TL': (margin, margin, fp + margin, fp + margin),
        'TR': (img_size - fp - margin, margin, img_size - margin, fp + margin),
        'BL': (margin, img_size - fp - margin, fp + margin, img_size - margin),
    }


def is_inside_finder(x, y, boxes):
    """检查点 (x,y) 是否落在任一定位符包围盒内。"""
    for (x1, y1, x2, y2) in boxes.values():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return True
    return False


def ensure_dir(path):
    """确保目录存在。"""
    Path(path).mkdir(parents=True, exist_ok=True)


# ============================================================================
# 墨水斑块生成算法 (Ink Blot Generator)
# ============================================================================

def generate_ink_splotch(shape, cx, cy, radius, irregularity=0.3):
    """
    在空白画布上生成单个不规则墨水斑块。

    算法流程:
        1. 以 (cx, cy) 为中心，radius 为基准半径
        2. 在圆周上以 random 扰动模拟不规则边界
        3. 填充多边形 → 高斯模糊 → 阈值 → 形态学膨胀
        4. 在边缘随机添加小墨滴 (卫星滴)

    参数:
        shape:       画布形状 (h, w)
        cx, cy:      斑块中心坐标
        radius:      基准半径 (px)
        irregularity:不规则度 [0, 1], 越大边缘越扭曲
    返回:
        uint8 mask, shape=(h,w), 0=无墨, 255=有墨
    """
    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)

    # 1. 生成不规则多边形轮廓点 (极坐标扰动)
    num_vertices = random.randint(12, 24)
    angles = np.linspace(0, 2 * np.pi, num_vertices, endpoint=False)
    radii = radius * (1.0 + irregularity * np.random.uniform(-1, 1, num_vertices))
    # 确保半径为正
    radii = np.maximum(radii, radius * 0.3)

    pts_x = np.clip(cx + radii * np.cos(angles), 0, w - 1).astype(np.int32)
    pts_y = np.clip(cy + radii * np.sin(angles), 0, h - 1).astype(np.int32)
    pts = np.stack([pts_x, pts_y], axis=-1)

    # 2. 填充多边形 → 主墨团
    cv2.fillPoly(mask, [pts], 255)

    # 3. 边缘柔化: 高斯模糊 + 阈值 (模拟墨水渗透边界)
    blur_ksize = max(3, int(radius * 0.25))
    if blur_ksize % 2 == 0:
        blur_ksize += 1
    mask = cv2.GaussianBlur(mask, (blur_ksize, blur_ksize), blur_ksize // 2)
    _, mask = cv2.threshold(mask, 60, 255, cv2.THRESH_BINARY)

    # 4. 形态学闭运算: 消除内部空洞，保持墨团连续
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    return mask


def add_satellite_droplets(mask, cx, cy, radius, num_droplets=None):
    """
    在主墨团周围添加卫星飞溅小墨滴。

    参数:
        mask:         当前墨水 mask (会被原地修改)
        cx, cy:       主墨团中心
        radius:       主墨团半径
        num_droplets: 小墨滴数量 (None = 随机)
    """
    if num_droplets is None:
        num_droplets = random.randint(3, 12)

    h, w = mask.shape
    for _ in range(num_droplets):
        # 在主墨团外围随机位置
        angle = random.uniform(0, 2 * np.pi)
        dist = radius * random.uniform(1.1, 1.8)
        dx = int(cx + dist * np.cos(angle))
        dy = int(cy + dist * np.sin(angle))
        dx = np.clip(dx, 0, w - 1)
        dy = np.clip(dy, 0, h - 1)

        # 小墨滴半径
        dr = random.randint(2, max(3, int(radius * 0.2)))
        cv2.circle(mask, (dx, dy), dr, 255, -1)


def generate_ink_mask(shape, num_blots=None, coverage=None,
                      avoid_boxes=None, target_boxes=None):
    """
    生成完整的墨水污染蒙版。

    参数:
        shape:         画布形状 (h, w)
        num_blots:     墨团数量 (None = 随机 3~12)
        coverage:      目标覆盖率 [0,1] (None = 不控, >0 时模拟覆盖率)
        avoid_boxes:   需要避开的包围盒字典 (Task A 用)
        target_boxes:  需要攻击的包围盒字典 (Task B 用)
    返回:
        uint8 mask, shape=(h,w), 0=无墨, 255=有墨
    """
    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)

    if num_blots is None:
        num_blots = random.randint(3, 12)

    # 计算可用区域 (非定位符区) 的中心候选点
    forbidden = set()
    if avoid_boxes is not None:
        for (x1, y1, x2, y2) in avoid_boxes.values():
            for fy in range(y1, y2, 4):  # 步进采样，加速
                for fx in range(x1, x2, 4):
                    forbidden.add((fx, fy))

    # 生成墨团
    for i in range(num_blots):
        # 选择墨团中心
        max_attempts = 50
        for _ in range(max_attempts):
            cx = random.randint(0, w - 1)
            cy = random.randint(0, h - 1)

            if avoid_boxes is not None:
                # 检查是否与任何禁止区域冲突 (使用粗粒度采样)
                blocked = False
                for (x1, y1, x2, y2) in avoid_boxes.values():
                    if x1 <= cx <= x2 and y1 <= cy <= y2:
                        blocked = True
                        break
                if blocked:
                    continue

            break

        # 如果需要攻击特定区域，则一定比例墨团中心强制落在目标区
        if target_boxes is not None and random.random() < 0.6:
            box = random.choice(list(target_boxes.values()))
            cx = random.randint(box[0], box[2])
            cy = random.randint(box[1], box[3])

        radius = random.randint(int(min(w, h) * 0.04), int(min(w, h) * 0.18))
        irregularity = random.uniform(0.15, 0.55)

        blot = generate_ink_splotch(shape, cx, cy, radius, irregularity)
        add_satellite_droplets(blot, cx, cy, radius)
        mask = cv2.bitwise_or(mask, blot)

    # 覆盖率控制: 如果当前覆盖超过目标，按比例随机删除部分墨团区域
    if coverage is not None and coverage > 0:
        current_cov = np.count_nonzero(mask) / (h * w)
        if current_cov > coverage * 1.15:  # 超出 15% 容差
            # 随机腐蚀 mask 达到目标覆盖率
            target_pixels = int(h * w * coverage)
            current_pixels = np.count_nonzero(mask)
            if current_pixels > target_pixels:
                # 随机丢弃 (current_pixels - target_pixels) 个墨点
                ink_coords = np.argwhere(mask > 0)
                drop_indices = np.random.choice(
                    len(ink_coords), current_pixels - target_pixels, replace=False)
                for idx in drop_indices:
                    y, x = ink_coords[idx]
                    mask[y, x] = 0

    return mask


# ============================================================================
# Task A: 数据区污染 (Data Region Pollution)
# ============================================================================

def generate_data_pollution_image(index, coverage_level=None):
    """
    生成一张数据区污染测试图。

    严格避开三个定位符包围盒，只在数据/校验区生成墨水。

    参数:
        index:           图片编号
        coverage_level:  覆盖率级别 (0.10 / 0.20 / 0.30), None=随机
    返回:
        (filename, numpy BGR image)
    """
    if coverage_level is None:
        coverage_level = random.choice([0.10, 0.20, 0.30])

    data = random_qr_data()
    qr_img, ecc = generate_qr_image(data)
    h, w = qr_img.shape[:2]

    # 计算三个定位符包围盒 (要避开的区域)
    fp_boxes = finder_bounding_boxes(w)

    # 生成墨水 mask (避开定位符)
    ink_mask = generate_ink_mask(
        (h, w),
        num_blots=random.randint(4, 15),
        coverage=coverage_level,
        avoid_boxes=fp_boxes,
    )

    # 叠加: 白色 QR → 墨水区变暗
    result = qr_img.copy()
    result[ink_mask > 0] = (result[ink_mask > 0].astype(np.float32) * 0.15).astype(np.uint8)

    # 文件名编码覆盖率
    level_str = f"{int(coverage_level*100):02d}"
    fname = f"data_pollution_{index:04d}_cov{level_str}.png"
    return fname, result


# ============================================================================
# Task B: 定位符毁灭 (Finder Pattern Destruction)
# ============================================================================

def generate_corner_destruction_image(index):
    """
    生成一张定位符毁灭测试图。

    随机选择以下策略之一:
      1. 边缘残缺: 精准遮盖某个定位符边缘的黑白边界 (50%)
      2. 单角毁灭: 100% 覆盖一个定位符 (30%)
      3. 双角攻击: 覆盖两个角 (更极端, 20%)
    """
    data = random_qr_data()
    qr_img, ecc = generate_qr_image(data)
    h, w = qr_img.shape[:2]
    fp_boxes = finder_bounding_boxes(w)
    result = qr_img.copy()

    strategy = random.choices(
        ['edge_damage', 'corner_kill', 'dual_kill'],
        weights=[50, 30, 20]
    )[0]

    if strategy == 'edge_damage':
        # 选一个定位符，在其边缘生成高密度墨团
        target_key = random.choice(list(fp_boxes.keys()))
        target_box = fp_boxes[target_key]
        tx1, ty1, tx2, ty2 = target_box

        # 在目标区域外围生成墨水 (恰好覆盖边缘)
        # 利用 target_boxes 参数使墨团中心偏向下标区域
        # 这里直接构建精细墨团
        edge_mask = np.zeros((h, w), dtype=np.uint8)
        center_x = (tx1 + tx2) // 2
        center_y = (ty1 + ty2) // 2
        radius = (tx2 - tx1) // 2 + random.randint(5, 15)

        blot = generate_ink_splotch((h, w), center_x, center_y, radius, irregularity=0.5)
        add_satellite_droplets(blot, center_x, center_y, radius, num_droplets=random.randint(8, 20))
        edge_mask = cv2.bitwise_or(edge_mask, blot)

        # 叠加: 暗化墨区
        result[edge_mask > 0] = (
            result[edge_mask > 0].astype(np.float32) * 0.12).astype(np.uint8)

        fname = f"corner_edge_{index:04d}.png"

    elif strategy == 'corner_kill':
        # 选择一个角，100% 覆盖
        target_key = random.choice(list(fp_boxes.keys()))
        target_box = fp_boxes[target_key]
        tx1, ty1, tx2, ty2 = target_box

        # 生成一个大墨团精确覆盖目标定位符
        kill_mask = np.zeros((h, w), dtype=np.uint8)
        cx = (tx1 + tx2) // 2
        cy = (ty1 + ty2) // 2
        radius = (tx2 - tx1)  # 略大于定位符

        blot = generate_ink_splotch((h, w), cx, cy, radius, irregularity=0.3)
        add_satellite_droplets(blot, cx, cy, radius, num_droplets=random.randint(5, 15))
        kill_mask = cv2.bitwise_or(kill_mask, blot)

        # 确保核心区域 100% 覆盖 (填充定位符中心为纯黑)
        cv2.rectangle(kill_mask,
                      (tx1 + 5, ty1 + 5),
                      (tx2 - 5, ty2 - 5), 255, -1)

        result[kill_mask > 0] = (
            result[kill_mask > 0].astype(np.float32) * 0.08).astype(np.uint8)

        fname = f"corner_kill_{target_key}_{index:04d}.png"

    elif strategy == 'dual_kill':
        # 覆盖两个角
        keys = random.sample(list(fp_boxes.keys()), 2)
        dual_mask = np.zeros((h, w), dtype=np.uint8)

        for key in keys:
            box = fp_boxes[key]
            tx1, ty1, tx2, ty2 = box
            cx = (tx1 + tx2) // 2
            cy = (ty1 + ty2) // 2
            radius = (tx2 - tx1)

            blot = generate_ink_splotch((h, w), cx, cy, radius, irregularity=0.35)
            add_satellite_droplets(blot, cx, cy, radius, num_droplets=random.randint(5, 12))
            dual_mask = cv2.bitwise_or(dual_mask, blot)

            # 核心覆盖
            cv2.rectangle(dual_mask,
                          (tx1 + 3, ty1 + 3),
                          (tx2 - 3, ty2 - 3), 255, -1)

        result[dual_mask > 0] = (
            result[dual_mask > 0].astype(np.float32) * 0.08).astype(np.uint8)

        fname = f"corner_dual_{index:04d}.png"

    return fname, result


# ============================================================================
# 批量生成主逻辑
# ============================================================================

def batch_generate(generator_func, output_dir, count, desc,
                   parallel=True, **gen_kwargs):
    """
    批量调用生成函数，保存图片到 output_dir。
    """
    ensure_dir(output_dir)
    print(f"\n{'='*60}")
    print(f"  {desc}: {count} 张 -> {output_dir}")
    print(f"{'='*60}")

    if parallel and count >= 10:
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
            futures = {
                ex.submit(generator_func, i, **gen_kwargs): i
                for i in range(count)
            }
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
                fname, img = generator_func(i, **gen_kwargs)
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


class DataPollutionWrapper:
    """Task A 包装器: 按覆盖率级别均匀分配。"""

    def __init__(self, counts_per_level):
        self.counts = counts_per_level  # {0.10: N, 0.20: N, 0.30: N}
        self._cache = {}  # 缓存已分配的覆盖率

    def generate(self, index):
        # 确定此 index 的覆盖率级别
        if index not in self._cache:
            cumsum = 0
            for level, count in self.counts.items():
                cumsum += count
                if index < cumsum:
                    self._cache[index] = level
                    break
        level = self._cache.get(index, 0.20)
        return generate_data_pollution_image(index, coverage_level=level)


def main():
    parser = argparse.ArgumentParser(
        description='墨水污染 QR 码压力测试数据集生成器')
    parser.add_argument('--data-count', type=int, default=210,
                        help='Task A 数据区污染总数 (默认 210=3级×70)')
    parser.add_argument('--corner-count', type=int, default=110,
                        help='Task B 定位符毁灭总数 (默认 110)')
    parser.add_argument('--output', type=str,
                        default='../../images/stress_test',
                        help='输出根目录')
    parser.add_argument('--no-data', action='store_true',
                        help='跳过 Task A')
    parser.add_argument('--no-corner', action='store_true',
                        help='跳过 Task B')
    parser.add_argument('--no-parallel', action='store_true',
                        help='禁用多线程')
    args = parser.parse_args()

    root = os.path.abspath(args.output)
    parallel = not args.no_parallel

    # Task A: 三级覆盖率均匀分配
    data_total = max(args.data_count, 210)
    per_level = data_total // 3
    # 确保总数 = per_level * 3
    data_total = per_level * 3

    print("=" * 60)
    print("  墨水污染 QR 码压力测试数据集生成器")
    print(f"  Task A 数据区污染: {data_total} 张 (10%/20%/30% 各 {per_level})")
    print(f"  Task B 定位符毁灭: {max(args.corner_count, 110)} 张")
    print(f"  输出目录: {root}")
    print("=" * 60)

    if not args.no_data:
        wrapper = DataPollutionWrapper(
            counts_per_level={0.10: per_level, 0.20: per_level, 0.30: per_level}
        )
        batch_generate(
            wrapper.generate,
            os.path.join(root, 'ink_data_pollution'),
            data_total,
            'Task A: 数据区污染 (10/20/30% 三级均匀)',
            parallel=parallel,
        )

    if not args.no_corner:
        corner_total = max(args.corner_count, 110)
        batch_generate(
            generate_corner_destruction_image,
            os.path.join(root, 'ink_corner_destruction'),
            corner_total,
            'Task B: 定位符毁灭 (边缘残缺+单角/双角毁灭)',
            parallel=parallel,
        )

    print(f"\n{'='*60}")
    print(f"  全部完成!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
