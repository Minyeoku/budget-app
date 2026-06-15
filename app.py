# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import date, datetime
from zoneinfo import ZoneInfo

def today_kst():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()

st.set_page_config(page_title="가계부", page_icon="💰", layout="wide")

INCOME_CATS  = ["월급", "부수입", "투자수익", "용돈", "기타수입"]
EXPENSE_CATS = ["식비", "교통", "주거/관리비", "의료/건강", "문화/여가",
                "쇼핑/의류", "통신", "교육", "저축/보험", "술", "기타지출"]

CAT_COLORS = {
    "월급": "#2f9e44", "부수입": "#40c057", "투자수익": "#69db7c",
    "용돈": "#a9e34b", "기타수입": "#c0eb75",
    "식비": "#e03131", "교통": "#f03e3e", "주거/관리비": "#fa5252",
    "의료/건강": "#ff6b6b", "문화/여가": "#ff8787", "쇼핑/의류": "#ffa8a8",
    "통신": "#ffc9c9", "교육": "#e64980", "저축/보험": "#cc5de8",
    "술": "#f76707", "기타지출": "#845ef7",
}

# ── Supabase 클라이언트 ────────────────────────────────────────────
@st.cache_resource
def get_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

# ── DB CRUD ────────────────────────────────────────────────────────
def _empty_df():
    return pd.DataFrame({
        "id": pd.Series(dtype="int64"),
        "날짜": pd.Series(dtype="datetime64[ns]"),
        "유형": pd.Series(dtype="str"),
        "카테고리": pd.Series(dtype="str"),
        "금액": pd.Series(dtype="int64"),
        "메모": pd.Series(dtype="str"),
    })

@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    res = supabase.table("budget").select("*").order("날짜").execute()
    if not res.data:
        return _empty_df()
    df = pd.DataFrame(res.data)
    df["날짜"] = pd.to_datetime(df["날짜"])
    df["금액"] = df["금액"].astype(int)
    return df

def add_row(날짜, 유형, 카테고리, 금액, 메모):
    supabase.table("budget").insert({
        "날짜": str(날짜),
        "유형": 유형,
        "카테고리": 카테고리,
        "금액": int(금액),
        "메모": 메모 or "",
    }).execute()
    st.cache_data.clear()

def delete_row(row_id):
    supabase.table("budget").delete().eq("id", int(row_id)).execute()
    st.cache_data.clear()

def fmt(n):
    return f"₩{int(n):,}"

# ── 타이틀 ─────────────────────────────────────────────────────────
st.title("💰 가계부")

