import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import text
from db.connection import get_engine

st.set_page_config(
    page_title="Análises — Observatório de Manaus",
    page_icon="📊",
    layout="wide",
)

PERIOD_DAYS = 30

DOW_MAP = {1: "Dom", 2: "Seg", 3: "Ter", 4: "Qua", 5: "Qui", 6: "Sex", 7: "Sáb"}
DOW_ORDER = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


@st.cache_resource
def get_db():
    return get_engine()


def _start_utc() -> datetime:
    """Retorna o início do período de análise em UTC (dia inteiro, estável para cache)."""
    today_manaus = (datetime.utcnow() - timedelta(hours=4)).date()
    cutoff = today_manaus - timedelta(days=PERIOD_DAYS)
    return datetime(cutoff.year, cutoff.month, cutoff.day, 4, 0, 0)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


@st.cache_data(ttl=1800)
def load_topic_colors() -> dict[str, str]:
    with get_db().connect() as conn:
        rows = conn.execute(text("SELECT name, color FROM topics")).fetchall()
    return {name: color for name, color in rows}


@st.cache_data(ttl=1800)
def load_heatmap(start_utc: datetime) -> pd.DataFrame:
    with get_db().connect() as conn:
        result = conn.execute(text("""
            SELECT
                DAYOFWEEK(published_at - INTERVAL 4 HOUR) AS dow,
                HOUR(published_at - INTERVAL 4 HOUR)      AS hr,
                COUNT(*)                                   AS cnt
            FROM articles
            WHERE published_at >= :start AND is_local = 1
            GROUP BY dow, hr
        """), {"start": start_utc})
        return pd.DataFrame(result.fetchall(), columns=result.keys())


@st.cache_data(ttl=1800)
def load_topic_evolution(start_utc: datetime) -> pd.DataFrame:
    with get_db().connect() as conn:
        result = conn.execute(text("""
            SELECT
                YEARWEEK(a.published_at - INTERVAL 4 HOUR, 1) AS yw,
                MIN(DATE(a.published_at - INTERVAL 4 HOUR))   AS week_start,
                COALESCE(t.name, 'Outros')                    AS topic,
                COUNT(*)                                       AS cnt
            FROM articles a
            LEFT JOIN topics t ON a.topic_id = t.id
            WHERE a.published_at >= :start AND a.is_local = 1
            GROUP BY yw, topic
            ORDER BY yw
        """), {"start": start_utc})
        return pd.DataFrame(result.fetchall(), columns=result.keys())


@st.cache_data(ttl=1800)
def load_source_profile(start_utc: datetime) -> pd.DataFrame:
    with get_db().connect() as conn:
        result = conn.execute(text("""
            SELECT
                s.name                       AS source,
                COALESCE(t.name, 'Outros')   AS topic,
                COUNT(*)                     AS cnt
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            LEFT JOIN topics t ON a.topic_id = t.id
            WHERE a.published_at >= :start AND a.is_local = 1
            GROUP BY s.name, topic
            ORDER BY s.name, topic
        """), {"start": start_utc})
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def build_heatmap_fig(df: pd.DataFrame) -> go.Figure:
    matrix = pd.DataFrame(0, index=list(DOW_MAP.keys()), columns=list(range(24)))
    for _, row in df.iterrows():
        matrix.loc[int(row["dow"]), int(row["hr"])] = int(row["cnt"])
    matrix.index = [DOW_MAP[d] for d in matrix.index]
    matrix = matrix.loc[DOW_ORDER]

    fig = go.Figure(go.Heatmap(
        z=matrix.values,
        x=[f"{h:02d}h" for h in range(24)],
        y=DOW_ORDER,
        colorscale="YlOrRd",
        showscale=True,
        colorbar=dict(title="Notícias"),
        hovertemplate="<b>%{y}</b> às <b>%{x}</b><br>%{z} notícias<extra></extra>",
    ))
    fig.update_layout(
        height=300,
        margin=dict(l=60, r=40, t=10, b=60),
        xaxis_title="Hora do dia (horário de Manaus)",
        plot_bgcolor="#fafafa",
    )
    return fig


