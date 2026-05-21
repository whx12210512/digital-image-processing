#!/usr/bin/env python3
"""
AdvancedCVScanner v2.0.0 — 极端降质图像物理修复预处理管线
===========================================================
纯传统 DIP 方法: 矩阵运算、空间域滤波、OpenCV 形态学算子。
不依赖任何深度学习模型。

v2.0.0 改进:
  - 定位符检测: 轮廓法 → NCC 模板匹配 (cv2.matchTemplate)
  - 柱面展平:   边缘法 → 扫描线亮度剖面分析
  - 新增:       条形码自适应条宽重采样
  - 新增:       多尺度模板金字塔

四个核心模块:
  模块1: Virtual Finder Patcher  — 定位符缺失时的虚拟角点伪造 (NCC模板匹配)
  模块2: Cylindrical Unwarper    — 柱面弯曲逆投影展平 (扫描线剖面)
  模块3: Multi-ROI Cropper       — 多码同框分治裁剪
  模块4: Advanced Restoration    — 双边滤波 + 自适应形态学修复
"""

import cv2
import numpy as np
import math
from pyzbar.pyzbar import decode as pyzbar_decode
from PIL import Image


# ============================================================================
# 工具函数
# ============================================================================

def binarize(gray, block_size=15, C=4):
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, block_size, C)


def generate_finder_template(size):
    """
    生成标准回字形定位符模板用于 NCC 模板匹配。

    回字形结构 (7×7 模块):
      外框: 7×7 全黑正方形
      中框: 5×5 全白正方形
      内核: 3×3 全黑正方形

    生成多个尺度的模板以匹配不同大小的 QR 码。
    """
    if size < 14: size = 14
    if size % 2 == 0: size += 1
    half = size // 2
    tpl = np.full((size, size), 128, dtype=np.uint8)  # 中灰背景

    # 外框 7/7: 全黑
    cv2.rectangle(tpl, (0, 0), (size - 1, size - 1), 0, -1)
    # 中框 5/7: 全白
    inner1 = int(size * 5 / 14)
    cv2.rectangle(tpl, (half - inner1, half - inner1),
                  (half + inner1, half + inner1), 255, -1)
    # 内核 3/7: 全黑
    inner2 = int(size * 3 / 14)
    cv2.rectangle(tpl, (half - inner2, half - inner2),
                  (half + inner2, half + inner2), 0, -1)
    return tpl


# ============================================================================
# 模块 1: 虚拟角点伪造器 v2 — NCC 模板匹配
# ============================================================================

