"""Métricas de escrita agregadas por fonte (e, futuramente, por tema).

Mede o estilo da *chamada* (título + resumo) de cada fonte, pois é o texto
uniformemente disponível para todas as notícias — o corpo completo só existe
para parte dos artigos e enviesaria a comparação entre fontes.

Como os resumos individuais são curtos demais para métricas estáveis, medimos
sobre o **pool** de todas as notícias locais da fonte nos últimos 30 dias.
Roda 1x/dia no ciclo do worker e grava um snapshot diário em `writing_metrics`.

Métricas (todas robustas ao tamanho do texto):
  - lexical_density        densidade lexical: palavras de conteúdo / palavras totais
  - mtld                   diversidade lexical (Measure of Textual Lexical Diversity)
  - lexical_sophistication proporção de palavras de conteúdo raras (wordfreq pt)
  - nominalization_rate    substantivos nominalizados por 100 palavras (heurística de sufixos)
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import text
from db.connection import get_engine

logger = logging.getLogger(__name__)

PERIOD_DAYS = 30
BATCH       = 256

# Pool mínimo de palavras para a métrica ser estável; abaixo disso a fonte é omitida.
MIN_TOKENS = 500

# Palavra é "rara/sofisticada" se sua frequência Zipf no português for menor que isto.
# Zipf 3.0 ≈ 1 ocorrência por milhão de palavras. Limiar relativo: o que importa é
# a comparação entre fontes, não o valor absoluto.
RARE_ZIPF = 3.0

# Parâmetro canônico do MTLD (McCarthy & Jarvis, 2010).
MTLD_THRESHOLD = 0.720

# POS de conteúdo (lexical) vs. funcionais.
CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}
# Para sofisticação, nomes próprios são "raros" mas não sofisticados — ficam de fora.
SOPHIST_POS = {"NOUN", "VERB", "ADJ", "ADV"}

# Sufixos nominalizadores do português (conjunto conservador, evita os mais ruidosos
# como -ura). Heurística: contam substantivos cujo lema termina nestes sufixos.
NOMINAL_SUFFIXES = (
    "ção", "ções", "são", "sões", "mento", "mentos", "dade", "dades",
    "agem", "agens", "ância", "âncias", "ência", "ências", "ismo", "ismos",
)


def _load_spacy():
    import spacy
    try:
        return spacy.load("pt_core_news_sm", disable=["parser", "ner", "senter"])
    except OSError:
        logger.info("Baixando modelo spaCy pt_core_news_sm...")
        from spacy.cli import download
        download("pt_core_news_sm")
        return spacy.load("pt_core_news_sm", disable=["parser", "ner", "senter"])


def _mtld_pass(tokens: list[str], threshold: float) -> float:
    """Um sentido do MTLD: nº de palavras dividido pelo nº de fatores de TTR."""
    factors = 0.0
    types: set[str] = set()
    count = 0
    for tok in tokens:
        count += 1
        types.add(tok)
        if len(types) / count <= threshold:
            factors += 1
            types = set()
            count = 0
    if count > 0:
        ttr = len(types) / count
        factors += (1 - ttr) / (1 - threshold)
    if factors == 0:
        return float(len(tokens))
    return len(tokens) / factors


def _mtld(tokens: list[str], threshold: float = MTLD_THRESHOLD) -> float:
    """MTLD bidirecional (média ida/volta). Requer ao menos ~50 tokens."""
    forward  = _mtld_pass(tokens, threshold)
    backward = _mtld_pass(list(reversed(tokens)), threshold)
    return (forward + backward) / 2


def _is_nominalization(lemma: str) -> bool:
    return lemma.endswith(NOMINAL_SUFFIXES) and len(lemma) > 5


def _compute_pool(texts: list[str], nlp) -> dict | None:
    """Calcula as 4 métricas sobre o pool de textos de um grupo.

    Retorna None se o pool não atingir MIN_TOKENS.
    """
    from wordfreq import zipf_frequency

    total_words   = 0   # palavras (tokens alfabéticos) — denominador da densidade
    content_words = 0   # palavras de conteúdo (CONTENT_POS)
    nominalizations = 0
    sophist_total = 0   # palavras de conteúdo elegíveis à sofisticação
    sophist_rare  = 0
    seq: list[str] = []  # sequência ordenada de palavras para o MTLD

    for doc in nlp.pipe(texts, batch_size=BATCH):
        for token in doc:
            if not token.is_alpha:
                continue
            total_words += 1
            seq.append(token.text.lower())
            pos = token.pos_
            if pos in CONTENT_POS:
                content_words += 1
            if pos == "NOUN" and _is_nominalization(token.lemma_.lower()):
                nominalizations += 1
            if pos in SOPHIST_POS:
                sophist_total += 1
                if zipf_frequency(token.text.lower(), "pt") < RARE_ZIPF:
                    sophist_rare += 1

    if total_words < MIN_TOKENS:
        return None

    return {
        "lexical_density":        content_words / total_words,
        "mtld":                   _mtld(seq),
        "lexical_sophistication": (sophist_rare / sophist_total) if sophist_total else 0.0,
        "nominalization_rate":    nominalizations / total_words * 100,
        "n_tokens":               total_words,
    }


# Coluna de agrupamento por lente. O texto medido (título+resumo) é o mesmo;
# muda apenas a chave que define o pool.
_GROUP_COLUMN = {"source": "source_id", "topic": "topic_id"}


def _run_group(engine, today, start_utc, group_type: str, nlp) -> int:
    """Computa e grava as métricas de um tipo de agrupamento. Idempotente por dia.

    Retorna o nº de grupos gravados (0 se já calculado hoje ou sem dados).
    """
    with engine.connect() as conn:
        already = conn.execute(
            text("SELECT 1 FROM writing_metrics "
                 "WHERE computed_date = :d AND group_type = :g LIMIT 1"),
            {"d": today, "g": group_type},
        ).fetchone()
    if already:
        return 0

    col = _GROUP_COLUMN[group_type]
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT
                a.{col} AS gid,
                CONCAT(COALESCE(a.title, ''), ' ', COALESCE(a.summary, '')) AS texto
            FROM articles a
            WHERE a.published_at >= :start
              AND a.is_local = 1
              AND a.{col} IS NOT NULL
        """), {"start": start_utc}).fetchall()

    pools: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        texto = (row.texto or "").strip()
        if texto:
            pools[row.gid].append(texto)
    if not pools:
        return 0

    records = []
    for gid, texts in pools.items():
        metrics = _compute_pool(texts, nlp)
        if metrics is None:
            continue
        n_tokens = metrics.pop("n_tokens")
        for metric, value in metrics.items():
            records.append({
                "computed_date": today,
                "group_type":    group_type,
                "group_id":      gid,
                "metric":        metric,
                "value":         float(value),
                "n_articles":    len(texts),
                "n_tokens":      n_tokens,
            })

    if not records:
        return 0

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO writing_metrics
                (computed_date, group_type, group_id, metric, value, n_articles, n_tokens)
            VALUES
                (:computed_date, :group_type, :group_id, :metric, :value, :n_articles, :n_tokens)
        """), records)
    return len({r["group_id"] for r in records})


def run_writing_metrics():
    """Computa métricas de escrita por fonte e por tema, gravando snapshot diário.

    Roda 1x/dia. Carrega o spaCy apenas se houver alguma lente pendente.
    """
    engine = get_engine()
    today = (datetime.utcnow() - timedelta(hours=4)).date()

    with engine.connect() as conn:
        done = {
            r.group_type for r in conn.execute(
                text("SELECT DISTINCT group_type FROM writing_metrics "
                     "WHERE computed_date = :d"),
                {"d": today},
            ).fetchall()
        }
    pending = [g for g in _GROUP_COLUMN if g not in done]
    if not pending:
        return

    logger.info(f"Computando métricas de escrita: {', '.join(pending)}...")
    start_utc = datetime.utcnow() - timedelta(days=PERIOD_DAYS)
    nlp = _load_spacy()

    for group_type in pending:
        n = _run_group(engine, today, start_utc, group_type, nlp)
        if n:
            logger.info(f"Métricas de escrita salvas: {n} {group_type}(s) para {today}.")
