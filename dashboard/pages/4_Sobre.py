import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from sqlalchemy import text
from db.connection import get_engine

st.set_page_config(page_title="Sobre — Observatório de Manaus", page_icon="ℹ️", layout="wide")

st.title("ℹ️ Sobre o Observatório de Manaus")

# --- Apresentação ---
st.markdown("""
## O que é o Observatório de Manaus?

O **Observatório de Manaus** é uma plataforma de monitoramento contínuo de notícias e publicações
sobre a cidade de Manaus e o estado do Amazonas. A plataforma coleta, organiza e disponibiliza
de forma pública e gratuita o que é publicado nos principais portais e blogs de notícias da região.

A iniciativa nasce da compreensão de que o acesso organizado à informação é um instrumento
fundamental para a cidadania, a pesquisa acadêmica e a tomada de decisão baseada em evidências.
""")

st.divider()

# --- Como funciona ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
### Como funciona?

- **Coleta automática** a cada 30 minutos de portais e blogs locais via RSS
- **Classificação por temas** usando Processamento de Linguagem Natural (PLN)
- **Atualização contínua** sem intervenção humana
- **Código aberto** disponível no GitHub

Os dados coletados incluem título, resumo, fonte e data de publicação de cada notícia.
O conteúdo original permanece nos portais de origem — o Observatório apenas indexa e organiza.
""")

with col2:
    st.markdown("""
### Para quem é?

- **Cidadãos** que querem acompanhar o que acontece em Manaus em um só lugar
- **Pesquisadores e acadêmicos** que precisam de dados sobre cobertura midiática local
- **Jornalistas e comunicadores** que desejam identificar tendências e lacunas na cobertura
- **Gestores públicos** interessados em como os temas urbanos são tratados pela imprensa
- **Estudantes** que estudam comunicação, ciências sociais e políticas públicas
""")

st.divider()

# --- Estatísticas ao vivo ---
st.markdown("### Números do Observatório")

try:
    engine = get_engine()
    with engine.connect() as conn:
        total_articles = conn.execute(text("SELECT COUNT(*) FROM articles")).scalar()
        total_sources = conn.execute(text("SELECT COUNT(*) FROM sources WHERE active = 1")).scalar()
        total_topics = conn.execute(text("SELECT COUNT(*) FROM topics WHERE slug != 'outros'")).scalar()
        oldest = conn.execute(text("SELECT MIN(published_at) FROM articles WHERE published_at IS NOT NULL")).scalar()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Notícias coletadas", f"{total_articles:,}")
    c2.metric("Fontes monitoradas", total_sources)
    c3.metric("Temas classificados", total_topics)
    c4.metric("Monitorando desde", oldest.strftime("%d/%m/%Y") if oldest else "—")
except Exception:
    pass

st.divider()

# --- Fontes monitoradas ---
st.markdown("### Fontes monitoradas")

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

    col_p, col_b = st.columns(2)
    with col_p:
        st.markdown("**Portais de notícias**")
        for name, url, total in portais:
            st.markdown(f"- [{name}]({url}) — {total:,} notícias")

    with col_b:
        st.markdown("**Blogs**")
        for name, url, total in blogs:
            st.markdown(f"- [{name}]({url}) — {total:,} notícias")
except Exception:
    pass

st.divider()

# --- Equipe ---
st.markdown("""
### Equipe

O Observatório de Manaus é uma iniciativa do **LSI — Laboratório de Sistemas Inteligentes**
da **Universidade do Estado do Amazonas (UEA)**.

**Coordenação:** Tiago Eugenio de Melo
**Equipe:** Elloá Guedes, Carlos Maurício, Fábio Santos
**Contato:** tmelo@uea.edu.br | resumo@observatorio.manaus.br
""")

st.divider()

# --- Sobre o LSI ---
st.markdown("""
### Sobre o LSI

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

**Links úteis:**
- [Diretório de Laboratórios — UEA](https://dirlab.uea.edu.br/publico/view/217/)
- [Grupo de Pesquisa — CNPq](http://dgp.cnpq.br/dgp/espelhogrupo/358110)
- [LSI no YouTube](https://www.youtube.com/watch?v=up-c4irUINc)
""")

st.divider()

# --- Código aberto ---
st.markdown("""
### Código aberto

O código-fonte do Observatório de Manaus está disponível publicamente no GitHub:

🔗 [github.com/tmelo-uea/observatorio-manaus](https://github.com/tmelo-uea/observatorio-manaus)

Contribuições, sugestões e relatos de problemas são bem-vindos.
""")
