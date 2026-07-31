"""Extração de cobertura criminal a partir das matérias de Segurança e Justiça.

O que esta etapa mede é a COBERTURA DA IMPRENSA, não a criminalidade real —
só sabemos o que foi noticiado. Cada linha gravada representa o ato de noticiar
um crime; o agrupamento por caso vive em nlp/crime_clusterer.py e é derivado.

Decisões de projeto que explicam o formato do prompt:

  • Sem pré-filtro por palavra-chave. Testado sobre o acervo, um filtro assim
    tinha ~93% de precisão mas só ~60% de recall — e perdia de forma enviesada
    (tráfico e estelionato sumiam mais que homicídio). O LLM roda no pool
    inteiro do tema, ~61 artigos/dia, o que é barato.

  • Uma menção por FIGURA PENAL, não por pessoa. Operação com 12 prisões por
    tráfico = 1 menção com count_people=12.

  • O dispositivo legal NÃO é pedido ao modelo: vem do mapa determinístico em
    nlp/crime_types.py. Ao modelo só se pergunta se a MATÉRIA citou algum
    enquadramento — isso é observação sobre a imprensa, e é dado de pesquisa.
"""
import json
import os
from datetime import date, datetime, timedelta

from sqlalchemy import bindparam, or_, text as sql_text
from sqlalchemy.exc import IntegrityError

from db.connection import get_session
from db.models import Article, CrimeMention, Source, Topic
from nlp.crime_types import (
    VALID_SLUGS,
    group as crime_group,
    legal_ref,
    prompt_vocabulary,
)
from nlp.manaus_geo import is_amazonas, resolve as resolve_bairro
from nlp.prompts import render

EXTRACT_MODEL = "gpt-4o-mini"

# Temas cujas matérias entram no pool. Metade do que cai em "Segurança Pública"
# não é crime (incêndio, acidente, resgate, treinamento de bombeiros) — separar
# isso é justamente parte do trabalho do modelo.
TARGET_TOPICS = ("Segurança Pública", "Justiça e Direito")

VALID_STAGES = {"fato", "investigacao", "prisao", "julgamento", "condenacao"}

# Corpo da matéria truncado: o suficiente para o modelo situar o fato sem
# inflar o custo por chamada.
MAX_CONTENT_CHARS = 4000


def _manaus_today() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date()


def _manaus_date(dt: datetime | None) -> date | None:
    if not dt:
        return None
    return (dt - timedelta(hours=4)).date()


