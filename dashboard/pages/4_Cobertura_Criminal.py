import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import text
from db.connection import get_engine
from nlp.crime_types import CRIME_GROUPS, label as tipo_label, legal_ref, group_label

st.set_page_config(
    page_title="Cobertura Criminal — Observatório de Manaus",
    page_icon="🚔",
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

ZONA_CORES = {
    "Norte":        "#4e79a7",
    "Sul":          "#f28e2b",
    "Leste":        "#59a14f",
    "Oeste":        "#b07aa1",
    "Centro-Sul":   "#edc948",
    "Centro-Oeste": "#76b7b2",
}

# Agregado da cauda de categorias. Definidos no nível do módulo porque são
# usados em três blocos distintos — série, ranking de zonas e mapa.
OUTROS = "__outros__"
COR_OUTROS = "#6b7a82"   # distinto do cinza-claro de "Não classificado"

PERIODOS = {
    "Últimos 30 dias": 30,
    "Últimos 90 dias": 90,
    "Últimos 6 meses": 180,
    "Último ano": 365,
}


def fmt_br(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def texto(md: str) -> None:
    """Parágrafo explicativo, com a mesma tipografia da página de Análises.

    st.markdown puro, e não HTML injetado: pega o corpo padrão do Streamlit
    (1rem), que é o que a página de Análises usa — o helper anterior renderizava
    a 0,95rem, menor que o resto do site. De quebra, o **negrito** volta a
    funcionar: duas vezes um ** acabou dentro do HTML e apareceu como asterisco.
    """
    st.markdown(md)


@st.cache_resource
def get_db():
    return get_engine()


@st.cache_data(ttl=20)
def versao_dados() -> int:
    """Impressão digital da base, usada como chave de cache das demais consultas.

    Sem isto, cada consulta cacheia por 5 min com chave própria, e enquanto o
    backfill grava registros a página pode mostrar fotografias de momentos
    diferentes lado a lado — "últimos 30 dias" chegou a exibir MAIS matérias que
    "últimos 90 dias", porque o número de 90 vinha de um cache anterior. Passando
    esta versão como argumento, todas as consultas invalidam juntas e a página
    fica internamente consistente.
    """
    with get_db().connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM crime_mentions")).scalar() or 0


@st.cache_data(ttl=300)
def tem_dados(versao: int) -> bool:
    with get_db().connect() as conn:
        return bool(conn.execute(text("SELECT COUNT(*) FROM crime_mentions")).scalar())


@st.cache_data(ttl=300)
def load_panorama(versao: int, dias: int, municipio: str | None):
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    filtro = "AND m.municipio = :mun" if municipio else ""
    params = {"ini": inicio}
    if municipio:
        params["mun"] = municipio
    with get_db().connect() as conn:
        row = conn.execute(text(f"""
            SELECT COUNT(DISTINCT m.article_id)   AS materias,
                   COUNT(*)                       AS registros,
                   COUNT(DISTINCT m.crime_type)   AS figuras,
                   COUNT(DISTINCT a.source_id)    AS veiculos,
                   COUNT(DISTINCT m.municipio)    AS municipios
            FROM crime_mentions m
            JOIN articles a ON a.id = m.article_id
            WHERE m.reported_on >= :ini {filtro}
        """), params).fetchone()
    return {
        "materias": row[0] or 0,
        "registros": row[1] or 0,
        "figuras": row[2] or 0,
        "veiculos": row[3] or 0,
        "municipios": row[4] or 0,
    }


@st.cache_data(ttl=300)
def load_serie(versao: int, dias: int, municipio: str | None) -> pd.DataFrame:
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
def load_ranking(versao: int, dias: int, municipio: str | None) -> pd.DataFrame:
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    filtro = "AND m.municipio = :mun" if municipio else ""
    params = {"ini": inicio}
    if municipio:
        params["mun"] = municipio
    with get_db().connect() as conn:
        res = conn.execute(text(f"""
            SELECT m.crime_type, m.crime_group,
                   COUNT(*) AS mencoes
            FROM crime_mentions m
            WHERE m.reported_on >= :ini {filtro}
            GROUP BY m.crime_type, m.crime_group
            ORDER BY mencoes DESC
        """), params)
        return pd.DataFrame(res.fetchall(), columns=res.keys())


@st.cache_data
def carrega_bairros_geojson() -> dict:
    """Polígonos dos bairros de Manaus, com a zona de cada um.

    Montados a partir dos limites do OpenStreetMap: o OSM guarda cada contorno
    em vários trechos de linha abertos, que foram costurados ponta a ponta em
    anéis fechados. Todos fecharam naturalmente, sem emenda forçada.

    São 57 dos 64 bairros oficiais — alguns não estão mapeados na base aberta.
    A divisão em zonas é a da Lei Municipal nº 1.401/2010.
    """
    caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "bairros_manaus.geojson")
    try:
        with open(caminho, encoding="utf8") as fh:
            return json.load(fh)
    except Exception:
        return {}


@st.cache_data
def carrega_centros_zonas() -> dict:
    """Centro aproximado de cada zona, para posicionar o rótulo no mapa."""
    caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "zonas_manaus_centros.json")
    try:
        with open(caminho, encoding="utf8") as fh:
            return json.load(fh)
    except Exception:
        return {}


