import requests
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
from config import SEOUL_API_KEY

SDOT_URL = "http://openapi.seoul.go.kr:8088/{key}/xml/sDoTEnv/{start}/{end}/"

# S-DoT API 영문 자치구명 → 한국어 매핑
DISTRICT_MAP = {
    "Gangnam-gu":       "강남구",
    "Gangdong-gu":      "강동구",
    "Gangbuk-gu":       "강북구",
    "Gangseo-gu":       "강서구",
    "Gwanak-gu":        "관악구",
    "Gwangjin-gu":      "광진구",
    "Guro-gu":          "구로구",
    "Geumcheon-gu":     "금천구",
    "Nowon-gu":         "노원구",
    "Dobong-gu":        "도봉구",
    "Dongdaemun-gu":    "동대문구",
    "Dongjak-gu":       "동작구",
    "Mapo-gu":          "마포구",
    "Seodaemun-gu":     "서대문구",
    "Seocho-gu":        "서초구",
    "Seongdong-gu":     "성동구",
    "Seongbuk-gu":      "성북구",
    "Songpa-gu":        "송파구",
    "Yangcheon-gu":     "양천구",
    "Yeongdeungpo-gu":  "영등포구",
    "Yongsan-gu":       "용산구",
    "Eunpyeong-gu":     "은평구",
    "Jongno-gu":        "종로구",
    "Jung-gu":          "중구",
    "Jungnang-gu":      "중랑구",
}

BATCH = 1000  # API 최대 허용 건수


@st.cache_data(ttl=300, show_spinner=False)
def fetch_noise_data() -> pd.DataFrame:
    """
    S-DoT 환경정보 API에서 최신 센서 데이터를 가져와
    자치구별 평균 소음도(dB)를 반환.
    """
    try:
        # 최신 데이터가 앞에 정렬되어 있으므로 1~BATCH 조회
        url = SDOT_URL.format(key=SEOUL_API_KEY, start=1, end=BATCH)

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        rows = _parse_xml(resp.content)
        if not rows:
            return _fallback_noise_data()

        df = pd.DataFrame(rows)
        df["avg_noise"] = pd.to_numeric(df["avg_noise"], errors="coerce")
        df = df[df["avg_noise"] > 0].dropna(subset=["avg_noise"])  # 빈값·0 제거

        # 자치구별 평균 소음도 집계
        result = (
            df.groupby("district")
            .agg(noise_db=("avg_noise", "mean"), measured_at=("sensing_time", "max"))
            .reset_index()
        )
        result["noise_db"] = result["noise_db"].round(1)
        # 포맷 정리: "2026-04-28_02:07:00" → "2026-04-28 02:07"
        result["measured_at"] = result["measured_at"].str.replace("_", " ").str[:16]
        return result

    except Exception as e:
        st.warning(f"소음 API 호출 실패: {e} — 샘플 데이터 사용")
        return _fallback_noise_data()


def _parse_xml(content: bytes) -> list[dict]:
    root = ET.fromstring(content)
    rows = []
    for row in root.findall("row"):
        eng = row.findtext("AUTONOMOUS_DISTRICT", "").strip()
        district = DISTRICT_MAP.get(eng)
        if not district:
            continue
        rows.append({
            "district":     district,
            "avg_noise":    row.findtext("AVG_NOISE", ""),
            "sensing_time": row.findtext("SENSING_TIME", ""),
        })
    return rows


def _fallback_noise_data() -> pd.DataFrame:
    import random
    from config import DISTRICTS
    return pd.DataFrame({
        "district":    DISTRICTS,
        "noise_db":    [round(random.uniform(42, 72), 1) for _ in DISTRICTS],
        "measured_at": ["샘플 데이터"] * len(DISTRICTS),
    })