class VirtualFinderPatcher:
    """
    使用归一化互相关 (NCC) 模板匹配检测回字形定位符。

    数学原理:
        NCC(x,y) = Σ[(T(i,j)-μT)·(I(x+i,y+j)-μI)] /
                   √(Σ(T-μT)² · Σ(I-μI)²)
        值域 [-1, 1]，1 = 完美匹配。
        相比轮廓法，NCC 对遮挡、噪声、光照不均具有天然的鲁棒性。

    多尺度金字塔:
        生成 5~8 个不同尺度的模板 (边长 14~140px)，
        分别做 NCC 匹配，取所有尺度中得分 > 阈值的峰值点。
    """

    def __init__(self):
        self._templates = {}  # 缓存

    def _get_templates(self, min_size=14, max_size=140):
        sizes = []
        s = min_size
        while s <= max_size:
            sizes.append(s if s % 2 == 1 else s + 1)
            s = int(s * 1.3)
        if not sizes: sizes.append(21)
        result = []
        for sz in sizes:
            if sz not in self._templates:
                self._templates[sz] = generate_finder_template(sz)
            result.append((sz, self._templates[sz]))
        return result

    def detect_finder_centers(self, gray, threshold=0.55):
        """
        NCC 模板匹配检测定位符中心。

        步骤:
            1. 生成多尺度模板
            2. 对每个尺度做 cv2.matchTemplate (TM_CCOEFF_NORMED)
            3. 提取所有 score > threshold 的局部极大值
            4. 非极大值抑制 (NMS): 合并相邻重复检测
        """
        h, w = gray.shape
        raw_hits = []

        for tpl_size, tpl in self._get_templates(14, min(w, h) // 3):
            if tpl_size > w // 2 or tpl_size > h // 2:
                continue
            result = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
            # 找出所有超过阈值的点
            ys, xs = np.where(result >= threshold)
            for y, x in zip(ys, xs):
                raw_hits.append((x + tpl_size // 2, y + tpl_size // 2,
                                  result[y, x], tpl_size))

        if not raw_hits:
            return []

        # 按 score 降序排序
        raw_hits.sort(key=lambda h: h[2], reverse=True)

        # NMS: 合并距离小于 min_size 的重叠检测
        centers = []
        for cx, cy, score, size in raw_hits:
            keep = True
            for ex_cx, ex_cy, ex_size in centers:
                dist = math.hypot(cx - ex_cx, cy - ex_cy)
                if dist < max(size, ex_size) * 0.6:
                    keep = False
                    break
            if keep:
                centers.append((cx, cy, size))

        # 按坐标 (y, x) 排序便于后续分析
        centers.sort(key=lambda c: (c[1], c[0]))
        return centers

    def reconstruct_missing_finder(self, gray, centers):
        """根据已知定位符推算并绘制缺失的回字形。"""
        if len(centers) < 2: return False
        if len(centers) >= 3: return False

        h, w = gray.shape
        avg_size = int(np.mean([c[2] for c in centers]))
        xs, ys = [c[0] for c in centers], [c[1] for c in centers]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # 确定缺失角色: TL=(min_x,min_y), TR=(max_x,min_y), BL=(min_x,max_y)
        has_tl = any(abs(c[0]-min_x) < w*0.35 and abs(c[1]-min_y) < h*0.35 for c in centers)
        has_tr = any(abs(c[0]-max_x) < w*0.35 and abs(c[1]-min_y) < h*0.35 for c in centers)
        has_bl = any(abs(c[0]-min_x) < w*0.35 and abs(c[1]-max_y) < h*0.35 for c in centers)

        missing = None
        if has_tl and has_tr and not has_bl:
            tl = next(c for c in centers if abs(c[0]-min_x)<w*0.35 and abs(c[1]-min_y)<h*0.35)
            tr = next(c for c in centers if abs(c[0]-max_x)<w*0.35 and abs(c[1]-min_y)<h*0.35)
            side = int(math.hypot(tr[0]-tl[0], tr[1]-tl[1]))
            missing = (int(tl[0]), int(tl[1] + side))
        elif has_tl and has_bl and not has_tr:
            tl = next(c for c in centers if abs(c[0]-min_x)<w*0.35 and abs(c[1]-min_y)<h*0.35)
            bl = next(c for c in centers if abs(c[0]-min_x)<w*0.35 and abs(c[1]-max_y)<h*0.35)
            side = int(math.hypot(bl[0]-tl[0], bl[1]-tl[1]))
            missing = (int(tl[0] + side), int(tl[1]))
        elif has_tr and has_bl and not has_tl:
            tr = next(c for c in centers if abs(c[0]-max_x)<w*0.35 and abs(c[1]-min_y)<h*0.35)
            bl = next(c for c in centers if abs(c[0]-min_x)<w*0.35 and abs(c[1]-max_y)<h*0.35)
            missing = (int(bl[0]), int(tr[1]))
        else:
            side = int(math.hypot(max_x-min_x, max_y-min_y))
            if not has_tl: missing = (min_x, min_y)
            elif not has_tr: missing = (max_x, min_y)
            elif not has_bl: missing = (min_x, max_y)

        if missing is None: return False
        mx = np.clip(missing[0], avg_size, w-avg_size-1)
        my = np.clip(missing[1], avg_size, h-avg_size-1)
        fp_size = max(avg_size, min(w,h)//14)
        self._draw_finder(gray, mx, my, fp_size)
        return True

    def _draw_finder(self, img, cx, cy, size):
        half = size // 2
        if half < 3: return
        cv2.rectangle(img, (cx-half, cy-half), (cx+half, cy+half), 0, -1)
        i1 = int(size*5/14)
        cv2.rectangle(img, (cx-i1, cy-i1), (cx+i1, cy+i1), 255, -1)
        i2 = int(size*3/14)
        cv2.rectangle(img, (cx-i2, cy-i2), (cx+i2, cy+i2), 0, -1)


# ============================================================================
# 模块 2: 曲面逆投影展平 v2 — 扫描线剖面分析
# ============================================================================

class CylindricalUnwarper:
    """
    曲面逆投影展平 — 支持扫描线分析和数学模型逆变换。

    两种方法:
      1. unwarp(): 扫描线剖面分析 (适用于条形码等宽条码)
      2. unwarp_cylinder_inverse(): 数学模型逆变换 (适用于QR码柱面弯曲)

    柱面投影数学模型:
      正向 (平面→柱面):
        x' = cx + R * sin((x - cx) / R)
        y' = cy + (y - cy) * R / sqrt(R² + (x - cx)²)
      逆向 (柱面→平面):
        x  = cx + R * arcsin((x' - cx) / R)
        y  = cy + (y' - cy) * sqrt(1 + arcsin²((x' - cx) / R))
      其中 R = (w/2) / (curvature * π + 0.01), clamped to [50, ∞)
    """

    @staticmethod
    def unwarp_cylinder_inverse(image, curvature):
        """
        使用数学逆模型将柱面弯曲的图像展平。

        这是 build_cylinder_maps() 正向变换的严格逆变换。

        参数:
            image:     BGR 或灰度图像
            curvature: 估计的曲率 [0, 1], 0=平面, 1=强弯曲
        返回:
            展平后的 BGR 图像
        """
        is_gray = len(image.shape) == 2
        if is_gray:
            h, w = image.shape
            work = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            h, w = image.shape[:2]
            work = image.copy()

        cx = w / 2.0
        cy = h / 2.0
        R = max(50.0, (w / 2.0) / (curvature * math.pi + 0.01))

        y_dst, x_dst = np.mgrid[0:h, 0:w].astype(np.float32)

        # 逆向 x 坐标
        dx_norm = (x_dst - cx) / R
        # arcsin 的输入必须在 [-1, 1] 范围内
        dx_norm = np.clip(dx_norm, -0.9999, 0.9999)
        arcsin_term = np.arcsin(dx_norm)
        x_src = cx + R * arcsin_term

        # 逆向 y 坐标
        depth_factor = np.sqrt(1.0 + arcsin_term * arcsin_term)
        y_src = cy + (y_dst - cy) * depth_factor

        x_src = np.clip(x_src, 0, w - 1)
        y_src = np.clip(y_src, 0, h - 1)

        result = cv2.remap(work, x_src.astype(np.float32), y_src.astype(np.float32),
                           cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT,
                           borderValue=(255, 255, 255))
        if is_gray:
            return cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        return result

    @staticmethod
    def unwarp_cylinder_multi(image, curvatures=None):
        """
        尝试多个曲率值的逆柱面展平，返回所有展平结果。

        参数:
            image:      BGR 或灰度图像
            curvatures: 曲率值列表 (None=默认 12 个密集采样)
        返回:
            [(curvature, unwarped_image), ...]
        """
        if curvatures is None:
            curvatures = [0.06, 0.10, 0.14, 0.18, 0.22, 0.28, 0.34, 0.40, 0.48, 0.56]
        results = []
        for c in curvatures:
            unw = CylindricalUnwarper.unwarp_cylinder_inverse(image, c)
            results.append((c, unw))
        return results

    @staticmethod
    def estimate_curvature(image):
        """
        通过图像内容宽高比估计柱面曲率。

        原理: QR码是正方形，柱面投影后宽度被压缩。压缩比
        r = content_width / content_height 与曲率 c 的关系为:
        r ≈ sin(c*π + 0.01) / (c*π + 0.01)
        通过查找表反演得到估计曲率值。
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image if len(image.shape) == 2 else image
        if gray is None: return 0.20
        _, thresh = cv2.threshold(gray, 248, 255, cv2.THRESH_BINARY_INV)
        coords = cv2.findNonZero(thresh)
        if coords is None: return 0.20
        _, _, cw, ch = cv2.boundingRect(coords)
        if cw < 30 or ch < 30: return 0.20
        ratio = min(cw / max(ch, 1), 1.0)
        best_c, best_diff = 0.20, 999.0
        for c in [c / 100.0 for c in range(2, 50)]:
            arg = c * math.pi + 0.01
            expected = math.sin(arg) / arg if arg > 0.001 else 1.0
            diff = abs(expected - ratio)
            if diff < best_diff:
                best_diff = diff
                best_c = c
        return max(0.04, min(0.48, best_c))

    @staticmethod
    def unwarp_cylinder_adaptive(image, curvatures=None):
        """
        自适应逆柱面展平：先检测内容区域，用其几何中心作为展开原点。

        相比 unwarp_cylinder_multi，这个方法先找到图像中非背景区域的
        边界框，以边界框中心为展开中心，消除了 padding 带来的中心偏移问题。

        返回:
            [(curvature, unwarped_image), ...]
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image if len(image.shape) == 2 else image.copy()
        h, w = gray.shape[:2]

        # 检测内容区域 (非白色背景)
        _, thresh = cv2.threshold(gray, 248, 255, cv2.THRESH_BINARY_INV)
        coords = cv2.findNonZero(thresh)
        if coords is None:
            return CylindricalUnwarper.unwarp_cylinder_multi(image, curvatures)

        rx, ry, rw, rh = cv2.boundingRect(coords)
        # 扩展到包含完整内容
        rx, ry = max(0, rx - 3), max(0, ry - 3)
        rw, rh = min(w - rx, rw + 6), min(h - ry, rh + 6)

        if rw < 30 or rh < 30:
            return CylindricalUnwarper.unwarp_cylinder_multi(image, curvatures)

        # 裁剪到内容区并展开
        cropped = image[ry:ry + rh, rx:rx + rw]

        if curvatures is None:
            curvatures = [0.06, 0.10, 0.14, 0.18, 0.22, 0.28, 0.34, 0.40, 0.48, 0.56]

        results = []
        for c in curvatures:
            unw = CylindricalUnwarper.unwarp_cylinder_inverse(cropped, c)
            results.append((c, unw))
        return results

    @staticmethod
    def unwarp_cylinder_barcode(image, curvature):
        """
        专为一维条形码设计的纯水平逆柱面展平。

        与 QR 码不同，条形码的柱面弯曲仅影响水平方向 (垂直方向无深度缩放)。
        正向变换: x' = cx + R * sin((x - cx) / R), y' = y
        逆向变换: x  = cx + R * arcsin((x' - cx) / R), y = y'

        参数:
            image:     BGR 或灰度图像
            curvature: 曲率 [0, 1]
        返回:
            展平后的图像
        """
        is_gray = len(image.shape) == 2
        if is_gray:
            h, w = image.shape
            work = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            h, w = image.shape[:2]
            work = image.copy()

        cx = w / 2.0
        # 使用与生成器一致的 R 计算公式
        R = max(w * 0.3, w / (curvature * math.pi * 2 + 0.01))

        y_dst, x_dst = np.mgrid[0:h, 0:w].astype(np.float32)

        # 仅水平方向逆变换
        dx_norm = np.clip((x_dst - cx) / R, -0.9999, 0.9999)
        x_src = cx + R * np.arcsin(dx_norm)
        x_src = np.clip(x_src, 0, w - 1)

        # 垂直方向不变
        y_src = y_dst

        result = cv2.remap(work, x_src.astype(np.float32), y_src.astype(np.float32),
                           cv2.INTER_LANCZOS4,
                           borderMode=cv2.BORDER_CONSTANT,
                           borderValue=(255, 255, 255))
        if is_gray:
            return cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        return result

    @staticmethod
    def unwarp_cylinder_barcode_multi(image, curvatures=None):
        """
        尝试多个曲率值的条形码逆柱面展平。

        返回所有展平结果列表 [(curvature, image), ...]。
        """
        if curvatures is None:
            curvatures = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
        results = []
        for c in curvatures:
            unw = CylindricalUnwarper.unwarp_cylinder_barcode(image, c)
            results.append((c, unw))
        return results

    @staticmethod
    def unwarp_cylinder_targeted(image):
        """
        基于内容宽高比估计曲率后做精确逆柱面展平。

        先调用 estimate_curvature() 从图像压缩比推断曲率，
        再在该估计值附近做精细化扫描，大幅提高命中率。
        """
        est_c = CylindricalUnwarper.estimate_curvature(image)
        fine_curvatures = sorted(set(
            max(0.03, est_c + d) for d in [-0.08, -0.05, -0.02, 0.0, 0.02, 0.05, 0.08]
        ))
        return CylindricalUnwarper.unwarp_cylinder_multi(image, fine_curvatures)

    @staticmethod
    def unwarp(image, poly_degree=2):
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        h, w = gray.shape
        top_pts, bot_pts = [], []

        # 扫描线剖面: 每列提取上下边界
        for x in range(0, w, 2):
            col = gray[:, x].astype(np.float32)
            # 计算垂直梯度 (上下变化)
            grad = np.abs(np.diff(col, prepend=col[0]))
            # 寻找梯度最大的两个位置 (条码区域的上下边界)
            thresh_val = np.mean(grad) + 0.5 * np.std(grad)
            crossings = np.where(grad > thresh_val)[0]
            if len(crossings) >= 2:
                top_pts.append((x, crossings[0]))
                bot_pts.append((x, crossings[-1]))

        if len(top_pts) < 15:
            # 回退: 使用行方差法
            for x in range(0, w, 3):
                col = gray[:, x].astype(np.float32)
                # 滑动窗口计算局部方差
                window = 15
                variances = np.array([
                    np.var(col[i:i+window]) for i in range(h-window)])
                if np.max(variances) > 100:
                    var_thresh = np.max(variances) * 0.3
                    active = np.where(variances > var_thresh)[0]
                    if len(active) >= window:
                        top_pts.append((x, active[0]))
                        bot_pts.append((x, active[-1] + window))

        if len(top_pts) < 15:
            return image

        try:
            tp = np.array(top_pts)
            bp = np.array(bot_pts)
            top_poly = np.poly1d(np.polyfit(tp[:,0], tp[:,1], poly_degree))
            bot_poly = np.poly1d(np.polyfit(bp[:,0], bp[:,1], poly_degree))
        except:
            return image

        out_h, out_w = h, w
        map_x = np.zeros((out_h, out_w), dtype=np.float32)
        map_y = np.zeros((out_h, out_w), dtype=np.float32)
        for j in range(out_w):
            t = np.clip(top_poly(j), 0, h-1)
            b = np.clip(bot_poly(j), 0, h-1)
            if b - t < 5: t, b = 0.0, float(h-1)
            for i in range(out_h):
                map_x[i,j] = float(j)
                map_y[i,j] = t + (b-t)*i/(out_h-1)
        return cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))


