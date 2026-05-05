import pandas as pd
from pathlib import Path

PARK_CSV = Path(__file__).parent.parent / "공원데이터.csv"

DISTRICT_AREA_KM2 = {
    "종로구": 23.91, "중구": 9.96,   "용산구": 21.87, "성동구": 16.86,
    "광진구": 17.06, "동대문구": 14.22, "중랑구": 18.49, "성북구": 24.58,
    "강북구": 23.60, "도봉구": 20.65, "노원구": 35.44, "은평구": 29.71,
    "서대문구": 17.63, "마포구": 23.85, "양천구": 17.40, "강서구": 41.45,
    "구로구": 20.12, "금천구": 13.02, "영등포구": 24.55, "동작구": 16.35,
    "관악구": 29.57, "서초구": 46.98, "강남구": 39.50, "송파구": 33.88,
    "강동구": 24.59,
}


def fetch_green_data() -> pd.DataFrame:
    raw = pd.read_csv(PARK_CSV, encoding="utf-8-sig", header=None)

    # 첫 3행은 멀티레벨 헤더 → 4행째부터 데이터
    data = raw.iloc[3:].copy()
    data.columns = [
        "type1", "district",
        "park_area", "park_per_capita",
        "urban_park_area", "urban_park_per_capita",
        "walk_park_area", "walk_per_capita",
    ]

    data = data[data["district"].isin(DISTRICT_AREA_KM2.keys())].copy()

    data["walk_park_area"] = pd.to_numeric(data["walk_park_area"], errors="coerce")

    # 도보생활권공원 (단위: 천㎡ → ×1000 → ㎡)
    data["green_area"] = data["walk_park_area"] * 1000

    data["district_area"] = data["district"].map(DISTRICT_AREA_KM2) * 1_000_000
    data["green_ratio"] = (data["green_area"] / data["district_area"] * 100).round(2)

    return data[["district", "green_area", "district_area", "green_ratio"]].reset_index(drop=True)
