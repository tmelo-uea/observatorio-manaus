import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from db.connection import get_engine
from nlp.crime_types import CRIME_GROUPS, label as tipo_label

st.set_page_config(
    page_title="Metodologia — Observatório de Manaus",
    page_icon="📐",
    layout="wide",
)

JANELA_DIAS = 90


@st.cache_resource
def get_db():
    return get_engine()


@st.cache_data(ttl=300)
def tem_dados() -> bool:
    with get_db().connect() as conn:
        return bool(conn.execute(text("SELECT COUNT(*) FROM crime_mentions")).scalar())


@st.cache_data(ttl=300)
def load_cobertura_do_direito(dias: int) -> dict:
    """Quantas matérias citam o enquadramento jurídico — dado sobre a imprensa."""
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    with get_db().connect() as conn:
        row = conn.execute(text("""
            SELECT SUM(legal_cited_by_source = 1), COUNT(legal_cited_by_source),
                   COUNT(*)
            FROM crime_mentions WHERE reported_on >= :ini
        """), {"ini": inicio}).fetchone()
    return {"citam": int(row[0] or 0), "com_info": int(row[1] or 0), "total": int(row[2] or 0)}


@st.cache_data(ttl=300)
def load_precisao_datas(dias: int) -> pd.DataFrame:
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    with get_db().connect() as conn:
        res = conn.execute(text("""
            SELECT COALESCE(occurred_precision, 'não informada') AS precisao,
                   COUNT(*) AS cnt
            FROM crime_mentions WHERE reported_on >= :ini
            GROUP BY precisao ORDER BY cnt DESC
        """), {"ini": inicio})
        return pd.DataFrame(res.fetchall(), columns=res.keys())


@st.cache_data(ttl=300)
def load_export() -> pd.DataFrame:
    """Todas as menções com a matéria de origem, para conferência externa.

    NÃO inclui o campo de nomes próprios: ele existe apenas para agrupar
    menções do mesmo caso e não deve sair numa página pública.
    """
    with get_db().connect() as conn:
        res = conn.execute(text("""
            SELECT m.id                    AS mencao_id,
                   a.title                 AS materia,
                   a.url                   AS link,
                   s.name                  AS veiculo,
                   m.reported_on           AS publicada_em,
                   m.crime_type            AS figura_slug,
                   m.crime_group           AS grupo_slug,
                   m.legal_ref             AS dispositivo_legal,
                   m.stage                 AS etapa,
                   m.occurred_on           AS data_do_fato,
                   m.occurred_precision    AS precisao_da_data,
                   m.municipio, m.zona, m.bairro,
                   m.count_people          AS envolvidos,
                   m.description           AS descricao_extraida,
                   m.legal_cited_by_source AS materia_cita_lei,
                   m.confidence            AS confianca,
                   m.event_id              AS caso_id,
                   m.model                 AS modelo,
                   m.extracted_at          AS extraido_em
            FROM crime_mentions m
            JOIN articles a ON a.id = m.article_id
            JOIN sources s  ON s.id = a.source_id
            ORDER BY m.reported_on DESC, m.id DESC
        """))
        df = pd.DataFrame(res.fetchall(), columns=res.keys())
    if df.empty:
        return df
    df.insert(6, "figura_penal", [tipo_label(s) for s in df["figura_slug"]])
    df.insert(8, "grupo", [CRIME_GROUPS.get(g, g) for g in df["grupo_slug"]])
    df["materia_cita_lei"] = df["materia_cita_lei"].map({1: "sim", 0: "não"})
    return df


@st.cache_data(ttl=120)
def load_amostra(n: int = 10) -> pd.DataFrame:
    with get_db().connect() as conn:
        res = conn.execute(text("""
            SELECT m.id, m.crime_type, m.stage, m.occurred_on, m.occurred_precision,
                   m.reported_on, m.municipio, m.zona, m.bairro, m.count_people,
                   m.description, m.confidence, m.legal_ref, m.legal_cited_by_source,
                   m.event_id, a.title, a.url, s.name AS fonte
            FROM crime_mentions m
            JOIN articles a ON a.id = m.article_id
            JOIN sources s  ON s.id = a.source_id
            ORDER BY RAND()
            LIMIT :n
        """), {"n": n})
        return pd.DataFrame(res.fetchall(), columns=res.keys())


