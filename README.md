# 手账空间 · 拼贴小工具

> 上传照片 → 一键去背景 → 鼠标自由拼贴 → 导出可打印的 A4 PNG / PDF

把朋友圈、旅行碎片做成纸质手账，不用 PS、不用 Procreate，浏览器里 3 分钟搞定。

---

## ✨ 核心功能

| 步骤 | 做什么 |
|---|---|
| **1. 上传素材** | 一次拖入多张图片（PNG / JPG / JPEG / WEBP），自动建好素材库 |
| **2. 自动处理** | rembg + U2Net 一键去背景，结果可整包 ZIP 下载也可单张下载 |
| **3. 自由排版** | 手写 HTML5 Canvas 组件：**鼠标拖动 / 滚轮缩放**、键盘旋转、删除、调图层 |
| **4. 导出** | A4 300dpi 高清合成，输出 PNG（保留透明）+ PDF（直接打印） |

### 操作速查（Tab 3）

| 操作 | 对应行为 |
|---|---|
| 左键点击素材 | 选中（蓝色虚线框） |
| 按住鼠标拖动 | 移动 |
| 滚轮 | 放大 / 缩小 |
| `R` 键 | 顺时针旋转 15° |
| `[` / `]` | 调整图层先后 |
| `Delete` / `Backspace` | 删除当前选中 |
| `Esc` | 取消选中 |

---

## 🚀 在线体验（Streamlit Cloud 部署）

1. Fork 本仓库到自己的 GitHub。
2. 打开 [share.streamlit.io](https://share.streamlit.io) → **New app**。
3. 选 fork 后的仓库 + 分支，**Main file path** 填 `app.py`，Python 版本选 **3.10**。
4. 点 Deploy。
   - 首次构建约 3–5 分钟（装 onnxruntime / numba / scikit-image）。
   - 第一次访问页面会触发模型下载（约 170MB，30–60s），状态栏可看到进度。
   - 之后启动是秒开。

部署关键文件已经准备好：

- `requirements.txt` — 已 pin 在本地验证过的版本组合
- `.streamlit/config.toml` — 主题色 + 上传大小 + 关闭统计

---

## 🖥 本地运行

需要 Python **3.10** 或更新。

### 用 conda

```bash
conda create -n myvenv python=3.10 -y
conda activate myvenv

cd ai-journal
pip install -r requirements.txt
streamlit run app.py
```

### 用 venv

```bash
cd ai-journal
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

启动成功后默认打开 `http://localhost:8501`。**首次启动会自动下载 rembg 的 U2Net 模型（约 170MB，一次性）** 到 `~/.u2net/`，请耐心等待。

### 停止

- 前台运行：终端里 `Ctrl + C` 一次。
- 后台残留进程：
  ```powershell
  # PowerShell
  Get-NetTCPConnection -LocalPort 8501 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  ```
  ```bash
  # macOS / Linux
  lsof -ti :8501 | xargs kill -9
  ```

---

## 📁 项目结构

```
ai-journal/
├── app.py                   # 全部 Python 逻辑（约 340 行，单文件）
├── frontend/
│   └── index.html           # 自定义 HTML5 Canvas 组件（鼠标 + 滚轮 + 键盘）
├── requirements.txt
├── .streamlit/
│   └── config.toml          # Streamlit 主题 / 上传 / 隐私
└── README.md
```

---

## 🧱 技术栈

| 用途 | 库 |
|---|---|
| Web 框架 | [Streamlit](https://streamlit.io) 1.57 |
| AI 抠图 | [rembg](https://github.com/danielgatis/rembg) + [onnxruntime](https://onnxruntime.ai) + U2Net |
| 图像处理 | Pillow 12 |
| 排版画布 | 自研 HTML5 Canvas（`streamlit.components.v1.declare_component`） |
| PDF 导出 | Pillow `save(..., "PDF", resolution=300.0)` |

为什么不用 `streamlit-drawable-canvas`？该库与 Streamlit 1.40+ 兼容性已经走坏，画布在新版下经常白屏。本项目用原生 `<canvas>` 自己写，体验更可控。

---

## 🛠 已知限制与调优

- **单页手账** —— 暂不支持多页拼接。
- **无撤销栈** —— 删错只能再加回来。
- **CPU 慢？** 把 `app.py` 里 `new_session("u2net")` 换成：
  - `"u2netp"`（轻量小模型，速度快 2× 但边缘略糙）
  - `"isnet-general-use"`（边缘更精细，模型更大）
- **画布尺寸** —— `PREVIEW_W / PREVIEW_H` 控制预览大小，`A4_PX` 控制导出。两个公式共用 `base_scale = W / A4_PX[0]`，所见即所得。

---

## 📜 License

MIT。
