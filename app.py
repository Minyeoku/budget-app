# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import date, datetime

st.set_page_config(page_title="가계부", page_icon="💰", layout="wide")

DATA_FILE = os.path.join(os.path.dirname(__file__), "budget_data.csv")

INCOME_CATS  = ["월급", "부수입", "투자수익", "용돈", "기타수입"]
EXPENSE_CATS = ["식비", "교통", "주거/관리비", "의료/건강", "문화/여가",
                "쇼핑/의류", "통신", "교육", "저축/보험", "기타지출"]

CAT_COLORS = {
    "월급": "#2f9e44", "부수입": "#40c057", "투자수익": "#69db7c",
    "용돈": "#a9e34b", "기타수입": "#c0eb75",
    "식비": "#e03131", "교통": "#f03e3e", "주거/관리비": "#fa5252",
    "의료/건강": "#ff6b6b", "문화/여가": "#ff8787", "쇼핑/의류": "#ffa8a8",
    "통신": "#ffc9c9", "교육": "#e64980", "저축/보험": "#cc5de8",
    "기타지출": "#845ef7",
}

EMPTY_DF = pd.DataFrame(columns=["날짜", "유형", "카테고리", "금액", "메모"])

# ── 데이터: session_state 기반 (Streamlit Cloud 호환) + 로컬 CSV 병행 ──
def _init_state():
    if "budget_df" not in st.session_state:
        if os.path.exists(DATA_FILE):
            df = pd.read_csv(DATA_FILE, parse_dates=["날짜"])
            df["날짜"] = pd.to_datetime(df["날짜"])
            df["금액"] = pd.to_numeric(df["금액"], errors="coerce").fillna(0).astype(int)
        else:
            df = EMPTY_DF.copy()
        st.session_state.budget_df = df

_init_state()

def load_data() -> pd.DataFrame:
    return st.session_state.budget_df.copy()

def save_data(df: pd.DataFrame):
    st.session_state.budget_df = df.reset_index(drop=True)
    try:
        df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
    except Exception:
        pass  # Streamlit Cloud read-only 환경 대응

def add_row(날짜, 유형, 카테고리, 금액, 메모):
    df = load_data()
    new_row = pd.DataFrame([{"날짜": pd.Timestamp(날짜), "유형": 유형,
                              "카테고리": 카테고리, "금액": int(금액), "메모": 메모}])
    df = pd.concat([df, new_row], ignore_index=True).sort_values("날짜")
    save_data(df)

def delete_row(idx):
    df = load_data()
    df = df.drop(index=idx)
    save_data(df)

def upload_csv(uploaded_file):
    df = pd.read_csv(uploaded_file, parse_dates=["날짜"])
    df["날짜"] = pd.to_datetime(df["날짜"])
    df["금액"] = pd.to_numeric(df["금액"], errors="coerce").fillna(0).astype(int)
    save_data(df)

def fmt(n):
    return f"₩{int(n):,}"

# ── 상태 초기화 ─────────────────────────────────────────────────────
if "show_form" not in st.session_state:
    st.session_state.show_form = False

# ── 타이틀 ─────────────────────────────────────────────────────────
st.title("💰 가계부")

# ── 사이드바: 입력 폼 ───────────────────────────────────────────────
with st.sidebar:
    st.header("✏️ 내역 추가")
    # 유형은 폼 밖에서 선택 → 변경 즉시 카테고리 갱신
    유형 = st.radio("유형", ["수입", "지출"], horizontal=True, key="input_type")
    cats = INCOME_CATS if 유형 == "수입" else EXPENSE_CATS

    with st.form("add_form", clear_on_submit=True):
        d = st.date_input("날짜", value=date.today())
        cat = st.selectbox("카테고리", cats)
        amt = st.number_input("금액 (원)", min_value=0, step=1000, format="%d")
        memo = st.text_input("메모", placeholder="간단한 설명")
        submitted = st.form_submit_button("➕ 추가", use_container_width=True)
        if submitted:
            if amt <= 0:
                st.error("금액을 입력하세요.")
            else:
                add_row(d, 유형, cat, amt, memo)
                st.success("추가됐습니다!")
                st.rerun()

    st.divider()
    st.header("📂 데이터 가져오기")
    up = st.file_uploader("CSV 업로드 (기존 데이터 복원)", type=["csv"], label_visibility="collapsed")
    if up:
        upload_csv(up)
        st.success("데이터 불러왔어!")
        st.rerun()

    st.divider()
    st.header("🗓️ 기간 필터")
    df_all = load_data()
    if not df_all.empty:
        min_y = int(df_all["날짜"].dt.year.min())
        max_y = int(df_all["날짜"].dt.year.max())
    else:
        min_y = max_y = date.today().year
    sel_year = st.selectbox("연도", list(range(max_y, min_y - 1, -1)))
    months = ["전체"] + [f"{m}월" for m in range(1, 13)]
    sel_month_str = st.selectbox("월", months)
    sel_month = None if sel_month_str == "전체" else int(sel_month_str.replace("월", ""))

