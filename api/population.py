import requests
import pandas as pd
import streamlit as st
from config import SEOUL_API_KEY, POPULATION_API_URL, AREA_CODES

@st.cache_data(ttl=300, show_spinner=False)
def fetch_population_data() -> pd.DataFrame:
    """
    서울 실시간 도시데이터 생활인구 API (OA-21778) 호출.
    자치구별 현재 추정 생활인구를 반환.
    """
    records = []
    for district, area_name in AREA_CODES.items():
        url = POPULATION_API_URL.format(key=SEOUL_API_KEY, area_name=area_name)
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            raw = resp.json()

            ppltn = raw.get("SeoulRtd.citydata_ppltn", [{}])[0]
            records.append({
                "district":    district,
                "area_name":   area_name,
                "population":  int(ppltn.get("AREA_PPLTN_MAX", 0)),
                "congestion":  ppltn.get("AREA_CONGEST_LVL", "정보없음"),  # 여유/보통/약간붐빔/붐빔
                "updated_at":  ppltn.get("PPLTN_TIME", ""),
            })
        except Exception as e:
            records.append({
                "district":   district,
                "area_name":  area_name,
                "population": 0,
                "congestion": "오류",
                "updated_at": "",
            })

    df = pd.DataFrame(records)
    if df["population"].sum() == 0:
        st.warning("생활인구 API 호출 실패 — 샘플 데이터 사용")
        return _fallback_population_data()
    return df


def _fallback_population_data() -> pd.DataFrame:
    """API 미연동 시 사용할 더미 데이터."""
    import random
    from config import DISTRICTS
    levels = ["여유", "보통", "약간붐빔", "붐빔"]
    return pd.DataFrame({
        "district":   DISTRICTS,
        "population": [random.randint(5_000, 80_000) for _ in DISTRICTS],
        "congestion": [random.choice(levels) for _ in DISTRICTS],
        "updated_at": ["샘플 데이터"] * len(DISTRICTS),
    })