# "Press Enter to submit" 힌트 숨김
st.markdown("""
<style>
[data-testid="InputInstructions"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("✏️ 내역 추가")
    유형 = st.radio("유형", ["수입", "지출"], horizontal=True, key="input_type")
    cats = INCOME_CATS if 유형 == "수입" else EXPENSE_CATS

    with st.form("add_form", clear_on_submit=True):
        d   = st.date_input("날짜", value=today_kst())
        cat = st.selectbox("카테고리", cats)
        amt = st.number_input("금액 (원)", min_value=0, step=1000, format="%d")
        memo = st.text_input("메모", placeholder="간단한 설명")
        submitted = st.form_submit_button("➕ 추가", use_container_width=True)
        if submitted:
            if amt <= 0:
                st.error("금액을 입력하세요.")
            else:
                add_row(d, 유형, cat, amt, memo)
                st.success("추가됐어!")
                st.rerun()

    st.divider()
    st.header("🗓️ 기간 필터")
    df_all = load_data()
    if not df_all.empty:
        min_y = int(df_all["날짜"].dt.year.min())
        max_y = int(df_all["날짜"].dt.year.max())
    else:
        min_y = max_y = date.today().year
    sel_year      = st.selectbox("연도", list(range(max_y, min_y - 1, -1)))
    months        = ["전체"] + [f"{m}월" for m in range(1, 13)]
    sel_month_str = st.selectbox("월", months)
    sel_month     = None if sel_month_str == "전체" else int(sel_month_str.replace("월", ""))

# ── 데이터 필터 ─────────────────────────────────────────────────────
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
period    = f"{sel_year}년 {sel_month_str}"

m1, m2, m3, m4 = st.columns(4)
m1.metric("📅 기간", period)
m2.metric("💚 총 수입", fmt(total_in))
m3.metric("❤️ 총 지출", fmt(total_out))
m4.metric("💼 잔액", fmt(balance), delta=fmt(balance),
          delta_color="normal" if balance >= 0 else "inverse")

st.divider()

# ── 탭 ──────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 월별 추이", "🥧 카테고리 분석", "📋 내역 목록"])

# ── 탭1: 월별 추이 ──────────────────────────────────────────────────
with tab1:
    df_month = (
        df[df["날짜"].dt.year == sel_year]
        .assign(월=lambda x: x["날짜"].dt.month)
        .groupby(["월", "유형"])["금액"].sum()
        .reset_index()
    )

    if df_month.empty:
        st.info("해당 연도 데이터가 없습니다.")
    else:
        all_months = pd.DataFrame(
            [(m, t) for m in range(1, 13) for t in ["수입", "지출"]],
            columns=["월", "유형"],
        )
        df_month_full = all_months.merge(df_month, on=["월", "유형"], how="left").fillna(0)
        df_month_full["월라벨"] = df_month_full["월"].apply(lambda x: f"{x}월")

        fig_bar = px.bar(
            df_month_full, x="월라벨", y="금액", color="유형",
            barmode="group",
            color_discrete_map={"수입": "#2f9e44", "지출": "#e03131"},
            labels={"금액": "금액 (원)", "월라벨": "월"},
            title=f"{sel_year}년 월별 수입/지출",
            height=380, text_auto=True,
        )
        fig_bar.update_traces(
            marker_line_width=0,
            texttemplate="%{y:,.0f}",
            textposition="outside",
            textfont=dict(size=10),
        )
        fig_bar.update_layout(plot_bgcolor="#f8f9fa", yaxis_tickformat=",",
                              legend_title_text="", bargap=0.25)

        month_order = [f"{m}월" for m in range(1, 13)]
        df_balance = (
            df_month_full.groupby("월라벨")
            .apply(lambda g: g.loc[g["유형"]=="수입","금액"].sum()
                           - g.loc[g["유형"]=="지출","금액"].sum())
            .reset_index(name="잔액")
        )
        df_balance["월라벨"] = pd.Categorical(df_balance["월라벨"], categories=month_order, ordered=True)
        df_balance = df_balance.sort_values("월라벨")
        fig_bar.add_trace(go.Scatter(
            x=df_balance["월라벨"], y=df_balance["잔액"],
            mode="lines+markers", name="잔액",
            line=dict(color="#1971c2", width=2, dash="dot"),
            marker=dict(size=7),
        ))
        st.plotly_chart(fig_bar, use_container_width=True)

        df_daily_out = (
            df_view[df_view["유형"] == "지출"]
            .assign(날짜표시=lambda x: x["날짜"].dt.strftime("%Y-%m-%d"))
            .groupby("날짜표시")["금액"].sum()
            .reset_index()
            .sort_values("날짜표시")
        )
        if not df_daily_out.empty:
            fig_daily = px.bar(
                df_daily_out, x="날짜표시", y="금액",
                title=f"{period} 일별 지출",
                labels={"금액": "지출 (원)", "날짜표시": "날짜"},
                color_discrete_sequence=["#e03131"], height=280,
            )
            fig_daily.update_layout(plot_bgcolor="#f8f9fa", yaxis_tickformat=",",
                                    xaxis=dict(tickangle=-30))
            st.plotly_chart(fig_daily, use_container_width=True)

# ── 탭2: 카테고리 분석 ─────────────────────────────────────────────
with tab2:

    def pie_chart(df_sub, title):
        if df_sub.empty:
            fig = go.Figure()
            fig.update_layout(title=title, height=360,
                              annotations=[dict(text="데이터 없음", showarrow=False,
                                                font=dict(size=14, color="#adb5bd"))])
            return fig
        grp = df_sub.groupby("카테고리")["금액"].sum().reset_index()
        grp = grp[grp["금액"] > 0].sort_values("금액", ascending=False)
        fig = px.pie(grp, values="금액", names="카테고리", title=title,
                     height=360, color="카테고리",
                     color_discrete_map=CAT_COLORS, hole=0.38)
        fig.update_traces(textinfo="label+percent", textfont_size=11,
                          pull=[0.03]*len(grp))
        fig.update_layout(showlegend=True,
                          legend=dict(orientation="v", x=1.02, y=0.5))
        return fig

    def cat_table(df_sub):
        if df_sub.empty:
            return
        st.dataframe(
            df_sub.groupby("카테고리")["금액"].sum()
            .sort_values(ascending=False).reset_index()
            .rename(columns={"금액": "금액 (원)"}),
            hide_index=True, use_container_width=True,
        )

    def render_cat_section(df_filtered, label):
        col_in, col_out = st.columns(2)
        df_in  = df_filtered[df_filtered["유형"] == "수입"]
        df_out = df_filtered[df_filtered["유형"] == "지출"]
        with col_in:
            st.plotly_chart(pie_chart(df_in,  f"💚 수입 카테고리 ({label})"),
                            use_container_width=True)
            cat_table(df_in)
        with col_out:
            st.plotly_chart(pie_chart(df_out, f"❤️ 지출 카테고리 ({label})"),
                            use_container_width=True)
            cat_table(df_out)

    # 데이터 있는 월 목록
    df_year = df[df["날짜"].dt.year == sel_year]
    avail_months = sorted(df_year["날짜"].dt.month.unique())

    sub_tabs_labels = [f"{sel_year}년 전체"] + [f"{m}월" for m in avail_months]
    sub_tabs = st.tabs(sub_tabs_labels)

    # 연간 전체 탭
    with sub_tabs[0]:
        render_cat_section(df_year, f"{sel_year}년 전체")

    # 월별 탭
    for i, m in enumerate(avail_months):
        with sub_tabs[i + 1]:
            df_m = df_year[df_year["날짜"].dt.month == m]
            render_cat_section(df_m, f"{sel_year}년 {m}월")

# ── 탭3: 내역 목록 ──────────────────────────────────────────────────
with tab3:
    if df_view.empty:
        st.info("해당 기간에 내역이 없습니다.")
    else:
        show = df_view.copy()
        show["날짜str"] = show["날짜"].dt.strftime("%Y-%m-%d")
        show["금액표시"] = show.apply(
            lambda r: f"+{r['금액']:,}" if r["유형"]=="수입" else f"-{r['금액']:,}", axis=1)

        search = st.text_input("🔍 메모 검색", placeholder="키워드 입력...")
        if search:
            show = show[show["메모"].astype(str).str.contains(search, case=False, na=False)]

        type_filter = st.radio("유형 필터", ["전체", "수입만", "지출만"], horizontal=True)
        if type_filter == "수입만":
            show = show[show["유형"] == "수입"]
        elif type_filter == "지출만":
            show = show[show["유형"] == "지출"]

        st.markdown(f"**{len(show)}건**")

        # 날짜 내림차순 정렬 후 날짜별 그룹핑
        show_sorted = show.sort_values("날짜str", ascending=False)

        for date_str, grp in show_sorted.groupby("날짜str", sort=False):
            # 날짜 헤더 + 해당일 소계
            day_in  = grp[grp["유형"] == "수입"]["금액"].sum()
            day_out = grp[grp["유형"] == "지출"]["금액"].sum()
            badges  = []
            if day_in  > 0: badges.append(f"<span style='color:#2f9e44'>+{day_in:,}</span>")
            if day_out > 0: badges.append(f"<span style='color:#e03131'>-{day_out:,}</span>")
            st.markdown(
                f"**📅 {date_str}** &nbsp;&nbsp; {'&ensp;'.join(badges)}",
                unsafe_allow_html=True,
            )

            for _, row in grp.iterrows():
                color = "#2f9e44" if row["유형"] == "수입" else "#e03131"
                icon  = "💚" if row["유형"] == "수입" else "❤️"
                memo  = row["메모"] if pd.notna(row["메모"]) and row["메모"] else ""
                memo_str = f" &nbsp;·&nbsp; {memo}" if memo else ""

                col_info, col_del = st.columns([14, 1])
                with col_info:
                    st.markdown(
                        f"&nbsp;&nbsp;&nbsp; {icon} {row['카테고리']} &nbsp;"
                        f"<span style='color:{color};font-weight:bold;'>{row['금액표시']}원</span>"
                        f"{memo_str}",
                        unsafe_allow_html=True,
                    )
                with col_del:
                    if st.button("🗑️", key=f"del_{row['id']}", help="삭제"):
                        delete_row(row["id"])
                        st.rerun()

            st.divider()

        csv_bytes = df_view[["날짜","유형","카테고리","금액","메모"]].copy()
        csv_bytes["날짜"] = csv_bytes["날짜"].dt.strftime("%Y-%m-%d")
        st.download_button(
            "📥 CSV 내보내기",
            csv_bytes.to_csv(index=False, encoding="utf-8-sig"),
            file_name=f"가계부_{sel_year}년_{sel_month_str}.csv",
            mime="text/csv",
        )

