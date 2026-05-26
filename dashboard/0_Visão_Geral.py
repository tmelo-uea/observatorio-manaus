import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from sqlalchemy import text
from db.connection import get_engine
from dashboard.components.summary_card import render_summary_card
from notifications.email_sender import subscribe

def manaus_today():
    return (datetime.utcnow() - timedelta(hours=4)).date()

def manaus_day_utc_range(d):
    from datetime import date as _date
    start = datetime(d.year, d.month, d.day, 4, 0, 0)
    return start, start + timedelta(days=1)

st.set_page_config(
    page_title="Observatório de Manaus",
    page_icon="🔭",
    layout="wide",
)

st.markdown("""
<style>
    .metric-card { background: #f8f9fa; border-radius: 8px; padding: 16px; }
    .stMetric label { font-size: 0.85rem; color: #6c757d; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_db():
    return get_engine()

@st.cache_resource
def init_db():
    from db.connection import Base
    from db.seeds import seed_all
    Base.metadata.create_all(get_engine())
    seed_all()

init_db()

@st.cache_data(ttl=300)
def load_articles():
    engine = get_db()
    query = text("""
        SELECT
            a.id, a.title, a.url,
            LEFT(a.summary, 500) AS summary,
            a.published_at, a.collected_at, a.topic_score, a.is_local,
            s.name AS source, s.type AS source_type,
            t.name AS topic, t.slug AS topic_slug, t.color AS topic_color
        FROM articles a
        JOIN sources s ON a.source_id = s.id
        LEFT JOIN topics t ON a.topic_id = t.id
        ORDER BY a.published_at DESC
        LIMIT 5000
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    df["published_at"] = pd.to_datetime(df["published_at"])
    df["published_at_manaus"] = df["published_at"] - pd.Timedelta(hours=4)
    df["date"] = df["published_at_manaus"].dt.date
    return df


@st.cache_data(ttl=300)
def load_totals():
    """Contagens reais do banco, sem o limite de 5000."""
    engine = get_db()
    today = manaus_today()
    start_utc, end_utc = manaus_day_utc_range(today)
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM articles")).scalar()
        hoje = conn.execute(text(
            "SELECT COUNT(*) FROM articles "
            "WHERE published_at >= :s AND published_at < :e"
        ), {"s": start_utc, "e": end_utc}).scalar()
        semana = conn.execute(text(
            "SELECT COUNT(*) FROM articles "
            "WHERE published_at >= NOW() - INTERVAL 7 DAY"
        )).scalar()
        fontes = conn.execute(text(
            "SELECT COUNT(DISTINCT source_id) FROM articles "
            "WHERE published_at >= :s AND published_at < :e"
        ), {"s": start_utc, "e": end_utc}).scalar()
        ultima = conn.execute(text(
            "SELECT MAX(collected_at) FROM articles"
        )).scalar()
    return {"total": total, "hoje": hoje, "semana": semana, "fontes": fontes, "ultima": ultima}

@st.cache_data(ttl=3600)
def load_topics():
    engine = get_db()
    query = text("SELECT id, name, slug, color, display_order FROM topics ORDER BY display_order")
    with engine.connect() as conn:
        return pd.read_sql(query, conn)

# --- Header ---
col_title, col_refresh = st.columns([8, 1])
with col_title:
    st.title("🔭 Observatório de Manaus")
    st.caption("Monitoramento contínuo de notícias e publicações sobre a cidade de Manaus")
with col_refresh:
    if st.button("↻ Atualizar"):
        st.cache_data.clear()
        st.rerun()

try:
    df = load_articles()
    topics_df = load_topics()
    totals = load_totals()
    render_summary_card(get_db())
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados: {e}")
    st.stop()

if df.empty:
    st.warning("Nenhum artigo coletado ainda. Aguarde o coletor rodar.")
    st.stop()

# --- Sidebar / Filtros ---
st.sidebar.header("🔍 Filtros")

topic_options = ["Todos"] + topics_df["name"].tolist()
selected_topic = st.sidebar.selectbox("Tema", topic_options)

source_options = ["Todos"] + sorted(df["source"].unique().tolist())
selected_source = st.sidebar.selectbox("Portal / Blog", source_options)

with get_db().connect() as _conn:
    _types = [r[0] for r in _conn.execute(text("SELECT DISTINCT type FROM sources WHERE active = 1 ORDER BY type"))]
source_type_options = ["Todos"] + _types
selected_type = st.sidebar.selectbox("Tipo de fonte", source_type_options)

dates_valid = df["date"].dropna()
date_min = dates_valid.min() if not dates_valid.empty else pd.Timestamp.today().date()
date_max = dates_valid.max() if not dates_valid.empty else pd.Timestamp.today().date()
default_start = max(date_min, (pd.Timestamp.today() - pd.Timedelta(days=7)).date())
date_range = st.sidebar.date_input(
    "Período", value=(default_start, date_max),
    min_value=date_min, max_value=date_max
)

busca = st.sidebar.text_input("Buscar por palavra-chave")

show_all = st.sidebar.checkbox("Incluir notícias não locais", value=False)

st.sidebar.divider()
st.sidebar.markdown("### 📬 Receba as notícias de Manaus no seu e-mail")
st.sidebar.caption("Assine o boletim diário e fique por dentro dos principais acontecimentos.")
with st.sidebar.form("subscribe_form", clear_on_submit=True):
    email_input = st.text_input("Seu e-mail", placeholder="voce@email.com")
    submitted = st.form_submit_button("Inscrever-se", use_container_width=True)
    if submitted:
        if email_input and "@" in email_input:
            ok, msg = subscribe(email_input)
            if ok:
                st.success(msg)
            else:
                st.warning(msg)
        else:
            st.error("Informe um e-mail válido.")

# --- Aplicar filtros ---
filtered = df.copy()
if selected_topic != "Todos":
    filtered = filtered[filtered["topic"] == selected_topic]
if selected_source != "Todos":
    filtered = filtered[filtered["source"] == selected_source]
if selected_type != "Todos":
    filtered = filtered[filtered["source_type"] == selected_type]
if len(date_range) == 2:
    filtered = filtered[
        (filtered["date"] >= date_range[0]) & (filtered["date"] <= date_range[1])
    ]
if not show_all and "is_local" in filtered.columns:
    filtered = filtered[filtered["is_local"] == True]
if busca:
    mask = (
        filtered["title"].str.contains(busca, case=False, na=False) |
        filtered["summary"].str.contains(busca, case=False, na=False)
    )
    filtered = filtered[mask]

# --- Métricas rápidas ---
st.divider()
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total coletado", f"{totals['total']:,}")
c2.metric("Notícias no período", f"{len(filtered):,}")
c3.metric("Portais monitorados", filtered["source"].nunique())
c4.metric("Temas identificados", filtered["topic"].nunique())
c5.metric("Hoje", f"{totals['hoje']:,}")
c6.metric("Últimos 7 dias", f"{totals['semana']:,}")

# Última coleta
if totals["ultima"]:
    ultima_dt = pd.Timestamp(totals["ultima"]).replace(tzinfo=None)
    diff_min = int((pd.Timestamp(datetime.utcnow()) - ultima_dt).total_seconds() / 60)
    if diff_min < 60:
        ultima_str = f"há {diff_min} min"
    else:
        ultima_str = f"há {diff_min // 60}h{diff_min % 60:02d}min"
    st.caption(f"🟢 Última coleta: {ultima_str}")

st.divider()

# --- Linha do tempo ---
_MESES_ABR = {1:"jan",2:"fev",3:"mar",4:"abr",5:"mai",6:"jun",
              7:"jul",8:"ago",9:"set",10:"out",11:"nov",12:"dez"}

st.subheader("Volume de notícias por dia")
_TYPE_LABELS = {"portal": "Portal", "blog": "Blog", "youtube": "YouTube", "orgao_publico": "Órgão público"}
_TYPE_COLORS = {"Portal": "#2980b9", "Blog": "#e67e22", "YouTube": "#e74c3c", "Órgão público": "#27ae60"}
daily = filtered.copy()
daily["tipo"] = daily["source_type"].map(_TYPE_LABELS).fillna("Outros")
daily = daily.groupby(["date", "tipo"]).size().reset_index(name="count")
daily["date_ts"] = pd.to_datetime(daily["date"])
_dates = sorted(daily["date"].unique())
_tickvals = [pd.Timestamp(d) for d in _dates]
_ticktext = [f"{d.day} {_MESES_ABR[d.month]}" for d in _dates]
if _dates:
    _ticktext[0] = f"{_dates[0].day} {_MESES_ABR[_dates[0].month]}\n{_dates[0].year}"
fig_timeline = px.bar(
    daily, x="date_ts", y="count", color="tipo",
    labels={"date_ts": "Data", "count": "Notícias", "tipo": "Tipo"},
    color_discrete_map=_TYPE_COLORS,
    category_orders={"tipo": ["Portal", "Blog", "YouTube", "Órgão público"]},
)
fig_timeline.update_xaxes(tickvals=_tickvals, ticktext=_ticktext)
fig_timeline.update_layout(
    barmode="stack",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, title_text=""),
)
st.plotly_chart(fig_timeline, use_container_width=True)

