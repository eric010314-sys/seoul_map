from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
import requests
import pandas as pd
import streamlit as st
from config import SEOUL_API_KEY, CITYDATA_URL, HOTSPOT_DISTRICT, CONGEST_SCORE, DISTRICTS

SCORE_LABEL = {1: "여유", 2: "보통", 3: "약간붐빔", 4: "붐빔"}


def _fetch_one(area: str) -> tuple[str, int | None]:
    url = CITYDATA_URL.format(key=SEOUL_API_KEY, area=area)
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        level = root.findtext(".//AREA_CONGEST_LVL", "").strip()
        return area, CONGEST_SCORE.get(level)
    except Exception:
        return area, None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_congestion_data() -> pd.DataFrame:
    district_scores: dict[str, list[int]] = {}

    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(_fetch_one, area): area for area in HOTSPOT_DISTRICT}
        for fut in as_completed(futures):
            area, score = fut.result()
            if score is None:
                continue
            district = HOTSPOT_DISTRICT[area]
            district_scores.setdefault(district, []).append(score)

    records = []
    for dist in DISTRICTS:
        scores = district_scores.get(dist, [])
        if scores:
            avg = sum(scores) / len(scores)
            label = SCORE_LABEL.get(round(avg), "보통")
        else:
            avg = None
            label = "-"
        records.append({
            "district":         dist,
            "congestion_score": round(avg, 2) if avg is not None else None,
            "congestion_label": label,
        })

    if all(r["congestion_score"] is None for r in records):
        return _fallback()

    return pd.DataFrame(records)


def _fallback() -> pd.DataFrame:
    import random
    return pd.DataFrame({
        "district":         DISTRICTS,
        "congestion_score": [round(random.uniform(1, 4), 2) for _ in DISTRICTS],
        "congestion_label": [random.choice(["여유", "보통", "약간붐빔", "붐빔"]) for _ in DISTRICTS],
    })
