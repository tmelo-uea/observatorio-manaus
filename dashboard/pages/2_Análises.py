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


@st.cache_data(ttl=1800)
def load_records(start_utc: datetime) -> dict:
    """Recordes/superlativos do período (apenas notícias locais)."""
    out: dict = {}
    with get_db().connect() as conn:
        row = conn.execute(text("""
            SELECT COUNT(*) AS total,
                   COUNT(DISTINCT DATE(published_at - INTERVAL 4 HOUR)) AS dias
            FROM articles
            WHERE published_at >= :start AND is_local = 1
        """), {"start": start_utc}).fetchone()
        out["total"] = int(row.total or 0)
        out["dias"] = int(row.dias or 0)
        if out["total"] == 0:
            return out

        dias = conn.execute(text("""
            SELECT DATE(published_at - INTERVAL 4 HOUR) AS dia, COUNT(*) AS cnt
            FROM articles
            WHERE published_at >= :start AND is_local = 1
            GROUP BY dia ORDER BY cnt
        """), {"start": start_utc}).fetchall()
        out["dia_calmo"] = (dias[0].dia, int(dias[0].cnt))
        out["dia_movimentado"] = (dias[-1].dia, int(dias[-1].cnt))

        p = conn.execute(text("""
            SELECT s.name AS nome, COUNT(*) AS cnt
            FROM articles a JOIN sources s ON a.source_id = s.id
            WHERE a.published_at >= :start AND a.is_local = 1
            GROUP BY s.name ORDER BY cnt DESC LIMIT 1
        """), {"start": start_utc}).fetchone()
        out["portal"] = (p.nome, int(p.cnt))

        h = conn.execute(text("""
            SELECT HOUR(published_at - INTERVAL 4 HOUR) AS hr, COUNT(*) AS cnt
            FROM articles
            WHERE published_at >= :start AND is_local = 1
            GROUP BY hr ORDER BY cnt DESC LIMIT 1
        """), {"start": start_utc}).fetchone()
        out["hora_pico"] = (int(h.hr), int(h.cnt))

        t = conn.execute(text("""
            SELECT COALESCE(tp.name, 'Outros') AS nome, COUNT(*) AS cnt
            FROM articles a LEFT JOIN topics tp ON a.topic_id = tp.id
            WHERE a.published_at >= :start AND a.is_local = 1
            GROUP BY nome ORDER BY cnt DESC LIMIT 1
        """), {"start": start_utc}).fetchone()
        out["tema"] = (t.nome, int(t.cnt))

    return out


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


TOPIC_SHORT = {
    "Infraestrutura e Mobilidade": "Infraestrutura",
    "Tecnologia e Inovação":       "Tecnologia",
    "Economia e Negócios":         "Economia",
    "Segurança Pública":           "Segurança",
    "Política e Governo":          "Política",
    "Social e Cidadania":          "Social",
    "Cultura e Lazer":             "Cultura",
    "Meio Ambiente":               "Meio Ambiente",
    "Justiça e Direito":           "Justiça",
    "Educação":                    "Educação",
    "Saúde":                       "Saúde",
    "Esporte":                     "Esporte",
    "Outros":                      "Outros",
}


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
    df["topic_short"] = df["topic"].map(lambda t: TOPIC_SHORT.get(t, t))

    pivot = df.pivot_table(index="source", columns="topic_short", values="pct", fill_value=0)
    pivot = pivot.reindex(top_sources)

    row_height = 44
    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        text=[[f"{v}%" if v > 0 else "" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        textfont=dict(size=11),
        colorscale="Blues",
        showscale=True,
        colorbar=dict(title="% cobertura"),
        hovertemplate="<b>%{y}</b><br>%{x}: %{z}%<extra></extra>",
    ))
    fig.update_layout(
        height=max(420, len(top_sources) * row_height + 160),
        margin=dict(l=200, r=60, t=10, b=140),
        plot_bgcolor="#fafafa",
        xaxis=dict(
            tickangle=-90,
            tickfont=dict(size=12),
            side="bottom",
        ),
        yaxis=dict(tickfont=dict(size=12)),
    )
    return fig


_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
          "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _fmt_date(d) -> str:
    return f"{d.day} de {_MESES[d.month - 1]}"


def _num(n) -> str:
    return f"{n:,}".replace(",", ".")


def _noticias(n) -> str:
    return f"{_num(n)} notícia" + ("" if n == 1 else "s")


