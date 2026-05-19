# 数字图像处理 — 条形码/二维码识别

数字图像处理课程大作业 · 任务四 · 南方科技大学 电子与电气工程系 · 2026

基于传统数字图像处理技术的条形码/二维码自动检测、定位与解码系统。

## 项目结构

```
├── code/
│   ├── scanner-app/           # 移动端 Web 扫码应用 (PWA)
│   │   ├── index.html         #   主页面
│   │   ├── style.css          #   样式 (移动端 UI)
│   │   ├── app.js             #   扫码逻辑 (html5-qrcode + jsQR)
│   │   ├── manifest.json      #   PWA 清单
│   │   └── sw.js              #   Service Worker
│   ├── image-processing/      # 传统图像处理 Pipeline (Python)
│   │   ├── preprocess.py      #   图像预处理 (灰度化/滤波/二值化)
│   │   ├── localize.py        #   条码/二维码定位 (Canny/形态学/Finder Pattern)
│   │   ├── correct.py         #   几何校正 (旋转/透视变换)
│   │   ├── decode.py          #   解码识别 (EAN-13/Code-128/Code-39/QR)
│   │   ├── pipeline.py        #   完整识别管线
│   │   └── gui.py             #   桌面 GUI (tkinter)
│   └── test-generator/        # 测试图片生成器
│       └── generate_all.py    #   生成各类测试条码/二维码
├── images/test_images/        # 测试图片集 (~50+ 张)
├── results/                   # 识别结果输出
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

> **重要**: 浏览器摄像头 API (`getUserMedia`) 仅限**安全上下文**（HTTPS 或 localhost）。
> 手机通过局域网 IP 访问必须使用 HTTPS，否则会提示"权限不足"。

#### 方式一：HTTPS 本地服务器（推荐，手机/电脑均可）

```bash
cd code/scanner-app

# 1. 生成自签名证书（仅首次）
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
  -days 365 -nodes -subj "//CN=<你的IP地址>"

# 2. 启动 HTTPS 服务器
python server_https.py
```

电脑浏览器访问 `https://localhost:8443`，手机访问 `https://<电脑IP>:8443`。

首次访问时浏览器会提示证书不受信任，点击"高级 → 继续访问"即可。

> Windows 用户需额外放行防火墙端口:
> ```bash
> netsh advfirewall firewall add rule name="Scanner HTTPS 8443" dir=in action=allow protocol=TCP localport=8443
> ```

#### 方式二：HTTP 本地调试（仅电脑浏览器）

```bash
cd code/scanner-app
python -m http.server 8000
# 浏览器打开 http://localhost:8000
```

> `localhost` 被视为安全上下文，摄像头可正常使用。但手机通过 IP 访问 `http://<IP>:8000` 会因非 HTTPS 而无法调用摄像头。

#### 方式三：PWA / Netlify 在线版（推荐，手机/电脑均可，无需安装）

直接浏览器打开即用，支持 PWA 添加到桌面：

```
https://clever-torrone-2cb8c8.netlify.app
```

Chrome/Edge 打开后 → 菜单 → **"添加到主屏幕"** → 桌面出现独立 App 图标，全屏运行。

#### 方式四：Android APK（荣耀/小米等无 Google 服务的手机）

下载安装 APK，内置 WebView 加载扫码页面，不依赖 Google Play Services：

```
https://clever-torrone-2cb8c8.netlify.app/scanner.apk
```

> 自行构建 APK:
> ```bash
> npm install                      # 仅首次
> npx cap sync android             # 同步 web 资源
> cd android && ./gradlew assembleDebug
> # APK 输出: android/app/build/outputs/apk/debug/app-debug.apk
> ```

#### 方式五：直接打开文件（不支持摄像头）

双击 `code/scanner-app/index.html` 在浏览器中打开，可使用**图片上传识别**功能，但无法使用摄像头扫码。

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

## 测试结果

### 完整测试集 (195 张)

| 类别 | 数量 | 通过 | 正确率 |
|------|------|------|--------|
| 标准 QR 码 | 10 | 10 | 100% |
| 旋转 QR (10°/20°/30°/40°) | 24 | 24 | 100% |
| 高斯噪声 QR | 6 | 6 | 100% |
| 椒盐噪声 QR (强度10/20) | 12 | 12 | 100% |
| 模糊 QR | 10 | 10 | 100% |
| 光照不均 QR | 10 | 10 | 100% |
| 部分遮挡 QR | 5 | 5 | 100% |
| 透视畸变 QR (25%/40%) | 10 | 10 | 100% |
| 复杂背景 QR | 4 | 4 | 100% |
| 小型 QR | 5 | 5 | 100% |
| 多码图像 | 3 | 3 | 100% |
| 混合类型 | 3 | 3 | 100% |
| 基础 EAN-13 条码 | 5 | 5 | 100% |
| 基础 Code-128 条码 | 5 | 5 | 100% |
| 基础 Code-39 条码 | 5 | 5 | 100% |
| 旋转条码 (15°/30°) | 18 | 18 | 100% |
| 条码噪声/模糊 | 6 | 6 | 100% |
| **条码透视畸变 (12%/25%)** | 18 | 17 | 94.4% |
| **条码遮挡** | 9 | 9 | 100% |
| **条码光照变化 (40%/60%)** | 18 | 18 | 100% |
| **条码复杂背景** | 9 | 9 | 100% |
| **总计** | **195** | **194** | **99.5%** |

> 条码透视畸变采用真透视变换（非仿射），一维条码强度 12%/25%，QR 码强度 25%/40%。
> 唯一未通过: `barcode_code39_03_perspective_25.png` —
> Code-39 长条码 "DIP2026" 在 25% 透视下边缘条空宽度畸变超出 pyzbar 容限。

### 精选 50 组评估

从 195 张图片中按类别比例选取 50 张代表性样本：

| 指标 | 结果 |
|------|------|
| 通过数 | 50 / 50 |
| 正确率 | **100%** |
| 总耗时 | 2.0 秒 |
| 平均耗时 | 41 ms/图 |

## 技术路线

```
图像输入 → 预处理 → 定位检测 → 几何校正 → 解码识别 → 结果输出
  │          │          │          │          │
  │      灰度化    Canny边缘   霍夫变换   扫描线法
  │      滤波去噪   形态学膨胀   透视变换   条空宽度
  │      二值化    轮廓筛选   旋转校正   Finder Pattern
  │      CLAHE    梯度直方图              RS纠错
```

核心算法基于传统图像处理 (不依赖深度学习)，符合课程要求。

## 许可证

本项目为课程作业项目。