@st.cache_data(ttl=300)
def load_zonas(versao: int, dias: int, municipio: str | None):
    """Distribuição por zona MAIS o denominador.

    Sem saber quantas matérias puderam ser localizadas, as barras convidam a
    leitura de "distribuição da criminalidade" — que é exatamente o que esta
    página não mede.
    """
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    filtro = "AND municipio = :mun" if municipio else ""
    params = {"ini": inicio}
    if municipio:
        params["mun"] = municipio
    with get_db().connect() as conn:
        res = conn.execute(text(f"""
            SELECT zona, crime_group, COUNT(*) AS cnt
            FROM crime_mentions
            WHERE reported_on >= :ini AND zona IS NOT NULL {filtro}
            GROUP BY zona, crime_group
        """), params)
        df = pd.DataFrame(res.fetchall(), columns=res.keys())
        tot = conn.execute(text(f"""
            SELECT COUNT(*), SUM(zona IS NOT NULL)
            FROM crime_mentions WHERE reported_on >= :ini {filtro}
        """), params).fetchone()
    return df, int(tot[0] or 0), int(tot[1] or 0)


@st.cache_data(ttl=300)
def load_municipios(versao: int) -> list[str]:
    with get_db().connect() as conn:
        rows = conn.execute(text("""
            SELECT municipio, COUNT(*) c FROM crime_mentions
            WHERE municipio IS NOT NULL
            GROUP BY municipio ORDER BY c DESC LIMIT 30
        """)).fetchall()
    return [r[0] for r in rows]


@st.cache_data(ttl=300)
def load_caracterizacao(versao: int, dias: int) -> dict:
    """Números sobre o próprio método: quanto a imprensa tipifica e quanto data.

    Conta REGISTROS, não matérias: uma matéria gera mais de um registro quando
    noticia crimes de tipos diferentes. Rotular linha de tabela como "matéria"
    contradiria a unidade de análise declarada na própria metodologia.
    """
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    with get_db().connect() as conn:
        row = conn.execute(text("""
            SELECT SUM(legal_cited_by_source = 1), COUNT(legal_cited_by_source),
                   COUNT(*), SUM(occurred_precision = 'dia'),
                   COUNT(DISTINCT article_id)
            FROM crime_mentions WHERE reported_on >= :ini
        """), {"ini": inicio}).fetchone()
        # Proporção do tema que NÃO é crime, medida em vez de afirmada de memória
        aval = conn.execute(text("""
            SELECT COUNT(*) FROM articles a
            JOIN topics t ON a.topic_id = t.id
            WHERE a.is_local = 1 AND a.crime_processed_at IS NOT NULL
              AND t.name IN ('Segurança Pública', 'Justiça e Direito')
              AND a.published_at >= :ini
        """), {"ini": inicio}).scalar() or 0
    return {"citam": int(row[0] or 0), "com_info": int(row[1] or 0),
            "total": int(row[2] or 0), "com_dia": int(row[3] or 0),
            "materias": int(row[4] or 0), "avaliados": int(aval)}


# ---------------------------------------------------------------- cabeçalho

