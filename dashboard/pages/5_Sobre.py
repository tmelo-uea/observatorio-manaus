import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from sqlalchemy import text
from db.connection import get_engine

st.set_page_config(page_title="Sobre — Observatório de Manaus", page_icon="ℹ️", layout="wide")


def _num(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    background: linear-gradient(135deg, #1a3a5c 0%, #1e6091 100%);
    border-radius: 16px;
    padding: 36px 40px;
    margin-bottom: 26px;
">
    <div style="font-size: 2rem; font-weight: 800; color: #ffffff; margin-bottom: 12px; line-height: 1.2;">
        ℹ️ Sobre o Observatório de Manaus
    </div>
    <div style="font-size: 1.02rem; color: #e0ecf7; line-height: 1.8; text-align: justify;">
        O <strong style="color:#ffffff;">Observatório de Manaus</strong> é uma plataforma de monitoramento
        contínuo de notícias e publicações sobre a cidade de Manaus e o estado do Amazonas. Coleta, organiza
        e disponibiliza de forma pública e gratuita o que é publicado nos principais portais e blogs da região.
        A iniciativa nasce da compreensão de que o acesso organizado à informação é um instrumento fundamental
        para a cidadania, a pesquisa acadêmica e a tomada de decisão baseada em evidências.
    </div>
</div>
""", unsafe_allow_html=True)


# ── Estatísticas ao vivo ──────────────────────────────────────────────────────
try:
    engine = get_engine()
    with engine.connect() as conn:
        total_articles = conn.execute(text("SELECT COUNT(*) FROM articles")).scalar()
        total_sources = conn.execute(text("SELECT COUNT(*) FROM sources WHERE active = 1")).scalar()
        total_topics = conn.execute(text("SELECT COUNT(*) FROM topics WHERE slug != 'outros'")).scalar()
        oldest = conn.execute(text("SELECT MIN(collected_at) FROM articles")).scalar()

    stats = [
        ("📰", _num(total_articles), "notícias coletadas"),
        ("📡", _num(total_sources), "fontes monitoradas"),
        ("🏷️", _num(total_topics), "temas classificados"),
        ("📅", oldest.strftime("%d/%m/%Y") if oldest else "—", "monitorando desde"),
    ]
    cards = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:8px;">'
    for icon, big, label in stats:
        cards += (
            '<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-radius:12px;'
            'padding:20px 18px;text-align:center;">'
            f'<div style="font-size:1.6rem;margin-bottom:6px;">{icon}</div>'
            f'<div style="font-size:1.7rem;font-weight:800;color:#1a3a5c;line-height:1.1;">{big}</div>'
            f'<div style="font-size:0.85rem;color:#6c757d;margin-top:6px;'
            f'text-transform:uppercase;letter-spacing:0.03em;">{label}</div>'
            '</div>'
        )
    cards += '</div>'
    st.markdown(cards, unsafe_allow_html=True)
    st.caption("Números atualizados em tempo real, direto do banco de dados.")
except Exception:
    pass

st.divider()


# ── Como funciona / Para quem é ───────────────────────────────────────────────
def _info_card(title: str, items: list[str], accent: str) -> str:
    lis = "".join(
        f'<li style="margin-bottom:8px;line-height:1.5;">{it}</li>' for it in items
    )
    return (
        f'<div style="background:#ffffff;border:1px solid #e5e7eb;border-left:5px solid {accent};'
        f'border-radius:12px;padding:22px 26px;height:100%;">'
        f'<div style="font-size:1.15rem;font-weight:700;color:#1a3a5c;margin-bottom:14px;">{title}</div>'
        f'<ul style="margin:0;padding-left:20px;color:#374151;font-size:0.95rem;">{lis}</ul>'
        '</div>'
    )


col1, col2 = st.columns(2)
with col1:
    st.markdown(_info_card(
        "⚙️ Como funciona",
        [
            "<strong>Coleta automática</strong> a cada 30 minutos de portais e blogs locais via RSS",
            "<strong>Classificação por temas</strong> usando Processamento de Linguagem Natural (PLN)",
            "<strong>Resumos diários</strong> gerados automaticamente por inteligência artificial",
            "<strong>Atualização contínua</strong>, sem intervenção humana",
            "<strong>Código aberto</strong>, disponível no GitHub",
        ],
        "#1e6091",
    ), unsafe_allow_html=True)
    st.caption(
        "Coletamos título, resumo, fonte e data de cada notícia. O conteúdo original "
        "permanece nos portais de origem — o Observatório apenas indexa e organiza."
    )

with col2:
    st.markdown(_info_card(
        "👥 Para quem é",
        [
            "<strong>Cidadãos</strong> que querem acompanhar Manaus em um só lugar",
            "<strong>Pesquisadores e acadêmicos</strong> que precisam de dados sobre cobertura midiática local",
            "<strong>Jornalistas e comunicadores</strong> que buscam tendências e lacunas na cobertura",
            "<strong>Gestores públicos</strong> interessados em como os temas urbanos são tratados pela imprensa",
            "<strong>Estudantes</strong> de comunicação, ciências sociais e políticas públicas",
        ],
        "#27ae60",
    ), unsafe_allow_html=True)

st.divider()


# ── Fontes monitoradas ────────────────────────────────────────────────────────
st.markdown("### 📡 Fontes monitoradas")

try:
    with engine.connect() as conn:
        sources = conn.execute(text("""
            SELECT s.name, s.url, s.type, COUNT(a.id) AS total
            FROM sources s
            LEFT JOIN articles a ON a.source_id = s.id
            WHERE s.active = 1
            GROUP BY s.id, s.name, s.url, s.type
            ORDER BY total DESC
        """)).fetchall()

    portais = [(s.name, s.url, s.total) for s in sources if s.type == "portal"]
    blogs   = [(s.name, s.url, s.total) for s in sources if s.type == "blog"]
    outras  = [(s.name, s.url, s.total) for s in sources if s.type not in ("portal", "blog")]

    st.caption(
        f"{len(sources)} fontes ativas no momento. Veja quantas notícias cada uma já contribuiu."
    )

    def _source_list(title: str, items: list) -> None:
        if not items:
            return
        st.markdown(f"**{title}**")
        for name, url, total in items:
            st.markdown(f"- [{name}]({url}) &nbsp;·&nbsp; <span style='color:#6c757d;'>{_num(total)} notícias</span>",
                        unsafe_allow_html=True)

    col_p, col_b = st.columns(2)
    with col_p:
        _source_list("Portais de notícias", portais)
    with col_b:
        _source_list("Blogs", blogs)
        _source_list("Outras fontes", outras)
except Exception:
    pass

st.divider()


# ── Equipe ────────────────────────────────────────────────────────────────────
st.markdown("### 👤 Equipe")
st.markdown("""
<div style="background:#f8f9fa;border:1px solid #e5e7eb;border-radius:12px;padding:22px 26px;">
    <div style="font-size:0.95rem;color:#374151;line-height:1.9;">
        Uma iniciativa do <strong>LSI — Laboratório de Sistemas Inteligentes</strong>
        da <strong>Universidade do Estado do Amazonas (UEA)</strong>.<br>
        <strong>Coordenação:</strong> Tiago Eugenio de Melo<br>
        <strong>Equipe:</strong> Elloá Guedes, Carlos Maurício, Fábio Santos<br>
        <strong>Contato:</strong>
        <a href="mailto:tmelo@uea.edu.br">tmelo@uea.edu.br</a> ·
        <a href="mailto:resumo@observatorio.manaus.br">resumo@observatorio.manaus.br</a>
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()


# ── Sobre o LSI ───────────────────────────────────────────────────────────────
st.markdown("### 🔬 Sobre o LSI")
st.markdown("""
O **Laboratório de Sistemas Inteligentes (LSI)** da Universidade do Estado do Amazonas,
localizado na Sala A21 da Escola Superior de Tecnologia, congrega pesquisadores e
estudantes das áreas de Computação e afins que desenvolvem soluções de vanguarda para
problemas de domínios diversos utilizando métodos, técnicas e tecnologias da Inteligência
Artificial, Ciência dos Dados e Aprendizagem de Máquina.

Inaugurado em 2018 com recursos oriundos de editais da Fundação de Amparo à Pesquisa
do Estado do Amazonas (FAPEAM), atua em nível de graduação e pós-graduação,
colaborando para o aprimoramento do capital humano existente na região e para o emprego e
aprimoramento de métodos e técnicas inteligentes para o avanço da fronteira do conhecimento.

O LSI dispõe de servidores computacionais de alta capacidade para realização de
experimentos com volumes massivos de dados e oferece infraestrutura física e computacional
para os integrantes do Grupo de Pesquisa em Sistemas Inteligentes desenvolverem suas
atividades, as quais caracterizam-se por orientações de iniciação científica, trabalhos de
conclusão de curso de graduação, pesquisas em nível de mestrado e projetos de pesquisa e
desenvolvimento com parceiros diversos.
""")

lc1, lc2, lc3 = st.columns(3)
lc1.link_button("🏛️ Diretório de Laboratórios — UEA", "https://dirlab.uea.edu.br/publico/view/217/", use_container_width=True)
lc2.link_button("🔗 Grupo de Pesquisa — CNPq", "http://dgp.cnpq.br/dgp/espelhogrupo/358110", use_container_width=True)
lc3.link_button("▶️ LSI no YouTube", "https://www.youtube.com/watch?v=up-c4irUINc", use_container_width=True)

st.divider()


# ── Sobre o INCT TILDIAR ─────────────────────────────────────────────────────
st.markdown("### 🔬 Sobre o INCT TILDIAR")
st.markdown("""
O **INCT TILDIAR** (Instituto Nacional de Ciência e Tecnologia em Inteligência Artificial
Responsável para Linguística Computacional, Tratamento e Disseminação de Informação) é uma
rede nacional de pesquisa, sediada no Departamento de Ciência da Computação da UFMG, que reúne
cerca de 90 pesquisadores e mais de 30 universidades e centros de pesquisa do Brasil e do exterior
para desenvolver algoritmos e soluções que garantam informação confiável e ética, com foco na
língua portuguesa, privacidade e sustentabilidade.

O coordenador do Observatório de Manaus integra essa rede como pesquisador do INCT TILDIAR,
que conta ainda com instituições como UFAM, UFF, UFRGS, UFPA, UFG, UFCG, UFPE, IFG, CEFET-MG
e ICMC, além de parcerias corporativas (IBM, Google, Petrobras, JusBrasil) e institucionais
(TSE, MP-MG, MP-SC).
""")

st.link_button("🔗 tildiar.dcc.ufmg.br", "https://tildiar.dcc.ufmg.br", use_container_width=False)

st.divider()


# ── Código aberto ─────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg, #0d1117 0%, #1f2937 100%);border-radius:12px;
            padding:24px 28px;text-align:center;">
    <div style="font-size:1.2rem;font-weight:700;color:#ffffff;margin-bottom:8px;">
        💻 Código aberto
    </div>
    <div style="font-size:0.95rem;color:#cbd5e1;margin-bottom:16px;">
        Todo o código-fonte do Observatório de Manaus é público.
        Contribuições, sugestões e relatos de problemas são bem-vindos.
    </div>
</div>
""", unsafe_allow_html=True)
_gh1, _gh2, _gh3 = st.columns([1, 2, 1])
with _gh2:
    st.link_button(
        "⭐ github.com/tmelo-uea/observatorio-manaus",
        "https://github.com/tmelo-uea/observatorio-manaus",
        use_container_width=True,
    )

st.markdown(
    "<div style='text-align:center;margin-top:32px;'>"
    "<span style='font-size:0.78rem;color:#9ca3af;'>"
    "© 2026 Observatório de Manaus · LSI/UEA · "
    "<a href='/Privacidade' style='color:#9ca3af;'>Política de Privacidade</a>"
    "</span></div>",
    unsafe_allow_html=True,
)
