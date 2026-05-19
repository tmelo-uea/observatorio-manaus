import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from datetime import date
from db.connection import get_engine
from sqlalchemy import text


def _get_source_names(engine, article_ids: list) -> list[str]:
    if not article_ids:
        return []
    ids_str = ",".join(str(i) for i in article_ids[:60])
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT DISTINCT s.name FROM articles a "
            f"JOIN sources s ON a.source_id = s.id "
            f"WHERE a.id IN ({ids_str})"
        )).fetchall()
    return [r[0] for r in rows]


def render_summary_card(engine, topic_id: int | None = None, topic_name: str | None = None):
    today = date.today()

    # Busca resumo do banco
    with engine.connect() as conn:
        if topic_id is None:
            row = conn.execute(text(
                "SELECT summary, article_ids, article_count, generated_at "
                "FROM daily_summaries WHERE date = :d AND topic_id IS NULL "
                "ORDER BY generated_at DESC LIMIT 1"
            ), {"d": today}).fetchone()
        else:
            row = conn.execute(text(
                "SELECT summary, article_ids, article_count, generated_at "
                "FROM daily_summaries WHERE date = :d AND topic_id = :tid "
                "ORDER BY generated_at DESC LIMIT 1"
            ), {"d": today, "tid": topic_id}).fetchone()

    # Se não existe, oferece gerar sob demanda (para temas)
    if not row:
        if topic_id is not None:
            if st.button("🤖 Gerar resumo deste tema", key=f"gen_summary_{topic_id}"):
                with st.spinner("Gerando resumo com IA..."):
                    from nlp.summarizer import generate_summary
                    result = generate_summary(topic_id=topic_id)
                if result:
                    st.rerun()
                else:
                    st.warning("Artigos insuficientes para gerar resumo hoje.")
        return

    summary_text = row[0]
    article_ids = row[1] if isinstance(row[1], list) else []
    article_count = row[2]
    generated_at = row[3]

    sources = _get_source_names(engine, article_ids)
    if len(sources) > 4:
        sources_str = ", ".join(sources[:4]) + f" +{len(sources) - 4}"
    else:
        sources_str = ", ".join(sources)

    title = f"🤖 Resumo do dia — {today.strftime('%d de %B de %Y')}"
    if topic_name:
        title = f"🤖 Resumo de {topic_name} — {today.strftime('%d de %B de %Y')}"

    st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #eef6ff 0%, #f0f4ff 100%);
    border-left: 4px solid #4a90d9;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 16px;
">
    <div style="font-size:0.85rem; font-weight:600; color:#4a90d9; margin-bottom:8px; letter-spacing:0.03em;">
        {title}
    </div>
    <div style="font-size:1rem; color:#2c3e50; line-height:1.7;">
        {summary_text}
    </div>
    <div style="margin-top:12px; font-size:0.78rem; color:#7f8c8d; font-style:italic;">
        Baseado em {article_count} artigos &nbsp;·&nbsp; {sources_str}
    </div>
</div>
""", unsafe_allow_html=True)
