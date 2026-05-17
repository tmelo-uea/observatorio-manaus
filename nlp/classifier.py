import unicodedata
from db.connection import get_session
from db.models import Article, Topic


def normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def classify_article(text: str, topics: list[Topic]) -> tuple[int, float]:
    normalized = normalize(text)
    outros_id = next((t.id for t in topics if t.slug == "outros"), None)

    best_topic_id = outros_id
    best_score = 0.0

    for topic in topics:
        if topic.slug == "outros" or not topic.keywords:
            continue
        matches = sum(1 for kw in topic.keywords if normalize(kw) in normalized)
        score = matches / len(topic.keywords)
        if matches > best_score:
            best_score = score
            best_topic_id = topic.id

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
            text = f"{article.title or ''} {article.summary or ''}"
            topic_id, score = classify_article(text, topics)
            article.topic_id = topic_id
            article.topic_score = score
            classified += 1
        session.commit()
    finally:
        session.close()
    return classified
