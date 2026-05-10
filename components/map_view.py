import json
import requests
import pandas as pd
import streamlit as st

SEOUL_GEOJSON_URL = (
    "https://raw.githubusercontent.com/southkorea/seoul-maps/master/"
    "kostat/2013/json/seoul_municipalities_geo_simple.json"
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_geojson() -> dict:
    resp = requests.get(SEOUL_GEOJSON_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()


def build_html_map(
    noise_df: pd.DataFrame,
    cong_df: pd.DataFrame,
    green_df: pd.DataFrame,
    height: int = 580,
) -> str:
    geo = load_geojson()

    green_data      = {r["district"]: round(float(r["green_ratio"]), 2)
                       for _, r in green_df.iterrows() if pd.notna(r["green_ratio"])}
    noise_data      = {r["district"]: round(float(r["noise_db"]), 1)
                       for _, r in noise_df.iterrows() if pd.notna(r["noise_db"])}
    cong_score_data = {r["district"]: float(r["congestion_score"])
                       for _, r in cong_df.iterrows() if pd.notna(r["congestion_score"])}
    cong_label_data = {r["district"]: str(r["congestion_label"])
                       for _, r in cong_df.iterrows()}

    geo_js        = json.dumps(geo,             ensure_ascii=False)
    green_js      = json.dumps(green_data,      ensure_ascii=False)
    noise_js      = json.dumps(noise_data,      ensure_ascii=False)
    cong_score_js = json.dumps(cong_score_data, ensure_ascii=False)
    cong_label_js = json.dumps(cong_label_data, ensure_ascii=False)

    data_block = f"""
const GEO  = {geo_js};
const DATA = {{
  green      : {green_js},
  cong       : {cong_score_js},
  cong_label : {cong_label_js},
  noise      : {noise_js},
}};
const MAP_H = {height};
"""

    style = """
* { margin:0; padding:0; box-sizing:border-box; }
html,body { height:100%; overflow:hidden; background:#f1f5f0; }
#map { width:100%; height:100vh; }

/* 버튼 그룹 */
.controls {
  position:absolute; top:14px; left:14px; z-index:1000;
  display:flex; gap:6px;
}
.ctrl {
  display:flex; align-items:center; gap:5px;
  background:rgba(255,255,255,0.88); backdrop-filter:blur(8px);
  color:#166534; border:1px solid rgba(22,101,52,0.2);
  border-radius:999px; padding:7px 18px;
  font-size:13px; font-weight:600; cursor:pointer;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  transition:all .18s ease;
  box-shadow:0 2px 10px rgba(0,0,0,.12);
  letter-spacing:.01em; white-space:nowrap;
}
.ctrl:hover {
  background:rgba(220,252,231,0.95);
  color:#14532d;
  border-color:rgba(22,101,52,.35);
}
.ctrl.active {
  background:#16a34a;
  color:#ffffff;
  border-color:transparent;
  box-shadow:0 3px 14px rgba(22,163,74,.35);
}

/* 정보 패널 (클릭 시 표시) */
#panel {
  position:absolute; z-index:1000;
  background:rgba(255,255,255,0.97); backdrop-filter:blur(14px);
  color:#1e293b; border-radius:16px; padding:16px 20px;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:13px; min-width:195px; display:none;
  border:1px solid rgba(0,0,0,.07);
  box-shadow:0 8px 32px rgba(0,0,0,.15);
  pointer-events:auto;
}
.pheader {
  display:flex; justify-content:space-between; align-items:center;
  border-bottom:1px solid rgba(0,0,0,.07);
  padding-bottom:10px; margin-bottom:10px;
}
.pname { font-size:16px; font-weight:700; color:#0f172a; }
.pclose {
  background:none; border:none; cursor:pointer;
  color:#94a3b8; font-size:18px; line-height:1; padding:0;
}
.pclose:hover { color:#475569; }
.prow { display:flex; justify-content:space-between; gap:22px; margin:6px 0; }
.plabel { color:#94a3b8; }
.pval   { font-weight:600; }
.pdiv   {
  margin-top:10px; padding-top:10px;
  border-top:1px solid rgba(0,0,0,.06);
  font-size:11px;
}

/* 범례 */
#legend {
  position:absolute; bottom:20px; left:14px; z-index:1000;
  background:rgba(255,255,255,0.95); backdrop-filter:blur(14px);
  border-radius:12px; padding:13px 17px;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:11px; color:#64748b;
  border:1px solid rgba(0,0,0,.07);
  box-shadow:0 8px 32px rgba(0,0,0,.13);
}
#legend .ltitle { color:#475569; font-weight:600; font-size:12px; margin-bottom:8px; }
#lbar { width:155px; height:9px; border-radius:5px; margin:4px 0; }
.llabels { display:flex; justify-content:space-between; font-size:10px; color:#94a3b8; }
"""

    logic = """
const PAL = {
  green : ['#e8ede6','#c0cebc','#96ae90','#6d8e65','#46663f','#2b3b2b'],
  cong  : ['#e6eaed','#bcc5cd','#8ea2b0','#607f94','#3d5f76','#2b3b4b'],
  noise : ['#ede8e8','#cebbbb','#ae9090','#8e6565','#663d3d','#3b2b2b'],
};
const CONG_LABEL = {1:'여유', 2:'보통', 3:'약간붐빔', 4:'붐빔'};
const META = {
  green : { title:'공원접근비율 (%)',  fmt: v => v.toFixed(2)+'%' },
  cong  : { title:'혼잡도',      fmt: v => CONG_LABEL[Math.round(v)] || v.toFixed(1) },
  noise : { title:'소음 (dB)',   fmt: v => v.toFixed(1)+' dB' },
};

let ov = 'green', gLayer;
function getOvData(key) { return key === 'cong' ? DATA.cong : DATA[key]; }

const renderer = L.canvas({ padding: 0.5 });
const map = L.map('map', {zoomControl:false, attributionControl:false, preferCanvas:true})
             .setView([37.535, 127.01], 11);

L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
  {subdomains:'abcd', maxZoom:19}
).addTo(map);

function h2rgb(h) {
  return [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)];
}
function lerpColor(pal, t) {
  t = Math.max(0, Math.min(1, t));
  const s = t * (pal.length - 1);
  const i = Math.min(Math.floor(s), pal.length - 2);
  const f = s - i;
  const [r1,g1,b1] = h2rgb(pal[i]), [r2,g2,b2] = h2rgb(pal[i+1]);
  return `rgb(${Math.round(r1+(r2-r1)*f)},${Math.round(g1+(g2-g1)*f)},${Math.round(b1+(b2-b1)*f)})`;
}
function getColor(val) {
  const vals = Object.values(getOvData(ov)).filter(v => v != null);
  const min = Math.min(...vals), max = Math.max(...vals);
  if (val == null) return '#d1d5db';
  return lerpColor(PAL[ov], max > min ? (val - min) / (max - min) : 0);
}

function setOv(key) {
  ov = key;
  document.querySelectorAll('.ctrl').forEach(b => b.classList.remove('active'));
  document.getElementById('b-' + key).classList.add('active');
  updateLegend();
  renderLayer();
}


function updateLegend() {
  const vals = Object.values(getOvData(ov)).filter(v => v != null);
  const min = Math.min(...vals), max = Math.max(...vals);
  document.getElementById('ltitle').textContent = META[ov].title;
  document.getElementById('lbar').style.background =
    `linear-gradient(to right, ${PAL[ov].join(',')})`;
  document.getElementById('lmin').textContent = META[ov].fmt(min);
  document.getElementById('lmax').textContent = META[ov].fmt(max);
}

function renderLayer() {
  if (gLayer) map.removeLayer(gLayer);
  gLayer = L.geoJSON(GEO, {
    renderer: renderer,
    style: f => ({
      fillColor  : getColor(getOvData(ov)[f.properties.name]),
      weight     : 1.5,
      color      : 'rgba(255,255,255,.7)',
      fillOpacity: .75,
    }),
    onEachFeature: (f, lyr) => {
      const n = f.properties.name;
      lyr.on({
        click: e => {
          L.DomEvent.stopPropagation(e);
          const g  = DATA.green[n];
          const cs = DATA.cong[n];
          const cl = DATA.cong_label[n];
          const ns = DATA.noise[n];
          const panel = document.getElementById('panel');

          panel.style.display = 'block';
          panel.innerHTML = `
            <div class="pheader">
              <span class="pname">${n}</span>
              <button class="pclose" onclick="document.getElementById('panel').style.display='none'">×</button>
            </div>
            <div class="prow">
              <span class="plabel">🌿 공원접근비율</span>
              <span class="pval" style="color:#16a34a">${g != null ? g.toFixed(2)+'%' : '-'}</span>
            </div>
            <div class="prow">
              <span class="plabel">🚶 혼잡도</span>
              <span class="pval" style="color:#ea580c">${cl && cl !== 'None' ? cl : '-'}${cs != null ? ` <span style="color:#94a3b8;font-size:11px">(${cs.toFixed(1)})</span>` : ''}</span>
            </div>
            <div class="prow">
              <span class="plabel">🔊 소음도</span>
              <span class="pval" style="color:#f87171">${ns != null ? ns.toFixed(1)+' dB' : '-'}</span>
            </div>
          `;

          const cp  = e.containerPoint;
          const mEl = document.getElementById('map');
          const mW  = mEl.offsetWidth;
          const mH  = mEl.offsetHeight;
          const pW  = panel.offsetWidth  || 210;
          const pH  = panel.offsetHeight || 160;
          const off = 14;

          let left = cp.x + off;
          let top  = cp.y + off;
          if (left + pW > mW - 10) left = cp.x - pW - off;
          if (top  + pH > mH - 10) top  = cp.y - pH - off;
          left = Math.max(10, left);
          top  = Math.max(10, top);

          panel.style.left   = left + 'px';
          panel.style.top    = top  + 'px';
          panel.style.right  = 'auto';
          panel.style.bottom = 'auto';
        },
      });
    },
  }).addTo(map);
}

map.on('click', () => { document.getElementById('panel').style.display = 'none'; });

updateLegend();
renderLayer();
"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>{style}</style>
</head>
<body>
<div style="position:relative">
  <div id="map"></div>
  <div class="controls">
    <button class="ctrl active" id="b-green" onclick="setOv('green')">🌿 공원접근비율</button>
    <button class="ctrl"        id="b-cong"  onclick="setOv('cong')">🚶 혼잡도</button>
    <button class="ctrl"        id="b-noise" onclick="setOv('noise')">🔊 소음도</button>
  </div>
  <div id="panel"></div>
  <div id="legend">
    <div class="ltitle" id="ltitle"></div>
    <div id="lbar"></div>
    <div class="llabels"><span id="lmin"></span><span id="lmax"></span></div>
  </div>
</div>
<script>
{data_block}
{logic}
</script>
</body>
</html>"""
