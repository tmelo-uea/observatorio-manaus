import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from datetime import date
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


def _inject_nav_css():
    st.markdown("""
<style>
.summary-nav button[kind="secondary"] {
    border-radius: 50% !important;
    width: 2.4rem !important;
    height: 2.4rem !important;
    padding: 0 !important;
    font-size: 1.1rem !important;
    border: 2px solid #4a90d9 !important;
    color: #4a90d9 !important;
    background: white !important;
    line-height: 1 !important;
    min-height: unset !important;
}
.summary-nav button[kind="secondary"]:hover {
    background: #4a90d9 !important;
    color: white !important;
}
.summary-nav button[kind="secondary"]:disabled,
.summary-nav button[disabled] {
    border-color: #ddd !important;
    color: #ccc !important;
    cursor: not-allowed !important;
}
</style>
""", unsafe_allow_html=True)


def render_summary_card(engine, topic_id: int | None = None, topic_name: str | None = None):
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

    if nav_key not in st.session_state or st.session_state[nav_key] not in available:
        st.session_state[nav_key] = available[0]

    current = st.session_state[nav_key]
    idx = available.index(current)
    has_prev = idx < len(available) - 1
    has_next = idx > 0
    total = len(available)

    row = _get_summary_for_date(engine, current, topic_id)
    if not row:
        return

    summary_text = row[0]
    article_ids = row[1] if isinstance(row[1], list) else []
    article_count = row[2]

    sources = _get_source_names(engine, article_ids)
    sources_str = (
        ", ".join(sources[:4]) + f" +{len(sources) - 4} fontes"
        if len(sources) > 4 else ", ".join(sources)
    )

    data_fmt = f"{current.day} de {MESES[current.month]} de {current.year}"
    title = f"Resumo de {topic_name} — {data_fmt}" if topic_name else f"Resumo do dia — {data_fmt}"
    is_today = current == date.today()
    badge = '<span style="background:#4a90d9;color:white;font-size:0.7rem;padding:2px 8px;border-radius:10px;margin-left:8px;vertical-align:middle;">Hoje</span>' if is_today else ""

    _inject_nav_css()

    # Navegação
    st.markdown('<div class="summary-nav">', unsafe_allow_html=True)
    col_prev, col_info, col_next = st.columns([1, 10, 1])

    with col_prev:
        st.write("")
        if has_prev:
            if st.button("‹", key=f"prev_{nav_key}", help=f"Ver {available[idx+1].strftime('%d/%m/%Y')}"):
                st.session_state[nav_key] = available[idx + 1]
                st.rerun()

    with col_next:
        st.write("")
        if has_next:
            if st.button("›", key=f"next_{nav_key}", help=f"Ver {available[idx-1].strftime('%d/%m/%Y')}"):
                st.session_state[nav_key] = available[idx - 1]
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # Indicador de posição (ex: "2 de 5 dias")
    pos_label = f"dia {idx + 1} de {total}" if total > 1 else ""

    # Card principal
    st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #eef6ff 0%, #f0f4ff 100%);
    border-left: 5px solid #4a90d9;
    border-radius: 10px;
    padding: 22px 28px 18px 28px;
    margin-top: -0.5rem;
    margin-bottom: 8px;
    box-shadow: 0 2px 8px rgba(74,144,217,0.08);
">
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;">
        <div style="font-size:0.88rem; font-weight:700; color:#4a90d9; letter-spacing:0.03em;">
            🤖 {title}{badge}
        </div>
        <div style="font-size:0.75rem; color:#b0bec5;">{pos_label}</div>
    </div>
    <div style="font-size:1rem; color:#2c3e50; line-height:1.8; border-top:1px solid #dce8f7; padding-top:12px;">
        {summary_text}
    </div>
    <div style="
        margin-top:14px;
        padding-top:10px;
        border-top:1px solid #dce8f7;
        font-size:0.78rem;
        color:#7f8c8d;
        display:flex;
        align-items:center;
        gap:8px;
    ">
        <span>📰 Baseado em <strong>{article_count}</strong> artigos</span>
        <span style="color:#ccc;">·</span>
        <span>{sources_str}</span>
    </div>
</div>
""", unsafe_allow_html=True)
