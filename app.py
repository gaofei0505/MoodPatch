"""MoodPatch · 灵感手账空间

架构：
  · 前端 (frontend/index.html) — 完整 UI，通过 declare_component 双向通信
  · 上传流程：前端 base64 → postMessage → Python rembg(u2net) → 返回透明 PNG → 前端显示
  · rembg 用本地已下载的 u2net.onnx，无需重新下载
"""
import base64
import io
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
from PIL import Image
from rembg import new_session, remove

# ── 页面配置 ──────────────────────────────────────────
st.set_page_config(
    page_title="MoodPatch · 灵感手账空间",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 隐藏 Streamlit chrome
st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; height: 0; }
.block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stAppViewBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
[data-testid="stVerticalBlock"] > div { gap: 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── rembg u2net 模型（已本地下载，缓存到进程级） ──────
@st.cache_resource(show_spinner=False)
def get_session():
    return new_session("u2net")

@st.cache_data(show_spinner=False)
def run_rembg(img_bytes: bytes) -> bytes:
    return remove(img_bytes, session=get_session())

# ── Streamlit Component（双向通信） ───────────────────
FRONTEND_DIR = Path(__file__).parent / "frontend"
_canvas = components.declare_component("moodpatch", path=str(FRONTEND_DIR))

# ── Session state ─────────────────────────────────────
if "processed" not in st.session_state:
    st.session_state.processed = {}   # { id: "data:image/png;base64,..." }

# ── 渲染组件，传入已处理的图片 ────────────────────────
result = _canvas(
    processed_images=st.session_state.processed,
    default=None,
    key="moodpatch_canvas",
)

# ── 接收前端上传请求，用 rembg 处理后回传 ─────────────
if isinstance(result, dict) and result.get("action") == "remove_bg":
    items = result.get("images", [])   # [{ id, dataUrl }]
    changed = False
    for item in items:
        img_id = item.get("id")
        data_url = item.get("dataUrl", "")
        if not img_id or img_id in st.session_state.processed:
            continue
        # 解码 base64 → bytes
        if "," in data_url:
            data_url = data_url.split(",", 1)[1]
        img_bytes = base64.b64decode(data_url)
        # rembg 抠图
        try:
            result_bytes = run_rembg(img_bytes)
            b64 = base64.b64encode(result_bytes).decode()
            st.session_state.processed[img_id] = f"data:image/png;base64,{b64}"
            changed = True
        except Exception as e:
            st.session_state.processed[img_id] = f"error:{e}"
    if changed:
        st.rerun()
