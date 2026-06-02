import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import urllib.parse
import streamlit as st
from datetime import date, datetime, timedelta
from db.connection import get_engine
from sqlalchemy import text

SITE_URL = "https://www.observatorio.manaus.br"

_SVG_WHATSAPP = '<svg width="16" height="16" viewBox="0 0 24 24" fill="#fff"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zm-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884zm8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>'
_SVG_TELEGRAM = '<svg width="16" height="16" viewBox="0 0 24 24" fill="#fff"><path d="M23.91 3.79L20.3 20.84c-.25 1.21-.98 1.5-2 .94l-5.5-4.07-2.66 2.57c-.3.3-.55.56-1.1.56-.72 0-.6-.27-.84-.95L6.3 13.7l-5.45-1.7c-1.18-.35-1.19-1.16.26-1.75l21.26-8.2c.97-.43 1.9.24 1.53 1.73z"/></svg>'
_SVG_X = '<svg width="14" height="14" viewBox="0 0 24 24" fill="#fff"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'


def _build_share_links(summary_text: str, date_fmt: str) -> dict:
    full_text = (
        f"Resumo do Observatório de Manaus — {date_fmt}:\n\n"
        f"{summary_text}\n\n"
        f"Veja mais: {SITE_URL}"
    )
    first_sentence = summary_text.split(". ")[0].strip()
    if len(first_sentence) > 200:
        first_sentence = first_sentence[:197] + "..."
    x_text = f"Resumo do Observatório de Manaus ({date_fmt}): {first_sentence}"

    return {
        "full_text": full_text,
        "whatsapp": f"https://web.whatsapp.com/send?text={urllib.parse.quote(full_text)}",
        "telegram": (
            f"https://t.me/share/url?url={urllib.parse.quote(SITE_URL)}"
            f"&text={urllib.parse.quote(full_text)}"
        ),
        "x": (
            f"https://twitter.com/intent/tweet?text={urllib.parse.quote(x_text)}"
            f"&url={urllib.parse.quote(SITE_URL)}"
        ),
    }

def _manaus_today() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date()


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
    pass


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
    is_today = current == _manaus_today()
    badge = '<span style="background:#4a90d9;color:white;font-size:0.7rem;padding:2px 8px;border-radius:10px;margin-left:8px;vertical-align:middle;">Hoje</span>' if is_today else ""

    _inject_nav_css()

    # Navegação compacta
    nav_cols = st.columns([0.5, 0.5, 11])
    with nav_cols[0]:
        if has_prev:
            if st.button("‹", key=f"prev_{nav_key}", help=f"Ver {available[idx+1].strftime('%d/%m/%Y')}"):
                st.session_state[nav_key] = available[idx + 1]
                st.rerun()
    with nav_cols[1]:
        if has_next:
            if st.button("›", key=f"next_{nav_key}", help=f"Ver {available[idx-1].strftime('%d/%m/%Y')}"):
                st.session_state[nav_key] = available[idx - 1]
                st.rerun()

    # Indicador de posição (ex: "2 de 5 dias")
    pos_label = f"dia {idx + 1} de {total}" if total > 1 else ""

    share = _build_share_links(summary_text, data_fmt)
    share_buttons_html = (
        f'<span style="font-size:0.78rem;color:#7f8c8d;">Compartilhar:</span>'
        f'<a href="{share["whatsapp"]}" target="_blank" rel="noopener" title="WhatsApp" '
        f'style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;'
        f'border-radius:6px;background:#25D366;text-decoration:none;">{_SVG_WHATSAPP}</a>'
        f'<a href="{share["telegram"]}" target="_blank" rel="noopener" title="Telegram" '
        f'style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;'
        f'border-radius:6px;background:#229ED9;text-decoration:none;">{_SVG_TELEGRAM}</a>'
        f'<a href="{share["x"]}" target="_blank" rel="noopener" title="X (Twitter)" '
        f'style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;'
        f'border-radius:6px;background:#000;text-decoration:none;">{_SVG_X}</a>'
    )

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
        flex-wrap:wrap;
        gap:8px;
    ">
        <span>📰 Baseado em <strong>{article_count}</strong> artigos</span>
        <span style="color:#ccc;">·</span>
        <span style="flex:1;">{sources_str}</span>
        <span style="display:inline-flex;align-items:center;gap:6px;">{share_buttons_html}</span>
    </div>
</div>
""", unsafe_allow_html=True)
