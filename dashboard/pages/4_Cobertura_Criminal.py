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
                   COUNT(DISTINCT m.event_id)     AS casos,
                   COUNT(DISTINCT m.crime_type)   AS figuras,
                   COUNT(DISTINCT a.source_id)    AS veiculos
            FROM crime_mentions m
            JOIN articles a ON a.id = m.article_id
            WHERE m.reported_on >= :ini {filtro}
        """), params).fetchone()
    return {
        "mencoes": row[0] or 0,
        "casos": row[1] or 0,
        "figuras": row[2] or 0,
        "veiculos": row[3] or 0,
    }


@st.cache_data(ttl=300)
def load_serie(dias: int, municipio: str | None) -> pd.DataFrame:
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    filtro = "AND municipio = :mun" if municipio else ""
    params = {"ini": inicio}
    if municipio:
        params["mun"] = municipio
    with get_db().connect() as conn:
        res = conn.execute(text(f"""
            SELECT DATE_SUB(reported_on, INTERVAL WEEKDAY(reported_on) DAY) AS semana,
                   crime_group, COUNT(*) AS cnt
            FROM crime_mentions
            WHERE reported_on >= :ini {filtro}
            GROUP BY semana, crime_group
            ORDER BY semana
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
def load_repercussao(dias: int, limite: int = 15) -> pd.DataFrame:
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    with get_db().connect() as conn:
        res = conn.execute(text("""
            SELECT e.id, e.crime_type, e.occurred_on, e.bairro, e.municipio,
                   e.mention_count, e.source_count,
                   (SELECT m.description FROM crime_mentions m
                     WHERE m.event_id = e.id ORDER BY m.id LIMIT 1) AS descricao
            FROM crime_events e
            WHERE e.occurred_on >= :ini
            ORDER BY e.mention_count DESC, e.source_count DESC
            LIMIT :lim
        """), {"ini": inicio, "lim": limite})
        return pd.DataFrame(res.fetchall(), columns=res.keys())


@st.cache_data(ttl=300)
def load_cobertura_do_direito(dias: int) -> dict:
    """Quantas matérias citam o enquadramento jurídico — dado sobre a imprensa."""
    inicio = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=dias)
    with get_db().connect() as conn:
        row = conn.execute(text("""
            SELECT SUM(legal_cited_by_source = 1), COUNT(legal_cited_by_source)
            FROM crime_mentions WHERE reported_on >= :ini
        """), {"ini": inicio}).fetchone()
    return {"citam": int(row[0] or 0), "total": int(row[1] or 0)}


@st.cache_data(ttl=120)
def load_amostra(n: int = 10) -> pd.DataFrame:
    with get_db().connect() as conn:
        res = conn.execute(text("""
            SELECT m.id, m.crime_type, m.stage, m.occurred_on, m.occurred_precision,
                   m.reported_on,
                   m.municipio, m.zona, m.bairro, m.count_people, m.description,
                   m.confidence, m.legal_ref, m.legal_cited_by_source, m.event_id,
                   a.title, a.url, s.name AS fonte
            FROM crime_mentions m
            JOIN articles a ON a.id = m.article_id
            JOIN sources s  ON s.id = a.source_id
            ORDER BY RAND()
            LIMIT :n
        """), {"n": n})
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


# ---------------------------------------------------------------- cabeçalho

st.title("⚖️ Cobertura criminal na imprensa")
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
c2.metric("Casos distintos", fmt_br(pan["casos"]))
razao = (pan["mencoes"] / pan["casos"]) if pan["casos"] else 0
c3.metric("Matérias por caso", f"{razao:.1f}".replace(".", ","))
c4.metric("Veículos", fmt_br(pan["veiculos"]))

st.caption(
    "“Matérias por caso” é a razão entre cobertura e ocorrências distintas: quanto "
    "maior, mais a imprensa repetiu os mesmos casos."
)

st.divider()

# ---------------------------------------------------------------- série temporal

st.subheader("Evolução da cobertura")
st.caption("Matérias publicadas por semana, agrupadas pelo bem jurídico protegido.")

df_serie = load_serie(dias, municipio)
if df_serie.empty:
    st.info("Sem dados no período selecionado.")
else:
    df_serie["semana"] = pd.to_datetime(df_serie["semana"])
    ordem = df_serie.groupby("crime_group")["cnt"].sum().sort_values(ascending=False)
    fig = go.Figure()
    for grupo in ordem.index:
        gdf = df_serie[df_serie["crime_group"] == grupo].sort_values("semana")
        cor = GROUP_COLORS.get(grupo, "#95a5a6")
        nome = CRIME_GROUPS.get(grupo, grupo)
        fig.add_trace(go.Scatter(
            x=gdf["semana"], y=gdf["cnt"], name=nome, mode="lines",
            stackgroup="one", line=dict(color=cor, width=0.5),
            hovertemplate=f"<b>{nome}</b><br>Semana de %{{x|%d/%m}}: %{{y}} matérias<extra></extra>",
        ))
    fig.update_layout(
        height=400, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=80, b=50),
        plot_bgcolor="#fafafa", xaxis_title="", yaxis_title="Matérias por semana",
    )
    st.plotly_chart(fig, use_container_width=True)

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

