import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from db.connection import get_engine
from dashboard.components.summary_card import render_summary_card
from notifications.email_sender import subscribe, unsubscribe_by_token, run_digest

WHATSAPP_URL = "https://wa.me/559223981517?text=menu"


def fmt_br(n: int) -> str:
    return f"{n:,}".replace(",", ".")

st.set_page_config(
    page_title="Observatório de Manaus",
    page_icon="🔭",
    layout="wide",
)

# Meta tags para preview em redes sociais (WhatsApp, Telegram, X, Facebook)
st.markdown("""
<meta property="og:title" content="Observatório de Manaus">
<meta property="og:description" content="Monitoramento automático de notícias sobre Manaus e o Amazonas. Iniciativa do LSI/UEA.">
<meta property="og:url" content="https://www.observatorio.manaus.br">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Observatório de Manaus">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Observatório de Manaus">
<meta name="twitter:description" content="Monitoramento automático de notícias sobre Manaus e o Amazonas. Iniciativa do LSI/UEA.">
""", unsafe_allow_html=True)


@st.cache_resource
def get_db():
    return get_engine()


@st.cache_data(ttl=300)
def load_panorama():
    """Métricas das últimas 24 horas (apenas notícias locais)."""
    engine = get_db()
    start = datetime.utcnow() - timedelta(hours=24)
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT COUNT(*),
                   COUNT(DISTINCT a.topic_id),
                   COUNT(DISTINCT a.source_id)
            FROM articles a
            WHERE a.published_at >= :s AND a.is_local = 1
        """), {"s": start}).fetchone()
        ultima = conn.execute(text("SELECT MAX(collected_at) FROM articles")).scalar()
    return {"noticias": row[0] or 0, "temas": row[1] or 0, "portais": row[2] or 0, "ultima": ultima}


@st.cache_data(ttl=300)
def load_latest(limit=8):
    engine = get_db()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT a.title, a.url, a.published_at,
                   s.name AS source, t.name AS topic, t.color AS topic_color
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            LEFT JOIN topics t ON a.topic_id = t.id
            WHERE a.is_local = 1 AND a.published_at IS NOT NULL
            ORDER BY a.published_at DESC
            LIMIT :l
        """), {"l": limit})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    if not df.empty:
        df["published_manaus"] = pd.to_datetime(df["published_at"]) - pd.Timedelta(hours=4)
    return df


@st.cache_data(ttl=3600)
def load_institucional():
    engine = get_db()
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM articles")).scalar() or 0
        fontes = conn.execute(text("SELECT COUNT(*) FROM sources WHERE active = 1")).scalar() or 0
    return {"total": total, "fontes": fontes}


# --- Header ---
st.markdown("""
<div style="
    background: linear-gradient(135deg, #1a3a5c 0%, #1e6091 100%);
    border-radius: 14px;
    padding: 28px 36px;
    margin-bottom: 12px;
">
    <div style="font-size: 2rem; font-weight: 800; color: #ffffff; margin-bottom: 10px; line-height: 1.2;">
        🔭 Observatório de Manaus
    </div>
    <div style="font-size: 0.95rem; color: #bfdbfe; line-height: 1.7; text-align: justify;">
        Uma iniciativa do <strong style="color:#ffffff;">Laboratório de Sistemas Inteligentes (LSI)</strong>
        da Universidade do Estado do Amazonas (UEA). Monitora automaticamente notícias sobre Manaus
        e o Amazonas a partir de mais de 50 fontes (portais, blogs, canais do YouTube e órgãos públicos),
        com monitoramento contínuo e atualização automática.
    </div>
</div>
""", unsafe_allow_html=True)

# Descadastro de e-mail via token (link do boletim)
_unsubscribe_token = st.query_params.get("token", "")
if _unsubscribe_token:
    _ok, _msg = unsubscribe_by_token(_unsubscribe_token)
    if _ok:
        st.success(_msg)
    else:
        st.error(_msg)
    st.query_params.clear()

try:
    panorama = load_panorama()
    latest = load_latest()
    institucional = load_institucional()
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados: {e}")
    st.stop()

# --- Panorama atual ---
st.markdown(
    "<div style='display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-top:4px;'>"
    "<span style='font-size:1.4rem;font-weight:700;color:#1a3a5c;'>🌅 Panorama atual de Manaus</span>"
    "<span style='font-size:0.8rem;color:#64748b;background:#f1f5f9;border:1px solid #e2e8f0;"
    "border-radius:12px;padding:2px 10px;'>Últimas 24 horas · Todos os temas · Todos os portais</span>"
    "</div>",
    unsafe_allow_html=True,
)
st.write("")

