import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from sqlalchemy import text
from db.connection import get_engine
from dashboard.components.summary_card import (
    _build_share_links,
    _SVG_WHATSAPP,
    _SVG_TELEGRAM,
    _SVG_X,
)

st.set_page_config(
    page_title="Boletins — Observatório de Manaus",
    page_icon="📰",
    layout="wide",
)

MESES = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

PAGE_SIZE = 20


@st.cache_resource
def get_db():
    return get_engine()


@st.cache_data(ttl=300)
def count_summaries():
    engine = get_db()
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT COUNT(*) FROM daily_summaries WHERE topic_id IS NULL"
        )).scalar() or 0


@st.cache_data(ttl=300)
def load_summaries(limit):
    engine = get_db()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT date, summary, article_count, article_ids
            FROM daily_summaries
            WHERE topic_id IS NULL
            ORDER BY date DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    return rows


@st.cache_data(ttl=600)
def get_source_names(article_ids_tuple):
    if not article_ids_tuple:
        return []
    ids_str = ",".join(str(i) for i in article_ids_tuple[:60])
    engine = get_db()
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT DISTINCT s.name FROM articles a "
            f"JOIN sources s ON a.source_id = s.id "
            f"WHERE a.id IN ({ids_str})"
        )).fetchall()
    return [r[0] for r in rows]


st.title("📰 Boletins anteriores")
st.caption(
    "Aqui você encontra um resumo dos principais acontecimentos de Manaus em cada dia. "
    "Tudo o que foi notícia reunido em um só lugar: política, saúde, segurança, esporte e muito mais. "
    "Volte no tempo e acompanhe como a cidade vem se transformando dia a dia."
)

total = count_summaries()
if total == 0:
    st.info("Nenhum boletim disponível ainda.")
    st.stop()

if "boletins_pages" not in st.session_state:
    st.session_state.boletins_pages = 1

limit = st.session_state.boletins_pages * PAGE_SIZE
rows = load_summaries(limit)

st.write("")

for row in rows:
    summary_date = row[0]
    summary_text = row[1]
    article_count = row[2]
    article_ids = tuple(row[3]) if isinstance(row[3], list) else ()

    data_fmt = f"{summary_date.day} de {MESES[summary_date.month]} de {summary_date.year}"
    preview = summary_text[:180].rstrip()
    if len(summary_text) > 180:
        preview += "..."

    st.markdown(f"""
<div style="background:#f8fafc;border-left:4px solid #4a90d9;border-radius:8px;
            padding:16px 22px;margin-bottom:4px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="font-weight:700;color:#1e40af;font-size:0.95rem;">📅 {data_fmt}</span>
        <span style="font-size:0.78rem;color:#7f8c8d;">{article_count} artigos</span>
    </div>
    <div style="color:#475569;line-height:1.65;font-size:0.92rem;font-style:italic;">
        {preview}
    </div>
</div>
""", unsafe_allow_html=True)

    with st.expander("Ler boletim completo"):
        st.markdown(f"""
<div style="font-size:1rem;color:#2c3e50;line-height:1.8;padding:6px 0 12px 0;">
{summary_text}
</div>
""", unsafe_allow_html=True)

        sources = get_source_names(article_ids)
        if sources:
            sources_str = ", ".join(sources[:5])
            if len(sources) > 5:
                sources_str += f" +{len(sources) - 5} fontes"
            st.caption(f"📰 Fontes: {sources_str}")

        share = _build_share_links(summary_text, data_fmt)
        st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;margin-top:10px;">
    <span style="font-size:0.78rem;color:#7f8c8d;">Compartilhar:</span>
    <a href="{share['whatsapp']}" target="_blank" rel="noopener" title="WhatsApp"
       style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;
              border-radius:6px;background:#25D366;text-decoration:none;">{_SVG_WHATSAPP}</a>
    <a href="{share['telegram']}" target="_blank" rel="noopener" title="Telegram"
       style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;
              border-radius:6px;background:#229ED9;text-decoration:none;">{_SVG_TELEGRAM}</a>
    <a href="{share['x']}" target="_blank" rel="noopener" title="X (Twitter)"
       style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;
              border-radius:6px;background:#000;text-decoration:none;">{_SVG_X}</a>
</div>
""", unsafe_allow_html=True)

    st.write("")

if limit < total:
    st.divider()
    remaining = total - limit
    next_batch = min(PAGE_SIZE, remaining)
    if st.button(f"Carregar mais ({next_batch} de {remaining} restantes)",
                 use_container_width=True):
        st.session_state.boletins_pages += 1
        st.rerun()
else:
    st.divider()
    st.caption(f"📦 {total} boletins exibidos. Fim do arquivo.")