# ============================================================================
# 模块 3: 多码分治裁剪器
# ============================================================================

class MultiROICropper:
    """使用 NCC 定位符检测 + 空间聚类进行多码裁剪。"""

    def __init__(self):
        self.finder = VirtualFinderPatcher()

    def crop_rois(self, gray, bgr):
        centers = self.finder.detect_finder_centers(gray, threshold=0.5)
        h, w = gray.shape
        if len(centers) < 3:
            return [(gray, bgr, (0, 0, w, h))]

        # 空间聚类
        if centers:
            max_sz = max(c[2] for c in centers)
            cdist = max_sz * 6
            clusters, used = [], set()
            for i in range(len(centers)):
                if i in used: continue
                cl = [centers[i]]; used.add(i)
                for j in range(i+1, len(centers)):
                    if j in used: continue
                    for c in cl:
                        if math.hypot(centers[j][0]-c[0], centers[j][1]-c[1]) < cdist:
                            cl.append(centers[j]); used.add(j); break
                clusters.append(cl)

            rois = []
            for cl in clusters:
                if len(cl) < 2: continue
                xs = [c[0] for c in cl]; ys = [c[1] for c in cl]
                szs = [c[2] for c in cl]
                cx = int(np.mean(xs)); cy = int(np.mean(ys))
                half = int(max(szs)*2.8)
                x1, y1 = max(0, cx-half), max(0, cy-half)
                x2, y2 = min(w, cx+half), min(h, cy+half)
                if x2-x1 < 20 or y2-y1 < 20: continue
                rois.append((gray[y1:y2,x1:x2], bgr[y1:y2,x1:x2], (x1,y1,x2,y2)))
            if rois: return rois

        return [(gray, bgr, (0, 0, w, h))]