st.title("📐 Metodologia")
st.caption(
    "Como o Observatório produz os dados da página Cobertura Criminal: o que é "
    "medido, como é medido e o que o método não alcança."
)

st.page_link("pages/4_Cobertura_Criminal.py", label="Voltar para Cobertura Criminal", icon="⚖️")

st.divider()

st.markdown("""
### O que é medido

O Observatório coleta continuamente as publicações de dezenas de portais, blogs e
canais do Amazonas. Desta análise participam apenas as matérias classificadas como
locais e pertencentes aos temas *Segurança Pública* e *Justiça e Direito*.

Cada matéria desse conjunto é lida por um modelo de linguagem que responde se ela
noticia um crime e, em caso afirmativo, qual figura penal, em que etapa
(fato, investigação, prisão, julgamento ou condenação), quando, onde e quantas
pessoas estavam envolvidas. Cerca de metade do que é publicado sob o tema
*Segurança Pública* não trata de crime — incêndio, acidente, resgate, treinamento
de bombeiros — e é descartada nessa leitura.

### Unidade de análise

A unidade primária é a **matéria**, não o crime. Isso é deliberado: o objeto de
estudo é a cobertura jornalística, e só é possível observar o que foi publicado.

Uma operação policial com doze prisões por tráfico conta como uma matéria, com o
número de envolvidos registrado à parte. Uma matéria só gera mais de um registro se
noticiar crimes de tipos diferentes.

### Agrupamento por caso

Um mesmo crime costuma ser noticiado por vários veículos. Para distinguir *"vinte
crimes noticiados uma vez cada"* de *"um crime noticiado vinte vezes"* — afirmações
opostas sobre a imprensa —, os registros são agrupados por caso quando coincidem em
tipo penal, município, data aproximada, bairro e pessoas citadas.

O agrupamento é determinístico e revisável: não altera os registros originais e pode
ser recalculado a qualquer momento. Casos duvidosos permanecem separados, de modo que
a contagem de casos distintos é um **limite superior**.

### Classificação legal

As categorias correspondem a figuras do Código Penal e da legislação penal especial,
organizadas pelos Títulos do Código — o bem jurídico protegido. Sempre que o fato
configura uma figura autônoma, ela é preferida à genérica: feminicídio em vez de
homicídio, latrocínio em vez de roubo.

O dispositivo legal exibido **não é gerado pelo modelo**: vem de uma tabela fixa
associada a cada categoria, o que evita citações de artigos inventadas. Registra-se
separadamente se a própria matéria mencionou o enquadramento jurídico — isso é uma
característica do texto jornalístico, não do crime.

### Datas

O sistema guarda duas datas: a da publicação e a do fato. Elas são diferentes, e a
distinção importa — uma nota divulgada hoje sobre a condenação de um crime de anos
atrás é cobertura de hoje sobre um fato antigo.

Junto com a data do fato guarda-se **até onde a matéria permite datá-lo**: dia, mês ou
apenas ano. Quando o texto diz somente "em 2019", registra-se o ano — que é informação
real — e a imprecisão fica anotada, em vez de o sistema inventar um dia. Toda leitura
da data do fato deve considerar esse campo de precisão.

Os gráficos de evolução usam a data de **publicação**, e não a do fato, porque medem
cobertura.

### Localização

O bairro é extraído do texto quando citado, e a zona da cidade é derivada dele pela
divisão oficial da Lei Municipal nº 1.401/2010, que reconhece 64 bairros em seis
zonas administrativas. A maioria das matérias não informa bairro, de modo que a
distribuição geográfica descreve onde a imprensa **localiza** os fatos que noticia.

### Limitações conhecidas

- Crimes que não viraram notícia são invisíveis para o método.
- Veículos com maior volume de publicação pesam mais no resultado.
- A classificação é automática e contém erros. A amostra de verificação abaixo
  permite estimar a taxa de acerto.
- As referências legais aguardam revisão de especialista em Direito.
""")