def build_evolution_fig(df: pd.DataFrame, colors: dict[str, str]) -> go.Figure:
    df = df.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    topics = df.groupby("topic")["cnt"].sum().sort_values(ascending=False).index.tolist()

    fig = go.Figure()
    for topic in topics:
        color = colors.get(topic, "#95a5a6")
        r, g, b = _hex_to_rgb(color)
        tdf = df[df["topic"] == topic].sort_values("week_start")
        fig.add_trace(go.Scatter(
            x=tdf["week_start"],
            y=tdf["cnt"],
            name=topic,
            mode="lines",
            stackgroup="one",
            fillcolor=f"rgba({r},{g},{b},0.75)",
            line=dict(color=color, width=0.5),
            hovertemplate=f"<b>{topic}</b><br>Semana de %{{x|%d/%m}}: %{{y}}<extra></extra>",
        ))
    fig.update_layout(
        height=400,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=80, b=50),
        plot_bgcolor="#fafafa",
        xaxis_title="",
        yaxis_title="Notícias por semana",
    )
    return fig


def build_profile_fig(df: pd.DataFrame) -> go.Figure | None:
    # Top 15 fontes por volume total no período
    top_sources = (
        df.groupby("source")["cnt"].sum()
        .nlargest(15)
        .index.tolist()
    )
    df = df[df["source"].isin(top_sources)].copy()

    source_totals = df.groupby("source")["cnt"].sum()
    df["pct"] = df.apply(
        lambda r: round(r["cnt"] / source_totals[r["source"]] * 100), axis=1
    )

    pivot = df.pivot_table(index="source", columns="topic", values="pct", fill_value=0)
    pivot = pivot.reindex(top_sources)  # ordem por volume decrescente

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        text=[[f"{v}%" if v > 0 else "" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        colorscale="Blues",
        showscale=True,
        colorbar=dict(title="% da cobertura"),
        hovertemplate="<b>%{y}</b><br>%{x}: %{z}% das notícias<extra></extra>",
    ))
    fig.update_layout(
        height=max(380, len(top_sources) * 36),
        margin=dict(l=180, r=40, t=10, b=110),
        plot_bgcolor="#fafafa",
        xaxis=dict(tickangle=-35),
    )
    return fig


# ── Layout ──────────────────────────────────────────────────────────────────

st.markdown("""
<div style="
    background: linear-gradient(135deg, #1a3a5c 0%, #1e6091 100%);
    border-radius: 14px;
    padding: 22px 32px;
    margin-bottom: 20px;
">
    <div style="font-size: 1.6rem; font-weight: 800; color: #ffffff; margin-bottom: 6px;">
        📊 Análises
    </div>
    <div style="font-size: 0.9rem; color: #bfdbfe;">
        Padrões editoriais e de cobertura — últimos 30 dias · apenas notícias locais (Manaus / AM)
    </div>
</div>
""", unsafe_allow_html=True)

start = _start_utc()

try:
    topic_colors = load_topic_colors()
    df_heatmap = load_heatmap(start)
    df_evolution = load_topic_evolution(start)
    df_profile = load_source_profile(start)
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# ── 1. Heatmap de atividade ──────────────────────────────────────────────────
st.subheader("Ritmo de publicação")
st.caption("Quantidade de notícias publicadas por hora do dia e dia da semana.")

if df_heatmap.empty:
    st.info("Dados insuficientes para este gráfico.")
else:
    st.plotly_chart(build_heatmap_fig(df_heatmap), use_container_width=True)

st.divider()

# ── 2. Evolução dos temas ────────────────────────────────────────────────────
st.subheader("Evolução dos temas")
st.caption("Volume semanal de notícias por tema ao longo do período.")

if df_evolution.empty:
    st.info("Dados insuficientes para este gráfico.")
else:
    st.plotly_chart(build_evolution_fig(df_evolution, topic_colors), use_container_width=True)

st.divider()

# ── 3. Perfil editorial ──────────────────────────────────────────────────────
st.subheader("Perfil editorial das fontes")
st.caption(
    "Distribuição percentual da cobertura por tema em cada portal. "
    "Exibe as 15 fontes com maior volume de notícias locais no período."
)

if df_profile.empty:
    st.info("Dados insuficientes para este gráfico.")
else:
    fig_profile = build_profile_fig(df_profile)
    if fig_profile:
        st.plotly_chart(fig_profile, use_container_width=True)