# ── 데이터 로드 및 필터 ──────────────────────────────────────────────
df = load_data()

if df.empty:
    st.info("왼쪽 사이드바에서 첫 번째 내역을 추가해보세요! 📝")
    st.stop()

mask = df["날짜"].dt.year == sel_year
if sel_month:
    mask &= df["날짜"].dt.month == sel_month
df_view = df[mask].copy()

# ── 요약 메트릭 ─────────────────────────────────────────────────────
total_in  = df_view[df_view["유형"] == "수입"]["금액"].sum()
total_out = df_view[df_view["유형"] == "지출"]["금액"].sum()
balance   = total_in - total_out

m1, m2, m3, m4 = st.columns(4)
period = f"{sel_year}년 {sel_month_str}"
m1.metric("📅 기간", period)
m2.metric("💚 총 수입", fmt(total_in))
m3.metric("❤️ 총 지출", fmt(total_out))
delta_color = "normal" if balance >= 0 else "inverse"
m4.metric("💼 잔액", fmt(balance), delta=fmt(balance), delta_color=delta_color)

st.divider()

# ── 차트 영역 ───────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 월별 추이", "🥧 카테고리 분석", "📋 내역 목록"])

# ── 탭1: 월별 추이 ──────────────────────────────────────────────────
with tab1:
    df_month = (
        df[df["날짜"].dt.year == sel_year]
        .assign(월=df["날짜"].dt.month)
        .groupby(["월", "유형"])["금액"].sum()
        .reset_index()
    )

    if df_month.empty:
        st.info("해당 연도 데이터가 없습니다.")
    else:
        # 12개월 전체 틀 만들기
        all_months = pd.DataFrame(
            [(m, t) for m in range(1, 13) for t in ["수입", "지출"]],
            columns=["월", "유형"],
        )
        df_month_full = all_months.merge(df_month, on=["월", "유형"], how="left").fillna(0)
        df_month_full["월라벨"] = df_month_full["월"].apply(lambda x: f"{x}월")

        fig_bar = px.bar(
            df_month_full,
            x="월라벨", y="금액", color="유형",
            barmode="group",
            color_discrete_map={"수입": "#2f9e44", "지출": "#e03131"},
            labels={"금액": "금액 (원)", "월라벨": "월"},
            title=f"{sel_year}년 월별 수입/지출",
            height=380,
            text_auto=True,
        )
        fig_bar.update_traces(
            marker_line_width=0,
            texttemplate="%{y:,.0f}",
            textposition="outside",
            textfont=dict(size=10),
        )
        fig_bar.update_layout(
            plot_bgcolor="#f8f9fa",
            yaxis_tickformat=",",
            legend_title_text="",
            bargap=0.25,
        )

        # 잔액 라인 오버레이
        df_balance = (
            df_month_full.groupby("월라벨")
            .apply(lambda g: g.loc[g["유형"] == "수입", "금액"].sum()
                           - g.loc[g["유형"] == "지출", "금액"].sum())
            .reset_index(name="잔액")
        )
        # 월라벨 정렬 (1월~12월)
        month_order = [f"{m}월" for m in range(1, 13)]
        df_balance["월라벨"] = pd.Categorical(df_balance["월라벨"], categories=month_order, ordered=True)
        df_balance = df_balance.sort_values("월라벨")

        fig_bar.add_trace(
            go.Scatter(
                x=df_balance["월라벨"],
                y=df_balance["잔액"],
                mode="lines+markers",
                name="잔액",
                line=dict(color="#1971c2", width=2, dash="dot"),
                marker=dict(size=7),
            )
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # 누적 잔액 추이 (연간)
        df_sorted = (
            df[df["날짜"].dt.year == sel_year]
            .sort_values("날짜")
            .copy()
        )
        df_sorted["부호금액"] = df_sorted.apply(
            lambda r: r["금액"] if r["유형"] == "수입" else -r["금액"], axis=1
        )
        df_sorted["누적잔액"] = df_sorted["부호금액"].cumsum()
        df_sorted["날짜표시"] = df_sorted["날짜"].dt.strftime("%Y-%m-%d")

        fig_cum = px.scatter(
            df_sorted, x="날짜표시", y="누적잔액",
            title=f"{sel_year}년 누적 잔액 추이",
            labels={"누적잔액": "누적 잔액 (원)", "날짜표시": "날짜"},
            color_discrete_sequence=["#1971c2"],
            height=280,
        )
        fig_cum.update_traces(
            mode="lines+markers",
            marker=dict(size=8, line=dict(width=1.5, color="white")),
            line=dict(width=2),
        )
        fig_cum.update_layout(
            plot_bgcolor="#f8f9fa",
            yaxis_tickformat=",",
            xaxis=dict(tickangle=-30, nticks=12),
        )
        st.plotly_chart(fig_cum, use_container_width=True)

# ── 탭2: 카테고리 분석 ─────────────────────────────────────────────
with tab2:
    col_in, col_out = st.columns(2)

    def pie_chart(df_sub, title, color_map):
        if df_sub.empty:
            return go.Figure().update_layout(title=title, height=380)
        grp = df_sub.groupby("카테고리")["금액"].sum().reset_index()
        grp = grp[grp["금액"] > 0].sort_values("금액", ascending=False)
        colors = [color_map.get(c, "#adb5bd") for c in grp["카테고리"]]
        fig = px.pie(
            grp, values="금액", names="카테고리",
            title=title, height=380,
            color="카테고리",
            color_discrete_map=color_map,
            hole=0.35,
        )
        fig.update_traces(
            textinfo="label+percent",
            textfont_size=12,
            pull=[0.03] * len(grp),
        )
        fig.update_layout(showlegend=False)
        return fig

    df_in_view  = df_view[df_view["유형"] == "수입"]
    df_out_view = df_view[df_view["유형"] == "지출"]

    with col_in:
        st.plotly_chart(
            pie_chart(df_in_view, f"💚 수입 카테고리 ({period})", CAT_COLORS),
            use_container_width=True,
        )
        if not df_in_view.empty:
            grp_in = df_in_view.groupby("카테고리")["금액"].sum().sort_values(ascending=False)
            st.dataframe(
                grp_in.reset_index().rename(columns={"금액": "금액 (원)"}),
                hide_index=True, use_container_width=True,
            )

    with col_out:
        st.plotly_chart(
            pie_chart(df_out_view, f"❤️ 지출 카테고리 ({period})", CAT_COLORS),
            use_container_width=True,
        )
        if not df_out_view.empty:
            grp_out = df_out_view.groupby("카테고리")["금액"].sum().sort_values(ascending=False)
            st.dataframe(
                grp_out.reset_index().rename(columns={"금액": "금액 (원)"}),
                hide_index=True, use_container_width=True,
            )

# ── 탭3: 내역 목록 ──────────────────────────────────────────────────
with tab3:
    if df_view.empty:
        st.info("해당 기간에 내역이 없습니다.")
    else:
        # 표시용 컬럼 정리
        show = df_view.copy()
        show["날짜"] = show["날짜"].dt.strftime("%Y-%m-%d")
        show["금액표시"] = show.apply(
            lambda r: f"+{r['금액']:,}" if r["유형"] == "수입" else f"-{r['금액']:,}", axis=1
        )

        # 검색 필터
        search = st.text_input("🔍 메모 검색", placeholder="키워드 입력...")
        if search:
            show = show[show["메모"].astype(str).str.contains(search, case=False, na=False)]

        # 유형 필터
        type_filter = st.radio("유형 필터", ["전체", "수입만", "지출만"], horizontal=True)
        if type_filter == "수입만":
            show = show[show["유형"] == "수입"]
        elif type_filter == "지출만":
            show = show[show["유형"] == "지출"]

        st.markdown(f"**{len(show)}건**")

        for orig_idx, row in show.sort_values("날짜", ascending=False).iterrows():
            color = "#2f9e44" if row["유형"] == "수입" else "#e03131"
            icon  = "💚" if row["유형"] == "수입" else "❤️"
            c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 3, 1])
            c1.markdown(f"**{row['날짜']}**")
            c2.markdown(f"{icon} {row['카테고리']}")
            c3.markdown(f"<span style='color:{color};font-weight:bold;'>{row['금액표시']}</span>",
                        unsafe_allow_html=True)
            c4.markdown(row["메모"] if pd.notna(row["메모"]) and row["메모"] else "—")
            if c5.button("🗑️", key=f"del_{orig_idx}", help="삭제"):
                delete_row(orig_idx)
                st.rerun()

        st.divider()
        # CSV 다운로드
        csv_bytes = df_view.copy()
        csv_bytes["날짜"] = csv_bytes["날짜"].dt.strftime("%Y-%m-%d")
        st.download_button(
            "📥 CSV 내보내기",
            csv_bytes.to_csv(index=False, encoding="utf-8-sig"),
            file_name=f"가계부_{sel_year}년_{sel_month_str}.csv",
            mime="text/csv",
        )
