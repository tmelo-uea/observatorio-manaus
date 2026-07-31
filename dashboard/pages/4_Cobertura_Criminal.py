import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import text
from db.connection import get_engine
from nlp.crime_types import CRIME_GROUPS, label as tipo_label, legal_ref, group_label

st.set_page_config(
    page_title="Cobertura Criminal — Observatório de Manaus",
    page_icon="⚖️",
    layout="wide",
)

# Cores por grupo (bem jurídico tutelado). Paleta sóbria de propósito: o assunto
# não pede alarme visual, e vermelho saturado em tudo prejudica a leitura.
GROUP_COLORS = {
    "vida":                  "#8e3b46",
    "integridade":           "#b5651d",
    "liberdade":             "#7d6b8a",
    "patrimonio":            "#1e6091",
    "dignidade_sexual":      "#6a4c93",
    "paz_publica":           "#4a6670",
    "fe_publica":            "#7f8c8d",
    "administracao_publica": "#2c6a60",
    "drogas":                "#3a7ca5",
    "armas":                 "#5c5c5c",
    "ambiental":             "#4f772d",
    "transito":              "#c9a227",
    "outras_leis":           "#9a8c98",
    "outros":                "#adb5bd",
}

PERIODOS = {
    "Últimos 30 dias": 30,
    "Últimos 90 dias": 90,
    "Últimos 6 meses": 180,
    "Último ano": 365,
}


def fmt_br(n) -> str:
    return f"{int(n):,}".replace(",", ".")


@st.cache_resource
def get_db():
    return get_engine()


@st.cache_data(ttl=300)
def tem_dados() -> bool:
    with get_db().connect() as conn:
        return bool(conn.execute(text("SELECT COUNT(*) FROM crime_mentions")).scalar())


@st.cache_data(ttl=300)
def load_panorama(dias: int, municipio: str | None):
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    filtro = "AND m.municipio = :mun" if municipio else ""
    params = {"ini": inicio}
    if municipio:
        params["mun"] = municipio
    with get_db().connect() as conn:
        row = conn.execute(text(f"""
            SELECT COUNT(*)                       AS mencoes,
                   COUNT(DISTINCT m.crime_type)   AS figuras,
                   COUNT(DISTINCT a.source_id)    AS veiculos,
                   COUNT(DISTINCT m.municipio)    AS municipios
            FROM crime_mentions m
            JOIN articles a ON a.id = m.article_id
            WHERE m.reported_on >= :ini {filtro}
        """), params).fetchone()
    return {
        "mencoes": row[0] or 0,
        "figuras": row[1] or 0,
        "veiculos": row[2] or 0,
        "municipios": row[3] or 0,
    }


@st.cache_data(ttl=300)
def load_serie(dias: int, municipio: str | None) -> pd.DataFrame:
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    filtro = "AND municipio = :mun" if municipio else ""
    params = {"ini": inicio}
    if municipio:
        params["mun"] = municipio
    with get_db().connect() as conn:
        # Agrupa por DIA no banco; a decisão entre dia e semana é tomada depois,
        # em função de quanto período há de fato. Agrupar por semana direto no
        # SQL fazia toda a base recente cair num bucket só, e um gráfico de área
        # com um único ponto por série não desenha nada.
        res = conn.execute(text(f"""
            SELECT reported_on AS dia, crime_group, COUNT(*) AS cnt
            FROM crime_mentions
            WHERE reported_on >= :ini {filtro}
            GROUP BY dia, crime_group
            ORDER BY dia
        """), params)
        return pd.DataFrame(res.fetchall(), columns=res.keys())


@st.cache_data(ttl=300)
def load_ranking(dias: int, municipio: str | None) -> pd.DataFrame:
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    filtro = "AND m.municipio = :mun" if municipio else ""
    params = {"ini": inicio}
    if municipio:
        params["mun"] = municipio
    with get_db().connect() as conn:
        res = conn.execute(text(f"""
            SELECT m.crime_type, m.crime_group,
                   COUNT(*)                   AS mencoes,
                   COUNT(DISTINCT m.event_id) AS casos
            FROM crime_mentions m
            WHERE m.reported_on >= :ini {filtro}
            GROUP BY m.crime_type, m.crime_group
            ORDER BY mencoes DESC
        """), params)
        return pd.DataFrame(res.fetchall(), columns=res.keys())