def render_records(r: dict) -> None:
    if not r or r.get("total", 0) == 0:
        st.info("Dados insuficientes para os destaques do período.")
        return

    media = round(r["total"] / r["dias"]) if r["dias"] else 0
    tema_nome, tema_cnt = r["tema"]
    tema_pct = round(tema_cnt / r["total"] * 100)
    hora_h, hora_cnt = r["hora_pico"]
    hora_media = round(hora_cnt / r["dias"]) if r["dias"] else hora_cnt

    cards = [
        ("📅", "Dia mais movimentado", _fmt_date(r["dia_movimentado"][0]),
         _noticias(r["dia_movimentado"][1])),
        ("🗞️", "Portal mais ativo", r["portal"][0],
         _noticias(r["portal"][1])),
        ("⏰", "Hora de pico", f"{hora_h:02d}h",
         f"média de {hora_media} por dia"),
        ("🏷️", "Tema dominante", tema_nome,
         f"{tema_pct}% das notícias"),
        ("📊", "Média diária", _noticias(media), "por dia"),
        ("🤫", "Dia mais calmo", _fmt_date(r["dia_calmo"][0]),
         _noticias(r["dia_calmo"][1])),
    ]

    html = ('<div style="display:grid;grid-template-columns:repeat(3,1fr);'
            'gap:12px;margin-bottom:8px;">')
    for icon, label, big, sub in cards:
        html += (
            '<div style="background:#f8f9fa;border:1px solid #e5e7eb;'
            'border-radius:10px;padding:16px 18px;">'
            f'<div style="font-size:0.75rem;color:#6c757d;text-transform:uppercase;'
            f'letter-spacing:0.04em;margin-bottom:8px;">{icon}&nbsp; {label}</div>'
            f'<div style="font-size:1.2rem;font-weight:700;color:#1a3a5c;'
            f'line-height:1.25;">{big}</div>'
            f'<div style="font-size:0.85rem;color:#6c757d;margin-top:3px;">{sub}</div>'
            '</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ── Layout ──────────────────────────────────────────────────────────────────

st.markdown("""
<div style="
    background: linear-gradient(135deg, #1a3a5c 0%, #1e6091 100%);
    border-radius: 14px;
    padding: 22px 32px;
    margin-bottom: 20px;
">
    <div style="font-size: 1.6rem; font-weight: 800; color: #ffffff; margin-bottom: 8px;">
        📊 Análises
    </div>
    <div style="font-size: 0.95rem; color: #bfdbfe; line-height: 1.7;">
        Esta página reúne análises automáticas sobre o comportamento da mídia local nos
        <strong style="color:#ffffff;">últimos 30 dias</strong>, considerando apenas notícias
        classificadas como locais (Manaus e Amazonas). Os gráficos são atualizados a cada
        30 minutos junto com a coleta de notícias e revelam padrões editoriais que não são
        visíveis na leitura diária das manchetes.
    </div>
</div>
""", unsafe_allow_html=True)

start = _start_utc()

try:
    topic_colors = load_topic_colors()
    records = load_records(start)
    df_heatmap = load_heatmap(start)
    df_evolution = load_topic_evolution(start)
    df_profile = load_source_profile(start)
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# ── Destaques do período ──────────────────────────────────────────────────────
st.subheader("✨ Destaques do período")
st.markdown(
    "Um retrato rápido dos últimos 30 dias em seis números. "
    "**Dia mais movimentado** e **dia mais calmo** mostram os extremos de volume — "
    "úteis para perceber se houve um fato que disparou a cobertura ou um período de baixa. "
    "**Portal mais ativo** indica qual veículo mais produziu notícias locais no período. "
    "**Hora de pico** revela o horário em que a imprensa mais publica, em média, a cada dia. "
    "**Tema dominante** aponta qual assunto mais pautou a cidade e o quanto ele representou "
    "do total. **Média diária** dá a régua do ritmo normal de produção — o número de "
    "notícias locais que, em média, são publicadas por dia. "
    "Todos os valores consideram apenas notícias classificadas como locais (Manaus e Amazonas)."
)
render_records(records)

st.divider()

# ── 1. Heatmap de atividade ──────────────────────────────────────────────────
st.subheader("⏰ Ritmo de publicação")
st.markdown(
    "O gráfico abaixo mostra **quando** a mídia local publica notícias ao longo da semana. "
    "Cada célula indica o total de notícias publicadas naquele cruzamento de hora e dia. "
    "Cores mais escuras (vermelho intenso) indicam os horários de maior atividade; "
    "cores claras (amarelo) indicam períodos de baixo volume. "
    "Use este gráfico para entender o ciclo de produção jornalística local: "
    "quais dias concentram mais publicações, se há silêncio nos fins de semana "
    "e em que horas os portais costumam lançar suas principais reportagens."
)

if df_heatmap.empty:
    st.info("Dados insuficientes para este gráfico.")
else:
    st.plotly_chart(build_heatmap_fig(df_heatmap), use_container_width=True)

st.divider()

# ── 2. Evolução dos temas ────────────────────────────────────────────────────
st.subheader("📈 Evolução dos temas")
st.markdown(
    "O gráfico de área empilhada abaixo mostra como o **volume de notícias por tema** "
    "variou semana a semana ao longo dos últimos 30 dias. "
    "A altura total da área em cada semana representa o volume geral de notícias coletadas; "
    "a fatia de cada cor indica a contribuição de cada tema naquela semana. "
    "Picos em um tema específico podem indicar eventos relevantes — como uma crise de saúde "
    "pública, operações policiais ou grandes eventos culturais. "
    "Passe o cursor sobre o gráfico para ver os valores exatos por tema e semana."
)

if df_evolution.empty:
    st.info("Dados insuficientes para este gráfico.")
else:
    st.plotly_chart(build_evolution_fig(df_evolution, topic_colors), use_container_width=True)

st.divider()

# ── 3. Perfil editorial ──────────────────────────────────────────────────────
st.subheader("🗞️ Perfil editorial das fontes")
st.markdown(
    "O mapa de calor abaixo revela a **linha editorial de cada portal**: "
    "qual parcela da sua cobertura é dedicada a cada tema. "
    "Cada linha representa um portal (os 15 com maior volume de notícias locais no período) "
    "e cada coluna representa um tema. O valor em cada célula é o percentual "
    "daquele tema na cobertura total daquele portal — a soma das células de cada linha é 100%. "
    "Células mais escuras indicam especialização: um portal com 30% ou mais em Segurança, "
    "por exemplo, tem perfil policial predominante. "
    "Portais com distribuição uniforme entre temas têm cobertura generalista. "
    "Esta análise permite identificar quais vozes cobrem cada área temática da cidade "
    "e detectar lacunas — temas que nenhum portal cobre com profundidade."
)

if df_profile.empty:
    st.info("Dados insuficientes para este gráfico.")
else:
    fig_profile = build_profile_fig(df_profile)
    if fig_profile:
        st.plotly_chart(fig_profile, use_container_width=True)
