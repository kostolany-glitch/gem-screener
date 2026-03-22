"""
GEM 台股兩層篩選器 — Streamlit 網頁版 v3
修正：HTML 引號衝突、配色對比度
"""

import streamlit as st
import pandas as pd
import io

st.set_page_config(
    page_title="GEM 台股篩選器",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }

.gem-header {
    background: linear-gradient(135deg, #1a1f35 0%, #0d1b2a 100%);
    border: 1px solid #2a3550;
    border-radius: 12px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
}
.gem-title { font-size: 2rem; font-weight: 700; color: #f0f6ff; letter-spacing: 2px; margin: 0; }
.gem-subtitle { color: #7fa8d0; font-size: 0.9rem; margin-top: 0.3rem; }

.metric-card {
    background: #1a1f35;
    border: 1px solid #2a3550;
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-label { color: #7fa8d0; font-size: 0.78rem; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 0.5rem; }
.metric-value { font-size: 2.2rem; font-weight: 700; color: #f0f6ff; line-height: 1; }
.metric-value.green { color: #4ade80; }
.metric-value.amber { color: #fbbf24; }
.metric-value.red   { color: #f87171; }

.pass-badge {
    display: inline-block; background: #14532d; color: #86efac;
    border: 1px solid #22c55e; border-radius: 5px;
    padding: 2px 10px; font-size: 0.75rem; font-weight: 500;
}
.near-badge {
    display: inline-block; background: #1e3a5f; color: #93c5fd;
    border: 1px solid #3b82f6; border-radius: 5px;
    padding: 2px 10px; font-size: 0.75rem; font-weight: 500;
}
.warn-badge {
    display: inline-block; background: #451a03; color: #fcd34d;
    border: 1px solid #d97706; border-radius: 5px;
    padding: 2px 8px; font-size: 0.72rem; font-weight: 500;
}
.info-box {
    background: #1a1f35; border-left: 3px solid #3b82f6;
    border-radius: 0 8px 8px 0; padding: 0.8rem 1.2rem;
    margin: 0.5rem 0; font-size: 0.85rem; color: #cbd5e1;
}
.section-title {
    color: #94a3b8; font-size: 0.75rem; font-weight: 700;
    letter-spacing: 2px; text-transform: uppercase;
    border-bottom: 1px solid #2a3550;
    padding-bottom: 0.5rem; margin: 1.5rem 0 1rem;
}
.stTabs [data-baseweb="tab-list"] { background: #1a1f35; border-radius: 10px; padding: 4px; gap: 4px; }
.stTabs [data-baseweb="tab"] { color: #7fa8d0; border-radius: 7px; font-size: 0.85rem; }
.stTabs [aria-selected="true"] { background: #2a3550 !important; color: #f0f6ff !important; }
</style>
""", unsafe_allow_html=True)

# ── 欄位關鍵字 ──
COL_KEYWORDS = {
    "代號":    (["代號"],            []),
    "名稱":    (["名稱"],            []),
    "產業別":  (["產業別"],          []),
    "PER":     (["PER", "本益比"],   []),
    "累月年增": (["累月營收年增"],    []),
    "均量":    (["日均量"],          []),
    "乖離":    (["乖離"],            []),
    "RSI":     (["RSI12", "RSI 12"], ["週"]),
    "OSC":     (["OSC"],             ["週"]),
    "外資連買": (["連續買賣日數"],    []),
    "三大法人": (["三大法人買賣超"],  []),
    "融資5日":  (["融資5日增減"],     []),
    "融資60日": (["融資增減"],        ["5日"]),
    "券資比":   (["券資比"],          []),
}
CYCLICAL_INDUSTRY = ["鋼鐵", "航運", "證券"]
CYCLICAL_NAMES    = ["群聯", "慧榮", "聯陽", "旺宏", "南亞科", "華邦電"]

def find_col(df, keywords, exclude_keywords=None):
    exclude_keywords = exclude_keywords or []
    for col in df.columns:
        for kw in keywords:
            if kw in col:
                if any(ex in col for ex in exclude_keywords):
                    break
                return col
    return None

def resolve_cols(df):
    COL, missing = {}, []
    for key, (keywords, excludes) in COL_KEYWORDS.items():
        real = find_col(df, keywords, exclude_keywords=excludes)
        if real is None:
            missing.append(key)
            COL[key] = f"__MISSING_{key}__"
        else:
            COL[key] = real
    return COL, missing

def parse_num(s):
    if pd.isna(s): return float("nan")
    s = str(s).strip().replace(",","").replace("↗","").replace("↘","").replace("→","").replace("+","")
    try: return float(s)
    except: return float("nan")

def parse_direction(s):
    if pd.isna(s): return None
    s = str(s)
    if "↗" in s: return "up"
    if "↘" in s: return "down"
    if "→" in s: return "flat"
    return None

def is_cyclical(row, COL):
    industry = str(row.get(COL["產業別"], ""))
    name     = str(row.get(COL["名稱"], ""))
    return any(kw in industry for kw in CYCLICAL_INDUSTRY) or any(kw in name for kw in CYCLICAL_NAMES)

def load_df(uploaded_file):
    raw = uploaded_file.read()
    for enc in ["utf-8-sig", "big5", "cp950", "utf-8"]:
        try: return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except: continue
    return None

def run_layer1(df, COL):
    df = df.copy()
    df["_per"] = pd.to_numeric(df[COL["PER"]], errors="coerce")
    df["_rev"] = pd.to_numeric(df[COL["累月年增"]], errors="coerce")
    df["_vol"] = df[COL["均量"]].apply(parse_num)
    cond = (df["_per"] > 0) & (df["_per"] <= 50) & (df["_rev"] > 5) & (df["_vol"] > 500)
    result = df[cond].copy()
    result["景氣循環"] = result.apply(lambda r: is_cyclical(r, COL), axis=1)
    return result.sort_values("_rev", ascending=False).reset_index(drop=True)

def run_layer2(df, COL):
    df = df.copy()
    df["_bias"]    = df[COL["乖離"]].apply(parse_num)
    df["_rsi"]     = df[COL["RSI"]].apply(parse_num)
    df["_osc"]     = df[COL["OSC"]].apply(parse_num)
    df["_osc_dir"] = df[COL["OSC"]].apply(parse_direction)
    df["T1"] = (df["_bias"] >= -5) & (df["_bias"] <= 10)
    df["T2"] = (df["_rsi"]  >= 50) & (df["_rsi"]  <= 70)
    df["T3"] = (df["_osc"]  >  0)  & (df["_osc_dir"] == "up")
    df["tech_score"] = df[["T1","T2","T3"]].sum(axis=1)
    df["_frgn"] = pd.to_numeric(df[COL["外資連買"]], errors="coerce").fillna(0)
    df["_inst"] = df[COL["三大法人"]].apply(parse_num)
    df["_f60"]  = df[COL["融資60日"]].apply(parse_num)
    df["_f5"]   = df[COL["融資5日"]].apply(parse_num)
    df["_qr"]   = pd.to_numeric(df[COL["券資比"]], errors="coerce")
    df["C1"] = (df["_frgn"] >= 2).astype(int)
    df["C2"] = (df["_inst"] > 0).astype(int)
    f60n = df["_f60"] < 0
    f5n  = df["_f5"]  < 0
    df["C3"] = 0
    df.loc[f60n & f5n, "C3"] = 2
    df.loc[~(f60n & f5n) & (f60n | f5n), "C3"] = 1
    df["C4"] = (df["_qr"] < 3).astype(int)
    df["chip_score"] = df[["C1","C2","C3","C4"]].sum(axis=1)
    df["dual_pass"] = (df["tech_score"] >= 2) & (df["chip_score"] >= 3)
    df["near_pass"] = (~df["dual_pass"]) & ((df["tech_score"] >= 2) | (df["chip_score"] >= 3))
    return df

def render_tech(row):
    parts = []
    for t, label, val in [("T1","T1 乖離",f"{row['_bias']:.1f}%"),
                           ("T2","T2 RSI", f"{row['_rsi']:.1f}"),
                           ("T3","T3 OSC", f"{row['_osc']:.2f}{'↗' if row['T3'] else ''}")]:
        ok    = bool(row[t])
        icon  = "✓" if ok else "✗"
        color = "#86efac" if ok else "#94a3b8"
        parts.append('<span style="color:{};margin-right:14px">{} {} {}</span>'.format(color, icon, label, val))
    return "".join(parts)

def render_chip(row):
    labels = ["C1外資","C2法人","C3融資","C4券資"]
    vals   = [int(row["C1"]), int(row["C2"]), int(row["C3"]), int(row["C4"])]
    parts  = []
    for label, v in zip(labels, vals):
        color = "#86efac" if v > 0 else "#94a3b8"
        parts.append('<span style="color:{};margin-right:10px">{} +{}</span>'.format(color, label, v))
    tc = "#86efac" if row["chip_score"] >= 3 else "#fbbf24"
    parts.append('<span style="color:{};font-weight:700">總分 {}/5</span>'.format(tc, int(row["chip_score"])))
    return "".join(parts)

def gaps_text(row):
    gaps = []
    if row["tech_score"] < 2:
        t = []
        if not row["T1"]: t.append("T1乖離{:.1f}%".format(row["_bias"]))
        if not row["T2"]: t.append("T2 RSI{:.1f}".format(row["_rsi"]))
        if not row["T3"]: t.append("T3 OSC非正向上")
        gaps.append("技術缺：" + "、".join(t))
    if row["chip_score"] < 3:
        c = []
        if row["C1"]==0: c.append("C1外資未連買2日")
        if row["C2"]==0: c.append("C2三大法人賣超")
        if row["C3"]==0: c.append("C3融資未減少")
        if row["C4"]==0: c.append("C4券資比≥3%")
        gaps.append("籌碼缺：" + "、".join(c))
    return " / ".join(gaps)

def build_card_dual(row, COL):
    cyc_html = '<span class="warn-badge">⚠️ 景氣循環股</span>' if row["景氣循環"] else ""
    f60 = "負（淨減少）✓" if pd.notna(row["_f60"]) and row["_f60"] < 0 else "正（淨增加）"
    f5  = "{:+,}張".format(int(row["_f5"])) if pd.notna(row["_f5"]) else "N/A"
    code = str(row[COL["代號"]]).replace('="','').replace('"','')
    return (
        '<div style="background:#0a2e0a;border:1px solid #22c55e;border-radius:10px;padding:1.2rem 1.5rem;margin-bottom:1rem">'
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.8rem;flex-wrap:wrap;gap:8px">'
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
        '<span style="color:#86efac;font-weight:700;font-size:1.1rem">{}</span>'
        '<span style="color:#94a3b8;font-size:0.82rem">{} ｜ {}</span>{}</div>'
        '<div><span class="pass-badge">技術 {}/3</span>&nbsp;<span class="pass-badge">籌碼 {}/5</span></div></div>'
        '<div style="margin-bottom:0.5rem;font-size:0.85rem">{}</div>'
        '<div style="margin-bottom:0.5rem;font-size:0.85rem">{}</div>'
        '<div style="color:#cbd5e1;font-size:0.8rem">融資前60日：{} ／ 融資前5日：{}</div>'
        '</div>'
    ).format(row[COL["名稱"]], code, row[COL["產業別"]], cyc_html,
             int(row["tech_score"]), int(row["chip_score"]),
             render_tech(row), render_chip(row), f60, f5)

def build_card_near(row, COL):
    cyc_html = '<span class="warn-badge">⚠️ 景氣循環股</span>' if row["景氣循環"] else ""
    f60 = "負（淨減少）" if pd.notna(row["_f60"]) and row["_f60"] < 0 else "正（淨增加）"
    f5  = "{:+,}張".format(int(row["_f5"])) if pd.notna(row["_f5"]) else "N/A"
    code = str(row[COL["代號"]]).replace('="','').replace('"','')
    gaps = gaps_text(row)
    return (
        '<div style="background:#0d1829;border:1px solid #3b82f6;border-radius:10px;padding:1.2rem 1.5rem;margin-bottom:0.8rem">'
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.8rem;flex-wrap:wrap;gap:8px">'
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
        '<span style="color:#93c5fd;font-weight:600;font-size:1rem">{}</span>'
        '<span style="color:#94a3b8;font-size:0.82rem">{} ｜ {}</span>{}</div>'
        '<div><span class="near-badge">技術 {}/3</span>&nbsp;<span class="near-badge">籌碼 {}/5</span></div></div>'
        '<div style="margin-bottom:0.5rem;font-size:0.85rem">{}</div>'
        '<div style="margin-bottom:0.5rem;font-size:0.85rem">{}</div>'
        '<div style="color:#cbd5e1;font-size:0.8rem;margin-bottom:0.4rem">融資前60日：{} ／ 融資前5日：{}</div>'
        '<div style="background:#1e2a3a;border-radius:5px;padding:0.5rem 0.8rem;font-size:0.8rem;color:#fcd34d">🔍 需等待：{}</div>'
        '</div>'
    ).format(row[COL["名稱"]], code, row[COL["產業別"]], cyc_html,
             int(row["tech_score"]), int(row["chip_score"]),
             render_tech(row), render_chip(row), f60, f5, gaps)

# ── 主畫面 ──
st.markdown(
    '<div class="gem-header">'
    '<div class="gem-title">GEM 台股篩選器</div>'
    '<div class="gem-subtitle">基本面 × 技術面 × 籌碼面　兩層量化選股框架</div>'
    '</div>', unsafe_allow_html=True)

uploaded = st.file_uploader("上傳 CSV 檔案", type=["csv"], label_visibility="collapsed")

if uploaded is None:
    st.markdown('<div class="info-box">📂 請上傳從選股軟體匯出的 CSV 檔案，系統將自動執行兩層篩選並顯示結果。</div>', unsafe_allow_html=True)
    st.stop()

df_raw = load_df(uploaded)
if df_raw is None:
    st.error("❌ 無法讀取 CSV，請確認檔案格式與編碼")
    st.stop()

COL, missing = resolve_cols(df_raw)
if missing:
    st.warning("⚠️ 以下欄位未找到，相關條件將跳過：" + ", ".join(missing))

l1   = run_layer1(df_raw, COL)
l2   = run_layer2(l1, COL)
dual = l2[l2["dual_pass"]]
near = l2[l2["near_pass"]]

tab1, tab2, tab3, tab4 = st.tabs(["📊 總覽", "📋 第一層結果", "🎯 第二層結果", "📖 評分邏輯"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="metric-card"><div class="metric-label">原始清單</div><div class="metric-value">{}</div></div>'.format(len(df_raw)), unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="metric-card"><div class="metric-label">第一層通過</div><div class="metric-value green">{}</div></div>'.format(len(l1)), unsafe_allow_html=True)
    with c3:
        dc = "green" if len(dual) > 0 else "red"
        st.markdown('<div class="metric-card"><div class="metric-label">第二層雙達標</div><div class="metric-value {}">{}</div></div>'.format(dc, len(dual)), unsafe_allow_html=True)
    with c4:
        nc = "amber" if len(near) > 0 else "red"
        st.markdown('<div class="metric-card"><div class="metric-label">接近門檻</div><div class="metric-value {}">{}</div></div>'.format(nc, len(near)), unsafe_allow_html=True)

    if len(dual) == 0 and len(near) == 0:
        st.markdown('<div class="info-box" style="border-color:#f87171;margin-top:1.5rem">本次清單無任何標的達標或接近門檻，市場可能處於籌碼觀望期，建議持續追蹤。</div>', unsafe_allow_html=True)
    elif len(dual) == 0:
        st.markdown('<div class="info-box" style="border-color:#fbbf24;margin-top:1.5rem">本次無雙達標標的，但有 {} 檔接近門檻，可參考第二層結果追蹤等待條件成熟。</div>'.format(len(near)), unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="section-title">通過基本面篩選　共 {} 檔</div>'.format(len(l1)), unsafe_allow_html=True)
    st.caption("條件：PER > 0 且 ≤ 50 ／ 累月營收年增 > 5億 ／ 近5日均量 > 500張")
    for _, row in l1.iterrows():
        cyc_html = '<span class="warn-badge">⚠️ 景氣循環股</span>' if row["景氣循環"] else ""
        code = str(row[COL["代號"]]).replace('="','').replace('"','')
        st.markdown(
            '<div style="background:#1a1f35;border:1px solid #2a3550;border-radius:8px;'
            'padding:0.8rem 1.2rem;margin-bottom:0.5rem;display:flex;'
            'justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">'
            '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
            '<span style="color:#f0f6ff;font-weight:600;font-size:1rem">{}</span>'
            '<span style="color:#7fa8d0;font-size:0.82rem">{} ｜ {}</span>{}</div>'
            '<div><span style="color:#4ade80;font-weight:700;font-size:1.1rem">+{:.1f} 億</span>'
            '<span style="color:#7fa8d0;font-size:0.8rem;margin-left:12px">PER {:.1f}</span></div>'
            '</div>'.format(row[COL["名稱"]], code, row[COL["產業別"]], cyc_html, row["_rev"], row["_per"]),
            unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="section-title">雙達標　技術 ≥ 2 且 籌碼 ≥ 3　共 {} 檔</div>'.format(len(dual)), unsafe_allow_html=True)
    if len(dual) == 0:
        st.markdown('<div class="info-box">本次無雙達標標的。</div>', unsafe_allow_html=True)
    else:
        for _, row in dual.iterrows():
            st.markdown(build_card_dual(row, COL), unsafe_allow_html=True)

    st.markdown('<div class="section-title">接近門檻　技術或籌碼其中一項達標　共 {} 檔</div>'.format(len(near)), unsafe_allow_html=True)
    if len(near) == 0:
        st.markdown('<div class="info-box">本次無接近門檻標的。</div>', unsafe_allow_html=True)
    else:
        for _, row in near.iterrows():
            st.markdown(build_card_near(row, COL), unsafe_allow_html=True)

with tab4:
    rules = [
        ("第一層","PER","PER > 0 且 ≤ 50","排除虧損股與高估值，放行有合理本益比的成長股"),
        ("第一層","累月營收年增","> 5億","絕對金額門檻，確保篩出具規模的真成長股"),
        ("第一層","近5日均量","> 500張","避免流動性不足造成進出場滑價損失"),
        ("技術","T1 20日乖離","-5% ~ +10%","右側交易、不追高的進場位置設計"),
        ("技術","T2 RSI 12日","50 ~ 70","確認多方控盤但尚未過熱的健康動能區間"),
        ("技術","T3 OSC日線","數值為正且方向↗","確認短期多頭動能持續擴張，非僅反彈"),
        ("籌碼","C1 外資連買","連買 ≥ 2天 → +1","確認外資開始建立基本部位"),
        ("籌碼","C2 三大法人","前5日合計買超 → +1","交叉驗證法人合力站多方"),
        ("籌碼","C3 融資乾淨","60日+5日均減 → +2；擇一 → +1","純粹衡量散戶籌碼退場程度，與外資訊號切割"),
        ("籌碼","C4 券資比","< 3% → +1","空方壓力極小，上檔阻力低"),
        ("警示","景氣循環股","鋼鐵/航運/證券/記憶體控制IC","PER低+營收高可能是景氣頂點，需另行判斷產業週期"),
    ]
    layer_colors = {"第一層":"#3b82f6","技術":"#22c55e","籌碼":"#fbbf24","警示":"#f87171"}
    for layer, name, rule, intent in rules:
        color = layer_colors.get(layer, "#94a3b8")
        st.markdown(
            '<div style="background:#1a1f35;border:1px solid #2a3550;border-radius:8px;'
            'padding:0.8rem 1.2rem;margin-bottom:0.4rem;display:flex;gap:1rem;align-items:flex-start">'
            '<div style="min-width:60px;text-align:center">'
            '<span style="background:{0}22;color:{0};border:1px solid {0}55;border-radius:4px;'
            'padding:2px 8px;font-size:0.72rem;font-weight:700">{1}</span></div>'
            '<div><span style="color:#f0f6ff;font-weight:600;font-size:0.9rem">{2}</span>'
            '<span style="color:#7fa8d0;font-size:0.82rem;margin-left:8px">{3}</span>'
            '<div style="color:#94a3b8;font-size:0.78rem;margin-top:3px">{4}</div></div></div>'.format(
                color, layer, name, rule, intent),
            unsafe_allow_html=True)
    st.markdown('<div class="info-box" style="margin-top:1rem">本版本已移除董監持股條件，原因：董監持股與成長股邏輯相關性弱，且易誤殺外資偏好的分散持股標的。</div>', unsafe_allow_html=True)