st.markdown("""
<div style="
    background: linear-gradient(135deg, #1a3a5c 0%, #1e6091 100%);
    border-radius: 14px;
    padding: 22px 32px;
    margin-bottom: 20px;
">
    <div style="font-size: 1.6rem; font-weight: 800; color: #ffffff; margin-bottom: 8px;">
        🚔 Cobertura Criminal
    </div>
    <div style="font-size: 0.95rem; color: #bfdbfe; line-height: 1.7;">
        Quanto e como a imprensa do Amazonas noticia crimes. Cada matéria de
        <strong style="color:#ffffff;">Segurança Pública</strong> e
        <strong style="color:#ffffff;">Justiça e Direito</strong> é lida automaticamente,
        que identifica a figura penal, a etapa do caso, quando e onde o fato ocorreu.
        A página acompanha, ao longo do tempo, quais crimes aparecem nas notícias, em que
        parte da cidade e com que intensidade cada assunto é coberto.
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background:#fdf6e3;border-left:5px solid #b5651d;border-radius:10px;
            padding:18px 24px;margin:0 0 22px 0;">
    <div style="font-weight:700;color:#7c4a03;font-size:1.02rem;margin-bottom:6px;">
        O que estes números são — e o que não são
    </div>
    <div style="color:#5b4636;line-height:1.7;font-size:0.95rem;">
        Estes dados medem a <b>cobertura da imprensa</b>, não a criminalidade real.
        Crimes que não viraram notícia não aparecem aqui, e um mesmo crime muito
        noticiado pesa mais do que um crime pouco noticiado. Portanto os gráficos
        respondem <i>“o que a imprensa publicou”</i>, e nunca <i>“quantos crimes
        aconteceram”</i>. Para estatística criminal oficial, consulte a Secretaria de
        Segurança Pública do Amazonas.
    </div>
</div>
""", unsafe_allow_html=True)

VERSAO = versao_dados()

if not tem_dados(VERSAO):
    st.info(
        "A extração ainda não produziu registros. Os dados começam a aparecer no "
        "próximo ciclo do coletor, e o histórico é preenchido pelo backfill."
    )
    st.stop()

col_f1, col_f2 = st.columns([1, 1])
with col_f1:
    periodo_nome = st.selectbox("Período", list(PERIODOS), index=1)
with col_f2:
    municipios = load_municipios(VERSAO)
    escolha_mun = st.selectbox("Município", ["Todos"] + municipios, index=0)

dias = PERIODOS[periodo_nome]
municipio = None if escolha_mun == "Todos" else escolha_mun

# ---------------------------------------------------------------- panorama

pan = load_panorama(VERSAO, dias, municipio)
cartoes = [
    ("📰", "Matérias sobre crime", fmt_br(pan["materias"]),
     f'{fmt_br(pan["registros"])} registros classificados'),
    ("⚖️", "Figuras penais distintas", fmt_br(pan["figuras"]), "tipos identificados"),
    ("🗞️", "Veículos", fmt_br(pan["veiculos"]), "portais, blogs e canais"),
    ("📍", "Municípios", fmt_br(pan["municipios"]), "com fato localizado"),
]
html = ('<div style="display:grid;grid-template-columns:repeat(4,1fr);'
        'gap:12px;margin-bottom:10px;">')
for icone, rotulo, valor, sub in cartoes:
    html += (
        '<div style="background:#f8f9fa;border:1px solid #e5e7eb;'
        'border-radius:10px;padding:16px 18px;">'
        f'<div style="font-size:0.75rem;color:#6c757d;text-transform:uppercase;'
        f'letter-spacing:0.04em;margin-bottom:8px;">{icone}&nbsp; {rotulo}</div>'
        f'<div style="font-size:1.2rem;font-weight:700;color:#1a3a5c;'
        f'line-height:1.2;">{valor}</div>'
        f'<div style="font-size:0.85rem;color:#6c757d;margin-top:3px;">{sub}</div>'
        '</div>')
html += '</div>'
st.markdown(html, unsafe_allow_html=True)

texto("Cada matéria que noticia um crime gera um registro. Matérias diferentes sobre "
      "o mesmo caso ainda são contadas separadamente — o agrupamento por ocorrência "
      "está em desenvolvimento e é descrito na metodologia.")

st.divider()

# ---------------------------------------------------------------- série temporal

st.subheader("Evolução da cobertura")
texto(
    "Acompanhe o volume de matérias publicadas ao longo do tempo e a evolução dos "
    "principais grupos da classificação penal. Os dados representam cobertura "
    "jornalística e não correspondem ao número de crimes ou ocorrências distintas."
)

MESES_ABREV = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
               7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}
N_PRINCIPAIS_SERIE = 5

df_serie = load_serie(VERSAO, dias, municipio)
if df_serie.empty:
    st.info("Sem dados no período selecionado.")
