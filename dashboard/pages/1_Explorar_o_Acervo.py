import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime, timedelta
from sqlalchemy import text
from db.connection import get_engine
from dashboard.components.word_cloud import render_word_cloud


def manaus_today() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date()


st.set_page_config(
    page_title="Explorar o Acervo — Observatório de Manaus",
    page_icon="🔎",
    layout="wide",
)

_TYPE_LABELS = {"portal": "Portal", "blog": "Blog", "youtube": "YouTube", "orgao_publico": "Órgão público"}
_TYPE_COLORS = {"Portal": "#2980b9", "Blog": "#e67e22", "YouTube": "#e74c3c", "Órgão público": "#27ae60"}
_MESES_ABR = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
              7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}

PAGE_SIZE = 20
_FILTER_KEYS = ["f_periodo", "f_range", "f_tema", "f_fonte", "f_tipo", "f_busca", "f_show_all"]


def fmt_br(n: int) -> str:
    return f"{n:,}".replace(",", ".")


@st.cache_resource
def get_db():
    return get_engine()


@st.cache_data(ttl=3600)
def load_date_bounds():
    with get_db().connect() as conn:
        min_utc = conn.execute(text("SELECT MIN(published_at) FROM articles WHERE published_at IS NOT NULL")).scalar()
    today = manaus_today()
    date_min = (pd.Timestamp(min_utc) - pd.Timedelta(hours=4)).date() if min_utc else today
    return date_min, today


@st.cache_data(ttl=3600)
def load_topics():
    with get_db().connect() as conn:
        return pd.read_sql(text("SELECT id, name, slug, color, display_order FROM topics ORDER BY display_order"), conn)


@st.cache_data(ttl=3600)
def load_source_names():
    with get_db().connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT name FROM sources WHERE active = 1 ORDER BY name"))]


@st.cache_data(ttl=3600)
def load_source_types():
    with get_db().connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT DISTINCT type FROM sources WHERE active = 1 ORDER BY type"))]


@st.cache_data(ttl=300)
def load_articles(date_start, date_end):
    engine = get_db()
    start_utc = datetime(date_start.year, date_start.month, date_start.day, 4, 0, 0)
    end_utc = datetime(date_end.year, date_end.month, date_end.day, 4, 0, 0) + timedelta(days=1)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                a.id, a.title, a.url,
                LEFT(a.summary, 500) AS summary,
                a.published_at, a.is_local,
                s.name AS source, s.type AS source_type,
                t.name AS topic, t.color AS topic_color
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            LEFT JOIN topics t ON a.topic_id = t.id
            WHERE a.published_at >= :start AND a.published_at < :end
            ORDER BY a.published_at DESC
            LIMIT 5000
        """), {"start": start_utc, "end": end_utc})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    if not df.empty:
        df["published_at"] = pd.to_datetime(df["published_at"])
        df["published_at_manaus"] = df["published_at"] - pd.Timedelta(hours=4)
    return df


@st.cache_data(ttl=300)
def load_daily_counts(date_start, date_end, show_all, topic, source, source_type):
    """Agregação por dia sem LIMIT — contagem exata para gráfico e métricas."""
    engine = get_db()
    start_utc = datetime(date_start.year, date_start.month, date_start.day, 4, 0, 0)
    end_utc = datetime(date_end.year, date_end.month, date_end.day, 4, 0, 0) + timedelta(days=1)

    filters = ["a.published_at >= :start", "a.published_at < :end"]
    params = {"start": start_utc, "end": end_utc}

    if not show_all:
        filters.append("a.is_local = 1")
    if topic:
        filters.append("t.name = :topic")
        params["topic"] = topic
    if source:
        filters.append("s.name = :source")
        params["source"] = source
    if source_type:
        filters.append("s.type = :stype")
        params["stype"] = source_type

    where = " AND ".join(filters)
    sql = f"""
        SELECT
            DATE(a.published_at - INTERVAL 4 HOUR) AS day,
            s.type AS source_type,
            COUNT(*) AS cnt
        FROM articles a
        JOIN sources s ON a.source_id = s.id
        LEFT JOIN topics t ON a.topic_id = t.id
        WHERE {where}
        GROUP BY DATE(a.published_at - INTERVAL 4 HOUR), s.type
        ORDER BY day
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    if not df.empty:
        df["day"] = pd.to_datetime(df["day"])
    return df


st.title("🔎 Explorar o acervo")
st.caption(
    "Pesquise as notícias já coletadas pelo Observatório por período, tema, "
    "portal ou palavra-chave. Os gráficos e a lista abaixo refletem os filtros aplicados."
)

try:
    topics_df = load_topics()
    date_min, date_max = load_date_bounds()
    source_names = load_source_names()
    source_types = load_source_types()
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados: {e}")
    st.stop()

