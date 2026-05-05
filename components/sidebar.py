import streamlit as st
from config import DISTRICTS, OVERLAYS


def render_sidebar() -> dict:
    st.sidebar.title("서울 실시간 도시 현황")
    st.sidebar.markdown("---")

    overlay = st.sidebar.radio(
        "오버레이 선택",
        options=OVERLAYS,
        index=0,
        format_func=lambda x: {"녹지율": "🌿 녹지율", "유동인구": "👥 유동인구", "소음": "🔊 소음"}[x],
    )

    selected_district = st.sidebar.selectbox(
        "자치구 선택",
        options=["전체"] + DISTRICTS,
    )

    st.sidebar.markdown("---")
    auto_refresh = st.sidebar.toggle("자동 새로고침 (5분)", value=False)

    st.sidebar.markdown("---")
    st.sidebar.caption("데이터 출처")
    st.sidebar.caption("🌿 녹지율 — 정적 CSV")
    st.sidebar.caption("👥 유동인구 — 서울 OA-21778")
    st.sidebar.caption("🔊 소음 — 서울 OA-15473")

    return {
        "overlay":           overlay,
        "selected_district": selected_district,
        "auto_refresh":      auto_refresh,
    }