else:
    modo_serie = st.radio(
        "Modo da série", ["Volume total", "Principais grupos", "Composição (%)"],
        horizontal=True, label_visibility="collapsed", key="modo_serie")

    df_serie["dia"] = pd.to_datetime(df_serie["dia"])
    # Semana encerrada no domingo. A série é de COBERTURA, então agrega pela
    # data de publicação — data_do_fato diria quando o crime ocorreu, que é
    # outra pergunta.
    df_serie["semana"] = df_serie["dia"].dt.to_period("W-SUN").apply(
        lambda pr: pr.end_time.normalize())

    inicio_janela = pd.Timestamp((datetime.utcnow() - timedelta(hours=4)).date()
                                 - timedelta(days=dias))
    fim_janela = pd.Timestamp((datetime.utcnow() - timedelta(hours=4)).date())

    semanal = df_serie.groupby(["semana", "crime_group"], as_index=False)["cnt"].sum()
    total_sem = semanal.groupby("semana", as_index=False)["cnt"].sum().sort_values("semana")

    # Semana parcial: começa antes do início da janela ou termina depois de hoje.
    def parcial(fim_semana):
        return (fim_semana - pd.Timedelta(days=6)) < inicio_janela or fim_semana > fim_janela
    total_sem["parcial"] = total_sem["semana"].apply(parcial)

    eixo = dict(
        tickvals=list(total_sem["semana"]),
        ticktext=[f"{d.day} {MESES_ABREV[d.month]}" for d in total_sem["semana"]],
    )
    base_layout = dict(
        height=430, margin=dict(l=60, r=30, t=60, b=50), plot_bgcolor="white",
        xaxis=dict(showgrid=False, **eixo),
        yaxis=dict(showgrid=True, gridcolor="#eef2f4", zeroline=False),
        hovermode="x unified",
        legend=dict(orientation="h", traceorder="normal", yanchor="top",
                    y=-0.14, xanchor="left", x=0, font=dict(size=11)),
    )

    if modo_serie == "Volume total":
        st.markdown("#### Evolução do volume de cobertura")
        texto("Quantidade de matérias sobre ocorrências criminais publicadas em cada semana.")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=total_sem["semana"], y=total_sem["cnt"], mode="lines+markers",
            line=dict(color="#1e6091", width=2.5),
            marker=dict(size=[9 if pc else 6 for pc in total_sem["parcial"]],
                        color=["white" if pc else "#1e6091" for pc in total_sem["parcial"]],
                        line=dict(width=2, color="#1e6091")),
            customdata=[["semana parcial" if pc else ""] for pc in total_sem["parcial"]],
            hovertemplate="%{y} matérias %{customdata[0]}<extra></extra>",
            showlegend=False,
        ))
        fig.update_layout(yaxis_title="Matérias por semana", xaxis_title="", **base_layout)
        st.plotly_chart(fig, use_container_width=True)

    else:
        # Cinco maiores no recorte atual; o resto vira "Outros grupos".
        ordem = semanal.groupby("crime_group")["cnt"].sum().sort_values(ascending=False)
        principais = list(ordem.head(N_PRINCIPAIS_SERIE).index)
        semanal["exibicao"] = semanal["crime_group"].where(
            semanal["crime_group"].isin(principais), OUTROS)
        pv = semanal.pivot_table(index="semana", columns="exibicao", values="cnt",
                                 aggfunc="sum", fill_value=0).sort_index()
        colunas = [g for g in principais if g in pv.columns]
        if OUTROS in pv.columns:
            colunas.append(OUTROS)
        pv = pv[colunas]
        tot = pv.sum(axis=1)

        def nome_de(g):
            return "Outros grupos" if g == OUTROS else CRIME_GROUPS.get(g, g)

        def cor_de(g):
            return COR_OUTROS if g == OUTROS else GROUP_COLORS.get(g, "#95a5a6")

        if modo_serie == "Principais grupos":
            st.markdown("#### Evolução dos principais grupos da cobertura criminal")
            texto("Quantidade semanal de matérias nos grupos mais frequentes da classificação "
                  "penal. Clique na legenda para ocultar ou exibir cada linha.")
            fig = go.Figure()
            for g in colunas:
                fig.add_trace(go.Scatter(
                    x=pv.index, y=pv[g], name=nome_de(g), mode="lines",
                    line=dict(color=cor_de(g), width=2.2),
                    hovertemplate="%{y} matérias<extra>" + nome_de(g) + "</extra>",
                ))
            fig.update_layout(yaxis_title="Matérias por semana", xaxis_title="", **base_layout)
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.markdown("#### Composição da cobertura por grupo criminal")
            texto("Participação percentual de cada grupo no total de matérias publicadas em "
                  "cada semana.")
            pct = pv.div(tot.replace(0, 1), axis=0) * 100
            fig = go.Figure()
            for g in colunas:
                fig.add_trace(go.Bar(
                    x=pct.index, y=pct[g], name=nome_de(g),
                    marker=dict(color=cor_de(g)),
                    customdata=list(zip(pv[g], tot)),
                    hovertemplate=("%{customdata[0]} matérias — %{y:.1f}% "
                                   "(total da semana: %{customdata[1]})"
                                   "<extra>" + nome_de(g) + "</extra>"),
                ))
            fig.update_layout(barmode="stack", yaxis_title="% das matérias da semana",
                              xaxis_title="", **base_layout)
            fig.update_yaxes(range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)

    if total_sem["parcial"].any():
        st.caption(
            "Os valores são agregados por semana de publicação, encerrada no domingo. "
            "A primeira e a última semanas do período podem estar incompletas — "
            "aparecem com marcador vazado no modo de volume."
        )

