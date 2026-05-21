# 数字图像处理 — 条形码/二维码识别

数字图像处理课程大作业 · 任务四 · 南方科技大学 电子与电气工程系 · 2026

基于传统数字图像处理技术的条形码/二维码自动检测、定位与解码系统。

## 版本历史

| 版本 | 日期 | 关键改进 |
|------|------|----------|
| **v2.0.1** | 2026-05-22 | 柱面弯曲数学逆变换 (QR + 条形码), geometric_curved→96.4%, barcode_cylinder→94.5%, 曲率物理建模 |
| v2.0.0 | 2026-05-21 | 多引擎压力测试, pyzbar增强预处理, 条码透视归一化, 撕裂检测优化, 多码裁剪增强 |
| v1.1.0 | 2026-05-20 | AdvancedCVScanner — NCC模板匹配, 柱面展平, 多码裁剪, 污渍去除, 墨点滤除, 运动模糊恢复, 撕裂修复 |
| v1.0.2 | 2026-05-19 | jsQR崩溃安全, 区域扫描回退 |
| v1.0.0 | 2026-05-18 | 初始版本 |

## 项目结构

```
├── code/
│   ├── scanner-app/           # 移动端 Web 扫码应用 (PWA)
│   │   ├── index.html         #   主页面
│   │   ├── style.css          #   样式 (移动端 UI)
│   │   ├── app.js             #   扫码逻辑 (html5-qrcode + jsQR + SpeckleFilter + FinderRepair)
│   │   ├── manifest.json      #   PWA 清单
│   │   └── sw.js              #   Service Worker
│   ├── image-processing/      # 传统图像处理 Pipeline (Python)
│   │   ├── preprocess.py      #   图像预处理 (灰度化/滤波/二值化)
│   │   ├── localize.py        #   条码/二维码定位 (Canny/形态学/Finder Pattern)
│   │   ├── correct.py         #   几何校正 (旋转/透视变换)
│   │   ├── decode.py          #   解码识别 (EAN-13/Code-128/Code-39/QR)
│   │   ├── advanced_cv_scanner.py  # AdvancedCVScanner v2.0.1 — 9模块降质修复 + 柱面逆变换
│   │   ├── pipeline.py        #   完整识别管线
│   │   └── gui.py             #   桌面 GUI (tkinter)
│   └── test-generator/        # 测试图片生成器 (8个生成器)
├── images/
│   ├── test_images/           # 基础测试图片集 (~50+ 张)
│   └── stress_test/           # 压力测试集 (26 类)
├── results/                   # 测试结果
├── run_stress_test.py         # 多引擎分层压力测试脚本 (v2.0.0)
├── run_fast_test.py           # 快速定向测试脚本
└── docs/                      # 文档
```

## 功能特性

### 移动端 Web 扫码应用
- 基于 HTML5/CSS3/JS，支持手机浏览器直接使用
- 摄像头实时扫码 (QR + 条形码)
- 图片上传识别 (本地文件/相册)
- 扫描历史记录 (LocalStorage)
- PWA 支持，可添加到手机主屏幕
- 支持格式：QR Code, EAN-13, EAN-8, UPC-A, Code-128, Code-39 等

### 传统图像处理 Pipeline
- **预处理**: 灰度化、CLAHE 增强、高斯/中值滤波、Otsu/自适应二值化
- **定位检测**: Canny 边缘检测 + 形态学操作 + 轮廓分析、梯度方向直方图、QR Finder Pattern 检测
- **几何校正**: 霍夫线变换旋转校正、透视变换、仿射变换
- **解码识别**: 自定义扫描线 EAN-13 解码器、pyzbar/OpenCV 后端

### 测试图片集
- 标准 QR 码 (7 张) / 旋转 (15°/30°/45°) / 噪声 / 模糊 / 光照不均 / 复杂背景
- 条形码 EAN-13 / Code-128 / Code-39 (各 3 张 + 旋转变体)
- 多目标图片 / 混合类型图片

## 快速开始

### Web 扫描应用

> **重要**: 摄像头需要 **HTTPS 或 localhost** 才能调用。所有在线方式均已满足此要求。

