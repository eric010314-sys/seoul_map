import requests
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
from config import SEOUL_API_KEY

SDOT_URL = "http://openapi.seoul.go.kr:8088/{key}/xml/sDoTEnv/{start}/{end}/"

# sdot.py(Deno 엣지 함수)와 동일한 GU_TO_DONG 매핑
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

BATCH = 1000


@st.cache_data(ttl=300, show_spinner=False)
def fetch_noise_data() -> pd.DataFrame:
    """
    S-DoT API 1회 호출 후 sdot.py와 동일하게 자치구별 독립 필터링.
    각 자치구는 자신의 dong 목록에 매칭되는 행만 사용해 avg 계산.
    """
    try:
        url = SDOT_URL.format(key=SEOUL_API_KEY, start=1, end=BATCH)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        raw = _parse_xml(resp.content)
        if not raw:
            return _fallback_noise_data()

        df = pd.DataFrame(raw)
        df["avg_noise"] = pd.to_numeric(df["avg_noise"], errors="coerce")
        df["data_no"]   = pd.to_numeric(df["data_no"],   errors="coerce")
        df = df[df["avg_noise"] > 0].dropna(subset=["avg_noise"])

        # sdot.py와 동일: DATA_NO=2(보정값) 우선, 없으면 DATA_NO=1(원시값)
        corrected = df[df["data_no"] == 2]
        df = corrected if not corrected.empty else df[df["data_no"] == 1]

        # sdot.py를 25번 호출하는 것과 동일하게:
        # 자치구별로 독립적으로 dong 이름 포함 여부로 행을 필터링
        records = []
        for gu, dongs in GU_TO_DONG.items():
            dongs_lower = [d.lower() for d in dongs]
            mask = df["autonomous_district"].apply(
                lambda ad: any(d in ad.lower() for d in dongs_lower)
            )
            district_rows = df[mask]
            if district_rows.empty:
                continue
            records.append({
                "district":    gu,
                "noise_db":    round(district_rows["avg_noise"].mean(), 1),
                "measured_at": district_rows["sensing_time"].max(),
            })

        if not records:
            return _fallback_noise_data()

        result = pd.DataFrame(records)
        result["measured_at"] = result["measured_at"].str.replace("_", " ").str[:16]

        # 2.py와 동일하게 μ±σ 기반 4단계 분류
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
    """district 귀속 없이 원시 행 반환. 자치구 할당은 fetch_noise_data에서 구별로 처리."""
    root = ET.fromstring(content)
    rows = []
    for row in root.findall("row"):
        avg_noise = row.findtext("AVG_NOISE", "")
        if not avg_noise:
            continue
        rows.append({
            "autonomous_district": row.findtext("AUTONOMOUS_DISTRICT", "").strip(),
            "avg_noise":           avg_noise,
            "data_no":             row.findtext("DATA_NO", ""),
            "sensing_time":        row.findtext("SENSING_TIME", ""),
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
