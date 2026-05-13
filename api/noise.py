from __future__ import annotations

import math

import pandas as pd
import requests
import streamlit as st

from config import DISTRICTS, SEOUL_API_KEY

SDOT_URL = "http://openapi.seoul.go.kr:8088/{key}/json/sDoTEnv/1/1000/"

GU_TO_DONG = {
    "종로": ["Samcheong", "Gahoe", "Ihwa", "Changsin", "Pyeongchang", "Buam", "Hyehwa", "Muak", "Gyonam", "CheongwoonHyoja", "Sungin", "Sajik"],
    "중": ["Myeong", "Gwanghui", "Sindang", "Hoehyeon", "Sogong", "Pil", "Jangchung", "Eulji-ro", "Dasan", "Jungnim"],
    "용산": ["Itaewon", "Bogwang", "Cheongpa", "Hyochang", "Huam", "Ichon", "Seobinggo", "Wonhyo-ro", "Yongmun", "Hannam", "Hangang-ro"],
    "성동": ["Seongsu", "Majang", "Sageun", "Yongdap", "Songjeong", "Geumho", "Eungbong", "Haengdang", "Wangsimni"],
    "광진": ["Junggok", "Gwangjang", "Gunja", "Guui", "Jayang", "Hwayang"],
    "동대문": ["Imun", "Cheongnyangni", "Dapsip-ri", "Jeonnong", "Jangan", "Hwigyeong", "Yongshin"],
    "중랑": ["Sinnae", "Junghwa", "Myeonmok", "Sangbong", "Muk", "Mangu"],
    "성북": ["Dongseon", "Seongbuk", "Jongam", "Donam", "Samseon", "Bomun", "Jeongneung", "Gileum", "Seokgwan", "Anam", "Wolgok"],
    "강북": ["Beon", "Suyu", "Insu", "Songcheon", "Mia", "Samyang", "Ui", "Samgaksan"],
    "도봉": ["Chang", "Banghak", "Ssangmun", "Dobong"],
    "노원": ["Wolgye", "Sanggye", "Junggye", "Hagye", "Gongneung"],
    "은평": ["Nokbeon", "Eungam", "Bulgwang", "Gusan", "Daejo", "Galhyeon", "Jingwan", "Susaek"],
    "서대문": ["Hongje", "Hongeun", "Bukgajwa", "Cheonyeon", "Yeonhui", "Bukahyeon", "Sinchon", "Chunghyeon"],
    "마포": ["Mangwon", "Sangam", "Seogyo", "Seongsan", "Yonggang", "Sinsu", "Sogang", "Yeonnam", "Ahyeon", "Hapjeong", "Dohwa", "Gongdeok", "Daeheung", "Yeomni"],
    "양천": ["Sinjeong", "Mok", "Sinwol"],
    "강서": ["Gonghang", "Banghwa", "Gayang", "Deungchon", "Balsan", "Yeomchang", "Hwagok", "Ujangsan"],
    "구로": ["Gu-ro", "Gaebong", "Oryu", "Sugung", "Hang", "Gocheok", "Sindorim"],
    "금천": ["Gasan", "Doksan", "Siheung"],
    "영등포": ["Dorim", "Dangsan", "Yeouido", "Daerim", "Munllae", "Yangpyeong", "Sin-gil", "Yeongdeungpo"],
    "동작": ["Heukseok", "Sang-do", "Sadang", "Sindaebang", "Daebang", "Noryangjin", "Boramae"],
    "관악": ["Nakseongdae", "Cheongnyong", "Inheon", "Namhyeon", "Seorim", "Sinllim", "Nangok", "Jungang", "Haengun", "Seowon", "Euncheon", "Daehak", "Jowon", "Cheongnim", "Miseong", "Nanhyang", "Seonghyeon"],
    "서초": ["Bangbae", "Banpo", "Seocho", "Yangjae", "Jamwon", "Naegok"],
    "강남": ["Sinsa", "Apgujeong", "Yeoksam", "Daechi", "Gaepo", "Nonhyeon", "Cheongdam", "Samseong", "Dogok", "Ilwon", "Suseo", "Segok"],
    "송파": ["Jangji", "Garak", "Songpa", "Jamsil", "Ogeum", "Geoyeo", "Seokchon", "Bangi", "Munjeong", "Pungnap", "Wirye", "Oryun"],
    "강동": ["Dunchon", "Cheonho", "Seongnae", "Amsa", "Sangil", "Gil", "Godeok", "Gangil"],
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_noise_data() -> pd.DataFrame:
    try:
        rows = _fetch_sdot_rows()
        if not rows:
            return _fallback_noise_data()

        final_rows = _prefer_corrected_rows(rows)
        noise_rows = [_normalize_row(row) for row in final_rows]
        noise_rows = [row for row in noise_rows if row and _is_number(row["avg_noise"])]
        if not noise_rows:
            return _fallback_noise_data()

        result_rows = [_build_district_noise(district, noise_rows) for district in DISTRICTS]
        result = pd.DataFrame([row for row in result_rows if row is not None])
        if result.empty:
            return _fallback_noise_data()

        result["noise_label"] = _labels_from_lovable_boundaries(result["noise_db"])
        return result

    except Exception as e:
        st.warning(f"소음 API 호출 실패: {e} — 샘플 데이터 사용")
        return _fallback_noise_data()


def _fetch_sdot_rows() -> list[dict]:
    url = SDOT_URL.format(key=SEOUL_API_KEY)
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    rows = data.get("sDoTEnv", {}).get("row", [])
    return rows if isinstance(rows, list) else []


def _prefer_corrected_rows(rows: list[dict]) -> list[dict]:
    corrected = [row for row in rows if _to_number(row.get("DATA_NO")) == 2]
    if corrected:
        return corrected
    return [row for row in rows if _to_number(row.get("DATA_NO")) == 1]


def _normalize_row(row: dict) -> dict | None:
    avg_noise = _to_number(row.get("AVG_NOISE"))
    if avg_noise is None:
        return None
    return {
        "autonomous_district": str(row.get("AUTONOMOUS_DISTRICT") or ""),
        "avg_noise": avg_noise,
        "max_noise": _to_number(row.get("MAX_NOISE")),
        "min_noise": _to_number(row.get("MIN_NOISE")),
        "sensing_time": row.get("SENSING_TIME") or "",
        "data_no": _to_number(row.get("DATA_NO")),
    }


def _build_district_noise(district: str, rows: list[dict]) -> dict | None:
    # Mirrors the Lovable edge function, including JavaScript replace("구", "") behavior.
    district_key = district.replace("구", "").strip()
    target_dongs = GU_TO_DONG.get(district_key, [])

    if district_key and target_dongs:
        district_rows = [
            row
            for row in rows
            if any(dong in row["autonomous_district"] for dong in target_dongs)
        ]
    else:
        district_rows = rows

    noise_rows = district_rows if district_rows else rows
    if not noise_rows:
        return None

    avg_noise = sum(row["avg_noise"] for row in noise_rows) / len(noise_rows)
    first = noise_rows[0]
    max_values = [row["max_noise"] for row in noise_rows if row["max_noise"] is not None]
    min_values = [row["min_noise"] for row in noise_rows if row["min_noise"] is not None]

    return {
        "district": district,
        "noise_db": _round_one(avg_noise),
        "measured_at": first["sensing_time"],
        "max_noise": max(max_values) if max_values else None,
        "min_noise": min(min_values) if min_values else None,
        "data_no": first["data_no"],
    }


def _labels_from_lovable_boundaries(values: pd.Series) -> pd.Series:
    mean = values.mean()
    std = values.std(ddof=0)
    boundary1 = _round_one(mean - std)
    boundary2 = _round_one(mean)
    boundary3 = _round_one(mean + std)

    return values.apply(
        lambda db: (
            "조용"
            if db < boundary1
            else "보통"
            if db < boundary2
            else "활발함"
            if db < boundary3
            else "시끄러움"
        )
    )


def _to_number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _is_number(value) -> bool:
    return _to_number(value) is not None


def _round_one(value: float) -> float:
    return round(value * 10) / 10


def _fallback_noise_data() -> pd.DataFrame:
    import random

    noise_db = [round(random.uniform(42, 72), 1) for _ in DISTRICTS]
    mean = sum(noise_db) / len(noise_db)
    std = (sum((v - mean) ** 2 for v in noise_db) / len(noise_db)) ** 0.5
    b1, b2, b3 = _round_one(mean - std), _round_one(mean), _round_one(mean + std)
    labels = [
        "조용" if v < b1 else "보통" if v < b2 else "활발함" if v < b3 else "시끄러움"
        for v in noise_db
    ]
    return pd.DataFrame({
        "district": DISTRICTS,
        "noise_db": noise_db,
        "noise_label": labels,
        "measured_at": ["샘플 데이터"] * len(DISTRICTS),
    })