# ============================================================================
# 模块 4: 高维噪声与划痕缝合
# ============================================================================

class AdvancedRestoration:
    """双边滤波 + 自适应形态学 + 条码宽度重采样。"""

    @staticmethod
    def restore(image, is_1d_barcode=False):
        is_gray = len(image.shape) == 2
        work = image.copy() if is_gray else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        denoised = cv2.bilateralFilter(work, 5, 50, 50)
        binary = binarize(denoised, block_size=11, C=3)

        if is_1d_barcode:
            k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
        else:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, k)
        if np.mean(opened) < 5 or np.mean(opened) > 250:
            opened = binary
        return opened if is_gray else cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def adaptive_bar_resample(binary, num_slices=20):
        """
        条形码自适应条宽重采样。

        对柱面压缩的条码，沿水平方向做多个垂直切片的条宽分析，
        然后按平均条宽比例重新插值每一行，恢复均匀条宽。

        算法:
            1. 将图像水平分为 num_slices 个切片
            2. 每个切片内检测条宽比例
            3. 以条宽最宽的切片为基准，对其他切片做水平拉伸/压缩
            4. cv2.remap 完成重采样
        """
        h, w = binary.shape
        slice_w = w // num_slices
        if slice_w < 5: return binary

        # 估算每个切片的"条码密度"(黑像素比例)
        densities = []
        for i in range(num_slices):
            x1 = i * slice_w
            x2 = min(w, (i+1)*slice_w)
            slc = binary[:, x1:x2]
            densities.append(np.count_nonzero(slc == 0) / (h*(x2-x1)))

        if max(densities) - min(densities) < 0.02:
            return binary  # 无明显压缩

        # 以密度最大的切片为参考 (条码最宽处)
        ref_idx = np.argmax(densities)
        ref_center = int(ref_idx * slice_w + slice_w / 2)

        # 构建映射: 根据密度比调整水平坐标
        map_x = np.zeros((h, w), dtype=np.float32)
        map_y = np.zeros((h, w), dtype=np.float32)

        ref_density = max(densities, default=0.1)
        for j in range(w):
            slc_idx = min(j // slice_w, num_slices - 1)
            local_density = max(densities[slc_idx], 0.02)
            scale = ref_density / local_density
            # 调整: 压缩区域拉伸条宽
            src_x = ref_center + (j - ref_center) * scale
            for i in range(h):
                map_x[i, j] = np.clip(src_x, 0, w - 1)
                map_y[i, j] = float(i)

        return cv2.remap(binary, map_x, map_y, cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255)


# ============================================================================
# 模块 5: 颜色污渍去除 (Color Stain Remover)
# ============================================================================

class ColorStainRemover:
    """
    检测并去除半透明彩色污渍（咖啡渍/蓝色墨水）。

    算法:
        1. 分析 RGB 通道比值:
           - 褐色 (咖啡): R >> B, G 居中 → 检测 (R-B) > threshold 区域
           - 蓝色 (墨水): B >> R, G 居中 → 检测 (B-R) > threshold 区域
        2. 对检测到的污渍区域做白化 + 自适应二值化复原
        3. 形态学微调消除残余伪影
    """

    @staticmethod
    def remove_stains(bgr):
        """
        自动检测并移除彩色污渍。

        步骤:
            1. 分离 BGR 通道
            2. 褐色检测: mask_brown = ((R - B) > 35) & (G > 50)
            3. 蓝色检测: mask_blue  = ((B - R) > 35) & (G < 200)
            4. 合并蒙版 → 对该区域做自适应二值化复原
        """
        B = bgr[:, :, 0].astype(np.float32)
        G = bgr[:, :, 1].astype(np.float32)
        R = bgr[:, :, 2].astype(np.float32)

        h, w = bgr.shape[:2]

        # 褐色检测: R 显著大于 B 且偏暖色
        brown_mask = ((R - B) > 35) & (G > 50) & (R > 80)

        # 蓝色检测: B 显著大于 R 且偏冷色
        blue_mask = ((B - R) > 35) & (G < 200) & (B > 80)

        stain_mask = brown_mask | blue_mask

        if np.count_nonzero(stain_mask) < h * w * 0.01:
            return bgr  # 污渍面积太小, 跳过

        # 对被污染区域做白化处理
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 11, 3)

        result = bgr.copy()
        # 被污染区域: 用二值化结果替换
        for c in range(3):
            ch = result[:, :, c]
            ch[stain_mask] = 255 - binary[stain_mask]  # 白底黑码
        return result


# ============================================================================
# 模块 6: 微小墨点滤除 (Speckle Filter)
# ============================================================================

class SpeckleFilter:
    """
    使用形态学开运算滤除微小黑点（1-4px 墨斑），保留大块模块（6-10px）。

    数学原理:
        开运算 = 先腐蚀后膨胀。
        腐蚀: 移除小于核的黑色区域 → 1-4px 墨点消失
        膨胀: 恢复被腐蚀削薄的 QR 模块边界 → 10px 模块复原
        核大小 (3px): 介于墨点 (1-4px) 和 QR 模块 (6-10px) 之间

    效果: 4px 以下的墨点全被消除, QR 模块保留。
    """

    @staticmethod
    def remove_speckles(bgr, kernel_size=3):
        """
        滤除图像中的微小墨斑。

        参数:
            bgr:         BGR 图像
            kernel_size: 形态学核大小 (应介于墨斑大小和模块大小之间)
        返回:
            滤除后的 BGR 图像
        """
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        # 自适应二值化 → 白底黑码
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 11, 3)
        # 形态学开运算: 移除小于 kernel 的黑色斑点
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                           (kernel_size, kernel_size))
        opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # 如果开运算改变了太多 (> 60% 像素翻转), 可能不是墨点污染, 回退
        changed = np.count_nonzero(binary != opened) / binary.size
        if changed > 0.6:
            return bgr

        return cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR)


# ============================================================================
# 模块 7: 运动模糊恢复 (Motion Deblurrer)
# ============================================================================

