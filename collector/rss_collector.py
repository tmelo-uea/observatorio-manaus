import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime
from sqlalchemy.exc import IntegrityError
from db.connection import get_session
from db.models import Source, Article


def parse_date(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        value = getattr(entry, field, None)
        if value:
            return datetime(*value[:6])
    for field in ("published", "updated"):
        value = getattr(entry, field, None)
        if value:
            try:
                return parsedate_to_datetime(value).replace(tzinfo=None)
            except Exception:
                pass
    return None


def collect_source(source: Source) -> int:
    feed = feedparser.parse(source.rss_url, agent="ObservatorioManaus/1.0")
    count = 0
    session = get_session()
    try:
        for entry in feed.entries:
            article = Article(
                title=entry.get("title", "")[:500],
                url=entry.get("link", "")[:767],
                summary=entry.get("summary", ""),
                published_at=parse_date(entry),
                source_id=source.id,
            )
            session.add(article)
            try:
                session.commit()
                count += 1
            except IntegrityError:
                session.rollback()
    finally:
        session.close()
    return count


def run_collection() -> dict:
    session = get_session()
    sources = session.query(Source).filter_by(active=True).all()
    session.close()

    results = {}
    for source in sources:
        if not source.rss_url:
            continue
        try:
            n = collect_source(source)
            results[source.name] = {"status": "ok", "new_articles": n}
            print(f"[OK] {source.name}: {n} novos artigos")
        except Exception as e:
            results[source.name] = {"status": "error", "message": str(e)}
            print(f"[ERRO] {source.name}: {e}")
    return results