# --- Linha 2: por tema e por fonte ---
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

def _clean_text(series):
    import re
    def clean(t):
        t = re.sub(r"<[^>]+>", " ", t)           # remove tags HTML
        t = re.sub(r"https?://\S+", " ", t)       # remove URLs completas
        t = re.sub(r"\bhttps?\b", " ", t)         # remove http/https soltos
        t = re.sub(r"\b\w*\d\w*\b", " ", t)       # remove tokens com números
        t = re.sub(r"\b\w{1,2}\b", " ", t)        # remove palavras de 1-2 letras
        return t
    return series.dropna().apply(clean).str.cat(sep=" ")

# --- Nuvem de palavras ---
st.subheader("Nuvem de palavras")
texts = []
for col in ["title", "summary", "transcript"]:
    if col in filtered.columns:
        texts.append(_clean_text(filtered[col]))
all_text = " ".join(t for t in texts if t.strip())
if all_text.strip():
    stopwords = {
        "de", "da", "do", "dos", "das", "em", "no", "na", "nos", "nas",
        "e", "o", "a", "os", "as", "um", "uma", "uns", "umas",
        "com", "por", "para", "que", "se", "ao", "aos", "à", "às",
        "são", "mais", "foi", "será", "ser", "tem", "ter", "seus", "sua",
        "seu", "suas", "isso", "este", "esta", "esse", "essa", "esses", "essas",
        "ele", "ela", "eles", "elas", "nós", "eu", "você", "vocês",
        "já", "ainda", "também", "sobre", "entre", "após", "até", "como",
        "quando", "onde", "porque", "mas", "ou", "nem", "não", "sim",
        "muito", "bem", "aqui", "lá", "agora", "então", "assim", "tudo",
        "todos", "todas", "outro", "outra", "outros", "outras", "mesmo",
        "disse", "diz", "afirmou", "segundo", "conforme", "durante",
        "http", "https", "br", "href", "src", "img", "bit", "www",
        "apareceu", "primeiro", "post", "vivo", "acompanhe", "inscreva",
        "canal", "site", "neste", "nesta", "pelo", "pela", "pelos", "pelas",
        "notificações", "conteúdo", "conteúdos", "exclusivos", "informações",
        "instagram", "facebook", "tiktok", "youtube", "twitter", "whatsapp",
        # dias da semana — aparecem sem hífen por limitação da regex de tokenização
        "segunda", "terça", "terca", "quarta", "quinta", "sexta", "sábado", "sabado", "domingo", "feira",
        # boilerplate de portais
        "notícia", "notícias", "noticias", "noticia", "últimas", "ultimas", "leia", "veja", "segue",
        # genéricos jornalísticos
        "dia", "ano", "meio", "está", "esta", "vai", "vídeo", "video", "ocorreu", "visita",
        # referências a horário de transmissão
        "horário", "horario", "Brasília", "brasilia", "brasília",
        # nomes de fontes que aparecem nos próprios textos
        "atual", "notícias", "portais",
    }
    wc = WordCloud(
        width=1200, height=350, background_color="white",
        collocations=True, max_words=120, stopwords=stopwords,
        regexp=r"\b[^\W\d_]{2,}\b",
    ).generate(all_text)
    fig_wc, ax = plt.subplots(figsize=(14, 4))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    st.pyplot(fig_wc)
    plt.close(fig_wc)

# --- Feed de últimas notícias ---
st.divider()
st.subheader("Últimas notícias coletadas")

for _, row in filtered.head(5).iterrows():
    date_str = row["published_at_manaus"].strftime("%d/%m/%Y %H:%M") if pd.notna(row["published_at"]) else "—"
    topic_badge = f"`{row['topic']}`" if pd.notna(row["topic"]) else ""
    st.markdown(
        f"**[{row['title']}]({row['url']})** &nbsp; {topic_badge}  \n"
        f"<small>{row['source']} · {date_str}</small>",
        unsafe_allow_html=True,
    )
