import streamlit as st
import streamlit.components.v1 as components

from api.noise import fetch_noise_data
from api.congestion import fetch_congestion_data
from api.green_space import fetch_green_data
from components.map_view import build_html_map

st.set_page_config(
    page_title="서울 실시간 도시 현황",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
    <style>
    html { color-scheme: light only !important; }
    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    header[data-testid="stHeader"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    footer { visibility: hidden !important; }
    #MainMenu { display: none; }
    [data-testid="stStatusWidget"] { display: none; }
    iframe { display: block !important; margin: 0 !important; padding: 0 !important; vertical-align: top !important; }
    [data-testid="stVerticalBlock"]             { gap: 0 !important; }
    [data-testid="stCustomComponentV1"]         { line-height: 0 !important; margin: 0 !important; padding: 0 !important; }
    [data-testid="stElementContainer"]          { margin: 0 !important; padding: 0 !important; }
    [data-testid="stVerticalBlockBorderWrapper"]{ margin: 0 !important; padding: 0 !important; }
    </style>
""", unsafe_allow_html=True)


def main():
    with st.spinner("불러오는 중..."):
        noise_df = fetch_noise_data()
        cong_df  = fetch_congestion_data()
        green_df = fetch_green_data()

    html = build_html_map(noise_df, cong_df, green_df, height=600)
    components.html(html, height=600, scrolling=False)


if __name__ == "__main__":
    main()