@st.cache_data(ttl=300)
def load_zonas(dias: int) -> pd.DataFrame:
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    with get_db().connect() as conn:
        res = conn.execute(text("""
            SELECT zona, crime_group, COUNT(*) AS cnt
            FROM crime_mentions
            WHERE reported_on >= :ini AND zona IS NOT NULL
            GROUP BY zona, crime_group
        """), {"ini": inicio})
        return pd.DataFrame(res.fetchall(), columns=res.keys())


@st.cache_data(ttl=300)
def load_municipios() -> list[str]:
    with get_db().connect() as conn:
        rows = conn.execute(text("""
            SELECT municipio, COUNT(*) c FROM crime_mentions
            WHERE municipio IS NOT NULL
            GROUP BY municipio ORDER BY c DESC LIMIT 30
        """)).fetchall()
    return [r[0] for r in rows]


@st.cache_data(ttl=300)
def load_caracterizacao(dias: int) -> dict:
    """Números sobre o próprio método: quanto a imprensa tipifica e quanto data."""
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    with get_db().connect() as conn:
        row = conn.execute(text("""
            SELECT SUM(legal_cited_by_source = 1), COUNT(legal_cited_by_source),
                   COUNT(*), SUM(occurred_precision = 'dia')
            FROM crime_mentions WHERE reported_on >= :ini
        """), {"ini": inicio}).fetchone()
    return {"citam": int(row[0] or 0), "com_info": int(row[1] or 0),
            "total": int(row[2] or 0), "com_dia": int(row[3] or 0)}


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
                   m.tentativa,
                   m.occurred_on           AS data_do_fato,
                   m.occurred_precision    AS precisao_da_data,
                   m.municipio, m.zona, m.bairro,
                   m.count_people          AS envolvidos,
                   m.description           AS descricao_extraida,
                   COALESCE(NULLIF(a.content, ''), NULLIF(a.summary, ''),
                            NULLIF(a.transcript, '')) AS texto_da_materia,
                   m.legal_cited_by_source AS materia_cita_lei,
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
    # Vazio significa que o modelo não se pronunciou — diferente de "consumado".
    df["tentativa"] = df["tentativa"].map({1: "tentado", 0: "consumado"})

    # A data sai formatada conforme a precisão declarada. Guardamos internamente
    # 2025-01-01 com precisão "ano" para preservar o ano, mas exportar isso cru
    # faz 1º de janeiro parecer o dia do crime — uma auditoria leu exatamente
    # assim. Aqui "2025" é ano, "2025-10" é mês e a data cheia só aparece quando
    # a matéria realmente permitiu datar até o dia.
    def _data_por_precisao(row):
        d, prec = row["data_do_fato"], row["precisao_da_data"]
        if d is None or prec not in ("dia", "mes", "ano"):
            return ""
        if prec == "dia":
            return d.strftime("%Y-%m-%d")
        if prec == "mes":
            return d.strftime("%Y-%m")
        return d.strftime("%Y")
    df["data_do_fato"] = df.apply(_data_por_precisao, axis=1)

    # Texto da matéria, para conferir sem depender de o link abrir. Os feeds
    # vindos do Google News guardam URL de redirecionamento que muitas vezes não
    # resolve — numa avaliação de 50 registros, 46 ficaram inverificáveis por
    # isso. Sem tags HTML e sem quebras de linha, para não estourar a planilha.
    df["texto_da_materia"] = (
        df["texto_da_materia"].fillna("")
        .str.replace(r"<[^>]+>", " ", regex=True)
        .str.replace(r"&[a-z]+;|&#\d+;", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip().str.slice(0, 1500)
    )
    return df


@st.cache_data(ttl=120)
def load_amostra(n: int = 10) -> pd.DataFrame:
    with get_db().connect() as conn:
        res = conn.execute(text("""
            SELECT m.id, m.crime_type, m.stage, m.tentativa, m.occurred_on, m.occurred_precision,
                   m.reported_on, m.municipio, m.zona, m.bairro, m.count_people,
                   m.description, m.legal_ref, m.legal_cited_by_source,
                   m.event_id, a.title, a.url, s.name AS fonte
            FROM crime_mentions m
            JOIN articles a ON a.id = m.article_id
            JOIN sources s  ON s.id = a.source_id
            ORDER BY RAND()
            LIMIT :n
        """), {"n": n})
        return pd.DataFrame(res.fetchall(), columns=res.keys())


# ---------------------------------------------------------------- cabeçalho

st.title("⚖️ Cobertura Criminal")
st.caption(
    "Quanto e como a imprensa do Amazonas noticia crimes. Esta página acompanha, ao "
    "longo do tempo, quais crimes aparecem nas notícias, em que parte da cidade e com "
    "que intensidade cada caso é coberto."
)

st.markdown("""
<div style="background:#fdf6e3;border-left:4px solid #b5651d;border-radius:8px;
            padding:14px 20px;margin:6px 0 18px 0;">
    <div style="font-weight:700;color:#7c4a03;font-size:0.92rem;margin-bottom:4px;">
        O que estes números são — e o que não são
    </div>
    <div style="color:#5b4636;line-height:1.6;font-size:0.9rem;">
        Estes dados medem a <b>cobertura da imprensa</b>, não a criminalidade real.
        Crimes que não viraram notícia não aparecem aqui, e um mesmo crime muito
        noticiado pesa mais do que um crime pouco noticiado. Portanto os gráficos
        respondem <i>"o que a imprensa publicou"</i>, e nunca <i>"quantos crimes
        aconteceram"</i>. Para estatística criminal oficial, consulte a Secretaria de
        Segurança Pública do Amazonas.
    </div>
</div>
""", unsafe_allow_html=True)

if not tem_dados():
    st.info(
        "A extração ainda não produziu registros. Os dados começam a aparecer no "
        "próximo ciclo do coletor, e o histórico é preenchido pelo backfill."
    )
    st.stop()

col_f1, col_f2 = st.columns([1, 1])
with col_f1:
    periodo_nome = st.selectbox("Período", list(PERIODOS), index=1)
with col_f2:
    municipios = load_municipios()
    escolha_mun = st.selectbox("Município", ["Todos"] + municipios, index=0)

dias = PERIODOS[periodo_nome]
municipio = None if escolha_mun == "Todos" else escolha_mun

# ---------------------------------------------------------------- panorama

pan = load_panorama(dias, municipio)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Matérias sobre crime", fmt_br(pan["mencoes"]))
c2.metric("Figuras penais distintas", fmt_br(pan["figuras"]))
c3.metric("Veículos", fmt_br(pan["veiculos"]))
c4.metric("Municípios", fmt_br(pan["municipios"]))

st.caption(
    "Cada matéria que noticia um crime gera um registro. Matérias diferentes sobre "
    "o mesmo caso ainda são contadas separadamente — o agrupamento por ocorrência "
    "está em desenvolvimento e é descrito na metodologia."
)

st.divider()

# ---------------------------------------------------------------- série temporal

st.subheader("Evolução da cobertura")
st.caption("Matérias publicadas ao longo do tempo, agrupadas pelo bem jurídico protegido.")

df_serie = load_serie(dias, municipio)
if df_serie.empty:
    st.info("Sem dados no período selecionado.")
else:
    df_serie["dia"] = pd.to_datetime(df_serie["dia"])
    span = (df_serie["dia"].max() - df_serie["dia"].min()).days

    # Semana só faz sentido com período suficiente; abaixo disso, dia.
    if span > 60:
        df_serie["periodo"] = df_serie["dia"] - pd.to_timedelta(
            df_serie["dia"].dt.weekday, unit="D")
        unidade, rotulo = "semana", "Matérias por semana"
    else:
        df_serie["periodo"] = df_serie["dia"]
        unidade, rotulo = "dia", "Matérias por dia"

    df_serie = (df_serie.groupby(["periodo", "crime_group"], as_index=False)["cnt"]
                .sum())
    n_periodos = df_serie["periodo"].nunique()
    ordem = df_serie.groupby("crime_group")["cnt"].sum().sort_values(ascending=False)

    # Com poucos períodos, barras empilhadas: área e linha precisam de dois
    # pontos para desenhar, e um período único renderizava um gráfico em branco.
    usar_barra = n_periodos < 4

    fig = go.Figure()
    for grupo in ordem.index:
        gdf = df_serie[df_serie["crime_group"] == grupo].sort_values("periodo")
        cor = GROUP_COLORS.get(grupo, "#95a5a6")
        nome = CRIME_GROUPS.get(grupo, grupo)
        tip = f"<b>{nome}</b><br>%{{x|%d/%m/%Y}}: %{{y}} matérias<extra></extra>"
        if usar_barra:
            fig.add_trace(go.Bar(x=gdf["periodo"], y=gdf["cnt"], name=nome,
                                 marker=dict(color=cor), hovertemplate=tip))
        else:
            fig.add_trace(go.Scatter(
                x=gdf["periodo"], y=gdf["cnt"], name=nome, mode="lines",
                stackgroup="one", line=dict(color=cor, width=0.5),
                hovertemplate=tip))
    fig.update_layout(
        height=400, hovermode="x unified",
        barmode="stack" if usar_barra else None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=80, b=50),
        plot_bgcolor="#fafafa", xaxis_title="", yaxis_title=rotulo,
        xaxis=dict(type="date", tickformat="%d/%m"),
    )
    st.plotly_chart(fig, use_container_width=True)
    if n_periodos < 4:
        st.caption(
            f"Há apenas {n_periodos} dia(s) com registros. A série temporal só "
            "ganha forma conforme a extração cobrir um período maior."
        )