_type_display = [_TYPE_LABELS.get(t, t) for t in source_types]
_type_reverse = {_TYPE_LABELS.get(t, t): t for t in source_types}
_default_start = manaus_today() - timedelta(days=6)

# --- Filtros ---
with st.form("filtros"):
    c_per, c_range = st.columns([3, 2])
    with c_per:
        periodo = st.radio(
            "Período",
            ["Hoje", "Últimos 7 dias", "Últimos 30 dias", "Personalizado"],
            index=1, horizontal=True, key="f_periodo",
        )
    with c_range:
        custom_range = st.date_input(
            "Intervalo (para período personalizado)",
            value=(_default_start, date_max),
            min_value=min(date_min, _default_start), max_value=date_max,
            key="f_range",
        )
    c_tema, c_fonte, c_tipo = st.columns(3)
    tema = c_tema.selectbox("Tema", ["Todos"] + topics_df["name"].tolist(), key="f_tema")
    fonte = c_fonte.selectbox("Fonte", ["Todas"] + source_names, key="f_fonte")
    tipo = c_tipo.selectbox("Tipo de fonte", ["Todos"] + _type_display, key="f_tipo")
    c_busca, c_local = st.columns([3, 1])
    busca = c_busca.text_input("Palavra-chave", key="f_busca", placeholder="ex.: enchente, concurso, BR-319...")
    show_all = c_local.checkbox("Incluir notícias não locais", key="f_show_all")
    aplicar = st.form_submit_button("Aplicar filtros", type="primary", use_container_width=True)

if aplicar:
    st.session_state.explorar_pages = 1

# --- Resolve o período efetivo ---
_today = manaus_today()
if periodo == "Hoje":
    d_start, d_end = _today, _today
elif periodo == "Últimos 7 dias":
    d_start, d_end = _today - timedelta(days=6), _today
elif periodo == "Últimos 30 dias":
    d_start, d_end = _today - timedelta(days=29), _today
else:
    d_start = custom_range[0] if len(custom_range) >= 1 else _default_start
    d_end = custom_range[1] if len(custom_range) == 2 else date_max

_sel_topic = tema if tema != "Todos" else None
_sel_source = fonte if fonte != "Todas" else None
_sel_type = _type_reverse.get(tipo) if tipo != "Todos" else None

# --- Carrega dados ---
try:
    df = load_articles(d_start, d_end)
    daily_raw = load_daily_counts(d_start, d_end, show_all, _sel_topic, _sel_source, _sel_type)
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados: {e}")
    st.stop()

filtered = df.copy()
if not filtered.empty:
    if _sel_topic:
        filtered = filtered[filtered["topic"] == _sel_topic]
    if _sel_source:
        filtered = filtered[filtered["source"] == _sel_source]
    if _sel_type:
        filtered = filtered[filtered["source_type"] == _sel_type]
    if not show_all:
        filtered = filtered[filtered["is_local"] == True]
    if busca:
        mask = (
            filtered["title"].str.contains(busca, case=False, na=False) |
            filtered["summary"].str.contains(busca, case=False, na=False)
        )
        filtered = filtered[mask]

# Contagem exata (sem LIMIT); com busca por palavra-chave, usa a contagem do
# conjunto carregado (a busca é aplicada em memória)
n_found = len(filtered) if busca else (int(daily_raw["cnt"].sum()) if not daily_raw.empty else 0)

# --- Estado do filtro aplicado ---
if periodo == "Personalizado":
    periodo_label = f"{d_start.strftime('%d/%m/%Y')} a {d_end.strftime('%d/%m/%Y')}"
else:
    periodo_label = periodo
_state_parts = [periodo_label, tema if tema != "Todos" else "Todos os temas",
                fonte if fonte != "Todas" else "Todas as fontes"]
if tipo != "Todos":
    _state_parts.append(tipo)
if busca:
    _state_parts.append(f"“{busca}”")
_state_str = " · ".join(_state_parts)

c_state, c_clear = st.columns([5, 1])
with c_state:
    st.markdown(
        f"<div style='padding:10px 14px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;'>"
        f"<strong style='color:#1e40af;'>{fmt_br(n_found)} notícia{'s' if n_found != 1 else ''} encontrada{'s' if n_found != 1 else ''}</strong>"
        f"<span style='color:#64748b;font-size:0.88rem;'> — {_state_str}</span></div>",
        unsafe_allow_html=True,
    )
with c_clear:
    if st.button("Limpar filtros", use_container_width=True):
        for k in _FILTER_KEYS:
            st.session_state.pop(k, None)
        st.session_state.explorar_pages = 1
        st.rerun()

if filtered.empty:
    st.warning("Nenhuma notícia encontrada com os filtros atuais. Tente ampliar o período ou remover algum filtro.")
    st.stop()