class MotionDeblurrer:
    """
    使用反锐化掩膜 + 拉普拉斯锐化恢复运动模糊的 QR 码模块边界。

    数学原理:
        1. Unsharp Masking (反锐化掩膜):
           sharp = original + amount * (original - blurred)
           其中 blurred = GaussianBlur(original, sigma=2-4)
           "original - blurred" = 高频细节 (边缘)
           叠加回去 = 增强边缘对比度

        2. Laplacian 锐化:
           sharp = original - k * Laplacian(original)
           Laplacian 提取二阶导数 (边缘变化率)
           减去 Laplacian = 边缘过冲 → 黑白边界更锐利

        3. 激进的局部自适应二值化:
           小 block_size (7-9px) 可以在模糊区域重新建立
           清晰的模块边界, 因为局部阈值跟随模糊过渡区。
    """

    @staticmethod
    def deblur(bgr):
        """
        多尺度自适应二值化 + 反锐化掩膜恢复运动模糊 QR 码。

        策略: 运动模糊模糊了模块边界 → 不同模糊程度需要不同
        block_size 的局部阈值才能正确重建边界。
        生成多个二值化变体, 让扫描器并行尝试。
        """
        if len(bgr.shape) == 3:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = bgr.copy()

        # Unsharp masking 增强边缘
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        unsharp = cv2.addWeighted(gray, 3.0, blurred, -2.0, 0)

        # Laplacian 锐化
        lap_k = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        sharp = np.clip(cv2.filter2D(unsharp, -1, lap_k), 0, 255).astype(np.uint8)

        # 多尺度自适应二值化 —— 哪个 block_size 能重建模块边界?
        best = None
        best_score = -1
        for bs in [5, 7, 9, 11, 15, 21]:
            binary = cv2.adaptiveThreshold(sharp, 255,
                                            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, bs, 2)
            black_ratio = np.count_nonzero(binary == 0) / binary.size
            if 0.15 < black_ratio < 0.55:
                # 偏好黑像素比例接近 30% (典型 QR 码)
                score = 1.0 - abs(black_ratio - 0.30)
                if score > best_score:
                    best_score = score
                    best = binary

        if best is None:
            best = cv2.adaptiveThreshold(sharp, 255,
                                          cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 9, 2)

        return cv2.cvtColor(best, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def deblur_multi(bgr):
        """
        生成多个二值化变体用于并行解码尝试。

        对运动模糊图像, 不同区域的模糊程度不同,
        单一 block_size 无法全局最优。
        返回多个二值化结果, 让扫描器分别尝试。
        """
        if len(bgr.shape) == 3:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = bgr.copy()

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        unsharp = cv2.addWeighted(gray, 3.0, blurred, -2.0, 0)
        lap_k = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        sharp = np.clip(cv2.filter2D(unsharp, -1, lap_k), 0, 255).astype(np.uint8)

        variants = []
        for bs in [5, 7, 9, 11, 15]:
            binary = cv2.adaptiveThreshold(sharp, 255,
                                            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, bs, 2)
            variants.append(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR))
        return variants


# ============================================================================
# 模块 8: 撕裂修复 (Tear Inpainter)
# ============================================================================

class TearInpainter:
    """
    使用图像修复 (Inpainting) 填充撕裂/缺失区域。

    数学原理:
        cv2.inpaint 使用 Navier-Stokes 流体动力学方程或
        Fast Marching Method, 从破损区域边界向内部传播像素值,
        保持等照度线(isophotes)的连续性。

    撕裂检测:
        大面积异常空白区域 + 周围有正常内容 → 判定为撕裂
        排除: 整个图像本来就是白底的正常区域
    """

    @staticmethod
    def detect_tear_mask(gray):
        """检测撕裂/缺失区域 (大面积白块, 含近白色)。"""
        h, w = gray.shape
        # 降低阈值 (230) 捕获更多非纯白撕裂 (灰色边缘/阴影区分)
        white_mask = (gray > 230).astype(np.uint8) * 255

        # 只保留大块白区 (小面积是正常间隙)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel)

        # 只保留连通区域 > 300px² (降低门槛捕获更多撕裂)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            cleaned, connectivity=8)
        tear_mask = np.zeros_like(cleaned)
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area > 300:
                tear_mask[labels == i] = 255

        # 排除边缘正常白色区域 (整行/整列全白通常是空白边距)
        row_white = np.mean(tear_mask, axis=1)
        col_white = np.mean(tear_mask, axis=0)
        for y in range(h):
            if row_white[y] > 240:
                tear_mask[y, :] = 0
        for x in range(w):
            if col_white[x] > 240:
                tear_mask[:, x] = 0

        return tear_mask

    @staticmethod
    def inpaint_tears(bgr):
        """
        检测并修复撕裂区域。

        步骤:
            1. 检测大面积白色异常块
            2. cv2.inpaint 基于邻域修复
            3. 如果撕裂面积 >60% 则跳过 (无法修复)
        """
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        tear_mask = TearInpainter.detect_tear_mask(gray)

        tear_ratio = np.count_nonzero(tear_mask) / gray.size
        if tear_ratio < 0.01 or tear_ratio > 0.6:
            return bgr  # 太少或太多撕裂, 跳过

        # Navier-Stokes inpainting (保持等照度线连续性)
        inpainted = cv2.inpaint(bgr, tear_mask, inpaintRadius=5,
                                 flags=cv2.INPAINT_NS)
        return inpainted


# ============================================================================
# 模块 9: 条码透视归一化 (Perspective Barcode Normalizer) — v2.0.0
# ============================================================================