# ---------------------------------------------------------------- ranking

st.subheader("Figuras penais mais noticiadas")
st.caption(
    "Cada barra é um tipo penal, com o dispositivo legal correspondente. "
    "A coluna “casos” desconta a repetição entre veículos."
)

df_rank = load_ranking(dias, municipio)
if df_rank.empty:
    st.info("Sem dados no período selecionado.")
else:
    top = df_rank.head(18).iloc[::-1]
    fig_r = go.Figure(go.Bar(
        x=top["mencoes"],
        y=[tipo_label(t) for t in top["crime_type"]],
        orientation="h",
        marker=dict(color=[GROUP_COLORS.get(g, "#95a5a6") for g in top["crime_group"]]),
        customdata=[[legal_ref(t) or "—", c] for t, c in zip(top["crime_type"], top["casos"])],
        hovertemplate="<b>%{y}</b><br>%{x} matérias<br>%{customdata[1]} casos distintos"
                      "<br>%{customdata[0]}<extra></extra>",
    ))
    fig_r.update_layout(
        height=max(360, 22 * len(top)), margin=dict(l=10, r=40, t=20, b=40),
        plot_bgcolor="#fafafa", xaxis_title="Matérias no período", yaxis_title="",
    )
    st.plotly_chart(fig_r, use_container_width=True)

    with st.expander("Ver tabela completa com a tipificação legal"):
        tabela = pd.DataFrame({
            "Figura penal": [tipo_label(t) for t in df_rank["crime_type"]],
            "Dispositivo": [legal_ref(t) or "—" for t in df_rank["crime_type"]],
            "Grupo": [group_label(g) for g in df_rank["crime_group"]],
            "Matérias": df_rank["mencoes"],
            "Casos distintos": df_rank["casos"],
        })
        st.dataframe(tabela, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- zonas

df_zonas = load_zonas(dias)
if not df_zonas.empty:
    st.subheader("Distribuição por zona de Manaus")
    st.caption(
        "Só entram matérias que citam um bairro identificável. A maioria não cita — "
        "então isto mostra onde a imprensa **localiza** o crime, não onde ele se concentra."
    )
    pivot = df_zonas.pivot_table(index="zona", columns="crime_group",
                                 values="cnt", aggfunc="sum", fill_value=0)
    ordem_z = pivot.sum(axis=1).sort_values(ascending=True).index
    fig_z = go.Figure()
    for grupo in pivot.columns:
        fig_z.add_trace(go.Bar(
            y=ordem_z, x=pivot.loc[ordem_z, grupo], name=CRIME_GROUPS.get(grupo, grupo),
            orientation="h", marker=dict(color=GROUP_COLORS.get(grupo, "#95a5a6")),
            hovertemplate=f"<b>{CRIME_GROUPS.get(grupo, grupo)}</b><br>%{{y}}: %{{x}}<extra></extra>",
        ))
    fig_z.update_layout(
        barmode="stack", height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=40, t=80, b=40),
        plot_bgcolor="#fafafa", xaxis_title="Matérias", yaxis_title="",
    )
    st.plotly_chart(fig_z, use_container_width=True)

