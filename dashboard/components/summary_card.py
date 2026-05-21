import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from datetime import date, timedelta
from db.connection import get_engine
from sqlalchemy import text


MESES = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}


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


def _get_available_dates(engine, topic_id: int | None) -> list[date]:
    """Retorna lista de datas com resumo disponível, ordenadas decrescente."""
    with engine.connect() as conn:
        if topic_id is None:
            rows = conn.execute(text(
                "SELECT DISTINCT date FROM daily_summaries "
                "WHERE topic_id IS NULL ORDER BY date DESC"
            )).fetchall()
        else:
            rows = conn.execute(text(
                "SELECT DISTINCT date FROM daily_summaries "
                "WHERE topic_id = :tid ORDER BY date DESC"
            ), {"tid": topic_id}).fetchall()
    return [r[0] for r in rows]


def _get_summary_for_date(engine, d: date, topic_id: int | None):
    with engine.connect() as conn:
        if topic_id is None:
            return conn.execute(text(
                "SELECT summary, article_ids, article_count, generated_at "
                "FROM daily_summaries WHERE date = :d AND topic_id IS NULL "
                "ORDER BY generated_at DESC LIMIT 1"
            ), {"d": d}).fetchone()
        else:
            return conn.execute(text(
                "SELECT summary, article_ids, article_count, generated_at "
                "FROM daily_summaries WHERE date = :d AND topic_id = :tid "
                "ORDER BY generated_at DESC LIMIT 1"
            ), {"d": d, "tid": topic_id}).fetchone()


def _render_card(engine, row, d: date, topic_name: str | None):
    summary_text = row[0]
    article_ids = row[1] if isinstance(row[1], list) else []
    article_count = row[2]

    sources = _get_source_names(engine, article_ids)
    if len(sources) > 4:
        sources_str = ", ".join(sources[:4]) + f" +{len(sources) - 4}"
    else:
        sources_str = ", ".join(sources)

    data_fmt = f"{d.day} de {MESES[d.month]} de {d.year}"
    title = f"🤖 Resumo do dia — {data_fmt}"
    if topic_name:
        title = f"🤖 Resumo de {topic_name} — {data_fmt}"

    st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #eef6ff 0%, #f0f4ff 100%);
    border-left: 4px solid #4a90d9;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 4px;
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


def render_summary_card(engine, topic_id: int | None = None, topic_name: str | None = None):
    today = date.today()
    nav_key = f"summary_date_{topic_id}"

    available = _get_available_dates(engine, topic_id)

    if not available:
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

    # Inicializa navegação na data mais recente
    if nav_key not in st.session_state:
        st.session_state[nav_key] = available[0]

    current = st.session_state[nav_key]
    # Garante que a data atual ainda está disponível
    if current not in available:
        current = available[0]
        st.session_state[nav_key] = current

    idx = available.index(current)
    has_prev = idx < len(available) - 1  # datas anteriores (índice maior = mais antigo)
    has_next = idx > 0                   # datas posteriores (índice menor = mais recente)

    # Navegação: setas + data central
    col_prev, col_date, col_next = st.columns([1, 6, 1])

    with col_prev:
        if has_prev:
            prev_date = available[idx + 1]
            if st.button(f"← {prev_date.strftime('%d/%m')}", key=f"prev_{nav_key}"):
                st.session_state[nav_key] = prev_date
                st.rerun()
        else:
            st.write("")

    with col_date:
        st.write("")  # espaço visual

    with col_next:
        if has_next:
            next_date = available[idx - 1]
            if st.button(f"{next_date.strftime('%d/%m')} →", key=f"next_{nav_key}"):
                st.session_state[nav_key] = next_date
                st.rerun()
        else:
            st.write("")

    row = _get_summary_for_date(engine, current, topic_id)
    if row:
        _render_card(engine, row, current, topic_name)
