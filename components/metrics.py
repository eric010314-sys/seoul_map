import streamlit as st
import pandas as pd
from config import NOISE_LEVELS


def render_kpi_row(
    overlay: str,
    noise_df: pd.DataFrame,
    pop_df: pd.DataFrame,
    green_df: pd.DataFrame,
):
    """오버레이에 맞는 KPI 카드 2x2 렌더링 (모바일 대응)."""
    r1c1, r1c2 = st.columns(2)
    r2c1, r2c2 = st.columns(2)

    if overlay == "녹지율":
        total = green_df["green_area"].sum()
        top   = green_df.loc[green_df["green_area"].idxmax()]
        bot   = green_df.loc[green_df["green_area"].idxmin()]
        avg   = green_df["green_area"].mean()
        r1c1.metric("전체 녹지면적",  f"{int(total):,} ㎡")
        r1c2.metric("가장 초록",      top["district"], f"{int(top['green_area']):,} ㎡")
        r2c1.metric("녹지 부족",      bot["district"], f"{int(bot['green_area']):,} ㎡")
        r2c2.metric("자치구 평균",    f"{int(avg):,} ㎡")

    elif overlay == "유동인구":
        total    = pop_df["population"].sum()
        busiest  = pop_df.loc[pop_df["population"].idxmax()]
        quietest = pop_df.loc[pop_df["population"].idxmin()]
        jammed   = (pop_df["congestion"] == "붐빔").sum()
        r1c1.metric("전체 추정인구", f"{total:,} 명")
        r1c2.metric("가장 붐비는 곳", busiest["district"], busiest.get("congestion", ""))
        r2c1.metric("가장 한산한 곳", quietest["district"], f"{int(quietest['population']):,} 명")
        r2c2.metric("붐빔 자치구",    f"{jammed} 개")

    else:  # 소음
        avg    = noise_df["noise_db"].mean()
        loud   = noise_df.loc[noise_df["noise_db"].idxmax()]
        quiet  = noise_df.loc[noise_df["noise_db"].idxmin()]
        over65 = (noise_df["noise_db"] >= 65).sum()
        r1c1.metric("평균 소음도",    f"{avg:.1f} dB",          _noise_label(avg))
        r1c2.metric("가장 시끄러운 곳", loud["district"],        f"{loud['noise_db']:.1f} dB")
        r2c1.metric("가장 조용한 곳", quiet["district"],         f"{quiet['noise_db']:.1f} dB")
        r2c2.metric("65dB 초과",      f"{over65} 개")


def render_district_detail(
    district: str,
    noise_df: pd.DataFrame,
    pop_df: pd.DataFrame,
    green_df: pd.DataFrame,
):
    if district == "전체":
        st.info("사이드바에서 자치구를 선택하면 상세 정보를 확인할 수 있습니다.")
        return

    st.markdown(f"### {district} 상세 정보")
    c1, c2, c3 = st.columns(3)

    g = green_df[green_df["district"] == district]
    if not g.empty:
        c1.metric("🌿 녹지면적", f"{int(g.iloc[0]['green_area']):,} ㎡")

    p = pop_df[pop_df["district"] == district]
    if not p.empty:
        c2.metric("👥 추정인구", f"{int(p.iloc[0]['population']):,} 명", p.iloc[0].get("congestion", ""))
        c2.caption(f"갱신: {p.iloc[0].get('updated_at', '-')}")

    n = noise_df[noise_df["district"] == district]
    if not n.empty:
        db  = n.iloc[0]["noise_db"]
        mat = n.iloc[0]["measured_at"] if "measured_at" in n.columns else "-"
        c3.metric("🔊 소음도", f"{db:.1f} dB", _noise_label(db))
        c3.caption(f"측정: {mat}")


def render_ranking_table(
    noise_df: pd.DataFrame,
    pop_df: pd.DataFrame,
    green_df: pd.DataFrame,
    overlay: str,
):
    sort_col = {"녹지율": "green_area", "유동인구": "population", "소음": "noise_db"}[overlay]

    merged = green_df[["district", "green_area"]].merge(
        noise_df[["district", "noise_db"]], on="district", how="outer"
    ).merge(
        pop_df[["district", "population", "congestion"]], on="district", how="outer"
    )
    merged = merged.sort_values(sort_col, ascending=(overlay != "소음")).reset_index(drop=True)
    merged.index += 1
    merged = merged.rename(columns={
        "district":   "자치구",
        "green_area": "녹지면적(㎡)",
        "noise_db":   "소음도(dB)",
        "population": "추정인구(명)",
        "congestion": "혼잡도",
    })
    merged["추정인구(명)"] = merged["추정인구(명)"].apply(
        lambda x: f"{int(x):,}" if pd.notna(x) else "-"
    )
    st.dataframe(merged, width="stretch")


def _noise_label(db: float) -> str:
    for label, (lo, hi) in NOISE_LEVELS.items():
        if lo <= db < hi:
            return label
    return ""
