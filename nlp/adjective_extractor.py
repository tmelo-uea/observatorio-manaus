import logging
import math
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import text
from db.connection import get_engine

logger = logging.getLogger(__name__)


def _load_spacy():
    import spacy
    try:
        return spacy.load("pt_core_news_sm", disable=["parser", "ner", "senter"])
    except OSError:
        logger.info("Baixando modelo spaCy pt_core_news_sm...")
        from spacy.cli import download
        download("pt_core_news_sm")
        return spacy.load("pt_core_news_sm", disable=["parser", "ner", "senter"])


def run_adjective_extraction():
    """Extrai adjetivos distintivos por tema (TF-IDF) e salva no banco. Roda 1x/dia."""
    engine = get_engine()
    today = (datetime.utcnow() - timedelta(hours=4)).date()

    with engine.connect() as conn:
        already = conn.execute(
            text("SELECT 1 FROM topic_adjectives WHERE computed_date = :d LIMIT 1"),
            {"d": today},
        ).fetchone()
    if already:
        return

    logger.info("Extraindo adjetivos por tema...")
    start_utc = datetime.utcnow() - timedelta(days=30)

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                a.topic_id,
                CONCAT(COALESCE(a.title, ''), ' ', COALESCE(a.summary, '')) AS texto
            FROM articles a
            WHERE a.published_at >= :start
              AND a.is_local = 1
              AND a.topic_id IS NOT NULL
        """), {"start": start_utc}).fetchall()

    if not rows:
        logger.warning("Sem artigos para extração de adjetivos.")
        return

    topic_texts: dict[int, list[str]] = {}
    for row in rows:
        texto = (row.texto or "").strip()
        if texto:
            topic_texts.setdefault(row.topic_id, []).append(texto)

    if not topic_texts:
        return

    nlp = _load_spacy()
    N = len(topic_texts)

    topic_counts: dict[int, Counter] = {}
    for tid, texts in topic_texts.items():
        counts: Counter = Counter()
        for doc in nlp.pipe(texts, batch_size=256):
            for token in doc:
                if (
                    token.pos_ == "ADJ"
                    and not token.is_stop
                    and token.is_alpha
                    and len(token.lemma_) > 2
                ):
                    counts[token.lemma_.lower()] += 1
        topic_counts[tid] = counts

    # IDF: em quantos temas cada adjetivo aparece?
    df: Counter = Counter()
    for counts in topic_counts.values():
        for word in counts:
            df[word] += 1

    records = []
    for tid, counts in topic_counts.items():
        total = sum(counts.values()) or 1
        scores = {
            word: (freq / total) * math.log(N / df[word])
            for word, freq in counts.items()
        }
        top10 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
        for word, score in top10:
            records.append({
                "topic_id": tid,
                "word": word,
                "tfidf_score": float(score),
                "frequency": int(counts[word]),
                "computed_date": today,
            })

    if records:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO topic_adjectives
                    (topic_id, word, tfidf_score, frequency, computed_date)
                VALUES
                    (:topic_id, :word, :tfidf_score, :frequency, :computed_date)
            """), records)
        logger.info(f"Adjetivos salvos: {len(records)} registros para {today}.")
