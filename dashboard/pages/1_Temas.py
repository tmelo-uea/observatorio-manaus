import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import re
import unicodedata
import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from collections import Counter
from datetime import date, timedelta
from sqlalchemy import text
from db.connection import get_engine
from dashboard.components.summary_card import render_summary_card

st.set_page_config(page_title="Temas — Observatório de Manaus", page_icon="🏷️", layout="wide")

TOPIC_ICONS = {
    "Saúde":                    "🏥",
    "Segurança Pública":        "🚔",
    "Meio Ambiente":            "🌿",
    "Política e Governo":       "🏛️",
    "Economia e Negócios":      "💼",
    "Educação":                 "🎓",
    "Infraestrutura e Mobilidade": "🚌",
    "Cultura e Lazer":          "🎭",
    "Esporte":                  "⚽",
    "Tecnologia e Inovação":    "💡",
    "Justiça e Direito":        "⚖️",
    "Social e Cidadania":       "🤝",
}

STOPWORDS = {
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
    "disse", "diz", "afirmou", "segundo", "conforme", "durante", "novo",
    "nova", "dois", "três", "vier", "será", "pode", "deve", "vai",
    "http", "https", "www", "notícia", "notícias", "portal", "manaus",
}


@st.cache_resource
def get_db():
    return get_engine()


@st.cache_data(ttl=300)
def load_topics():
    engine = get_db()
    with engine.connect() as conn:
        return pd.read_sql(text("SELECT * FROM topics ORDER BY display_order"), conn)


@st.cache_data(ttl=300)
def load_topic_stats():
    """Métricas por tema: total hoje, total semana atual, semana anterior, fontes, última notícia."""
    engine = get_db()
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    prev_week_start = week_start - timedelta(days=7)
    query = text("""
        SELECT
            t.id,
            t.name,
            t.color,
            t.display_order,
            COUNT(a.id) AS total_all,
            SUM(CASE WHEN DATE(a.published_at) = :today THEN 1 ELSE 0 END) AS total_hoje,
            SUM(CASE WHEN DATE(a.published_at) >= :week_start THEN 1 ELSE 0 END) AS total_semana,
            SUM(CASE WHEN DATE(a.published_at) >= :prev_week_start
                      AND DATE(a.published_at) < :week_start THEN 1 ELSE 0 END) AS total_semana_ant,
            COUNT(DISTINCT CASE WHEN DATE(a.published_at) = :today THEN a.source_id END) AS fontes_hoje,
            MAX(a.published_at) AS ultima_noticia
        FROM topics t
        LEFT JOIN articles a ON a.topic_id = t.id
        GROUP BY t.id, t.name, t.color, t.display_order
        ORDER BY t.display_order
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={
            "today": today,
            "week_start": week_start,
            "prev_week_start": prev_week_start,
        })


@st.cache_data(ttl=300)
def load_today_titles(topic_id: int) -> list[str]:
    engine = get_db()
    today = date.today()
    query = text("""
        SELECT a.title FROM articles a
        WHERE a.topic_id = :tid AND DATE(a.published_at) = :today
        ORDER BY a.published_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"tid": topic_id, "today": today}).fetchall()
    return [r[0] for r in rows if r[0]]


