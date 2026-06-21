import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from sqlalchemy import text
from db.connection import get_engine

st.set_page_config(
    page_title="Análises — Observatório de Manaus",
    page_icon="📊",
    layout="wide",
)

PERIOD_DAYS = 30
MIN_TREND_RECENTE = 5

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
def load_topic_trend(start_utc: datetime) -> pd.DataFrame:
    mid_utc = start_utc + timedelta(days=15)
    with get_db().connect() as conn:
        result = conn.execute(text("""
            SELECT
                COALESCE(t.name, 'Outros') AS topic,
                SUM(CASE WHEN a.published_at < :mid  THEN 1 ELSE 0 END) AS cnt_ant,
                SUM(CASE WHEN a.published_at >= :mid THEN 1 ELSE 0 END) AS cnt_rec
            FROM articles a
            LEFT JOIN topics t ON a.topic_id = t.id
            WHERE a.published_at >= :start AND a.is_local = 1
            GROUP BY topic
        """), {"start": start_utc, "mid": mid_utc})
        return pd.DataFrame(result.fetchall(), columns=result.keys())


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
def load_topic_adjectives() -> tuple[pd.DataFrame, str | None]:
    """Retorna adjetivos do dia mais recente e a data de computação."""
    with get_db().connect() as conn:
        latest = conn.execute(
            text("SELECT MAX(computed_date) AS d FROM topic_adjectives")
        ).fetchone()
        if not latest or not latest.d:
            return pd.DataFrame(), None
        computed_date = str(latest.d)
        result = conn.execute(text("""
            SELECT t.name AS topic, t.color, ta.word, ta.tfidf_score, ta.frequency
            FROM topic_adjectives ta
            JOIN topics t ON ta.topic_id = t.id
            WHERE ta.computed_date = :d
            ORDER BY t.display_order, ta.tfidf_score DESC
        """), {"d": latest.d})
        return pd.DataFrame(result.fetchall(), columns=result.keys()), computed_date


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
def load_writing_metrics(group_type: str) -> tuple[pd.DataFrame, str | None]:
    """Métricas de escrita (por 'source' ou 'topic') do snapshot mais recente."""
    table = "sources" if group_type == "source" else "topics"
    with get_db().connect() as conn:
        latest = conn.execute(text(
            "SELECT MAX(computed_date) AS d FROM writing_metrics WHERE group_type = :g"
        ), {"g": group_type}).fetchone()
        if not latest or not latest.d:
            return pd.DataFrame(), None
        computed_date = str(latest.d)
        result = conn.execute(text(f"""
            SELECT g.name AS grupo, wm.metric, wm.value, wm.n_articles
            FROM writing_metrics wm
            JOIN {table} g ON wm.group_id = g.id
            WHERE wm.group_type = :g AND wm.computed_date = :d
        """), {"g": group_type, "d": latest.d})
        return pd.DataFrame(result.fetchall(), columns=result.keys()), computed_date


@st.cache_data(ttl=1800)
def load_writing_insight(group_type: str) -> str | None:
    """Texto da análise interpretativa (IA) mais recente para a lente."""
    with get_db().connect() as conn:
        row = conn.execute(text("""
            SELECT text FROM writing_insights
            WHERE group_type = :g
            ORDER BY computed_date DESC, id DESC LIMIT 1
        """), {"g": group_type}).fetchone()
    return row.text if row else None


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