class PerspectiveBarcodeNormalizer:
    """
    检测并校正一维条形码的透视畸变。

    算法:
        1. 检测条码区域的上下边界点 (通过扫描线梯度)
        2. 拟合边界多项式 → 判断是否透视畸变
        3. 计算逆透视变换 → 将斜视条码归一化为正视矩形
        4. 同时处理柱面弯曲 (配合 CylindricalUnwarper)

    关键: 一维条码信息仅沿水平方向分布 → 透视压缩一侧的条宽
          比例被破坏 → 通过逆变换恢复均匀条宽。
    对于完全水平透视 (只压缩一侧), 使用简单的线性拉伸;
    对于柱面弯曲, 使用扫描线密度修正。
    """

    @staticmethod
    def detect_barcode_bounds(gray):
        """
        扫描线法检测条码区域上下边界。
        利用条码内部黑白交替导致局部方差大的特性。
        """
        h, w = gray.shape
        top_pts, bot_pts = [], []

        for x in range(0, w, max(1, w // 30)):
            col = gray[:, x].astype(np.float32)
            # 滑动窗口方差
            window = 15
            if h <= window: continue
            variances = np.array([np.var(col[i:i+window]) for i in range(h-window)])
            max_var = np.max(variances)
            if max_var > 80:  # 条码区域方差明显大于背景
                thresh = max_var * 0.25
                active = np.where(variances > thresh)[0]
                if len(active) >= 5:
                    top_pts.append((x, active[0] + window//2))
                    bot_pts.append((x, active[-1] + window//2))

        if len(top_pts) < 10:
            return None, None
        return top_pts, bot_pts

    @staticmethod
    def normalize_perspective(bgr):
        """
        检测并校正透视畸变。方法: 轮廓分析 + 密度均衡。

        策略优先级:
          1. 扫描线边界检测 (精确但需要清晰边界)
          2. 二值化 + 轮廓分析 (鲁棒, 适用于模糊条码)
          3. 密度梯度均衡 (最后手段, 不依赖边界)
        """
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # --- Method 1: 扫描线边界检测 ---
        top_pts, bot_pts = PerspectiveBarcodeNormalizer.detect_barcode_bounds(gray)
        if top_pts is not None and len(top_pts) >= 10:
            tp_arr = np.array(top_pts)
            bp_arr = np.array(bot_pts)
            try:
                top_poly = np.polyfit(tp_arr[:, 0], tp_arr[:, 1], 2)
                bot_poly = np.polyfit(bp_arr[:, 0], bp_arr[:, 1], 2)

                tl = np.polyval(top_poly, 0)
                tr = np.polyval(top_poly, w - 1)
                bl = np.polyval(bot_poly, 0)
                br = np.polyval(bot_poly, w - 1)

                lh = abs(bl - tl)
                rh = abs(br - tr)

                if min(lh, rh) > 10 and max(lh, rh) / max(min(lh, rh), 1) >= 1.25:
                    margin = 5
                    src = np.float32([
                        [0, max(0, tl - margin)], [w - 1, max(0, tr - margin)],
                        [w - 1, min(h - 1, br + margin)], [0, min(h - 1, bl + margin)],
                    ])
                    target_h = int(min(h, max(lh, rh) * 1.3))
                    dst = np.float32([[0, 0], [w - 1, 0], [w - 1, target_h - 1], [0, target_h - 1]])
                    H = cv2.getPerspectiveTransform(src, dst)
                    return cv2.warpPerspective(bgr, H, (w, target_h),
                                              borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))
            except:
                pass

        # --- Method 2: 二值化 + 轮廓检测 ---
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 21, 5)
        # 大核闭运算连接条码区域
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            # 取面积最大的轮廓
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)
            if area > w * h * 0.1:
                # 获取最小外接矩形
                rect = cv2.minAreaRect(largest)
                box = cv2.boxPoints(rect).astype(np.int32)

                # 对四个角点排序: TL, TR, BR, BL
                pts = box.astype(np.float32)
                # 按 x 排序分为左右两组
                sorted_x = pts[np.argsort(pts[:, 0])]
                left = sorted_x[:2]
                right = sorted_x[2:]
                # 每组按 y 排序
                left = left[np.argsort(left[:, 1])]
                right = right[np.argsort(right[:, 1])]

                src_pts = np.float32([left[0], right[0], right[1], left[1]])

                # 目标矩形
                tl_w = np.linalg.norm(right[0] - left[0])
                bl_w = np.linalg.norm(right[1] - left[1])
                target_w = int((tl_w + bl_w) / 2)
                tl_h = np.linalg.norm(left[1] - left[0])
                tr_h = np.linalg.norm(right[1] - right[0])
                target_h = int((tl_h + tr_h) / 2)

                if target_w > 20 and target_h > 20:
                    dst_pts = np.float32([[0, 0], [target_w - 1, 0],
                                          [target_w - 1, target_h - 1], [0, target_h - 1]])
                    try:
                        H = cv2.getPerspectiveTransform(src_pts, dst_pts)
                        return cv2.warpPerspective(bgr, H, (target_w, target_h),
                                                  borderMode=cv2.BORDER_CONSTANT,
                                                  borderValue=(255, 255, 255))
                    except:
                        pass

        # --- Method 3: 密度均衡 (不需要边界检测) ---
        return PerspectiveBarcodeNormalizer._density_equalize(bgr)

    @staticmethod
    def _density_equalize(bgr):
        """基于密度的条宽均衡: 拉伸黑密度低的列, 压缩黑密度高的列。"""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # 找到条码行
        row_means = np.mean(gray, axis=1)
        bar_rows = np.where(row_means < 240)[0]
        if len(bar_rows) < 20:
            return bgr

        bar = gray[bar_rows[0]:bar_rows[-1] + 1, :]
        bh = bar.shape[0]

        # 每列黑密度
        col_density = np.mean(bar < 128, axis=0).astype(np.float64)
        kernel_size = max(5, w // 20)
        if kernel_size % 2 == 0:
            kernel_size += 1
        col_density = cv2.GaussianBlur(col_density.reshape(1, -1), (kernel_size, 1), kernel_size//3)[0]

        # 目标密度 = 最大密度的 90%
        target = np.percentile(col_density[col_density > 0.01], 90) if np.any(col_density > 0.01) else 0.3
        if target < 0.05:
            return bgr

        scale = np.clip(target / np.maximum(col_density, 0.02), 0.4, 3.0)

        # 构建 remap — 累积缩放
        map_x = np.zeros((bh, w), dtype=np.float32)
        cum = 0.0
        for j in range(w):
            cum += scale[j]
            map_x[:, j] = cum
        max_x = map_x[:, -1].mean()
        if max_x < 1:
            return bgr
        map_x = map_x / max_x * (w - 1)

        map_y = np.tile(np.arange(bh, dtype=np.float32).reshape(-1, 1), (1, w))
        equalized = cv2.remap(bar, map_x, map_y, cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=255)

        # 重建全图
        result = np.full_like(bgr, 255)
        result[bar_rows[0]:bar_rows[-1] + 1, :] = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)
        return result


# ============================================================================
# 模块 8 (续): 增强撕裂修复 — 多尺度桥接 + 撕裂碎片拼接
# ============================================================================

class AdvancedCVScanner:
    """
    一站式降质图像预处理与解码扫描器 v2.0.0。

    改进:
      - NCC 模板匹配替代轮廓检测 (定位符检测鲁棒性大幅提升)
      - 扫描线剖面分析替代 Canny 边界提取
      - 新增条码宽度重采样
    """

    def __init__(self):
        self.finder_patcher = VirtualFinderPatcher()
        self.unwarper = CylindricalUnwarper()
        self.cropper = MultiROICropper()
        self.restorer = AdvancedRestoration()
        self.stain_remover = ColorStainRemover()
        self.speckle_filter = SpeckleFilter()
        self.deblurrer = MotionDeblurrer()
        self.tear_inpainter = TearInpainter()
        self.perspective_normalizer = PerspectiveBarcodeNormalizer()

    def classify_damage(self, gray):
        issues = []
        h, w = gray.shape
        centers = self.finder_patcher.detect_finder_centers(gray)

        if len(centers) >= 6:
            issues.append('multi_code')
        if len(centers) < 3:
            issues.append('finder_missing')

        # 弯曲检测: 扫描线方差的垂直位置变化
        top_positions = []
        for x in range(0, w, max(1, w//40)):
            col = gray[:, x].astype(np.float32)
            window = 12
            variances = np.array([np.var(col[i:i+window]) for i in range(h-window)])
            if np.max(variances) > 100:
                top_positions.append((x, np.argmax(variances > np.max(variances)*0.3)))
        if len(top_positions) > 10:
            try:
                tx, ty = np.array(top_positions).T
                c = np.polyfit(tx, ty, 2)
                if abs(c[0])*w*w > h*0.25:
                    issues.append('curved')
            except: pass

        lap = cv2.Laplacian(gray, cv2.CV_64F)
        if lap.var() > 500 or lap.var() < 10:
            issues.append('noisy')

        # 条形码检测: 无回字形 + 高宽比大 → 可能是条码
        if not centers and w > h * 1.5:
            issues.append('likely_barcode')

        return issues, centers

    def _load_image(self, image_input):
        """统一图像加载: 返回 (bgr, gray)。"""
        if isinstance(image_input, str):
            pil = Image.open(image_input)
            arr = np.array(pil.convert('RGB'))
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        elif len(image_input.shape) == 3:
            bgr = image_input.copy()
        else:
            bgr = cv2.cvtColor(image_input, cv2.COLOR_GRAY2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        return bgr, gray

    def _try_all_variants(self, bgr, gray):
        """
        对输入图像生成多个预处理变体，逐个尝试解码。
        不再依赖分类 — 所有修复模块无条件运行。
        返回所有解码结果的并集。
        """
        h, w = gray.shape
        variants = []

        # ---- V0: 原图 ----
        variants.append(('raw', bgr))

        # ---- V1: 双边滤波降噪 ----
        try:
            denoised_gray = cv2.bilateralFilter(gray, 5, 50, 50)
            binary = binarize(denoised_gray, 11, 3)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            if 5 < np.mean(closed) < 250:
                variants.append(('restored_qr', cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR)))
        except: pass

        # ---- V2: 条码专用修复 (垂直核 + 条宽重采样) ----
        try:
            bc_binary = binarize(cv2.bilateralFilter(gray, 5, 50, 50), 11, 3)
            k_bc = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
            bc_closed = cv2.morphologyEx(bc_binary, cv2.MORPH_CLOSE, k_bc)
            if 5 < np.mean(bc_closed) < 250:
                variants.append(('restored_bc', cv2.cvtColor(bc_closed, cv2.COLOR_GRAY2BGR)))
                # 条宽重采样
                resampled = AdvancedRestoration.adaptive_bar_resample(bc_closed)
                variants.append(('bar_resampled', cv2.cvtColor(resampled, cv2.COLOR_GRAY2BGR)))
        except: pass

        # ---- V2b: 条码透视归一化 (v2.0.0) ----
        try:
            if w > h * 1.3:  # 可能是条形码 (宽度大于高度)
                normalized = self.perspective_normalizer.normalize_perspective(bgr)
                if normalized is not None:
                    variants.append(('persp_norm', normalized))
                    # 对归一化后的结果再二值化
                    ng = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
                    nb = cv2.adaptiveThreshold(ng, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                              cv2.THRESH_BINARY, 15, 4)
                    variants.append(('persp_norm_bin', cv2.cvtColor(nb, cv2.COLOR_GRAY2BGR)))
        except: pass

        # ---- V3: 曲面展平 (扫描线法) ----
        try:
            unwarped = self.unwarper.unwarp(bgr)
            variants.append(('unwarped', unwarped))
        except: pass

        # ---- V3b: 数学模型逆柱面展平 (多曲率) ----
        try:
            for curv, unw in self.unwarper.unwarp_cylinder_multi(bgr):
                variants.append((f'cylinder_inv_c{curv:.2f}', unw))
                if len(unw.shape) == 3:
                    ng = cv2.cvtColor(unw, cv2.COLOR_BGR2GRAY)
                else:
                    ng = unw
                nb = cv2.adaptiveThreshold(ng, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 15, 3)
                variants.append((f'cylinder_inv_bin_c{curv:.2f}', cv2.cvtColor(nb, cv2.COLOR_GRAY2BGR)))
        except: pass

        # ---- V3c: 自适应逆柱面展平 (检测内容中心后再展开) ----
        try:
            for curv, unw in self.unwarper.unwarp_cylinder_adaptive(bgr,
                    [0.08, 0.14, 0.20, 0.28, 0.36, 0.44]):
                variants.append((f'cyl_adapt_c{curv:.2f}', unw))
                if len(unw.shape) == 3:
                    ng = cv2.cvtColor(unw, cv2.COLOR_BGR2GRAY)
                else:
                    ng = unw
                nb = cv2.adaptiveThreshold(ng, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 15, 3)
                variants.append((f'cyl_adapt_bin_c{curv:.2f}', cv2.cvtColor(nb, cv2.COLOR_GRAY2BGR)))
        except: pass

        # ---- V3d: 条形码专用柱面展平 (仅水平方向逆向) ----
        try:
            if w > h * 1.2:  # 宽图像更可能是条形码
                for curv, unw in self.unwarper.unwarp_cylinder_barcode_multi(bgr):
                    variants.append((f'barcode_cyl_c{curv:.2f}', unw))
                    if len(unw.shape) == 3:
                        ng2 = cv2.cvtColor(unw, cv2.COLOR_BGR2GRAY)
                    else:
                        ng2 = unw
                    nb2 = cv2.adaptiveThreshold(ng2, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                               cv2.THRESH_BINARY, 15, 3)
                    variants.append((f'barcode_cyl_bin_c{curv:.2f}', cv2.cvtColor(nb2, cv2.COLOR_GRAY2BGR)))
        except: pass

        # ---- V4: 定位符修补 (标准 NCC) ----
        try:
            centers = self.finder_patcher.detect_finder_centers(gray, threshold=0.45)
            if len(centers) >= 2 and len(centers) < 3:
                patched_gray = gray.copy()
                if self.finder_patcher.reconstruct_missing_finder(patched_gray, centers):
                    variants.append(('finder_patched',
                                     cv2.cvtColor(patched_gray, cv2.COLOR_GRAY2BGR)))
            elif len(centers) >= 6:
                rois = self.cropper.crop_rois(gray, bgr)
                for i, (rg, rb, _) in enumerate(rois):
                    if rb is not None:
                        variants.append((f'roi_{i}', rb))
        except: pass

        # ---- V5: 低阈值查找器修补 (for torn/damaged finders) ----
        try:
            centers_low = self.finder_patcher.detect_finder_centers(gray, threshold=0.35)
            if 2 <= len(centers_low) < 3:
                patched_low = gray.copy()
                if self.finder_patcher.reconstruct_missing_finder(patched_low, centers_low):
                    variants.append(('finder_patched_low',
                                     cv2.cvtColor(patched_low, cv2.COLOR_GRAY2BGR)))
        except: pass

        # ---- V5b: 极低阈值 (for severely torn) ----
        try:
            centers_vlow = self.finder_patcher.detect_finder_centers(gray, threshold=0.30)
            if 2 <= len(centers_vlow) < 3:
                patched_vlow = gray.copy()
                if self.finder_patcher.reconstruct_missing_finder(patched_vlow, centers_vlow):
                    final_v = self.restorer.restore(
                        cv2.cvtColor(patched_vlow, cv2.COLOR_GRAY2BGR), is_1d_barcode=False)
                    if len(final_v.shape) == 2: final_v = cv2.cvtColor(final_v, cv2.COLOR_GRAY2BGR)
                    variants.append(('finder_vlow', final_v))
        except: pass

        # ---- V5c: 多码裁剪 (极低阈值, 针对 multi_qr) ----
        try:
            centers_tiny = self.finder_patcher.detect_finder_centers(gray, threshold=0.30)
            if len(centers_tiny) >= 4:  # 多个定位符 → 多码图像
                rois = self.cropper.crop_rois(gray, bgr)
                for i, (rg, rb, _) in enumerate(rois):
                    if rb is not None and rb.shape[0] > 20 and rb.shape[1] > 20:
                        variants.append((f'roi_tiny_{i}', rb))
        except: pass

        # ---- V5d: 超低阈值查找器 + 修补 + 去噪 (for very damaged QR) ----
        try:
            centers_dmg = self.finder_patcher.detect_finder_centers(gray, threshold=0.25)
            if 2 <= len(centers_dmg) < 3:
                patched_dmg = gray.copy()
                if self.finder_patcher.reconstruct_missing_finder(patched_dmg, centers_dmg):
                    restored_dmg = self.restorer.restore(
                        cv2.cvtColor(patched_dmg, cv2.COLOR_GRAY2BGR), is_1d_barcode=False)
                    if len(restored_dmg.shape) == 2:
                        restored_dmg = cv2.cvtColor(restored_dmg, cv2.COLOR_GRAY2BGR)
                    variants.append(('finder_dmg', restored_dmg))
            elif len(centers_dmg) >= 4:
                rois_dmg = self.cropper.crop_rois(gray, bgr)
                for i, (rg, rb, _) in enumerate(rois_dmg):
                    if rb is not None and rb.shape[0] > 20 and rb.shape[1] > 20:
                        variants.append((f'roi_dmg_{i}', rb))
        except: pass

        # ---- V6: 原图 + 查找器修补 (不依赖检测) ----
        try:
            centers2 = self.finder_patcher.detect_finder_centers(gray, threshold=0.4)
            if 2 <= len(centers2) < 3:
                patched2 = gray.copy()
                if self.finder_patcher.reconstruct_missing_finder(patched2, centers2):
                    # 修补后再降噪
                    final = self.restorer.restore(
                        cv2.cvtColor(patched2, cv2.COLOR_GRAY2BGR), is_1d_barcode=False)
                    if len(final.shape) == 2: final = cv2.cvtColor(final, cv2.COLOR_GRAY2BGR)
                    variants.append(('patched_restored', final))
        except: pass

        # ---- V6: 对比度增强 (CLAHE) ----
        try:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            variants.append(('clahe', cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)))
        except: pass

        # ---- V7: 颜色污渍去除 (咖啡/蓝墨水) ----
        try:
            cleaned = self.stain_remover.remove_stains(bgr)
            variants.append(('stain_free', cleaned))
        except: pass

        # ---- V8: 微小墨点滤除 (1-4px speckle removal) ----
        try:
            despeckled = self.speckle_filter.remove_speckles(bgr)
            variants.append(('despeckled', despeckled))
        except: pass

        # ---- V9: 运动模糊恢复 (multi-scale adaptive threshold) ----
        try:
            for i, dv in enumerate(self.deblurrer.deblur_multi(bgr)):
                variants.append((f'deblur_{i}', dv))
        except: pass

        # ---- V10: 撕裂修复 (inpainting) ----
        try:
            inpainted = self.tear_inpainter.inpaint_tears(bgr)
            variants.append(('tear_fixed', inpainted))
        except: pass

        # ---- V11: 形态学桥接 (closing to bridge torn edges) ----
        try:
            gray2 = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            binary = cv2.adaptiveThreshold(gray2, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 11, 3)
            # 大核闭运算桥接撕裂缝隙
            for ks in [7, 11, 15]:
                k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
                bridged = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k)
                if 10 < np.mean(bridged) < 245:
                    variants.append((f'bridged_{ks}', cv2.cvtColor(bridged, cv2.COLOR_GRAY2BGR)))
        except: pass

        # ---- V12: 水平/垂直分割解码 (for strip tears) ----
        try:
            gray3 = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            # 检测全白行/列 (撕裂线)
            row_mean = np.mean(gray3, axis=1)
            col_mean = np.mean(gray3, axis=0)
            tear_rows = np.where(row_mean > 250)[0]
            tear_cols = np.where(col_mean > 250)[0]
            # 如果有连续白行 >10px → 水平撕裂
            if len(tear_rows) > 10:
                # 找到最大间隙
                gaps = np.diff(tear_rows)
                big_gaps = np.where(gaps > 10)[0]
                if len(big_gaps) > 0:
                    split_y = tear_rows[big_gaps[len(big_gaps)//2]]
                    top = bgr[:split_y, :]
                    bot = bgr[split_y:, :]
                    for i, frag in enumerate([top, bot]):
                        if frag.shape[0] > 30 and frag.shape[1] > 30:
                            variants.append((f'hsplit_{i}', frag))
            if len(tear_cols) > 10:
                gaps = np.diff(tear_cols)
                big_gaps = np.where(gaps > 10)[0]
                if len(big_gaps) > 0:
                    split_x = tear_cols[big_gaps[len(big_gaps)//2]]
                    left = bgr[:, :split_x]
                    right = bgr[:, split_x:]
                    for i, frag in enumerate([left, right]):
                        if frag.shape[0] > 30 and frag.shape[1] > 30:
                            variants.append((f'vsplit_{i}', frag))
        except: pass

        # ---- 解码所有变体 ----
        all_results = []
        for tag, variant in variants:
            for r in self._decode(variant):
                key = r[0]
                if not any(existing[0] == key for existing in all_results):
                    all_results.append(r)
        return all_results

    def process_and_decode(self, image_input):
        """
        主入口 v2.0.0: 全模块无条件应用策略。

        生成 6~8 个预处理变体 → 逐一 pyzbar 解码 → 取并集返回。
        不再依赖启发式分类，每个模块都有机会贡献。
        """
        bgr, gray = self._load_image(image_input)
        return self._try_all_variants(bgr, gray)

    def _decode(self, img):
        try:
            if len(img.shape) == 2:
                pil = Image.fromarray(img).convert('RGB')
            else:
                pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            return [(d.data.decode('utf-8', errors='replace').strip(),
                     'QR Code' if d.type == 'QRCODE' else 'Barcode', d.type)
                    for d in pyzbar_decode(pil)]
        except: return []
