# 数字图像处理 — 条形码/二维码识别

数字图像处理课程大作业 · 任务四 · 南方科技大学 电子与电气工程系 · 2026

基于传统数字图像处理技术的条形码/二维码自动检测、定位与解码系统。

## 版本历史

| 版本 | 日期 | 关键改进 |
|------|------|----------|
| **v2.0.0** | 2026-05-21 | 多引擎压力测试, pyzbar增强预处理, 条码透视归一化, 撕裂检测优化, 多码裁剪增强 |
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
│   │   ├── advanced_cv_scanner.py  # AdvancedCVScanner v2.0.0 — 9模块降质修复
│   │   ├── pipeline.py        #   完整识别管线
│   │   └── gui.py             #   桌面 GUI (tkinter)
│   └── test-generator/        # 测试图片生成器 (8个生成器)
├── images/
│   ├── test_images/           # 基础测试图片集 (~50+ 张)
│   └── stress_test/           # 压力测试集 (2,658 张, 21 类)
├── results/                   # 测试结果
├── run_stress_test.py         # 多引擎分层压力测试脚本 (v2.0.0)
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
| **在线版** | 有网络, 无需安装, 支持 PWA 添加到桌面 | [Netlify 在线版](https://clever-torrone-2cb8c8.netlify.app) |
| **APK 安装** | 无 Google 服务 (荣耀/小米), 离线使用 | [GitHub Releases](https://github.com/whx12210512/digital-image-processing/releases/latest) |

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

## 测试结果 (v2.0.0)

### 多引擎压力测试 (2,658 张 — 21 类)

使用 **pyzbar** (增强预处理) + **cv2.QRCodeDetector** + **AdvancedCVScanner** 三引擎分层测试。

| 类别 | 数量 | 正确率 | 状态 |
|------|------|--------|------|
| barcode_geometric | 110 | 12.7% | FAIL ⚠ |
| barcode_ink | 110 | 100.0% | PASS |
| barcode_scratches | 110 | 95.5% | PASS |
| damage_noise | 110 | 70.9% | FAIL ⚠ |
| edge_quiet_zone | 164 | 95.7% | PASS |
| edge_tear | 110 | 48.2% | FAIL ⚠ |
| flaw_highlight | 110 | 100.0% | PASS |
| flaw_low_contrast | 110 | 100.0% | PASS |
| flaw_motion_blur | 330 | 83.9% | PASS |
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
| multi_qr | 110 | 70.0% | FAIL ⚠ |
| **总计** | **2,658** | **85.3%** | **17/21 PASS** |

### v2.0.0 改进成果

| 改进项 | 提升 |
|--------|------|
| ink_data_pollution | 76.2% → **100.0%** (+23.8%) |
| ink_corner_destruction | 85.4% → **93.9%** (+8.5%) |
| flaw_motion_blur | 80.9% → **83.9%** (+3.0%) |
| barcode_scratches | 92.7% → **95.5%** (+2.8%) |
| damage_noise | 67.3% → **70.9%** (+3.6%) |
| liquid_coffee | 97.5% → **100.0%** (+2.5%) |

### 不可恢复类别分析

| 类别 | 原因 |
|------|------|
| barcode_geometric (12.7%) | 透视压缩 (25-70%) + 柱面弯曲从根本上破坏条空宽度比, pyzbar 无法恢复 |
| edge_tear (48.2%) | 大面积撕裂/碎片导致 >40% 数据缺失, 修复算法无法重建缺失模块 |
| damage_noise (70.9%) | 随机破坏 (划痕+噪声+模糊+遮挡) 在 ~30% 图像中损毁 QR 定位符 |
| multi_qr (70.0%) | 多码图像中小码 (<50px) 或高度变换码超出定位符检测能力 |

## 技术路线

### AdvancedCVScanner v2.0.0 — 9 模块降质修复管线

```
图像输入 → 降质分类 → 模块化修复 → 多引擎解码 → 结果输出
  │            │           │              │
  │     NCC模板匹配    模块1: 定位符修补    pyzbar
  │     扫描线剖面     模块2: 柱面展平    cv2.QRCodeDetector
  │                   模块3: 多码裁剪    AdvancedCVScanner
  │                   模块4: 降噪修复
  │                   模块5: 颜色污渍去除
  │                   模块6: 墨点滤除
  │                   模块7: 运动模糊恢复
  │                   模块8: 撕裂修复
  │                   模块9: 条码透视归一化 (NEW v2.0.0)
```

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