def build_trend_fig(df: pd.DataFrame) -> go.Figure | None:
    rows = []
    for _, row in df.iterrows():
        ant = int(row["cnt_ant"])
        rec = int(row["cnt_rec"])
        if rec < MIN_TREND_RECENTE or ant == 0:
            continue
        delta = (rec - ant) / ant * 100
        rows.append({"topic": row["topic"], "ant": ant, "rec": rec, "delta": delta})

    if not rows:
        return None

    rows.sort(key=lambda x: x["delta"])  # ascendente → maior crescimento no topo

    topics = [r["topic"] for r in rows]
    deltas = [r["delta"] for r in rows]
    ants   = [r["ant"]   for r in rows]
    recs   = [r["rec"]   for r in rows]

    xmax   = max(abs(d) for d in deltas)
    xrange = xmax * 1.5

    def _bar_color(delta: float) -> str:
        t = min(abs(delta) / xmax, 1.0)
        intensity = 0.3 + 0.7 * t
        if delta >= 0:
            r, g, b = _hex_to_rgb("#bfdbfe")
            r2, g2, b2 = _hex_to_rgb("#1e6091")
        else:
            r, g, b = _hex_to_rgb("#fecaca")
            r2, g2, b2 = _hex_to_rgb("#c0392b")
        return "#{:02x}{:02x}{:02x}".format(
            int(r + (r2 - r) * intensity),
            int(g + (g2 - g) * intensity),
            int(b + (b2 - b) * intensity),
        )

    bar_colors  = [_bar_color(d) for d in deltas]
    edge_colors = ["#1e6091" if d >= 0 else "#c0392b" for d in deltas]

    fig = go.Figure(go.Bar(
        x=deltas,
        y=topics,
        orientation="h",
        marker=dict(color=bar_colors, line=dict(color=edge_colors, width=0.8)),
        customdata=list(zip(ants, recs)),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Últimos 15 dias: <b>%{customdata[1]}</b> notícias<br>"
            "15 dias anteriores: <b>%{customdata[0]}</b> notícias<br>"
            "Variação: <b>%{x:.1f}%</b><extra></extra>"
        ),
    ))

    PAD = xmax * 0.04
    annotations = []
    for i, (delta, ant, rec) in enumerate(zip(deltas, ants, recs)):
        sign  = "+" if delta >= 0 else ""
        label = f"{sign}{delta:.0f}%  {ant}→{rec}"
        if delta >= 0:
            annotations.append(dict(
                x=delta + PAD, y=topics[i], text=label, showarrow=False,
                xanchor="left", yanchor="middle",
                font=dict(size=11, color="#1e293b"),
            ))
        else:
            annotations.append(dict(
                x=delta - PAD, y=topics[i], text=label, showarrow=False,
                xanchor="right", yanchor="middle",
                font=dict(size=11, color="#1e293b"),
            ))

    annotations += [
        dict(x=0.02, y=-0.1, xref="paper", yref="paper",
             text="← queda", showarrow=False, xanchor="left",
             font=dict(size=10, color="#c0392b")),
        dict(x=0.98, y=-0.1, xref="paper", yref="paper",
             text="crescimento →", showarrow=False, xanchor="right",
             font=dict(size=10, color="#1e6091")),
    ]

    fig.update_layout(
        height=max(360, len(topics) * 44 + 120),
        plot_bgcolor="#f8fafc",
        paper_bgcolor="#ffffff",
        margin=dict(l=10, r=10, t=10, b=60),
        xaxis=dict(
            range=[-xrange, xrange],
            zeroline=True, zerolinecolor="#94a3b8", zerolinewidth=1.5,
            gridcolor="#e2e8f0", ticksuffix="%",
            tickfont=dict(color="#64748b", size=9),
            title=dict(
                text="Variação em relação aos 15 dias anteriores (%)",
                font=dict(size=10, color="#64748b"),
            ),
        ),
        yaxis=dict(tickfont=dict(size=11, color="#1e293b"), showgrid=False),
        shapes=[
            dict(type="rect", xref="x", yref="paper",
                 x0=-xrange, y0=0, x1=0, y1=1,
                 fillcolor="#fef2f2", opacity=0.5, line_width=0, layer="below"),
            dict(type="rect", xref="x", yref="paper",
                 x0=0, y0=0, x1=xrange, y1=1,
                 fillcolor="#eff6ff", opacity=0.5, line_width=0, layer="below"),
        ],
        annotations=annotations,
        showlegend=False,
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


# (chave no BD, rótulo, unidade/subtítulo, formatação do valor real)
WRITING_METRICS = [
    ("lexical_sophistication", "Sofisticação", "% palavras raras", lambda v: f"{v * 100:.1f}%"),
    ("nominalization_rate",    "Nominalização", "por 100 palavras", lambda v: f"{v:.1f}"),
    ("word_length",            "Comprimento",   "letras/palavra",   lambda v: f"{v:.2f}"),
]


def build_writing_fig(df: pd.DataFrame, top_n: int | None = None) -> go.Figure | None:
    """Pequenos múltiplos de barras divergentes: distância de cada grupo à média do corpus."""
    keys = [m[0] for m in WRITING_METRICS]
    arts = df.groupby("grupo")["n_articles"].max()
    groups = arts.nlargest(top_n).index.tolist() if top_n else list(arts.index)

    pivot = (df[df["grupo"].isin(groups)]
             .pivot_table(index="grupo", columns="metric", values="value")
             .reindex(columns=keys))
    if pivot.dropna(how="all").empty:
        return None

    # Ordena por "elaboração geral" (média das métricas normalizadas); maior no topo do gráfico.
    norm = pivot.copy()
    for k in keys:
        lo, hi = norm[k].min(), norm[k].max()
        norm[k] = (norm[k] - lo) / (hi - lo) if hi > lo else 0.5
    order = norm.mean(axis=1).sort_values().index.tolist()  # asc → topo do plot = maior
    pivot = pivot.reindex(order)
    arts = arts.reindex(order)

    avgs = {k: pivot[k].mean() for k in keys}
    subtitles = [f"{lbl}<br><sub>{sub} · média {fmt(avgs[key])}</sub>"
                 for key, lbl, sub, fmt in WRITING_METRICS]

    fig = make_subplots(rows=1, cols=len(WRITING_METRICS), shared_yaxes=True,
                        subplot_titles=subtitles, horizontal_spacing=0.045)
    for j, (key, label, sub, fmt) in enumerate(WRITING_METRICS, 1):
        dev = pivot[key] - avgs[key]
        colors = ["#2563eb" if d >= 0 else "#f59e0b" for d in dev]
        fig.add_trace(go.Bar(
            y=list(pivot.index), x=dev, orientation="h",
            marker=dict(color=colors),
            text=[fmt(v) for v in pivot[key]], textposition="outside",
            textfont=dict(size=10, color="#334155"),
            customdata=[[fmt(v), int(arts[g])] for g, v in zip(pivot.index, pivot[key])],
            hovertemplate=f"<b>%{{y}}</b><br>{label}: %{{customdata[0]}}<br>%{{customdata[1]}} notícias<extra></extra>",
            cliponaxis=False,
        ), row=1, col=j)
        fig.add_vline(x=0, line=dict(color="#94a3b8", width=1.5), row=1, col=j)
        m = max(abs(dev.min()), abs(dev.max())) * 1.5 or 1
        fig.update_xaxes(range=[-m, m], showticklabels=False, showgrid=False,
                         zeroline=False, row=1, col=j)

    fig.update_yaxes(tickfont=dict(size=11, color="#1e293b"))
    fig.update_annotations(font_size=13)
    fig.update_layout(
        showlegend=False, bargap=0.35,
        height=max(380, len(pivot) * 34 + 130),
        margin=dict(l=160, r=20, t=80, b=20),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig


def build_adj_heatmap_fig(df: pd.DataFrame) -> go.Figure | None:
    if df.empty:
        return None

    # Ordem dos temas conforme display_order (preservada pela query)
    topics_ordered = list(dict.fromkeys(df["topic"].tolist()))
    abbrev = [TOPIC_SHORT.get(t, t) for t in topics_ordered]

    # Top 10 por tema, normalizado por coluna (0–1 dentro de cada tema)
    word_matrix: list[list[str]]   = []
    z_matrix:    list[list[float]] = []
    hover_matrix: list[list[str]]  = []

    for rank in range(10):
        word_row:  list[str]   = []
        z_row:     list[float] = []
        hover_row: list[str]   = []
        for topic in topics_ordered:
            t_df = (
                df[df["topic"] == topic]
                .sort_values("tfidf_score", ascending=False)
                .reset_index(drop=True)
            )
            if rank < len(t_df):
                row    = t_df.iloc[rank]
                scores = t_df["tfidf_score"].tolist()
                s_min, s_max = min(scores), max(scores)
                z_norm = (row["tfidf_score"] - s_min) / (s_max - s_min) if s_max > s_min else 1.0
                word_row.append(row["word"])
                z_row.append(round(z_norm, 4))
                hover_row.append(
                    f"<b>{topic}</b> — {rank + 1}º mais distintivo<br>"
                    f"Adjetivo: <b>{row['word']}</b><br>"
                    f"Ocorrências: <b>{int(row['frequency'])}</b><br>"
                    f"Score TF-IDF: <b>{row['tfidf_score']:.4f}</b>"
                )
            else:
                word_row.append("")
                z_row.append(float("nan"))
                hover_row.append("")
        word_matrix.append(word_row)
        z_matrix.append(z_row)
        hover_matrix.append(hover_row)

    fig = go.Figure(go.Heatmap(
        z=z_matrix,
        x=abbrev,
        y=[f"{i + 1}º" for i in range(10)],
        text=word_matrix,
        customdata=hover_matrix,
        texttemplate="%{text}",
        textfont=dict(size=12, color="white", family="Arial Black, Arial, sans-serif"),
        colorscale=[[0, "#1d4ed8"], [1, "#0f172a"]],
        showscale=False,
        hovertemplate="%{customdata}<extra></extra>",
        xgap=2,
        ygap=2,
    ))

    fig.update_layout(
        height=430,
        margin=dict(l=40, r=20, t=10, b=110),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(
            tickangle=-45,
            tickfont=dict(size=11, color="#1e293b"),
            side="bottom",
        ),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=11, color="#64748b"),
            showgrid=False,
        ),
    )
    return fig