# ---------------------------------------------------------------- rodapé

st.divider()

# ---------------------------------------------------------------- rodapé

df_export = load_export()
if not df_export.empty:
    csv = df_export.to_csv(index=False, sep=";").encode("utf-8-sig")
    col_a, col_b = st.columns([1, 3])
    with col_a:
        st.download_button(
            "⬇️ Baixar dados em CSV",
            data=csv,
            file_name=f"cobertura_criminal_{datetime.utcnow():%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_b:
        st.caption(
            f"**{len(df_export)} registros**, um por crime noticiado, com o link da "
            "matéria de origem ao lado da classificação — para conferir linha a linha. "
            "Ponto e vírgula como separador e UTF-8 com BOM, para abrir direto no Excel "
            "sem quebrar acentuação."
        )

with st.expander("📐 Metodologia da análise"):
    st.markdown("""
**O que é medido.** O Observatório coleta continuamente as publicações de dezenas de
portais, blogs e canais do Amazonas. Desta análise participam apenas as matérias
classificadas como locais e pertencentes aos temas *Segurança Pública* e
*Justiça e Direito*. Cada matéria desse conjunto é lida por um modelo de linguagem que
responde se ela noticia um crime e, em caso afirmativo, qual figura penal, em que etapa
(fato, investigação, prisão, julgamento ou condenação), quando, onde e quantas pessoas
estavam envolvidas. Cerca de metade do que é publicado sob o tema *Segurança Pública*
não trata de crime — incêndio, acidente, resgate, treinamento de bombeiros — e é
descartada nessa leitura.

**Unidade de análise.** A unidade primária é a *matéria*, não o crime. Isso é
deliberado: o objeto de estudo é a cobertura jornalística, e só é possível observar o
que foi publicado. Uma operação policial com doze prisões por tráfico conta como uma
matéria, com o número de envolvidos registrado à parte. Uma matéria só gera mais de um
registro se noticiar crimes de tipos diferentes.

**Agrupamento por caso — em desenvolvimento, atualmente desligado.** Um mesmo crime
costuma ser noticiado por vários veículos, e distinguir *"vinte crimes noticiados uma
vez cada"* de *"um crime noticiado vinte vezes"* é uma pergunta central sobre a
imprensa. A primeira versão do agrupamento não conseguia fundir registros quando a
matéria não nomeava pessoas — o que é a regra no noticiário policial brasileiro — e
produzia praticamente um caso por matéria. Como isso levava a página a afirmar que não
há repetição de cobertura, o que é falso, o agrupamento foi desativado até ser
refeito. **Enquanto isso, cada matéria conta como um registro, e o total NÃO deve ser
lido como número de crimes distintos.**

**Classificação legal.** As categorias correspondem a figuras do Código Penal e da
legislação penal especial, organizadas pelos Títulos do Código — o bem jurídico
protegido. Sempre que o fato configura uma figura autônoma, ela é preferida à genérica:
feminicídio em vez de homicídio, latrocínio em vez de roubo. O dispositivo legal
exibido **não é gerado pelo modelo**: vem de uma tabela fixa associada a cada categoria,
o que evita citações de artigos inventadas. Registra-se separadamente se a própria
matéria mencionou o enquadramento jurídico — isso é característica do texto
jornalístico, não do crime.

**Datas.** O sistema guarda duas datas: a da publicação e a do fato. A distinção
importa — uma nota divulgada hoje sobre a condenação de um crime de anos atrás é
cobertura de hoje sobre um fato antigo. Junto com a data do fato guarda-se até onde a
matéria permite datá-lo: dia, mês ou apenas ano. Quando o texto diz somente "em 2019",
registra-se o ano, que é informação real, em vez de o sistema inventar um dia. Os
gráficos de evolução usam a data de **publicação**, porque medem cobertura.

**Localização.** O bairro é extraído do texto quando citado, e a zona da cidade é
derivada dele pela divisão oficial da Lei Municipal nº 1.401/2010, que reconhece 64
bairros em seis zonas administrativas. Os 62 municípios do Amazonas vêm do IBGE, e
crime ocorrido fora deles é descartado. A maioria das matérias não informa bairro, de
modo que a distribuição geográfica descreve onde a imprensa *localiza* os fatos.

**Limitações conhecidas.**
- Crimes que não viraram notícia são invisíveis para o método.
- Veículos com maior volume de publicação pesam mais no resultado.
- A classificação é automática e contém erros; a amostra de verificação abaixo permite
  estimar a taxa de acerto.
- As referências legais aguardam revisão de especialista em Direito.
""")

    car = load_caracterizacao(dias)
    if car["total"]:
        pct_lei = (100 * car["citam"] / car["com_info"]) if car["com_info"] else 0
        pct_dia = 100 * car["com_dia"] / car["total"]
        m1, m2, m3 = st.columns(3)
        m1.metric("Matérias analisadas", fmt_br(car["total"]), help=periodo_nome)
        m2.metric("Citam o enquadramento jurídico", f"{pct_lei:.0f}%",
                  help="Nomeiam a figura penal ou o artigo de lei")
        m3.metric("Datam o fato até o dia", f"{pct_dia:.0f}%",
                  help="Nas demais, a matéria não permite precisão de dia")
        st.caption(
            "Estes três números descrevem o texto jornalístico, não a criminalidade: "
            "dizem com que frequência a imprensa local tipifica juridicamente o que "
            "noticia e com que precisão data os fatos."
        )

    st.divider()
    st.markdown("**Amostra de verificação** — comparar a extração com a matéria original")
    st.caption(
        "Dez registros sorteados aleatoriamente, com a matéria original ao lado. "
        "Serve para conferir se a leitura automática corresponde ao que o texto diz."
    )
    if st.button("Sortear outra amostra"):
        load_amostra.clear()
    for _, r in load_amostra().iterrows():
        st.markdown(f"**[{r['title']}]({r['url']})**  \n*{r['fonte']}*")
        st.dataframe(pd.DataFrame({
            "Campo": ["Figura penal", "Dispositivo", "Etapa", "Tentado?", "Data do fato",
                      "Precisão da data", "Publicação", "Município", "Zona",
                      "Bairro", "Envolvidos", "Matéria cita enquadramento",
                      "Caso agrupado"],
            "Extraído": [
                tipo_label(r["crime_type"]), r["legal_ref"] or "—", r["stage"],
                {1: "tentado", 0: "consumado"}.get(r["tentativa"], "—"),
                r["occurred_on"] or "não informada",
                r["occurred_precision"] or "—", r["reported_on"],
                r["municipio"] or "—", r["zona"] or "—", r["bairro"] or "—",
                r["count_people"] if r["count_people"] is not None else "—",
                {1: "sim", 0: "não"}.get(r["legal_cited_by_source"], "—"),
                f"#{r['event_id']}" if r["event_id"] else "—",
            ],
        }), use_container_width=True, hide_index=True)
        st.caption(f"Descrição extraída: {r['description']}")
        st.divider()

st.caption(
    "Observatório de Manaus — LSI/UEA. Dados atualizados automaticamente a cada 30 minutos."
)
