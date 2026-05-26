import re
import unicodedata
from db.connection import get_session
from db.models import Article, Topic


def normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def keyword_matches(keyword: str, text: str) -> bool:
    kw = normalize(keyword)
    if " " in kw:
        return kw in text
    return bool(re.search(r"\b" + re.escape(kw) + r"\b", text))


MIN_SCORE_THRESHOLD = 0.02
MIN_MATCHES_THRESHOLD = 2


def classify_article(text: str, topics: list[Topic]) -> tuple[int, float]:
    normalized = normalize(text)
    outros_id = next((t.id for t in topics if t.slug == "outros"), None)

    best_topic_id = outros_id
    best_score = 0.0
    best_matches = 0

    for topic in topics:
        if topic.slug == "outros" or not topic.keywords:
            continue
        matches = sum(1 for kw in topic.keywords if keyword_matches(kw, normalized))
        if matches == 0:
            continue
        score = matches / len(topic.keywords)
        if score > best_score:
            best_score = score
            best_matches = matches
            best_topic_id = topic.id

    if best_score < MIN_SCORE_THRESHOLD and best_matches < MIN_MATCHES_THRESHOLD:
        return outros_id, round(best_score, 4)

    return best_topic_id, round(best_score, 4)


def run_classification(batch_size: int = 500) -> int:
    session = get_session()
    classified = 0
    try:
        topics = session.query(Topic).all()
        unclassified = (
            session.query(Article)
            .filter(Article.topic_id.is_(None))
            .limit(batch_size)
            .all()
        )
        for article in unclassified:
            text = f"{article.title or ''} {article.summary or ''} {article.transcript or ''}"
            topic_id, score = classify_article(text, topics)
            article.topic_id = topic_id
            article.topic_score = score
            classified += 1
        session.commit()
    finally:
        session.close()
    return classified


def reclassify_outros(batch_size: int = 1000) -> int:
    """Reclassifica artigos em 'Outros' com os temas e keywords atuais."""
    session = get_session()
    reclassified = 0
    try:
        topics = session.query(Topic).all()
        outros = next((t for t in topics if t.slug == "outros"), None)
        if not outros:
            return 0
        articles = (
            session.query(Article)
            .filter(Article.topic_id == outros.id)
            .limit(batch_size)
            .all()
        )
        for article in articles:
            text = f"{article.title or ''} {article.summary or ''} {article.transcript or ''}"
            topic_id, score = classify_article(text, topics)
            article.topic_id = topic_id
            article.topic_score = score
            reclassified += 1
        session.commit()
        print(f"  Reclassificados {reclassified} artigos de 'Outros'.")
    finally:
        session.close()
    return reclassified