@st.cache_data(ttl=300)
def load_top_sources_today(topic_id: int, limit: int = 3):
    engine = get_db()
    today = date.today()
    query = text("""
        SELECT s.name, COUNT(a.id) AS total
        FROM articles a
        JOIN sources s ON a.source_id = s.id
        WHERE a.topic_id = :tid AND DATE(a.published_at) = :today
        GROUP BY s.id, s.name
        ORDER BY total DESC
        LIMIT :lim
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"tid": topic_id, "today": today, "lim": limit}).fetchall()
    return [(r[0], r[1]) for r in rows]


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
        LIMIT 500
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"topic_id": int(topic_id)})
    df["published_at"] = pd.to_datetime(df["published_at"])
    df["date"] = df["published_at"].dt.date
    return df


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def extract_keywords(titles: list[str], top_n: int = 6) -> list[str]:
    words = []
    for title in titles:
        clean = _normalize(title)
        clean = re.sub(r"[^a-z\s]", " ", clean)
        for w in clean.split():
            if len(w) >= 4 and w not in STOPWORDS:
                words.append(w)
    counts = Counter(words).most_common(top_n * 3)
    seen_roots = []
    result = []
    for word, _ in counts:
        if not any(word[:5] == r[:5] for r in seen_roots):
            seen_roots.append(word)
            result.append(word)
        if len(result) == top_n:
            break
    return result


def _time_ago(dt) -> str:
    if pd.isna(dt):
        return "—"
    diff = pd.Timestamp.now() - pd.Timestamp(dt)
    mins = int(diff.total_seconds() / 60)
    if mins < 60:
        return f"{mins} min"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h"
    return f"{diff.days}d"


def render_theme_card(row, summary_row):
    topic_id = int(row["id"])
    name = row["name"]
    color = row["color"] or "#4a90d9"
    icon = TOPIC_ICONS.get(name, "📰")

    total_hoje = int(row["total_hoje"] or 0)
    fontes_hoje = int(row["fontes_hoje"] or 0)
    total_semana = int(row["total_semana"] or 0)
    total_semana_ant = int(row["total_semana_ant"] or 0)
    ultima = row["ultima_noticia"]

    # Tendência semanal
    if total_semana_ant > 0:
        delta_pct = ((total_semana - total_semana_ant) / total_semana_ant) * 100
        delta_str = f"+{delta_pct:.0f}%" if delta_pct >= 0 else f"{delta_pct:.0f}%"
        delta_color = "#16a34a" if delta_pct >= 0 else "#dc2626"
        delta_arrow = "▲" if delta_pct >= 0 else "▼"
    else:
        delta_str = ""
        delta_color = "#6b7280"
        delta_arrow = ""

    em_alta = total_semana > total_semana_ant and total_semana_ant > 0

    # Keywords dos títulos de hoje
    titles = load_today_titles(topic_id)
    keywords = extract_keywords(titles) if titles else []
    chips_html = "".join(
        f'<span style="padding:5px 11px;border-radius:999px;background:#ffffff;'
        f'border:1px solid #dbeafe;color:#1d4ed8;font-size:0.82rem;font-weight:700;">{kw}</span>'
        for kw in keywords
    ) if keywords else '<span style="color:#9ca3af;font-size:0.85rem;">Sem dados suficientes hoje</span>'

    # Top fontes de hoje
    top_sources = load_top_sources_today(topic_id)
    max_count = top_sources[0][1] if top_sources else 1
    sources_html = ""
    for src_name, src_count in top_sources:
        pct = int((src_count / max_count) * 100)
        sources_html += f"""
        <div style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;font-size:0.88rem;font-weight:700;margin-bottom:4px;">
                <span>{src_name}</span><span>{src_count}</span>
            </div>
            <div style="height:8px;background:#e2e8f0;border-radius:999px;overflow:hidden;">
                <span style="display:block;height:100%;width:{pct}%;border-radius:999px;
                background:linear-gradient(90deg,{color},{color}99);"></span>
            </div>
        </div>"""
    if not sources_html:
        sources_html = '<span style="color:#9ca3af;font-size:0.85rem;">Sem artigos hoje</span>'

    # Resumo do dia
    if summary_row:
        summary_text = summary_row[0]
        article_count = summary_row[2]
        leitura_html = f"""
        <p style="margin:0 0 8px;font-size:0.86rem;text-transform:uppercase;
            letter-spacing:0.06em;color:#6b7280;font-weight:800;">Leitura do Observatório</p>
        <p style="margin:0;font-size:1rem;line-height:1.75;color:#334155;">{summary_text}</p>
        <p style="margin:10px 0 0;font-size:0.78rem;color:#9ca3af;">
            Baseado em {article_count} artigos publicados hoje</p>"""
    else:
        leitura_html = """
        <p style="margin:0 0 8px;font-size:0.86rem;text-transform:uppercase;
            letter-spacing:0.06em;color:#6b7280;font-weight:800;">Leitura do Observatório</p>
        <p style="margin:0;font-size:0.95rem;color:#9ca3af;font-style:italic;">
            Resumo não disponível — artigos insuficientes hoje.</p>"""

    status_badge = f"""
        <div style="display:inline-flex;align-items:center;gap:6px;padding:7px 12px;
            border-radius:999px;background:#ecfdf5;color:#166534;font-size:0.85rem;
            font-weight:700;border:1px solid #bbf7d0;">
            ▲ Em alta esta semana
        </div>""" if em_alta else ""

    delta_html = f'<div style="font-size:0.76rem;margin-top:5px;color:{delta_color};font-weight:700;">{delta_arrow} {delta_str} vs. semana anterior</div>' if delta_str else ""

    st.markdown(f"""
<div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:22px;
    box-shadow:0 4px 18px rgba(15,23,42,0.07);overflow:hidden;margin-bottom:4px;">

  <!-- Cabeçalho -->
  <div style="background:linear-gradient(135deg,#eff6ff 0%,#eef2ff 55%,#f8fafc 100%);
      padding:22px 26px 18px;border-bottom:1px solid #dbeafe;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
      <div style="display:flex;align-items:center;gap:14px;">
        <div style="width:52px;height:52px;border-radius:18px;display:grid;place-items:center;
            background:#ffffff;box-shadow:0 6px 16px rgba(37,99,235,0.13);font-size:1.7rem;">
            {icon}
        </div>
        <div>
          <div style="font-size:0.76rem;font-weight:800;letter-spacing:0.08em;
              text-transform:uppercase;color:{color};margin-bottom:3px;">
              Resumo automático por tema
          </div>
          <div style="font-size:1.45rem;font-weight:800;color:#0f172a;line-height:1.2;">{name}</div>
        </div>
      </div>
      {status_badge}
    </div>

    <!-- Métricas -->
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">
      <div style="background:rgba(255,255,255,0.8);border:1px solid rgba(219,234,254,0.9);
          border-radius:14px;padding:13px 15px;">
        <div style="font-size:0.77rem;color:#6b7280;margin-bottom:3px;">Notícias hoje</div>
        <div style="font-size:1.4rem;font-weight:800;color:#111827;">{total_hoje}</div>
        {delta_html}
      </div>
      <div style="background:rgba(255,255,255,0.8);border:1px solid rgba(219,234,254,0.9);
          border-radius:14px;padding:13px 15px;">
        <div style="font-size:0.77rem;color:#6b7280;margin-bottom:3px;">Fontes hoje</div>
        <div style="font-size:1.4rem;font-weight:800;color:#111827;">{fontes_hoje}</div>
      </div>
      <div style="background:rgba(255,255,255,0.8);border:1px solid rgba(219,234,254,0.9);
          border-radius:14px;padding:13px 15px;">
        <div style="font-size:0.77rem;color:#6b7280;margin-bottom:3px;">Assuntos detectados</div>
        <div style="font-size:1.4rem;font-weight:800;color:#111827;">{len(keywords)}</div>
      </div>
      <div style="background:rgba(255,255,255,0.8);border:1px solid rgba(219,234,254,0.9);
          border-radius:14px;padding:13px 15px;">
        <div style="font-size:0.77rem;color:#6b7280;margin-bottom:3px;">Última notícia</div>
        <div style="font-size:1.4rem;font-weight:800;color:#111827;">{_time_ago(ultima)}</div>
      </div>
    </div>
  </div>

  <!-- Corpo -->
  <div style="padding:22px 26px 20px;display:grid;grid-template-columns:1.3fr 0.7fr;gap:24px;">
    <div>{leitura_html}</div>
    <div style="display:flex;flex-direction:column;gap:16px;">
      <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:16px;padding:15px;">
        <div style="font-size:0.8rem;text-transform:uppercase;letter-spacing:0.06em;
            font-weight:800;color:#475569;margin-bottom:10px;">Assuntos em destaque</div>
        <div style="display:flex;flex-wrap:wrap;gap:7px;">{chips_html}</div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:16px;padding:15px;">
        <div style="font-size:0.8rem;text-transform:uppercase;letter-spacing:0.06em;
            font-weight:800;color:#475569;margin-bottom:10px;">Fontes mais presentes</div>
        {sources_html}
      </div>
    </div>
  </div>

</div>
""", unsafe_allow_html=True)


try:
    topics_df = load_topics()
    stats_df = load_topic_stats()
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}")
    st.stop()

# --- Visão geral ---
st.title("🏷️ Temas")
st.caption("Distribuição e resumos automáticos por tema")

counts_df = stats_df[stats_df["name"] != "Outros"].copy()
color_map = dict(zip(counts_df["name"], counts_df["color"]))
fig = px.bar(
    counts_df.sort_values("total_all"),
    x="total_all", y="name", orientation="h", color="name",
    color_discrete_map=color_map,
    labels={"total_all": "Total de notícias", "name": "Tema"},
)
fig.update_layout(showlegend=False, yaxis=dict(categoryorder="total ascending"), height=380)
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Resumos por tema")
st.caption("Clique em um tema para expandir o resumo do dia.")

engine = get_db()
topics_iter = stats_df[stats_df["name"] != "Outros"].iterrows()

for _, topic_row in topics_iter:
    topic_id = int(topic_row["id"])
    name = topic_row["name"]
    icon = TOPIC_ICONS.get(name, "📰")
    total_hoje = int(topic_row["total_hoje"] or 0)
    em_alta = int(topic_row["total_semana"] or 0) > int(topic_row["total_semana_ant"] or 0) and int(topic_row["total_semana_ant"] or 0) > 0
    badge = " 🔥" if em_alta else ""
    label = f"{icon} {name}{badge}  —  {total_hoje} notícias hoje"

    with st.expander(label):
        # Busca resumo de hoje
        with engine.connect() as conn:
            summary_row = conn.execute(text(
                "SELECT summary, article_ids, article_count, generated_at "
                "FROM daily_summaries WHERE date = :d AND topic_id = :tid "
                "ORDER BY generated_at DESC LIMIT 1"
            ), {"d": date.today(), "tid": topic_id}).fetchone()

        render_theme_card(topic_row, summary_row)

        # Botão para gerar resumo se não existir
        if not summary_row:
            if st.button("🤖 Gerar resumo com IA", key=f"gen_{topic_id}"):
                with st.spinner("Gerando resumo..."):
                    from nlp.summarizer import generate_summary
                    result = generate_summary(topic_id=topic_id)
                if result:
                    st.rerun()
                else:
                    st.warning("Artigos insuficientes para gerar resumo hoje.")

        st.divider()

        # Detalhe completo do tema
        df = load_articles_by_topic(topic_id)
        if not df.empty:
            c1, c2 = st.columns(2)
            with c1:
                daily = df.groupby(["date", "source"]).size().reset_index(name="count")
                fig2 = px.line(daily, x="date", y="count", color="source", markers=True,
                               labels={"date": "Data", "count": "Notícias", "source": "Fonte"},
                               title=f"Volume diário — {name}")
                fig2.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02))
                st.plotly_chart(fig2, use_container_width=True)

            with c2:
                st.markdown(f"**Últimas notícias — {name}**")
                for _, row in df.head(8).iterrows():
                    date_str = row["published_at"].strftime("%d/%m %H:%M") if pd.notna(row["published_at"]) else "—"
                    st.markdown(
                        f"[{row['title']}]({row['url']})  \n"
                        f"<small>{row['source']} · {date_str}</small>",
                        unsafe_allow_html=True,
                    )