st.subheader("Figuras penais mais noticiadas")
texto(
    "Cada barra é um tipo penal, com o dispositivo legal correspondente. "
    "Matérias diferentes sobre o mesmo caso são contadas separadamente."
)

df_rank = load_ranking(VERSAO, dias, municipio)
if df_rank.empty:
    st.info("Sem dados no período selecionado.")
else:
    top = df_rank.head(18).iloc[::-1]
    fig_r = go.Figure(go.Bar(
        x=top["mencoes"],
        y=[tipo_label(t) for t in top["crime_type"]],
        orientation="h",
        marker=dict(color=[GROUP_COLORS.get(g, "#95a5a6") for g in top["crime_group"]]),
        customdata=[[legal_ref(t) or "—"] for t in top["crime_type"]],
        hovertemplate="<b>%{y}</b><br>%{x} matérias<br>%{customdata[0]}<extra></extra>",
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
        })
        st.dataframe(tabela, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- zonas

df_zonas, zonas_total, zonas_com = load_zonas(VERSAO, dias, municipio)
if not df_zonas.empty:
    st.subheader("Cobertura criminal por zona de Manaus")
    pct_zona = (100 * zonas_com / zonas_total) if zonas_total else 0
    texto(
        f"Das **{fmt_br(zonas_total)} matérias** do período, **{fmt_br(zonas_com)} "
        f"({pct_zona:.0f}%)** informam bairro ou zona. Cada matéria é contada "
        "separadamente; o gráfico mede cobertura jornalística, não número de "
        "ocorrências nem concentração da criminalidade."
    )

    modo = st.radio("Modo de exibição", ["Quantidade", "Composição (%)"],
                    horizontal=True, label_visibility="collapsed", key="modo_zona")

    pivot = df_zonas.pivot_table(index="zona", columns="crime_group",
                                 values="cnt", aggfunc="sum", fill_value=0)

    # Grupos ordenados por volume; a cauda vira "Outros grupos". Onze categorias
    # numa legenda de uma linha ficavam ilegíveis e com cores confundíveis.
    N_PRINCIPAIS = 7
    totais_grupo = pivot.sum().sort_values(ascending=False)
    principais = list(totais_grupo.head(N_PRINCIPAIS).index)
    cauda = [g for g in totais_grupo.index if g not in principais]
    if cauda:
        pivot[OUTROS] = pivot[cauda].sum(axis=1)
        pivot = pivot[principais + [OUTROS]]
    else:
        pivot = pivot[principais]

    totais_zona = pivot.sum(axis=1)
    ordem_z = totais_zona.sort_values(ascending=True).index  # maior no topo

    percentual = modo == "Composição (%)"
    plot = pivot.div(totais_zona.replace(0, 1), axis=0) * 100 if percentual else pivot

    fig_z = go.Figure()
    for grupo in pivot.columns:
        nome = "Outros grupos" if grupo == OUTROS else CRIME_GROUPS.get(grupo, grupo)
        cor = COR_OUTROS if grupo == OUTROS else GROUP_COLORS.get(grupo, "#95a5a6")
        abs_ = pivot.loc[ordem_z, grupo]
        pct = (abs_ / totais_zona[ordem_z].replace(0, 1) * 100)
        fig_z.add_trace(go.Bar(
            y=ordem_z, x=plot.loc[ordem_z, grupo], name=nome, orientation="h",
            marker=dict(color=cor),
            customdata=list(zip(abs_, pct)),
            hovertemplate=(f"<b>{nome}</b><br>%{{y}}: %{{customdata[0]}} matérias"
                           " (%{customdata[1]:.0f}% da zona)<extra></extra>"),
        ))

    # Total ao final de cada barra: dispensa o leitor de estimar pelo eixo.
    if not percentual:
        for zona in ordem_z:
            tot = int(totais_zona[zona])
            share = 100 * tot / max(1, int(totais_zona.sum()))
            fig_z.add_annotation(
                x=tot, y=zona, text=f"<b>{tot}</b> · {share:.0f}%",
                showarrow=False, xanchor="left", xshift=8,
                font=dict(size=11, color="#5b6b73"),
            )

    fig_z.update_layout(
        barmode="stack", height=340,
        # traceorder normal: sem isto o Plotly INVERTE a legenda em barras
        # empilhadas, e ela passa a listar as cores na ordem oposta à dos
        # segmentos — o leitor precisa procurar cada cor de trás para frente.
        legend=dict(orientation="h", traceorder="normal", yanchor="bottom",
                    y=1.02, xanchor="left", x=0, font=dict(size=11)),
        margin=dict(l=10, r=90, t=90, b=40),
        plot_bgcolor="#fafafa", yaxis_title="",
        xaxis_title=("% da cobertura da zona" if percentual
                         else "Matérias com localização identificável"),
        xaxis=dict(range=[0, 100]) if percentual else {},
    )
    st.plotly_chart(fig_z, use_container_width=True)

    # ------------------------------------------------------------------ mapa
    geo = carrega_bairros_geojson()
    centros = carrega_centros_zonas()
    if geo:
        MIN_PARA_PINTAR = 20
        st.markdown("#### Grupo predominante na cobertura criminal por zona")
        texto(
            "A cor indica o grupo mais frequente nas matérias com localização "
            "identificável em cada zona. O mapa representa o perfil da cobertura "
            "jornalística, não a intensidade da criminalidade."
        )

        dominante = {}
        for zona in pivot.index:
            serie = pivot.loc[zona]
            total = int(serie.sum())
            g = serie.idxmax()
            n = int(serie.max())
            sem_amostra = total < MIN_PARA_PINTAR
            dominante[zona] = {
                "slug": None if sem_amostra else g,
                "grupo": ("amostra pequena" if sem_amostra else
                          ("Outros grupos" if g == OUTROS else CRIME_GROUPS.get(g, g))),
                "n": n, "total": total,
                "pct_grupo": 100 * n / max(1, total),
            }

        # A COR passa a codificar o GRUPO, com a mesma paleta do gráfico. Antes
        # ela codificava a zona — informação que a posição no mapa já dá —, e o
        # grupo ficava só em texto na legenda. Pior: quatro zonas com o mesmo
        # grupo predominante apareciam em quatro cores distintas, escondendo o
        # principal achado. Agora zonas com o mesmo perfil compartilham a cor.
        def cor_do_grupo(slug):
            if slug is None:
                return "#c9d1d6"
            if slug == OUTROS:
                return COR_OUTROS
            return GROUP_COLORS.get(slug, "#95a5a6")

        fig_mapa = go.Figure()
        vistos = set()
        for zona in pivot.index:
            locais = [f["properties"]["bairro"] for f in geo["features"]
                      if f["properties"]["zona"] == zona]
            if not locais:
                continue
            d = dominante[zona]
            cor = cor_do_grupo(d["slug"])
            # uma entrada de legenda por GRUPO, não por zona
            primeira = d["grupo"] not in vistos
            vistos.add(d["grupo"])
            fig_mapa.add_trace(go.Choroplethmapbox(
                geojson=geo, locations=locais, z=[1] * len(locais),
                featureidkey="properties.bairro", name=d["grupo"],
                colorscale=[[0, cor], [1, cor]], showscale=False,
                showlegend=primeira, legendgroup=d["grupo"],
                # linha interna discreta: os bairros de uma mesma zona devem ler
                # como um bloco só, já que a análise é por zona
                marker=dict(line=dict(width=0.3, color="rgba(255,255,255,0.55)"),
                            opacity=0.78),
                customdata=[[zona, d["grupo"], d["n"], d["total"], d["pct_grupo"]]] * len(locais),
                hovertemplate=("<b>Zona %{customdata[0]}</b>"
                               "<br>%{customdata[3]} matérias localizadas"
                               "<br>Predominante: %{customdata[1]}"
                               "<br>%{customdata[2]} matérias — %{customdata[4]:.0f}% "
                               "da cobertura da zona<extra></extra>"),
            ))

        if centros:
            # Sem a cor identificando a zona, o nome precisa estar no mapa.
            # Texto puro: marcador de mapa não interpreta HTML.
            rot = [(z, c) for z, c in centros.items() if z in pivot.index]
            fig_mapa.add_trace(go.Scattermapbox(
                lat=[c["lat"] for _, c in rot], lon=[c["lon"] for _, c in rot],
                mode="text", text=[z for z, _ in rot],
                textfont=dict(size=13, color="#1f2a30"),
                hoverinfo="skip", showlegend=False,
            ))

        fig_mapa.update_layout(
            # ZOOM: o Mapbox GL usa tiles de 512px, não 256. Calcular com 256 dá
            # um nível a MAIS, e cada nível dobra a ampliação — era o motivo de o
            # mapa cortar por mais que se aumentasse a margem.
            mapbox=dict(style="carto-positron",
                        center=dict(lat=-3.0382, lon=-59.9981), zoom=10.8),
            dragmode=False, height=820,
            legend=dict(title=dict(text="Grupo predominante"), orientation="v",
                        yanchor="bottom", y=0.01, xanchor="left", x=0.01,
                        bgcolor="rgba(255,255,255,0.93)", bordercolor="#d7dee2",
                        borderwidth=1, font=dict(size=11)),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        col_esq, col_mapa, col_dir = st.columns([1, 2, 1])
        with col_mapa:
            st.plotly_chart(fig_mapa, use_container_width=True, config={
                "scrollZoom": False, "displayModeBar": False, "doubleClick": False,
            })
        st.caption(
            f"{len(geo['features'])} dos 64 bairros oficiais têm limite cartográfico "
            "na base aberta usada (OpenStreetMap); os demais não aparecem, e o vazio "
            "indica ausência de limite mapeado, não ausência de cobertura. A divisão "
            "em zonas é a da Lei Municipal nº 1.401/2010. Zona com menos de "
            f"{MIN_PARA_PINTAR} matérias no período fica em cinza."
        )

# ---------------------------------------------------------------- rodapé

st.divider()

# ---------------------------------------------------------------- rodapé

st.markdown("""
<div style="background:#eef4f9;border:1px solid #cfe0ee;border-radius:10px;
            padding:14px 20px;margin:6px 0 10px 0;max-width:1080px;">
    <span style="display:inline-block;background:#1e6091;color:#fff;font-size:0.7rem;
                 font-weight:700;letter-spacing:0.05em;text-transform:uppercase;
                 padding:3px 9px;border-radius:20px;margin-right:10px;">
        Classificação automática</span>
    <span style="display:inline-block;background:#8a6d3b;color:#fff;font-size:0.7rem;
                 font-weight:700;letter-spacing:0.05em;text-transform:uppercase;
                 padding:3px 9px;border-radius:20px;">
        Agrupamento por caso desativado</span>
    <div style="font-size:0.95rem;color:#22384c;line-height:1.65;margin-top:10px;">
        A análise mede <b>cobertura jornalística</b>. A unidade principal é a
        <b>matéria</b>, e os totais <b>não representam crimes distintos</b>.
    </div>
</div>
""", unsafe_allow_html=True)

car = load_caracterizacao(VERSAO, dias)
if car["total"]:
    pct_lei = (100 * car["citam"] / car["com_info"]) if car["com_info"] else 0
    pct_dia = 100 * car["com_dia"] / car["total"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Registros classificados", fmt_br(car["total"]),
              help=f'{fmt_br(car["materias"])} matérias distintas no período. Uma '
                   "matéria gera mais de um registro quando noticia crimes de tipos "
                   "diferentes.")
    m2.metric("Citam enquadramento jurídico", f"{pct_lei:.0f}%",
              help=f'{fmt_br(car["citam"])} de {fmt_br(car["com_info"])} registros '
                   "em que o modelo se pronunciou sobre isso.")
    m3.metric("Fatos datados até o dia", f"{pct_dia:.0f}%",
              help=f'{fmt_br(car["com_dia"])} de {fmt_br(car["total"])} registros. '
                   "Nos demais a matéria não permite precisão de dia.")
    texto(
        "O total indica o volume analisado. Os percentuais descrevem o texto "
        "jornalístico, não a criminalidade: mostram com que frequência as matérias "
        "apresentam um enquadramento jurídico explícito e com que precisão informam "
        "a data do fato."
    )

with st.expander("📐 Metodologia da análise"):
    st.markdown('<div style="max-width:1080px;">', unsafe_allow_html=True)
    descarte = ""
    if car.get("avaliados") and car["avaliados"] > car.get("materias", 0):
        pct_desc = 100 * (car["avaliados"] - car["materias"]) / car["avaliados"]
        descarte = (f" No período, **{pct_desc:.0f}%** das publicações desses temas "
                    "não noticiavam crime e foram descartadas.")
    st.markdown(f"""
**O que é analisado.** O Observatório coleta continuamente publicações de dezenas de
portais, blogs e canais do Amazonas. Participam desta análise apenas as matérias
classificadas como locais e vinculadas aos temas *Segurança Pública* ou
*Justiça e Direito*.

Um modelo de linguagem verifica se cada matéria noticia uma ocorrência criminal
concreta. Em caso afirmativo, identifica a figura penal, a etapa noticiada — fato,
investigação, prisão, julgamento ou condenação —, a data e o local do fato e, quando
possível, quantifica separadamente vítimas e suspeitos.

Uma parcela relevante das publicações desses temas não noticia crimes: incêndios sem
indício de crime, acidentes, resgates, treinamentos, campanhas educativas, balanços
estatísticos e matérias institucionais são descartados.{descarte}

**Unidade de análise.** A unidade primária é a **matéria jornalística**, não o crime.
A escolha é deliberada: o objeto de estudo é a cobertura da imprensa, e só é possível
observar aquilo que foi publicado. Uma operação policial com doze prisões por tráfico
conta como uma matéria; vítimas e suspeitos, quando informados, vão em campos
separados. Uma matéria gera mais de um registro apenas quando noticia crimes de tipos
diferentes.

**Agrupamento por caso — em desenvolvimento, atualmente desativado.** Um mesmo crime
pode ser noticiado por vários veículos, e distinguir "vinte crimes noticiados uma vez
cada" de "um crime noticiado vinte vezes" é questão central para o estudo da cobertura.
A primeira versão do agrupamento tinha dificuldade para fundir matérias que não
mencionavam nomes de pessoas, situação frequente no noticiário policial, e produzia
praticamente um caso por matéria. Foi desativado até ser reformulado. Enquanto isso as
matérias são contabilizadas separadamente, e os totais **não devem ser interpretados
como número de crimes distintos**.

**Classificação penal.** As categorias correspondem a figuras do Código Penal e da
legislação penal especial. Para fins analíticos, são agrupadas segundo o bem jurídico
protegido, tomando como referência os Títulos do Código Penal e mantendo grupos
próprios para leis especiais.

Quando a narrativa permite identificar uma figura penal autônoma, ela é preferida à
genérica: feminicídio em vez de homicídio, latrocínio em vez de roubo. A classificação
é automática e tem finalidade informativa — **não substitui o enquadramento das
autoridades competentes**.

O dispositivo legal exibido **não é gerado pelo modelo**: vem de uma tabela fixa
associada a cada categoria, o que evita a citação de artigos inexistentes. Registra-se
separadamente se a própria matéria menciona a figura penal ou o artigo de lei — isso
caracteriza o texto jornalístico, não o crime.

**Datas.** O sistema mantém duas: a de publicação da matéria e a do fato. A distinção
importa, porque uma notícia publicada hoje sobre a condenação de um crime de anos atrás
é cobertura atual sobre fato antigo. A data do fato preserva somente a precisão que a
matéria oferece — dia, mês, ano ou desconhecida. Quando o texto informa apenas "em
2019", registra-se somente o ano, sem inventar mês ou dia. Os gráficos de evolução usam
a **data de publicação**, porque medem o comportamento da cobertura.

**Localização.** O bairro é extraído quando aparece no texto, e a zona administrativa é
derivada da divisão oficial da Lei Municipal nº 1.401/2010, que distribui os 64 bairros
de Manaus em seis zonas. A lista dos 62 municípios amazonenses segue o IBGE, e
ocorrências claramente localizadas fora do Amazonas são descartadas. Como muitas
matérias não informam bairro, a distribuição geográfica mostra **onde a imprensa
consegue localizar os fatos que noticia**, e não onde a criminalidade se concentra.

**Limitações conhecidas.**
- Crimes que não se tornam notícia são invisíveis para o método.
- Veículos que publicam mais têm maior peso no conjunto.
- Matérias diferentes sobre o mesmo caso são contadas separadamente enquanto o
  agrupamento estiver desativado.
- A classificação é automática e está sujeita a erros. Estimar a taxa de acerto exige
  amostra aleatória ou estratificada, conferida contra as matérias de origem; amostra
  escolhida por suspeita encontra defeitos, mas não mede o conjunto.
- As associações entre categorias e dispositivos legais aguardam revisão de
  especialista em Direito.
""")
    st.markdown('</div>', unsafe_allow_html=True)

st.caption(
    "Observatório de Manaus — LSI/UEA. Dados atualizados automaticamente a cada 30 minutos."
)