def _call_llm(prompt: str) -> dict | None:
    """Chama o modelo pedindo JSON. Devolve dict ou None em qualquer falha."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  [crimes] OPENAI_API_KEY não configurada — extração não executada.")
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=EXTRACT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900,
            temperature=0.1,          # tarefa de extração, não de redação
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        if not raw:
            return None
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [crimes] Resposta não era JSON válido: {e}")
        return None
    except Exception as e:
        print(f"  [crimes] Erro na API: {e}")
        return None


def _article_text(article: Article) -> str:
    """Monta o texto enviado ao modelo: título + resumo + corpo truncado.

    O corpo importa: o caso do 'desembargador' mostrou que resumo feito só de
    títulos herda o erro de uma única fonte. Com o corpo, o modelo tem contexto
    para desambiguar.
    """
    partes = [f"TÍTULO: {article.title}"]
    if article.summary:
        partes.append(f"RESUMO: {article.summary[:1500]}")
    corpo = article.content or article.transcript
    if corpo:
        partes.append(f"TEXTO: {corpo[:MAX_CONTENT_CHARS]}")
    return "\n\n".join(partes)


def _select_pending(session, limit: int):
    """Artigos locais dos temas-alvo ainda não avaliados, mais recentes primeiro."""
    topic_ids = [
        t.id for t in session.query(Topic).filter(Topic.name.in_(TARGET_TOPICS)).all()
    ]
    if not topic_ids:
        print(f"  [crimes] Nenhum tema encontrado entre {TARGET_TOPICS} — nada a fazer.")
        return []
    return (
        session.query(Article)
        .join(Source, Article.source_id == Source.id)
        .filter(
            Article.is_local.is_(True),
            Article.topic_id.in_(topic_ids),
            Article.crime_processed_at.is_(None),
            # Vídeo do YouTube ainda sem transcrição é só um título. Como a
            # extração passou a rodar ANTES da transcrição no job(), sem este
            # filtro ele seria avaliado pelo título e marcado como processado
            # para sempre. Espera a transcrição e entra num ciclo seguinte.
            or_(Source.type != "youtube", Article.transcript.isnot(None)),
        )
        # Sem nulls_last(): o MySQL não aceita a cláusula NULLS LAST, e em DESC
        # ele já ordena os NULL por último, que é o comportamento desejado.
        .order_by(Article.published_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )


def _parse_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# O modelo às vezes devolve a STRING "null" em vez do null do JSON. Sem isto,
# gravaríamos "null" como nome de município — visto no teste com artigos reais.
_VAZIOS = {"null", "none", "nulo", "n/a", "na", "-", "—", "desconhecido", "não informado"}


def _clean_str(value, max_len: int) -> str | None:
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v or v.lower() in _VAZIOS:
        return None
    return v[:max_len]


def _clean_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _clean_slug(value) -> str:
    """Slug inválido vira 'outro', mas NUNCA em silêncio.

    Quando o modelo usa um identificador fora da lista, quase sempre é porque a
    figura penal existe no noticiário e falta na taxonomia — foi assim que
    apareceram ocultação de cadáver e exploração sexual de vulnerável, ambas
    inventadas pelo modelo antes de eu tê-las cadastrado. Registrar no log faz a
    próxima lacuna se revelar sozinha, em vez de sumir dentro de 'outro'.
    """
    slug = (value or "").strip().lower()
    if slug in VALID_SLUGS:
        return slug
    if slug:
        print(f"  [crimes] Figura penal desconhecida sugerida pelo modelo: '{slug}' "
              f"— avaliar inclusão em nlp/crime_types.py")
    return "outro"


def _build_mention(article: Article, item: dict, reported_on: date) -> CrimeMention | None:
    slug = _clean_slug(item.get("type"))

    stage = (item.get("stage") or "fato").strip().lower()
    if stage not in VALID_STAGES:
        stage = "fato"

    bairro, zona = resolve_bairro(_clean_str(item.get("bairro"), 80))

    # A data só entra se a matéria permitir datar o fato ATÉ O DIA. O modelo não
    # admite ignorar o dia — proibido de inventar, respondia 2023-01-01 e depois
    # 2023-06-01 para o mesmo caso. Perguntar a precisão e filtrar aqui resolve.
    precisao = (_clean_str(item.get("occurred_precision"), 12) or "").lower()
    if precisao not in {"dia", "mes", "ano", "desconhecida"}:
        precisao = None
    # A data é guardada NORMALIZADA pela precisão, não descartada: o ano de um
    # crime antigo é informação real e útil; só o dia é que seria invenção. A
    # coluna occurred_precision diz como ler o campo — quem consultar occurred_on
    # sem olhar a precisão precisa saber que 1º de janeiro pode significar
    # "algum dia de 2019".
    # Efeito colateral bom: duas matérias sobre o mesmo caso de 2019 caem no
    # mesmo bloco de agrupamento. Com NULL cairiam no bloco de HOJE, porque o
    # clusterer usa reported_on como alternativa — misturadas a crimes recentes.
    occurred = _parse_date(item.get("occurred_on"))
    if occurred and precisao == "mes":
        occurred = occurred.replace(day=1)
    elif occurred and precisao == "ano":
        occurred = occurred.replace(month=1, day=1)
    elif occurred and precisao != "dia":
        occurred = None  # precisão desconhecida: não há ano confiável a preservar

    # Guarda para fato antigo retomado por matéria de desdobramento. A imprensa
    # raramente repete a data exata nesse contexto e o modelo afirma precisão de
    # dia que não tem: o mesmo release do Caso Débora respondeu 2023-01-01 numa
    # rodada e 2023-06-01 na seguinte, ambas como "dia".
    # Inclui 'prisao' porque prender alguém por crime de 2019 também é
    # desdobramento — foi por essa fresta que passou um "2019-01-01".
    if (occurred and stage in {"prisao", "julgamento", "condenacao"}
            and (reported_on - occurred).days > 60):
        precisao = "ano"
        occurred = occurred.replace(month=1, day=1)

    # 1º de janeiro de ano anterior é a assinatura clássica de preenchimento:
    # crime de réveillon seria noticiado na época, não anos depois. Mantém o
    # ano, que é a parte verdadeira, e rebaixa a precisão.
    if (occurred and occurred.month == 1 and occurred.day == 1
            and occurred.year < reported_on.year):
        precisao = "ano"

    descricao = (item.get("description") or "").strip()
    if not descricao:
        # description é NOT NULL; sem ela o registro não tem valor de leitura
        descricao = article.title[:500]

    secundarios = [
        s for s in (
            _clean_slug(x) for x in (item.get("secondary_types") or [])
            if isinstance(x, str)
        ) if s != slug
    ]

    entidades = [
        e.strip()[:120] for e in (item.get("entities") or [])
        if isinstance(e, str) and e.strip()
    ]

    contagem = _clean_int(item.get("count_people"))

    confianca = item.get("confidence")
    if isinstance(confianca, bool) or not isinstance(confianca, (int, float)):
        confianca = None

    municipio = _clean_str(item.get("municipio"), 80)

    # Guarda de localidade. O filtro is_local já roda antes, na seleção dos
    # artigos — mas ele erra: numa amostra de 25 matérias TODAS com is_local=1,
    # três noticiavam crimes de Medellín, São Paulo e Rio de Janeiro (o caso
    # Henry Borel está registrado como falso positivo conhecido desde junho).
    # Como o modelo extrai o município, dá para barrar aqui de graça.
    # Município ausente não é motivo para descartar: a maioria das matérias não
    # o nomeia, e descartar o desconhecido trocaria contaminação por perda.
    if is_amazonas(municipio) is False:
        print(f"  [crimes] Menção descartada — município fora do Amazonas: "
              f"'{municipio}' (artigo {article.id}; is_local errou)")
        return None

    local_txt = _clean_str(item.get("location_text"), 255)
    trecho_legal = _clean_str(item.get("legal_text_source"), 255)

    citou = item.get("legal_cited_by_source")
    citou = bool(citou) if isinstance(citou, bool) else None

    return CrimeMention(
        article_id=article.id,
        crime_type=slug,
        crime_group=crime_group(slug),
        crime_types=secundarios or None,
        stage=stage,
        occurred_on=occurred,
        occurred_precision=precisao,
        reported_on=reported_on,
        municipio=municipio,
        zona=zona,
        bairro=bairro,
        location_text=local_txt,
        count_people=contagem,
        description=descricao[:2000],
        legal_ref=legal_ref(slug),
        legal_cited_by_source=citou,
        legal_text_source=trecho_legal,
        entities=entidades or None,
        confidence=float(confianca) if confianca is not None else None,
        model=EXTRACT_MODEL,
        extracted_at=datetime.utcnow(),
    )


def extract_from_article(session, article: Article) -> int:
    """Processa um artigo. Devolve quantas menções foram gravadas.

    Marca crime_processed_at inclusive quando NÃO há crime — senão o artigo
    voltaria à fila a cada ciclo. Em falha de API o campo fica nulo de
    propósito: é o que torna a etapa retomável sozinha no ciclo seguinte.
    """
    reported_on = _manaus_date(article.published_at) or _manaus_date(article.collected_at) \
        or _manaus_today()

    # A data de publicação vai NO PROMPT porque sem ela o modelo inventa o ano ao
    # ver data relativa. Medido: "na noite de terça (2)", numa matéria de junho de
    # 2026, virava 2023-10-02 — três anos de erro na série.
    # O vocabulário vem do código, não do banco: a taxonomia é determinística e
    # não deve poder ser editada por engano junto com a redação do prompt.
    prompt = render(
        "crime.extract",
        vocabulario=prompt_vocabulary(),
        data_publicacao=reported_on.strftime("%d/%m/%Y"),
        texto=_article_text(article),
    )
    data = _call_llm(prompt)
    if data is None:
        return -1  # falha de API: não marcar como processado

    gravadas = 0
    if data.get("is_crime"):
        vistos = set()
        for item in (data.get("crimes") or []):
            if not isinstance(item, dict):
                continue
            mention = _build_mention(article, item, reported_on)
            if mention is None or mention.crime_type in vistos:
                continue  # uma menção por figura penal, por artigo
            vistos.add(mention.crime_type)
            session.add(mention)
            try:
                session.flush()
                gravadas += 1
            except IntegrityError:
                # já existe menção deste tipo para este artigo (reprocessamento)
                session.rollback()

    article.crime_processed_at = datetime.utcnow()
    return gravadas


def run_crime_extraction(limit: int = 20) -> int:
    """Processa até `limit` artigos pendentes. Devolve o total de menções gravadas.

    Vazão de referência: ~61 artigos/dia no pool = ~1,3 por ciclo de 30 min.
    limit=20 dá folga de 15x, então a fila não acumula.
    """
    session = get_session()
    total_mencoes = 0
    processados = 0
    com_crime = 0
    falhas = 0
    try:
        pendentes = _select_pending(session, limit)
        if not pendentes:
            return 0
        for article in pendentes:
            n = extract_from_article(session, article)
            if n < 0:
                falhas += 1
                if falhas >= 3:
                    # API caindo em série: parar e tentar no próximo ciclo em vez
                    # de queimar o resto do limite contra um provedor indisponível
                    print("  [crimes] 3 falhas seguidas de API — interrompendo o ciclo.")
                    break
                continue
            falhas = 0
            processados += 1
            if n > 0:
                com_crime += 1
                total_mencoes += n
            session.commit()
        session.commit()
        if processados or total_mencoes:
            print(f"  [crimes] {processados} artigos avaliados, {com_crime} com crime, "
                  f"{total_mencoes} menções gravadas.")
        return total_mencoes
    finally:
        session.close()


def pending_count() -> int:
    """Tamanho da fila — útil no painel para saber se a extração está acompanhando."""
    session = get_session()
    try:
        stmt = sql_text("""
            SELECT COUNT(*) FROM articles a
            JOIN topics t ON a.topic_id = t.id
            JOIN sources s ON a.source_id = s.id
            WHERE a.is_local = 1
              AND a.crime_processed_at IS NULL
              AND t.name IN :nomes
              AND (s.type <> 'youtube' OR a.transcript IS NOT NULL)
        """).bindparams(bindparam("nomes", expanding=True))
        row = session.execute(stmt, {"nomes": list(TARGET_TOPICS)}).scalar()
        return int(row or 0)
    finally:
        session.close()