st.divider()

if not tem_dados():
    st.info("A extração ainda não produziu registros para caracterizar.")
    st.stop()

st.subheader("O método sobre os próprios dados")

leis = load_cobertura_do_direito(JANELA_DIAS)
df_prec = load_precisao_datas(JANELA_DIAS)
pct = (100 * leis["citam"] / leis["com_info"]) if leis["com_info"] else 0
com_dia = int(df_prec.loc[df_prec["precisao"] == "dia", "cnt"].sum()) if not df_prec.empty else 0
pct_dia = (100 * com_dia / leis["total"]) if leis["total"] else 0

c1, c2, c3 = st.columns(3)
c1.metric("Matérias analisadas", f"{leis['total']:,}".replace(",", "."),
          help=f"Últimos {JANELA_DIAS} dias")
c2.metric("Citam o enquadramento jurídico", f"{pct:.0f}%",
          help="Proporção das matérias que nomeiam a figura penal ou o artigo de lei")
c3.metric("Permitem datar o fato até o dia", f"{pct_dia:.0f}%",
          help="Nas demais, a data do fato fica vazia por falta de precisão na fonte")

st.caption(
    "Estes três números descrevem o texto jornalístico, não a criminalidade: dizem "
    "com que frequência a imprensa local tipifica juridicamente o que noticia e com "
    "que precisão data os fatos."
)

st.subheader("Conferir os dados")

df_export = load_export()
if not df_export.empty:
    csv = df_export.to_csv(index=False, sep=";").encode("utf-8-sig")
    col_a, col_b = st.columns([1, 3])
    with col_a:
        st.download_button(
            "⬇️ Baixar CSV",
            data=csv,
            file_name=f"cobertura_criminal_{datetime.utcnow():%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_b:
        st.caption(
            f"**{len(df_export)} registros**, um por crime noticiado, com o link da "
            "matéria de origem ao lado da classificação — feito para conferir linha a "
            "linha. Separado por ponto e vírgula e codificado em UTF-8 com BOM, para "
            "abrir direto no Excel sem quebrar acentuação. O campo interno de nomes "
            "próprios não é exportado."
        )

with st.expander("Amostra de verificação — comparar extração com a matéria original", expanded=True):
    st.caption(
        "Dez registros sorteados aleatoriamente, com a matéria original ao lado. "
        "Serve para conferir se a leitura automática corresponde ao que o texto diz."
    )
    if st.button("Sortear outra amostra"):
        load_amostra.clear()
    amostra = load_amostra()
    for _, r in amostra.iterrows():
        conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "—"
        st.markdown(f"**[{r['title']}]({r['url']})**  \n*{r['fonte']}*")
        detalhes = pd.DataFrame({
            "Campo": ["Figura penal", "Dispositivo", "Etapa", "Data do fato",
                      "Precisão da data", "Publicação", "Município", "Zona",
                      "Bairro", "Envolvidos", "Matéria cita enquadramento",
                      "Confiança", "Caso agrupado"],
            "Extraído": [
                tipo_label(r["crime_type"]), r["legal_ref"] or "—", r["stage"],
                r["occurred_on"] or "não informada",
                r["occurred_precision"] or "—", r["reported_on"],
                r["municipio"] or "—", r["zona"] or "—", r["bairro"] or "—",
                r["count_people"] if r["count_people"] is not None else "—",
                {1: "sim", 0: "não"}.get(r["legal_cited_by_source"], "—"),
                conf, f"#{r['event_id']}" if r["event_id"] else "—",
            ],
        })
        st.dataframe(detalhes, use_container_width=True, hide_index=True)
        st.caption(f"Descrição extraída: {r['description']}")
        st.divider()

st.caption("Observatório de Manaus — LSI/UEA.")
