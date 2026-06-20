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


def run_writing_metrics():
    """Computa métricas de escrita por fonte e grava snapshot diário. Roda 1x/dia."""
    engine = get_engine()
    today = (datetime.utcnow() - timedelta(hours=4)).date()

    with engine.connect() as conn:
        already = conn.execute(
            text("SELECT 1 FROM writing_metrics "
                 "WHERE computed_date = :d AND group_type = 'source' LIMIT 1"),
            {"d": today},
        ).fetchone()
    if already:
        return

    logger.info("Computando métricas de escrita por fonte...")
    start_utc = datetime.utcnow() - timedelta(days=PERIOD_DAYS)

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                a.source_id AS gid,
                CONCAT(COALESCE(a.title, ''), ' ', COALESCE(a.summary, '')) AS texto
            FROM articles a
            WHERE a.published_at >= :start
              AND a.is_local = 1
              AND a.source_id IS NOT NULL
        """), {"start": start_utc}).fetchall()

    if not rows:
        logger.warning("Sem artigos para métricas de escrita.")
        return

    pools: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        texto = (row.texto or "").strip()
        if texto:
            pools[row.gid].append(texto)

    if not pools:
        return

    nlp = _load_spacy()
    records = []
    for gid, texts in pools.items():
        metrics = _compute_pool(texts, nlp)
        if metrics is None:
            continue
        n_tokens = metrics.pop("n_tokens")
        for metric, value in metrics.items():
            records.append({
                "computed_date": today,
                "group_type":    "source",
                "group_id":      gid,
                "metric":        metric,
                "value":         float(value),
                "n_articles":    len(texts),
                "n_tokens":      n_tokens,
            })

    if records:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO writing_metrics
                    (computed_date, group_type, group_id, metric, value, n_articles, n_tokens)
                VALUES
                    (:computed_date, :group_type, :group_id, :metric, :value, :n_articles, :n_tokens)
            """), records)
        n_sources = len({r["group_id"] for r in records})
        logger.info(f"Métricas de escrita salvas: {n_sources} fontes para {today}.")
