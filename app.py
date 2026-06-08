"""MoodPatch · 灵感手账空间 v2

rembg u2net 从 repo 内 models/u2net.onnx 加载，无需运行时下载。
"""
import base64
import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="MoodPatch · 灵感手账空间",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; height: 0; }
.block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stAppViewBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
[data-testid="stVerticalBlock"] > div { gap: 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── rembg：从 repo 内模型文件加载，无需网络 ──────────
MODEL_PATH = Path(__file__).parent / "models" / "u2net.onnx"

@st.cache_resource(show_spinner=False)
def get_rembg_session():
    """从 repo 内 models/u2net.onnx 加载，失败返回 None。"""
    try:
        # 告诉 rembg 去哪找模型（跳过下载）
        os.environ["U2NET_HOME"] = str(MODEL_PATH.parent)
        from rembg import new_session
        return new_session("u2net")
    except Exception as e:
        st.warning(f"rembg 加载失败: {e}", icon="⚠️")
        return None

def do_remove_bg(img_bytes: bytes) -> bytes | None:
    session = get_rembg_session()
    if session is None:
        return None
    try:
        from rembg import remove
        return remove(img_bytes, session=session)
    except Exception:
        return None

# ── Streamlit Component ────────────────────────────────
FRONTEND_DIR = Path(__file__).parent / "frontend"
_canvas = components.declare_component("moodpatch", path=str(FRONTEND_DIR))

if "processed" not in st.session_state:
    st.session_state.processed = {}

result = _canvas(
    processed_images=st.session_state.processed,
    default=None,
    key="moodpatch_canvas",
    height=2600,
)

if isinstance(result, dict) and result.get("action") == "remove_bg":
    items = result.get("images", [])
    changed = False

    for item in items:
        img_id = item.get("id")
        data_url = item.get("dataUrl", "")
        if not img_id or img_id in st.session_state.processed:
            continue

        raw = data_url.split(",", 1)[1] if "," in data_url else data_url
        img_bytes = base64.b64decode(raw)

        result_bytes = do_remove_bg(img_bytes)

        if result_bytes:
            b64 = base64.b64encode(result_bytes).decode()
            st.session_state.processed[img_id] = f"data:image/png;base64,{b64}"
        else:
            # 降级：返回原图
            st.session_state.processed[img_id] = data_url

        changed = True

    if changed:
        st.rerun()