render_summary_card(get_db())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Notícias nas últimas 24h", fmt_br(panorama["noticias"]))
c2.metric("Temas em destaque", panorama["temas"])
c3.metric("Portais consultados", panorama["portais"])
if panorama["ultima"]:
    _ultima_manaus = pd.Timestamp(panorama["ultima"]) - pd.Timedelta(hours=4)
    c4.metric("Atualizado às", _ultima_manaus.strftime("%H:%M"))

st.divider()

# --- Últimas notícias ---
st.subheader("Últimas notícias")
for _, row in latest.iterrows():
    date_str = row["published_manaus"].strftime("%d/%m/%Y %H:%M")
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

st.page_link("pages/1_Explorar_o_Acervo.py", label="Ver todas as notícias →", icon="🔎")

st.divider()

# --- Receba as notícias ---
st.subheader("📬 Receba as notícias de Manaus")
col_wa, col_mail = st.columns(2)

with col_wa:
    st.markdown(f"""
<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:18px 22px;height:100%;">
    <div style="font-weight:700;color:#166534;margin-bottom:6px;">💬 Pelo WhatsApp</div>
    <div style="font-size:0.9rem;color:#374151;line-height:1.6;margin-bottom:12px;">
        Converse com o bot do Observatório: peça o resumo do dia ou
        escolha um tema específico, na hora que quiser.
    </div>
    <a href="{WHATSAPP_URL}" target="_blank" rel="noopener" style="
        display:inline-block;background:#25D366;color:#fff;font-weight:600;
        padding:8px 18px;border-radius:8px;text-decoration:none;font-size:0.9rem;">
        Abrir conversa no WhatsApp
    </a>
</div>
""", unsafe_allow_html=True)

with col_mail:
    st.markdown(
        "<div style='font-weight:700;color:#1e40af;margin-bottom:6px;'>📧 Por e-mail</div>"
        "<div style='font-size:0.9rem;color:#374151;line-height:1.6;'>"
        "Assine o boletim diário e receba os principais acontecimentos toda manhã.</div>",
        unsafe_allow_html=True,
    )
    with st.form("subscribe_form", clear_on_submit=True):
        email_input = st.text_input("Seu e-mail", placeholder="voce@email.com", label_visibility="collapsed")
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

# --- Rodapé institucional ---
st.divider()
st.markdown(
    f"<div style='text-align:center;color:#64748b;font-size:0.88rem;padding:6px 0 2px 0;'>"
    f"Desde o início do projeto, o Observatório já analisou "
    f"<strong>{fmt_br(institucional['total'])}</strong> notícias de "
    f"<strong>{institucional['fontes']}</strong> fontes monitoradas.</div>",
    unsafe_allow_html=True,
)

# --- Admin (acessível apenas via ?admin=1) ---
if st.query_params.get("admin") == "1":
    st.sidebar.header("⚙️ Admin")
    admin_pwd = st.sidebar.text_input("Senha", type="password", key="admin_pwd")
    if admin_pwd == os.getenv("ADMIN_PASSWORD", "obs@manaus"):
        if st.sidebar.button("↻ Limpar cache de dados"):
            st.cache_data.clear()
            st.rerun()
        if st.sidebar.button("📤 Disparar digest agora (teste)", type="primary"):
            _sendgrid_key = os.getenv("SENDGRID_API_KEY", "")
            _brevo_key = os.getenv("BREVO_API_KEY", "")

            if _sendgrid_key:
                _provider = "Sendgrid"
                _from = os.getenv("SENDGRID_FROM_EMAIL", "")
                st.sidebar.caption(f"📧 Provedor: {_provider} | De: `{_from}`")
            elif _brevo_key:
                _provider = "Brevo"
                _from = os.getenv("BREVO_SENDER_EMAIL", "")
                st.sidebar.caption(f"📧 Provedor: {_provider} | De: `{_from}`")
            else:
                st.sidebar.error("Nenhum provedor de email configurado (SENDGRID_API_KEY ou BREVO_API_KEY).")

            if _sendgrid_key or _brevo_key:
                with st.spinner(f"Enviando via {_provider}..."):
                    try:
                        sent = run_digest(force=True, min_summaries=1)
                        st.sidebar.success(f"✓ Digest enviado para {sent} assinante(s).")
                    except Exception as _e:
                        err_str = str(_e).lower()
                        if "timeout" in err_str:
                            st.sidebar.error(f"⏱️ Timeout: Verifique credenciais ou conectividade.\n\nErro: {_e}")
                        elif "not configured" in err_str:
                            st.sidebar.error(f"⚙️ Provedor não configurado corretamente.\n\nErro: {_e}")
                        else:
                            st.sidebar.error(f"❌ Erro ao enviar: {_e}")
    elif admin_pwd:
        st.sidebar.error("Senha incorreta.")