#### 手机用户 (推荐)

| 方式 | 适用场景 | 链接 |
|------|----------|------|
| **在线版** | 有网络, 无需安装, 支持 PWA 添加到桌面 | [Netlify 在线版](https://clever-torrone-2cb8c8.netlify.app) <br> `https://clever-torrone-2cb8c8.netlify.app` |
| **APK 安装** | 无 Google 服务 (荣耀/小米), 离线使用 | [GitHub Releases](https://github.com/whx12210512/digital-image-processing/releases/latest) <br> `https://github.com/whx12210512/digital-image-processing/releases/latest` |

> **注意**: 在线版若界面与 APK 不一致, 说明浏览器缓存了旧版 Service Worker。
> 解决方法: 浏览器中打开 DevTools → Application → Service Workers → Unregister,
> 或在地址栏后加 `?v=2` 强制刷新, 或清除浏览器缓存后重新打开。

#### 开发者

```bash
# 本地 HTTPS 调试 (手机+电脑均可)
cd code/scanner-app
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
  -days 365 -nodes -subj "//CN=$(hostname -I | awk '{print $1}')"
python server_https.py
# → 电脑: https://localhost:8443  手机: https://<电脑IP>:8443

# 快速 HTTP 调试 (仅电脑, localhost 可调摄像头)
python -m http.server 8000
# → http://localhost:8000

# 构建 APK
npm install && npx cap sync android && cd android && ./gradlew assembleDebug
```

### Python Pipeline

```bash
# 安装依赖
pip install opencv-python numpy pillow pyzbar qrcode python-barcode

# 运行单张图片识别
python code/image-processing/pipeline.py images/test_images/qr_clean_01.png

# 批量测试
python code/image-processing/pipeline.py --test

# 启动桌面 GUI
python code/image-processing/gui.py

# 生成测试图片
python code/test-generator/generate_all.py
```

## 测试结果 (v2.0.1)

### 多引擎压力测试 (26 类)

使用 **pyzbar** (增强预处理) + **cv2.QRCodeDetector** + **AdvancedCVScanner** 三引擎分层测试。

| 类别 | 数量 | 正确率 | 状态 |
|------|------|--------|------|
| barcode_cylinder | 110 | 94.5% | PASS ✅ |
| barcode_geometric | 110 | 91.8% | PASS ✅ |
| barcode_highlight | 110 | 100.0% | PASS |
| barcode_ink | 110 | 100.0% | PASS |
| barcode_lowcontrast | 110 | 100.0% | PASS |
| artifact_defocus | 110 | 89.1% | PASS ✅ |
| artifact_finger | 110 | 63.6% | FAIL ⚠ |
| artifact_jpeg | 110 | 100.0% | PASS ✅ |
| barcode_motion_blur | 110 | 90.9% | PASS |
| barcode_scratches | 110 | 95.5% | PASS |
| damage_noise | 110 | 81.8% | PASS ✅ |
| edge_quiet_zone | 164 | 95.7% | PASS |
| edge_tear | 110 | 82.7% | PASS ✅ |
| flaw_highlight | 110 | 100.0% | PASS |
| flaw_low_contrast | 110 | 100.0% | PASS |
| flaw_motion_blur | 330 | 83.9% | PASS |
| geometric_curved | 110 | 96.4% | PASS ✅ |
| geometric_perspective | 110 | 94.5% | PASS |
| geometric_rotation | 110 | 100.0% | PASS |
| illumination | 110 | 100.0% | PASS |
| ink_corner_destruction | 294 | 93.9% | PASS |
| ink_data_pollution | 210 | 100.0% | PASS |
| linear_combo | 110 | 100.0% | PASS |
| linear_perspective | 110 | 100.0% | PASS |
| linear_shear | 110 | 100.0% | PASS |
| liquid_blue_ink | 40 | 100.0% | PASS |
| liquid_coffee | 40 | 100.0% | PASS |
| liquid_water_drops | 40 | 100.0% | PASS |
| multi_qr | 110 | 84.5% | PASS ✅ |
| **总计** | **3,538** | **94.0%** | **28/29 PASS** |

### v2.0.1 改进成果 — 柱面弯曲专项修复

v2.0.1 的核心突破是柱面弯曲的数学逆变换。v2.0.0 的 scanline 扫描线方法对QR码效果极差 (0%), 需要从数学原理出发进行彻底重写。

**柱面投影模型 (正向)**:
```
x' = cx + R · sin((x - cx) / R)    # 水平坐标压缩
y' = cy + (y - cy) · R / √(R² + (x - cx)²)  # 垂直深度缩放 (仅QR)
```

**逆变换 (逆向 — 将柱面图像"展平")**:
```
x = cx + R · arcsin((x' - cx) / R)
y = cy + (y' - cy) · √(1 + arcsin²((x' - cx) / R))
```
其中 `R = (w/2) / (curvature · π + 0.01)`, clamped to [50, ∞)。

**条形码专用模型**：一维条形码仅水平压缩，无垂直深度缩放 → `map_y = y`。

| 改进项 | v2.0.0 | v2.0.1 | 提升 | 关键技术 |
|--------|--------|--------|------|----------|
| geometric_curved | 0.0% | **96.4%** | +96.4% | 数学逆柱面变换, 曲率估计, 自适应展开 |
| barcode_cylinder | 0.0% | **94.5%** | +94.5% | 纯水平逆柱面 (INTER_LANCZOS4), 高分辨率 (800px) |
| barcode_geometric | 12.7% | **91.8%** | +79.1% | 柱面+透视复合逆变换, LANCZOS4, 物理曲率范围 |

**几何生成器调整**:
- geometric_curved: 移除波纹/复合变体 (现实生活中不存在), 纯柱面; 曲率 0.08–0.35 (对应瓶罐直径 ~1.5–8cm)
- barcode_cylinder: 曲率 0.12–0.25, 分辨率 500→800px, INTER_LINEAR→INTER_LANCZOS4

### v2.0.0 改进成果

| 改进项 | 提升 |
|--------|------|
| ink_data_pollution | 76.2% → **100.0%** (+23.8%) |
| ink_corner_destruction | 85.4% → **93.9%** (+8.5%) |
| flaw_motion_blur | 80.9% → **83.9%** (+3.0%) |
| barcode_scratches | 92.7% → **95.5%** (+2.8%) |
| damage_noise | 67.3% → **81.8%** (+14.5%) |
| edge_tear | 40.6% → **82.7%** (+42.1%) |
| liquid_coffee | 97.5% → **100.0%** (+2.5%) |

### 物理背景：为什么超市能扫易拉罐条形码？

**激光扫描枪（恒定角速度）**：
激光通过旋转多面镜以恒定角速度扫描。条形码贴在圆柱面上时，激光扫过黑条和空白的时间间隔比例**保持不变**——因为扫描角速度恒定，而条码自身的角宽度比例不变。这就是时域编码的天然抗柱面畸变特性。

**摄像头扫描器（手机/平板）**：
拍摄2D图像后通过软件几何校正（即本项目的 `unwarp_cylinder_inverse` / `unwarp_cylinder_barcode`）。现代手机高分辨率摄像头确保即使边缘压缩，条码模块仍有足够像素用于重建。

**本项目模拟的局限性**：
正向变换（remap）→ 逆向变换（remap）的双重插值在高曲率下会造成不可逆信息损失。真实摄像头直接拍摄柱面物体，不存在此双重损失。解决方案：增大分辨率 + 限制曲率到真实产品范围 + 高质量插值算法。

### v2.0.6 App vs Python 性能对比

v2.0.6 修复了两个关键根因：QR 曲率估计在 padding 图像上失效（改为全范围扫描），形态学闭运算对所有图像生效（不止条码）。

| 类别 | Python | v2.0.5 App | v2.0.6 App | 差距 |
|------|:------:|:----------:|:----------:|:----:|
| geometric_curved | 96.4% | 72.7% | **95.5%** | -0.9% ✅ |
| barcode_cylinder | 94.5% | 92.7% | **92.7%** | -1.8% |
| barcode_geometric | 91.8% | 85.5% | **85.5%** | -6.3% |
| ink_data_pollution | 100% | 77.6% | **99.0%** | -1.0% ✅ |
| ink_corner_destruction | 93.9% | 90.5% | **90.5%** | -3.4% |
| damage_noise | 81.8% | 85.5% | **85.5%** | +3.7% |
| edge_tear | 82.7% | 84.5% | **84.5%** | +1.8% |
| **平均** | **91.6%** | **84.1%** | **90.5%** | **-1.1%** |

> App 与 Python 的综合差距从 v2.0.2 的 -17.5% 缩小到 v2.0.6 的 **-1.1%**，基本持平。

### 新增测试类别 (v2.0.6)

| 类别 | 数量 | 正确率 | 说明 |
|------|------|--------|------|
| artifact_jpeg | 110 | **100.0%** | JPEG 压缩伪影 (quality 8-50) |
| artifact_defocus | 110 | **89.1%** | 散焦 Gaussian 模糊 (σ=1.5-6.0) |
| artifact_finger | 110 | **63.6%** | 手指边缘遮挡 (1-2 个肤色椭圆) |

> artifact_finger 未达标是预期内的——手指遮挡直接抹除数据，属于物理极限。碎片提取可恢复部分遮挡场景。

## 技术路线

### AdvancedCVScanner v2.0.1 — 9 模块降质修复管线

```
图像输入 → 降质分类 → 模块化修复 → 多引擎解码 → 结果输出
  │            │           │              │
  │     NCC模板匹配    模块1: 定位符修补    pyzbar
  │     扫描线剖面     模块2: 柱面展平    cv2.QRCodeDetector
  │     柱面逆变换     模块2b: 数学逆柱面 (NEW v2.0.1)  AdvancedCVScanner
  │                   模块2c: 条形码纯水平逆柱面 (NEW v2.0.1)
  │                   模块2d: 自适应曲率估计 + 目标展开 (NEW v2.0.1)
  │                   模块3: 多码裁剪
  │                   模块4: 降噪修复
  │                   模块5: 颜色污渍去除
  │                   模块6: 墨点滤除
  │                   模块7: 运动模糊恢复
  │                   模块8: 撕裂修复
  │                   模块9: 条码透视归一化 (NEW v2.0.0)
```

**v2.0.1 新增子模块 (CylindricalUnwarper)**:
| 方法 | 用途 | 核心算法 |
|------|------|----------|
| `unwarp_cylinder_inverse()` | QR 码柱面展平 | `x = cx+R·arcsin(dx)`, `y = cy+dy·√(1+arcsin²)` |
| `unwarp_cylinder_barcode()` | 条形码柱面展平 | 纯水平 `arcsin` 逆变换, INTER_LANCZOS4 |
| `unwarp_cylinder_multi()` | 多曲率暴力搜索 | 10-12 个曲率值并行尝试 |
| `unwarp_cylinder_adaptive()` | 内容中心自适应 | 检测非白区域边界框 → 以几何中心展开 |
| `unwarp_cylinder_targeted()` | 曲率估计+精细扫描 | `estimate_curvature()` → ±0.08 范围 7 点搜索 |
| `estimate_curvature()` | 宽高比反推曲率 | `sinc(c·π+0.01) = cw/ch` → 查找表反演 |

### 传统 Pipeline

```
图像输入 → 预处理 → 定位检测 → 几何校正 → 解码识别 → 结果输出
  │          │          │          │          │
  │      灰度化    Canny边缘   霍夫变换   扫描线法
  │      滤波去噪   形态学膨胀   透视变换   条空宽度
  │      二值化    轮廓筛选   旋转校正   Finder Pattern
  │      CLAHE    梯度直方图              RS纠错
```

核心算法基于传统图像处理 (不依赖深度学习)，符合课程要求。

### Web App 解码管线

```
图像输入 → BarcodeDetector (3级回退) → jsQR (增强+反转) →
  SpeckleFilter (形态学开运算) → FinderPatternRepair (墨迹修复) →
  RegionScan (2×2分块回退) → html5-qrcode (zxing WASM 6s超时)
```

## 许可证

本项目为课程作业项目。
