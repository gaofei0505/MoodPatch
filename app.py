"""手账空间 — AI 拼贴小工具

四个步骤：上传 → 自动处理（去背景）→ 自由排版（鼠标拖 / 滚轮缩放）→ 导出 PNG/PDF
全部 Python 逻辑在这一个文件里；前端画布组件在 ./frontend/index.html。

部署入口：streamlit run app.py
"""
import base64
import io
import time
import zipfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from rembg import new_session, remove

# ---------- 基本配置 ----------
st.set_page_config(
    page_title="手账空间",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "About": "**手账空间** · 上传照片 → 自动去背景 → 自由拼贴 → 一键导出 A4 可打印 PNG/PDF。",
        "Get help": None,
        "Report a bug": None,
    },
)

PREVIEW_W, PREVIEW_H = 600, 849     # 预览画布显示尺寸（约 A4 比例 1:1.414）
A4_PX = (2480, 3508)                # A4 @ 300dpi 导出分辨率
FRONTEND_DIR = Path(__file__).parent / "frontend"

ss = st.session_state
ss.setdefault("originals", [])      # list[bytes]
ss.setdefault("cutouts", [])        # list[bytes]，RGBA PNG
ss.setdefault("layout", [])         # list[dict]，画布上的元素
ss.setdefault("final", None)        # PIL.Image
ss.setdefault("upload_sig", None)


# ---------- 抠图 ----------
@st.cache_resource(show_spinner=False)
def get_session():
    """rembg 模型 session（进程级缓存）。

    首次调用会下载 u2net.onnx（~170MB）到 ~/.u2net/，并加载到内存里。
    在 Streamlit Cloud 上首启大约 30–60s。后续都是秒级。
    """
    return new_session("u2net")


@st.cache_data(show_spinner=False)
def cut(img_bytes: bytes) -> bytes:
    return remove(img_bytes, session=get_session())


def warmup_model():
    """启动后异步预热模型 + 写入 session_state；后续 Tab 2 不再等。"""
    if ss.get("model_status") == "ready":
        return
    ss["model_status"] = "loading"
    t0 = time.perf_counter()
    try:
        get_session()
        ss["model_status"] = "ready"
        ss["model_load_sec"] = round(time.perf_counter() - t0, 1)
    except Exception as e:  # 网络问题 / 模型下载失败时降级
        ss["model_status"] = "error"
        ss["model_error"] = str(e)


# ---------- 渲染（与前端 itemBox 公式保持一致） ----------
@st.cache_data(show_spinner=False)
def _decode_cutout(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b)).convert("RGBA")


def render(layout, size, cutouts) -> Image.Image:
    W, H = size
    page = Image.new("RGBA", (W, H), "white")
    base_scale = W / A4_PX[0]  # 不论预览还是 A4 导出，公式一致
    for item in layout:
        idx = int(item.get("src_idx", -1))
        if idx < 0 or idx >= len(cutouts):
            continue
        im = _decode_cutout(cutouts[idx])
        w = max(1, int(im.width * float(item.get("scale", 1.0)) * base_scale))
        h = max(1, int(im.height * float(item.get("scale", 1.0)) * base_scale))
        im = im.resize((w, h), Image.LANCZOS)
        angle = float(item.get("angle", 0) or 0)
        if angle:
            im = im.rotate(-angle, expand=True, resample=Image.BICUBIC)
        cx = int(float(item.get("cx", 0.5)) * W)
        cy = int(float(item.get("cy", 0.5)) * H)
        x = cx - im.width // 2
        y = cy - im.height // 2
        page.alpha_composite(im, (x, y))
    return page


