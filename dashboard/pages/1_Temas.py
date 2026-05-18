import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from sqlalchemy import text
from db.connection import get_engine

st.set_page_config(page_title="Temas — Observatório de Manaus", page_icon="🏷️", layout="wide")

st.title("🏷️ Explorar por Tema")

@st.cache_resource
def get_db():
    return get_engine()

@st.cache_data(ttl=300)
def load_topics():
    engine = get_db()
    with engine.connect() as conn:
        return pd.read_sql(text("SELECT * FROM topics ORDER BY display_order"), conn)

@st.cache_data(ttl=300)
def load_articles_by_topic(topic_id):
    engine = get_db()
    query = text("""
        SELECT a.id, a.title, a.url, a.summary, a.published_at,
               s.name AS source, t.name AS topic, t.color AS topic_color
        FROM articles a
        JOIN sources s ON a.source_id = s.id
        JOIN topics t ON a.topic_id = t.id
        WHERE a.topic_id = :topic_id
        ORDER BY a.published_at DESC
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"topic_id": int(topic_id)})
    df["published_at"] = pd.to_datetime(df["published_at"])
    df["date"] = df["published_at"].dt.date
    return df

try:
    topics_df = load_topics()
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}")
    st.stop()

# --- Visão geral de todos os temas ---
st.subheader("Visão geral")

@st.cache_data(ttl=300)
def load_topic_counts():
    engine = get_db()
    query = text("""
        SELECT t.name, t.color, t.display_order, COUNT(a.id) AS total
        FROM topics t
        LEFT JOIN articles a ON a.topic_id = t.id
        GROUP BY t.id, t.name, t.color, t.display_order
        ORDER BY t.display_order
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn)

counts_df = load_topic_counts()
color_map = dict(zip(counts_df["name"], counts_df["color"]))
fig = px.bar(
    counts_df[counts_df["name"] != "Outros"],
    x="total", y="name", orientation="h", color="name",
    color_discrete_map=color_map,
    labels={"total": "Notícias", "name": "Tema"},
)
fig.update_layout(showlegend=False, yaxis=dict(categoryorder="total ascending"))
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Detalhe por tema ---
st.subheader("Detalhe por tema")
topic_names = topics_df[topics_df["name"] != "Outros"]["name"].tolist()
selected = st.selectbox("Selecione um tema", topic_names)
topic_row = topics_df[topics_df["name"] == selected].iloc[0]

df = load_articles_by_topic(topic_row["id"])

if df.empty:
    st.info("Nenhum artigo classificado neste tema ainda.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Total de notícias", len(df))
c2.metric("Fontes diferentes", df["source"].nunique())
dates = df["date"].dropna()
periodo = f"{dates.min()} → {dates.max()}" if not dates.empty else "—"
c3.metric("Período", periodo)

# Linha do tempo
daily = df.groupby(["date", "source"]).size().reset_index(name="count")
fig2 = px.line(daily, x="date", y="count", color="source", markers=True,
               title=f"Volume diário — {selected}",
               labels={"date": "Data", "count": "Notícias", "source": "Fonte"})
st.plotly_chart(fig2, use_container_width=True)

def _strip_html(series):
    import re
    return series.dropna().apply(lambda t: re.sub(r"<[^>]+>", " ", t)).str.cat(sep=" ")

# Nuvem de palavras
texts = []
for col in ["title", "summary", "transcript"]:
    if col in df.columns:
        texts.append(_strip_html(df[col]))
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
        "http", "br", "href", "src", "img",
    }
    wc = WordCloud(width=900, height=280, background_color="white",
                   collocations=False, max_words=80, stopwords=stopwords,
                   regexp=r"\b[^\W\d_]{2,}\b").generate(all_text)
    fig_wc, ax = plt.subplots(figsize=(12, 3.5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    st.pyplot(fig_wc)
    plt.close(fig_wc)

# Lista de artigos
st.subheader(f"Últimas notícias — {selected}")
for _, row in df.head(25).iterrows():
    date_str = row["published_at"].strftime("%d/%m/%Y %H:%M") if pd.notna(row["published_at"]) else "—"
    st.markdown(
        f"**[{row['title']}]({row['url']})**  \n"
        f"<small>{row['source']} · {date_str}</small>",
        unsafe_allow_html=True,
    )
