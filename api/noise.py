import requests
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
from config import SEOUL_API_KEY

SDOT_URL = "http://openapi.seoul.go.kr:8088/{key}/xml/sDoTEnv/{start}/{end}/"

# XML AUTONOMOUS_DISTRICT 필드는 구 단위 영문명(예: "Jung-gu") 반환
DISTRICT_MAP = {
    "Gangnam-gu":      "강남구",
    "Gangdong-gu":     "강동구",
    "Gangbuk-gu":      "강북구",
    "Gangseo-gu":      "강서구",
    "Gwanak-gu":       "관악구",
    "Gwangjin-gu":     "광진구",
    "Guro-gu":         "구로구",
    "Geumcheon-gu":    "금천구",
    "Nowon-gu":        "노원구",
    "Dobong-gu":       "도봉구",
    "Dongdaemun-gu":   "동대문구",
    "Dongjak-gu":      "동작구",
    "Mapo-gu":         "마포구",
    "Seodaemun-gu":    "서대문구",
    "Seocho-gu":       "서초구",
    "Seongdong-gu":    "성동구",
    "Seongbuk-gu":     "성북구",
    "Songpa-gu":       "송파구",
    "Yangcheon-gu":    "양천구",
    "Yeongdeungpo-gu": "영등포구",
    "Yongsan-gu":      "용산구",
    "Eunpyeong-gu":    "은평구",
    "Jongno-gu":       "종로구",
    "Jung-gu":         "중구",
    "Jungnang-gu":     "중랑구",
}

BATCH = 1000


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_noise_data() -> pd.DataFrame:
    try:
        url = SDOT_URL.format(key=SEOUL_API_KEY, start=1, end=BATCH)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        rows = _parse_xml(resp.content)
        if not rows:
            return _fallback_noise_data()

        df = pd.DataFrame(rows)
        df["avg_noise"] = pd.to_numeric(df["avg_noise"], errors="coerce")
        df["data_no"]   = pd.to_numeric(df["data_no"],   errors="coerce")
        df = df.dropna(subset=["avg_noise"])

        # DATA_NO=2(보정값) 우선, 없으면 DATA_NO=1(원시값)
        corrected = df[df["data_no"] == 2]
        df = corrected if not corrected.empty else df[df["data_no"] == 1]

        result = (
            df.groupby("district")
            .agg(noise_db=("avg_noise", "mean"), measured_at=("sensing_time", "max"))
            .reset_index()
        )
        result["noise_db"]    = result["noise_db"].round(1)
        result["measured_at"] = result["measured_at"].str.replace("_", " ").str[:16]

        # μ±σ 기반 4단계 분류 (2.py와 동일)
        vals = result["noise_db"]
        mean = vals.mean()
        std  = vals.std(ddof=0)
        b1, b2, b3 = mean - std, mean, mean + std
        result["noise_label"] = vals.apply(
            lambda db: "조용" if db < b1 else "보통" if db < b2 else "활발함" if db < b3 else "시끄러움"
        )
        return result

    except Exception as e:
        st.warning(f"소음 API 호출 실패: {e} — 샘플 데이터 사용")
        return _fallback_noise_data()


def _parse_xml(content: bytes) -> list[dict]:
    root = ET.fromstring(content)
    rows = []
    for row in root.findall("row"):
        eng      = row.findtext("AUTONOMOUS_DISTRICT", "").strip()
        district = DISTRICT_MAP.get(eng)
        if not district:
            continue
        rows.append({
            "district":     district,
            "avg_noise":    row.findtext("AVG_NOISE", ""),
            "data_no":      row.findtext("DATA_NO", ""),
            "sensing_time": row.findtext("SENSING_TIME", ""),
        })
    return rows


def _fallback_noise_data() -> pd.DataFrame:
    import random
    from config import DISTRICTS
    noise_db = [round(random.uniform(42, 72), 1) for _ in DISTRICTS]
    mean = sum(noise_db) / len(noise_db)
    std  = (sum((v - mean) ** 2 for v in noise_db) / len(noise_db)) ** 0.5
    b1, b2, b3 = mean - std, mean, mean + std
    labels = [
        "조용" if v < b1 else "보통" if v < b2 else "활발함" if v < b3 else "시끄러움"
        for v in noise_db
    ]
    return pd.DataFrame({
        "district":    DISTRICTS,
        "noise_db":    noise_db,
        "noise_label": labels,
        "measured_at": ["샘플 데이터"] * len(DISTRICTS),
    })
