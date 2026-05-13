from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import streamlit as st

from config import DISTRICTS, SEOUL_API_KEY

SDOT_URL = "http://openapi.seoul.go.kr:8088/{key}/xml/sDoTEnv/1/1000/"

# sdot-noise 엣지 함수와 동일한 GU_TO_DONG
GU_TO_DONG: dict[str, list[str]] = {
    "종로": ["Samcheong","Gahoe","Ihwa","Changsin","Pyeongchang","Buam","Hyehwa","Muak","Gyonam","CheongwoonHyoja","Sungin","Sajik"],
    "중":   ["Myeong","Gwanghui","Sindang","Hoehyeon","Sogong","Pil","Jangchung","Eulji-ro","Dasan","Jungnim"],
    "용산": ["Itaewon","Bogwang","Cheongpa","Hyochang","Huam","Ichon","Seobinggo","Wonhyo-ro","Yongmun","Hannam","Hangang-ro"],
    "성동": ["Seongsu","Majang","Sageun","Yongdap","Songjeong","Geumho","Eungbong","Haengdang","Wangsimni"],
    "광진": ["Junggok","Gwangjang","Gunja","Guui","Jayang","Hwayang"],
    "동대문": ["Imun","Cheongnyangni","Dapsip-ri","Jeonnong","Jangan","Hwigyeong","Yongshin"],
    "중랑": ["Sinnae","Junghwa","Myeonmok","Sangbong","Muk","Mangu"],
    "성북": ["Dongseon","Seongbuk","Jongam","Donam","Samseon","Bomun","Jeongneung","Gileum","Seokgwan","Anam","Wolgok"],
    "강북": ["Beon","Suyu","Insu","Songcheon","Mia","Samyang","Ui","Samgaksan"],
    "도봉": ["Chang","Banghak","Ssangmun","Dobong"],
    "노원": ["Wolgye","Sanggye","Junggye","Hagye","Gongneung"],
    "은평": ["Nokbeon","Eungam","Bulgwang","Gusan","Daejo","Galhyeon","Jingwan","Susaek"],
    "서대문": ["Hongje","Hongeun","Bukgajwa","Cheonyeon","Yeonhui","Bukahyeon","Sinchon","Chunghyeon"],
    "마포": ["Mangwon","Sangam","Seogyo","Seongsan","Yonggang","Sinsu","Sogang","Yeonnam","Ahyeon","Hapjeong","Dohwa","Gongdeok","Daeheung","Yeomni"],
    "양천": ["Sinjeong","Mok","Sinwol"],
    "강서": ["Gonghang","Banghwa","Gayang","Deungchon","Balsan","Yeomchang","Hwagok","Ujangsan"],
    "구로": ["Gu-ro","Gaebong","Oryu","Sugung","Hang","Gocheok","Sindorim"],
    "금천": ["Gasan","Doksan","Siheung"],
    "영등포": ["Dorim","Dangsan","Yeouido","Daerim","Munllae","Yangpyeong","Sin-gil","Yeongdeungpo"],
    "동작": ["Heukseok","Sang-do","Sadang","Sindaebang","Daebang","Noryangjin","Boramae"],
    "관악": ["Nakseongdae","Cheongnyong","Inheon","Namhyeon","Seorim","Sinllim","Nangok","Jungang","Haengun","Seowon","Euncheon","Daehak","Jowon","Cheongnim","Miseong","Nanhyang","Seonghyeon"],
    "서초": ["Bangbae","Banpo","Seocho","Yangjae","Jamwon","Naegok"],
    "강남": ["Sinsa","Apgujeong","Yeoksam","Daechi","Gaepo","Nonhyeon","Cheongdam","Samseong","Dogok","Ilwon","Suseo","Segok"],
    "송파": ["Jangji","Garak","Songpa","Jamsil","Ogeum","Geoyeo","Seokchon","Bangi","Munjeong","Pungnap","Wirye","Oryun"],
    "강동": ["Dunchon","Cheonho","Seongnae","Amsa","Sangil","Gil","Godeok","Gangil"],
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_noise_data() -> pd.DataFrame:
    try:
        url = SDOT_URL.format(key=SEOUL_API_KEY)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        all_rows = _parse_xml(resp.content)

        if not all_rows:
            return _fallback_noise_data()

        # noise_quantiles 엣지 함수와 동일: 25개 구 각각 avg_noise 계산
        district_noises: dict[str, float] = {}
        for gu in DISTRICTS:
            avg = _avg_noise_for_district(gu, all_rows)
            if avg is not None:
                district_noises[gu] = avg

        if not district_noises:
            return _fallback_noise_data()

        # noise_quantiles 엣지 함수와 동일: μ±σ 경계값 계산
        vals = list(district_noises.values())
        mean = sum(vals) / len(vals)
        std  = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        b1 = round((mean - std) * 10) / 10
        b2 = round(mean        * 10) / 10
        b3 = round((mean + std) * 10) / 10

        def label(db: float) -> str:
            if db < b1: return "조용"
            if db < b2: return "보통"
            if db < b3: return "활발함"
            return "시끄러움"

        records = [
            {"district": gu, "noise_db": district_noises[gu],
             "noise_label": label(district_noises[gu]), "measured_at": ""}
            for gu in DISTRICTS if gu in district_noises
        ]
        return pd.DataFrame(records)

    except Exception as e:
        st.warning(f"소음 API 호출 실패: {e} — 샘플 데이터 사용")
        return _fallback_noise_data()


def _parse_xml(content: bytes) -> list[dict]:
    root = ET.fromstring(content)
    rows = []
    for row in root.findall("row"):
        avg = row.findtext("AVG_NOISE", "")
        if not avg:
            continue
        # ADMINISTRATIVE_DISTRICT = 동 단위 영문명
        # Lovable JSON의 AUTONOMOUS_DISTRICT와 동일한 역할
        rows.append({
            "AUTONOMOUS_DISTRICT": row.findtext("ADMINISTRATIVE_DISTRICT", "").strip(),
            "AVG_NOISE":    avg,
            "DATA_NO":      row.findtext("DATA_NO", ""),
            "SENSING_TIME": row.findtext("SENSING_TIME", ""),
        })
    return rows


def _avg_noise_for_district(district: str, all_rows: list[dict]) -> float | None:
    """sdot-noise 엣지 함수 로직과 동일."""
    # DATA_NO=2(보정값) 우선, 없으면 DATA_NO=1
    corrected = [r for r in all_rows if _to_int(r.get("DATA_NO")) == 2]
    final_rows = corrected if corrected else [r for r in all_rows if _to_int(r.get("DATA_NO")) == 1]

    district_key = district.replace("구", "").strip()
    target_dongs = GU_TO_DONG.get(district_key, [])

    if district_key and target_dongs:
        district_rows = [
            r for r in final_rows
            if any(dong in (r.get("AUTONOMOUS_DISTRICT") or "") for dong in target_dongs)
        ]
    else:
        district_rows = final_rows

    noise_rows = district_rows if district_rows else final_rows
    noise_rows = [r for r in noise_rows if r.get("AVG_NOISE") not in (None, "") and _is_number(r.get("AVG_NOISE"))]

    if not noise_rows:
        return None

    avg = sum(float(r["AVG_NOISE"]) for r in noise_rows) / len(noise_rows)
    return round(avg * 10) / 10


def _to_int(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _is_number(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _fallback_noise_data() -> pd.DataFrame:
    import random
    noise_db = [round(random.uniform(42, 72), 1) for _ in DISTRICTS]
    mean = sum(noise_db) / len(noise_db)
    std  = (sum((v - mean) ** 2 for v in noise_db) / len(noise_db)) ** 0.5
    b1 = round((mean - std) * 10) / 10
    b2 = round(mean        * 10) / 10
    b3 = round((mean + std) * 10) / 10
    return pd.DataFrame({
        "district":    DISTRICTS,
        "noise_db":    noise_db,
        "noise_label": [
            "조용" if v < b1 else "보통" if v < b2 else "활발함" if v < b3 else "시끄러움"
            for v in noise_db
        ],
        "measured_at": ["샘플 데이터"] * len(DISTRICTS),
    })