# ---------------------------------------------------------------- repercussão

st.subheader("Casos com maior repercussão")
st.caption("Ocorrências que mais renderam matérias — a medida de amplificação editorial.")

df_rep = load_repercussao(dias)
if df_rep.empty:
    st.info("Ainda não há casos agrupados no período.")
else:
    for _, r in df_rep.iterrows():
        if r["mention_count"] < 2:
            continue
        local = " · ".join(x for x in [r["bairro"], r["municipio"]] if x)
        data = r["occurred_on"].strftime("%d/%m/%Y") if r["occurred_on"] else "data não informada"
        st.markdown(f"""
<div style="background:#f8fafc;border-left:4px solid #4a90d9;border-radius:8px;
            padding:12px 18px;margin-bottom:8px;">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
        <span style="font-weight:700;color:#1e40af;font-size:0.92rem;">
            {tipo_label(r['crime_type'])}
        </span>
        <span style="font-size:0.78rem;color:#7f8c8d;white-space:nowrap;">
            {r['mention_count']} matérias · {r['source_count']} veículos
        </span>
    </div>
    <div style="color:#475569;line-height:1.6;font-size:0.9rem;margin-top:6px;">
        {r['descricao'] or ''}
    </div>
    <div style="font-size:0.76rem;color:#94a3b8;margin-top:6px;">
        {data}{' · ' + local if local else ''}
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------- metodologia

st.subheader("📐 Metodologia")

leis = load_cobertura_do_direito(dias)
pct_leis = (100 * leis["citam"] / leis["total"]) if leis["total"] else 0

st.markdown(f"""
**O que é medido.** O Observatório coleta continuamente as publicações de dezenas de
portais, blogs e canais do Amazonas. Desta página participam apenas as matérias
classificadas como locais e pertencentes aos temas *Segurança Pública* e
*Justiça e Direito*. Cada matéria desse conjunto é lida por um modelo de linguagem
que responde se ela noticia um crime e, em caso afirmativo, qual figura penal,
em que etapa (fato, investigação, prisão, julgamento ou condenação), quando, onde
e quantas pessoas estavam envolvidas.

**Unidade de análise.** A unidade primária é a *matéria*, não o crime. Isso é
deliberado: o objeto de estudo é a cobertura jornalística, e só é possível observar
o que foi publicado. Uma operação policial com doze prisões por tráfico conta como
uma matéria, com o número de envolvidos registrado à parte. Uma matéria só gera mais
de um registro se noticiar crimes de tipos diferentes.

**Agrupamento por caso.** Um mesmo crime costuma ser noticiado por vários veículos.
Para distinguir "vinte crimes noticiados uma vez" de "um crime noticiado vinte vezes",
os registros são agrupados por caso quando coincidem em tipo penal, município, data
aproximada, bairro e pessoas citadas. O agrupamento é determinístico e revisável: ele
não altera os registros originais, e pode ser recalculado a qualquer momento. Casos
duvidosos permanecem separados — a contagem de casos distintos é, portanto, um limite
superior.

**Classificação legal.** As categorias correspondem a figuras do Código Penal e da
legislação penal especial. O dispositivo legal exibido **não** é gerado pelo modelo:
ele vem de uma tabela fixa associada a cada categoria, o que evita citações de artigos
inventadas. Separadamente, registra-se se a própria matéria mencionou o enquadramento
jurídico — no período selecionado, **{pct_leis:.0f}% das matérias** citaram algum
enquadramento, o que é uma característica do texto jornalístico, não do crime.

**Localização.** O bairro é extraído do texto quando citado, e a zona da cidade é
derivada dele. A maioria das matérias não informa bairro, de modo que a distribuição
geográfica descreve onde a imprensa localiza os fatos que noticia.

**Limitações conhecidas.**
- Crimes não noticiados são invisíveis para o método.
- Veículos com maior volume de publicação pesam mais no resultado.
- A classificação é automática e contém erros; a amostra de verificação abaixo permite
  estimar a taxa de acerto.
- Matérias sobre desdobramentos judiciais de casos antigos entram com a data do fato
  quando ela é informada, e com a data de publicação quando não é.
""")

with st.expander("Amostra de verificação — comparar extração com a matéria original"):
    st.caption(
        "Dez registros sorteados aleatoriamente. Serve para conferir se a leitura "
        "automática corresponde ao que a matéria diz."
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

st.caption(
    "Observatório de Manaus — LSI/UEA. Dados atualizados automaticamente a cada 30 minutos."
)