# --- Métricas do resultado ---
st.write("")
m1, m2 = st.columns(2)
m1.metric("Portais nos resultados", filtered["source"].nunique())
m2.metric("Temas nos resultados", filtered["topic"].nunique())
if len(df) == 5000:
    st.caption("⚠️ Período com muitas notícias — listas e distribuições consideram as 5.000 mais recentes.")

st.divider()

# --- Volume por dia ---
st.subheader("Volume de notícias por dia")
daily = daily_raw.copy()
if not daily.empty:
    daily["tipo"] = daily["source_type"].map(_TYPE_LABELS).fillna("Outros")
    daily = daily.groupby(["day", "tipo"])["cnt"].sum().reset_index(name="count")
    _all_days = pd.date_range(d_start, d_end, freq="D")
    _tickvals = list(_all_days)
    _ticktext = [f"{d.day} {_MESES_ABR[d.month]}" for d in _all_days]
    if _ticktext:
        _ticktext[0] = f"{_all_days[0].day} {_MESES_ABR[_all_days[0].month]}\n{_all_days[0].year}"
    fig_timeline = px.bar(
        daily, x="day", y="count", color="tipo",
        labels={"day": "Data", "count": "Notícias", "tipo": "Tipo"},
        color_discrete_map=_TYPE_COLORS,
        category_orders={"tipo": ["Portal", "Blog", "YouTube", "Órgão público"]},
    )
    fig_timeline.update_xaxes(
        tickvals=_tickvals, ticktext=_ticktext,
        range=[_all_days[0] - pd.Timedelta(hours=12), _all_days[-1] + pd.Timedelta(hours=12)],
    )
    fig_timeline.update_layout(
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, title_text=""),
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

# --- Distribuições ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Distribuição por tema")
    if filtered["topic"].notna().any():
        topic_counts = filtered["topic"].value_counts().reset_index()
        topic_counts.columns = ["Tema", "Quantidade"]
        color_map = dict(zip(topics_df["name"], topics_df["color"]))
        fig_topics = px.bar(
            topic_counts, x="Quantidade", y="Tema", orientation="h",
            color="Tema", color_discrete_map=color_map,
        )
        fig_topics.update_layout(showlegend=False, yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig_topics, use_container_width=True)
    else:
        st.info("Classificação de temas em andamento.")

with col_right:
    st.subheader("Notícias por fonte")
    source_counts = filtered["source"].value_counts().reset_index()
    source_counts.columns = ["Fonte", "Quantidade"]
    top_sources = source_counts.head(20)
    fig_sources = px.bar(
        top_sources, x="Quantidade", y="Fonte", orientation="h",
        labels={"Quantidade": "Notícias", "Fonte": ""},
        color="Quantidade",
        color_continuous_scale="Blues",
        text="Quantidade",
    )
    fig_sources.update_traces(textposition="outside")
    fig_sources.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        yaxis=dict(categoryorder="total ascending"),
        height=520,
        margin=dict(l=0, r=40, t=10, b=10),
    )
    if len(source_counts) > 20:
        st.caption(f"Top 20 de {len(source_counts)} fontes")
    st.plotly_chart(fig_sources, use_container_width=True)

# --- Nuvem de palavras ---
st.subheader("Nuvem de palavras")
render_word_cloud(filtered)

st.divider()

# --- Notícias correspondentes ---
st.subheader("Notícias correspondentes")

if "explorar_pages" not in st.session_state:
    st.session_state.explorar_pages = 1

limit = st.session_state.explorar_pages * PAGE_SIZE
for _, row in filtered.head(limit).iterrows():
    date_str = row["published_at_manaus"].strftime("%d/%m/%Y %H:%M") if pd.notna(row["published_at"]) else "—"
    if pd.notna(row["topic"]):
        _color = row["topic_color"] or "#64748b"
        topic_badge = (
            f"<span style='background:{_color}22;color:{_color};font-size:0.72rem;"
            f"padding:2px 8px;border-radius:10px;font-weight:600;'>{row['topic']}</span>"
        )
    else:
        topic_badge = ""
    st.markdown(
        f"**[{row['title']}]({row['url']})** &nbsp; {topic_badge}  \n"
        f"<small>{row['source']} · {date_str}</small>",
        unsafe_allow_html=True,
    )

shown = min(limit, len(filtered))
if shown < len(filtered):
    st.divider()
    remaining = len(filtered) - shown
    if st.button(f"Carregar mais ({min(PAGE_SIZE, remaining)} de {remaining} restantes)", use_container_width=True):
        st.session_state.explorar_pages += 1
        st.rerun()
else:
    st.caption(f"{shown} notícia{'s' if shown != 1 else ''} exibida{'s' if shown != 1 else ''}.")