def build_adj_fig(words: pd.DataFrame, color: str) -> go.Figure:
    words = words.sort_values("frequency")  # crescente → mais frequente no topo
    r, g, b = _hex_to_rgb(color)

    fig = go.Figure(go.Bar(
        x=words["frequency"],
        y=words["word"],
        orientation="h",
        marker=dict(
            color=f"rgba({r},{g},{b},0.75)",
            line=dict(color=color, width=0.8),
        ),
        customdata=words[["tfidf_score"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Ocorrências: <b>%{x}</b><br>"
            "Score TF-IDF: <b>%{customdata[0]:.4f}</b><extra></extra>"
        ),
        text=words["frequency"].astype(str) + "×",
        textposition="outside",
        textfont=dict(size=11, color="#1e293b"),
    ))

    fig.update_layout(
        height=380,
        plot_bgcolor="#f8fafc",
        paper_bgcolor="#ffffff",
        margin=dict(l=10, r=60, t=10, b=40),
        xaxis=dict(
            title=dict(text="Ocorrências nos últimos 30 dias", font=dict(size=10, color="#64748b")),
            gridcolor="#e2e8f0",
            tickfont=dict(color="#64748b", size=9),
        ),
        yaxis=dict(tickfont=dict(size=12, color="#1e293b"), showgrid=False),
        showlegend=False,
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
    topic_colors        = load_topic_colors()
    records             = load_records(start)
    df_trend            = load_topic_trend(start)
    df_heatmap          = load_heatmap(start)
    df_evolution        = load_topic_evolution(start)
    df_profile          = load_source_profile(start)
    df_wr_src, wr_src_date = load_writing_metrics("source")
    df_wr_top, wr_top_date = load_writing_metrics("topic")
    wr_src_insight         = load_writing_insight("source")
    df_adj, adj_date    = load_topic_adjectives()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# ── Destaques do período ──────────────────────────────────────────────────────
st.subheader("✨ Destaques do período")
st.markdown(
    "Um retrato rápido dos últimos 30 dias em seis números. "
    "**Dia mais movimentado** e **dia mais calmo** mostram os extremos de volume, "
    "úteis para perceber se houve um fato que disparou a cobertura ou um período de baixa. "
    "**Portal mais ativo** indica qual veículo mais produziu notícias locais no período. "
    "**Hora de pico** revela o horário em que a imprensa mais publica, em média, a cada dia. "
    "**Tema dominante** aponta qual assunto mais pautou a cidade e o quanto ele representou "
    "do total. **Média diária** dá a régua do ritmo normal de produção, ou seja, o número de "
    "notícias locais que, em média, são publicadas por dia. "
    "Todos os valores consideram apenas notícias classificadas como locais (Manaus e Amazonas)."
)
render_records(records)

st.divider()

# ── 1. Tendência dos temas ───────────────────────────────────────────────────
st.subheader("📈 Tendência dos temas")
st.markdown(
    "Compara o volume de notícias por tema nos **últimos 15 dias** com os **15 dias anteriores**. "
    "Barras à direita (azul) indicam crescimento de cobertura; à esquerda (vermelho) indicam queda. "
    "A intensidade da cor é proporcional à magnitude da variação — azul escuro significa forte alta, "
    "vermelho intenso significa forte queda. "
    "Temas com menos de 5 notícias no período recente são omitidos para evitar ruído estatístico. "
    "Passe o cursor sobre as barras para ver os valores exatos."
)

if df_trend.empty:
    st.info("Dados insuficientes para este gráfico.")
else:
    fig_trend = build_trend_fig(df_trend)
    if fig_trend:
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Dados insuficientes para este gráfico.")

st.divider()

# ── 3. Heatmap de atividade ──────────────────────────────────────────────────
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

st.divider()

# ── 4. Métricas de escrita ───────────────────────────────────────────────────
st.subheader("✍️ Métricas de escrita")
st.markdown(
    "Três métricas linguísticas que caracterizam o **estilo do texto** — não *o que* se cobre, "
    "mas *como* se escreve. "
    "**Sofisticação** é a fração de palavras raras ou pouco frequentes na língua. "
    "**Nominalização** conta substantivos derivados de verbos (decisão, investimento, crescimento) por 100 "
    "palavras — indicador de formalidade. "
    "**Comprimento** é o número médio de letras por palavra — palavras mais longas tendem a ser mais formais "
    "ou técnicas. "
    "Cada barra mostra a **distância da média** da imprensa local: **azul** acima da média, **laranja** abaixo. "
    "As medidas consideram apenas **título + resumo** das notícias locais (o estilo da chamada, não do corpo da "
    "matéria), na janela dos **últimos 30 dias**, que é atualizada diariamente. "
    "São uma descrição de **estilo, não de qualidade** — não dizem que um veículo escreve melhor que outro."
)

_WR_EMPTY = ("Dados ainda não disponíveis — as métricas são computadas uma vez ao dia "
             "no ciclo do worker (a cada 30 min). Tente novamente em alguns minutos.")

tab_fonte, tab_tema = st.tabs(["Por fonte", "Por tema"])

with tab_fonte:
    st.caption("Estilo de escrita dos 15 portais com mais notícias locais no período, "
               "ordenados pela elaboração geral do texto (mais elaborado no topo).")
    if df_wr_src.empty:
        st.info(_WR_EMPTY)
    else:
        fig = build_writing_fig(df_wr_src, top_n=15)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        if wr_src_insight:
            st.markdown(
                f"""<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-left:4px solid #2563eb;
                border-radius:8px;padding:14px 18px;margin-top:6px;">
                <div style="font-size:0.72rem;color:#6c757d;text-transform:uppercase;letter-spacing:0.04em;
                margin-bottom:6px;">🤖 Análise gerada por IA</div>
                <div style="font-size:0.95rem;color:#1e293b;line-height:1.6;">{wr_src_insight}</div>
                </div>""",
                unsafe_allow_html=True,
            )
        if wr_src_date:
            st.caption(f"Atualizado em {wr_src_date} · Passe o cursor sobre as barras para ver os valores")

with tab_tema:
    st.caption("Estilo de escrita entre os temas — revela diferenças de registro, por exemplo se Justiça e "
               "Economia usam linguagem mais formal que Esporte ou Cultura.")
    if df_wr_top.empty:
        st.info(_WR_EMPTY)
    else:
        fig = build_writing_fig(df_wr_top)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        if wr_top_date:
            st.caption(f"Atualizado em {wr_top_date} · Passe o cursor sobre as barras para ver os valores")

st.divider()

# ── 5. Adjetivos por tema ────────────────────────────────────────────────────
st.subheader("🔤 Adjetivos mais distintivos por tema")
st.markdown(
    "Os 10 adjetivos que melhor **caracterizam a linguagem** usada pela mídia em cada tema, "
    "calculados pelo método TF-IDF. Palavras que aparecem muito num tema mas pouco nos demais "
    "recebem pontuação alta. As linhas mostram o ranking de 1º a 10º dentro de cada tema; "
    "células mais escuras indicam adjetivos mais distintivos. "
    "Análise atualizada uma vez por dia com base nos últimos 30 dias."
)

if df_adj.empty:
    st.info("Dados ainda não disponíveis — o extrator roda uma vez ao dia no ciclo do worker (a cada 30 min). Tente novamente em alguns minutos.")
else:
    fig_heatmap = build_adj_heatmap_fig(df_adj)
    if fig_heatmap:
        st.plotly_chart(fig_heatmap, use_container_width=True)
    if adj_date:
        st.caption(f"Atualizado em {adj_date} · Passe o cursor sobre as células para ver frequência e score TF-IDF")

    with st.expander("Explorar tema em detalhe"):
        topics_available = df_adj["topic"].unique().tolist()
        selected = st.selectbox("Selecione o tema", topics_available, key="adj_topic")
        df_sel = df_adj[df_adj["topic"] == selected].copy()
        color  = df_sel["color"].iloc[0] if not df_sel.empty else "#1e6091"

        col_chart, col_info = st.columns([3, 1])
        with col_chart:
            st.plotly_chart(build_adj_fig(df_sel, color), use_container_width=True)
        with col_info:
            st.markdown(f"**Tema:** {selected}")
            st.markdown(f"**Atualizado em:** {adj_date}")
            st.markdown("---")
            for _, row in df_sel.sort_values("tfidf_score", ascending=False).iterrows():
                st.markdown(f"· {row['word']} ({row['frequency']}×)")
