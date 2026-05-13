import requests
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
from config import SEOUL_API_KEY

SDOT_URL = "http://openapi.seoul.go.kr:8088/{key}/xml/sDoTEnv/{start}/{end}/"

# sdot.py(Deno 엣지 함수)와 동일한 GU_TO_DONG 매핑
# AUTONOMOUS_DISTRICT 필드는 행정동 영문명을 반환하므로 동 이름 기반으로 필터링
GU_TO_DONG = {
    "종로구": ["Samcheong","Gahoe","Ihwa","Changsin","Pyeongchang","Buam","Hyehwa","Muak","Gyonam","CheongwoonHyoja","Sungin","Sajik"],
    "중구":   ["Myeong","Gwanghui","Sindang","Hoehyeon","Sogong","Pil","Jangchung","Eulji-ro","Dasan","Jungnim"],
    "용산구": ["Itaewon","Bogwang","Cheongpa","Hyochang","Huam","Ichon","Seobinggo","Wonhyo-ro","Yongmun","Hannam","Hangang-ro"],
    "성동구": ["Seongsu","Majang","Sageun","Yongdap","Songjeong","Geumho","Eungbong","Haengdang","Wangsimni"],
    "광진구": ["Junggok","Gwangjang","Gunja","Guui","Jayang","Hwayang"],
    "동대문구": ["Imun","Cheongnyangni","Dapsip-ri","Jeonnong","Jangan","Hwigyeong","Yongshin"],
    "중랑구": ["Sinnae","Junghwa","Myeonmok","Sangbong","Muk","Mangu"],
    "성북구": ["Dongseon","Seongbuk","Jongam","Donam","Samseon","Bomun","Jeongneung","Gileum","Seokgwan","Anam","Wolgok"],
    "강북구": ["Beon","Suyu","Insu","Songcheon","Mia","Samyang","Ui","Samgaksan"],
    "도봉구": ["Chang","Banghak","Ssangmun","Dobong"],
    "노원구": ["Wolgye","Sanggye","Junggye","Hagye","Gongneung"],
    "은평구": ["Nokbeon","Eungam","Bulgwang","Gusan","Daejo","Galhyeon","Jingwan","Susaek"],
    "서대문구": ["Hongje","Hongeun","Bukgajwa","Cheonyeon","Yeonhui","Bukahyeon","Sinchon","Chunghyeon"],
    "마포구": ["Mangwon","Sangam","Seogyo","Seongsan","Yonggang","Sinsu","Sogang","Yeonnam","Ahyeon","Hapjeong","Dohwa","Gongdeok","Daeheung","Yeomni"],
    "양천구": ["Sinjeong","Mok","Sinwol"],
    "강서구": ["Gonghang","Banghwa","Gayang","Deungchon","Balsan","Yeomchang","Hwagok","Ujangsan"],
    "구로구": ["Gu-ro","Gaebong","Oryu","Sugung","Hang","Gocheok","Sindorim"],
    "금천구": ["Gasan","Doksan","Siheung"],
    "영등포구": ["Dorim","Dangsan","Yeouido","Daerim","Munllae","Yangpyeong","Sin-gil","Yeongdeungpo"],
    "동작구": ["Heukseok","Sang-do","Sadang","Sindaebang","Daebang","Noryangjin","Boramae"],
    "관악구": ["Nakseongdae","Cheongnyong","Inheon","Namhyeon","Seorim","Sinllim","Nangok","Jungang","Haengun","Seowon","Euncheon","Daehak","Jowon","Cheongnim","Miseong","Nanhyang","Seonghyeon"],
    "서초구": ["Bangbae","Banpo","Seocho","Yangjae","Jamwon","Naegok"],
    "강남구": ["Sinsa","Apgujeong","Yeoksam","Daechi","Gaepo","Nonhyeon","Cheongdam","Samseong","Dogok","Ilwon","Suseo","Segok"],
    "송파구": ["Jangji","Garak","Songpa","Jamsil","Ogeum","Geoyeo","Seokchon","Bangi","Munjeong","Pungnap","Wirye","Oryun"],
    "강동구": ["Dunchon","Cheonho","Seongnae","Amsa","Sangil","Gil","Godeok","Gangil"],
}

# 빠른 역방향 조회: 동 이름(소문자) → 구
_DONG_TO_GU: dict[str, str] = {
    dong.lower(): gu
    for gu, dongs in GU_TO_DONG.items()
    for dong in dongs
}

BATCH = 1000


@st.cache_data(ttl=300, show_spinner=False)
def fetch_noise_data() -> pd.DataFrame:
    """
    S-DoT 환경정보 API에서 최신 센서 데이터를 가져와
    자치구별 평균 소음도(dB)를 반환.
    """
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
        df = df[df["avg_noise"] > 0].dropna(subset=["avg_noise"])

        # DATA_NO=2(보정값) 우선, 없으면 DATA_NO=1(원시값) 사용
        corrected = df[df["data_no"] == 2]
        df = corrected if not corrected.empty else df[df["data_no"] == 1]

        result = (
            df.groupby("district")
            .agg(noise_db=("avg_noise", "mean"), measured_at=("sensing_time", "max"))
            .reset_index()
        )
        result["noise_db"] = result["noise_db"].round(1)
        result["measured_at"] = result["measured_at"].str.replace("_", " ").str[:16]
        return result

    except Exception as e:
        st.warning(f"소음 API 호출 실패: {e} — 샘플 데이터 사용")
        return _fallback_noise_data()


def _parse_xml(content: bytes) -> list[dict]:
    root = ET.fromstring(content)
    rows = []
    for row in root.findall("row"):
        ad = row.findtext("AUTONOMOUS_DISTRICT", "").strip()
        # sdot.py와 동일하게 행정동 이름 포함 여부로 자치구 판별
        district = _resolve_district(ad)
        if not district:
            continue
        rows.append({
            "district":     district,
            "avg_noise":    row.findtext("AVG_NOISE", ""),
            "data_no":      row.findtext("DATA_NO", ""),
            "sensing_time": row.findtext("SENSING_TIME", ""),
        })
    return rows


def _resolve_district(autonomous_district: str) -> str | None:
    ad_lower = autonomous_district.lower()
    for dong, gu in _DONG_TO_GU.items():
        if dong in ad_lower:
            return gu
    return None


def _fallback_noise_data() -> pd.DataFrame:
    import random
    from config import DISTRICTS
    return pd.DataFrame({
        "district":    DISTRICTS,
        "noise_db":    [round(random.uniform(42, 72), 1) for _ in DISTRICTS],
        "measured_at": ["샘플 데이터"] * len(DISTRICTS),
    })