# ---------- 自定义画布组件（双向 iframe 通信） ----------
@st.cache_data(show_spinner=False)
def _b64_data_url(b: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(b).decode()


# declare_component 用 path 指向前端目录，Streamlit 自动处理 postMessage 协议
_canvas_component = components.declare_component(
    "layout_canvas", path=str(FRONTEND_DIR)
)


def layout_canvas(layout, cutouts, key="layout_canvas"):
    """挂 HTML5 Canvas 组件；前端通过 streamlit:setComponentValue 把
    最新的 layout 回传过来。返回 dict 或 None。"""
    data_urls = [_b64_data_url(b) for b in cutouts]
    return _canvas_component(
        width=PREVIEW_W,
        height=PREVIEW_H,
        a4_px=list(A4_PX),
        layout=layout,
        cutouts_data_urls=data_urls,
        default=None,
        key=key,
    )


# ---------- ZIP 打包 ----------
def make_cutouts_zip(cutouts, originals) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, c in enumerate(cutouts):
            # 沿用原图主名，省得用户看不懂；找不到就用 cutout_i
            name = "cutout"
            if i < len(originals):
                name = "cutout_" + str(i)
            zf.writestr(f"{name}.png", c)
    return buf.getvalue()


# ---------- UI ----------
st.title("手账空间")
st.caption("上传照片 → 自动处理 → 自由拼贴 → 导出可打印 PNG/PDF")

# 首启时同步预热模型，整个过程对用户可见（spinner + 进度提示）。
# 之所以在主流程同步执行而不是后台线程：Streamlit 的 cache_resource 与 session_state
# 需要在脚本主线程被访问，避免跨线程读写带来的怪象；并且整体只阻塞首次冷启 30–60s。
if ss.get("model_status") != "ready":
    with st.status(
        "正在准备 AI 抠图模型（首次启动需下载约 170MB，之后秒开）...",
        expanded=False,
    ) as status_box:
        warmup_model()
        if ss.get("model_status") == "ready":
            status_box.update(
                label=f"模型就绪 ✓（耗时 {ss.get('model_load_sec', '?')} s）",
                state="complete",
                expanded=False,
            )
        else:
            status_box.update(
                label="模型加载失败，可稍后重试",
                state="error",
                expanded=True,
            )
            st.error(f"模型加载错误：{ss.get('model_error', '未知')}")

# 侧边栏：模型状态 + 帮助
with st.sidebar:
    st.subheader("状态")
    s = ss.get("model_status", "unknown")
    if s == "ready":
        st.success(f"AI 模型就绪（{ss.get('model_load_sec', '?')} s）")
    elif s == "loading":
        st.info("AI 模型加载中...")
    elif s == "error":
        st.error("模型加载失败")
        if st.button("重试加载模型"):
            ss.pop("model_status", None)
            st.rerun()
    st.divider()
    st.subheader("快速指南")
    st.markdown(
        "1. **上传素材** — 多张照片一起拖入\n"
        "2. **自动处理** — 一键去背景，可整包下载\n"
        "3. **自由排版** — 鼠标拖动 / 滚轮缩放 / 键盘旋转\n"
        "4. **导出** — A4 300dpi PNG / PDF\n"
    )
    st.divider()
    st.caption("基于 rembg (U2Net) · Streamlit · Pillow")

tab1, tab2, tab3, tab4 = st.tabs(["1. 上传素材", "2. 自动处理", "3. 自由排版", "4. 导出"])

# ----- Tab 1: 上传 -----
with tab1:
    files = st.file_uploader(
        "批量上传照片/素材",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )
    if files:
        sig = tuple((f.name, f.size) for f in files)
        if sig != ss.upload_sig:
            ss.originals = [f.getvalue() for f in files]
            ss.cutouts = []
            ss.layout = []
            ss.final = None
            ss.upload_sig = sig
    if ss.originals:
        st.success(f"已上传 {len(ss.originals)} 张，下一步去「自动处理」")
        cols = st.columns(4)
        for i, b in enumerate(ss.originals):
            cols[i % 4].image(b, width=150, caption=f"#{i}")
    else:
        st.info("请先选择一张或多张图片")

# ----- Tab 2: 自动处理 -----
with tab2:
    c_left, c_right = st.columns([1, 3])
    with c_left:
        do_cut = st.button("开始处理", type="primary", disabled=not ss.originals)
        if ss.originals:
            st.caption(f"待处理：{len(ss.originals)} 张")
    if do_cut:
        bar = st.progress(0.0, text="处理中...")
        ss.cutouts = []
        for i, b in enumerate(ss.originals):
            ss.cutouts.append(cut(b))
            bar.progress((i + 1) / len(ss.originals), text=f"已完成 {i + 1}/{len(ss.originals)}")
        bar.empty()
        st.success("处理完成！下一步去「自由排版」")

    if ss.cutouts:
        st.divider()
        # ★ 一键下载所有透明背景素材
        zip_bytes = make_cutouts_zip(ss.cutouts, ss.originals)
        st.download_button(
            f"📦 一键下载所有素材 ({len(ss.cutouts)} 张 · ZIP)",
            zip_bytes,
            file_name="cutouts.zip",
            mime="application/zip",
            type="primary",
        )
        st.caption("ZIP 内是去背景的 PNG，可直接拿去别处用")
        st.divider()
        st.write("抠图前后对比：")
        for i, (o, c) in enumerate(zip(ss.originals, ss.cutouts)):
            c1, c2 = st.columns(2)
            c1.image(o, caption=f"原图 #{i}", width=240)
            c2.image(c, caption=f"抠图 #{i}（透明背景）", width=240)
            # 单张也能直接下
            c2.download_button(
                f"⬇ 下载 #{i}",
                c,
                file_name=f"cutout_{i}.png",
                mime="image/png",
                key=f"dl_{i}",
            )

# ----- Tab 3: 自由排版 -----
with tab3:
    if not ss.cutouts:
        st.warning("还没有可用素材，请先到「自动处理」生成抠图")
    else:
        left, right = st.columns([1, 2])

        with left:
            st.subheader("素材库")
            st.caption("点 ➕ 添加到画布；可重复添加")
            grid = st.columns(3)
            for i, c in enumerate(ss.cutouts):
                with grid[i % 3]:
                    st.image(c, width=80)
                    if st.button("➕", key=f"add_{i}"):
                        ss.layout.append({
                            "src_idx": i,
                            "cx": 0.5,
                            "cy": 0.5,
                            "scale": 0.6,
                            "angle": 0.0,
                        })
                        st.rerun()

            st.divider()
            st.markdown(
                "**鼠标操作：**\n"
                "- 点击素材 → 选中（蓝色虚线框）\n"
                "- 按住拖动 → 移动\n"
                "- 滚轮 → 缩放\n\n"
                "**键盘（先点一下画布让它聚焦）：**\n"
                "- `R` 旋转 15°\n"
                "- `[` / `]` 调整图层\n"
                "- `Delete` 删除\n"
                "- `Esc` 取消选中"
            )
            if ss.layout:
                if st.button("清空画布"):
                    ss.layout = []
                    ss.final = None
                    st.rerun()
            st.caption(f"当前画布 {len(ss.layout)} 个元素")

        with right:
            st.subheader("画布（A4 比例 · 实时）")
            # 组件返回前端最新 layout；把它写回 ss.layout 供导出使用
            result = layout_canvas(ss.layout, ss.cutouts, key="canvas")
            if isinstance(result, dict) and "layout" in result:
                new_layout = result["layout"]
                # 只有真的变了才更新 + rerun，避免无限循环
                if new_layout != ss.layout:
                    ss.layout = new_layout
                    st.rerun()
            st.caption(
                "鼠标松开 / 滚轮停下后自动同步到 Python。"
                "导出时按 A4 300dpi 重新合成，无锯齿。"
            )

# ----- Tab 4: 导出 -----
with tab4:
    if not ss.layout:
        st.warning("画布还是空的，请先去「自由排版」摆放素材")
    else:
        st.write(f"将合成 {len(ss.layout)} 个元素，按 A4 300dpi（{A4_PX[0]}×{A4_PX[1]}）输出")
        if st.button("生成成品", type="primary"):
            with st.spinner("正在合成 A4 高清图..."):
                ss.final = render(ss.layout, A4_PX, ss.cutouts)
            st.success("生成完成！")

    if ss.final is not None:
        st.image(ss.final, width=400, caption=f"A4 成品预览 ({A4_PX[0]}×{A4_PX[1]} px)")

        png_buf = io.BytesIO()
        ss.final.save(png_buf, "PNG")
        pdf_buf = io.BytesIO()
        ss.final.convert("RGB").save(pdf_buf, "PDF", resolution=300.0)

        d1, d2 = st.columns(2)
        d1.download_button("下载 PNG", png_buf.getvalue(), "journal.png", "image/png")
        d2.download_button("下载 PDF (A4)", pdf_buf.getvalue(), "journal.pdf", "application/pdf")
