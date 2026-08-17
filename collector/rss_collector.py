import feedparser
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from sqlalchemy.exc import IntegrityError
from db.connection import get_session
from db.models import Source, Article

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

def fetch_feed(url: str):
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        return feedparser.parse(resp.content), None
    except Exception as e:
        # Não usar feedparser.parse(url) aqui: se requests já falhou (inclusive
        # por timeout), deixar o feedparser buscar a URL por conta própria é
        # sem timeout algum (sem socket.setdefaulttimeout global no projeto),
        # e pode travar o job() inteiro por dias (incidente 2026-08-13/17).
        return feedparser.parse(""), str(e)


def parse_date(entry) -> datetime | None:
    # published_parsed/updated_parsed já são UTC (feedparser normaliza)
    for field in ("published_parsed", "updated_parsed"):
        value = getattr(entry, field, None)
        if value:
            return datetime(*value[:6])
    # Fallback para strings brutas: converter para UTC antes de remover tzinfo
    for field in ("published", "updated"):
        value = getattr(entry, field, None)
        if value:
            try:
                dt = parsedate_to_datetime(value)
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
    return None


def collect_source(source: Source) -> int:
    feed, fetch_err = fetch_feed(source.rss_url)
    if fetch_err:
        print(f"  [fetch] {source.name}: requests falhou ({fetch_err})")
    n_entries = len(feed.entries)
    if n_entries == 0:
        bozo_ex = type(feed.get("bozo_exception")).__name__ if feed.get("bozo_exception") else None
        print(f"  [feed vazio] {source.name}: status={feed.get('status','?')} bozo={feed.get('bozo')} bozo_ex={bozo_ex}")
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
    sources = session.query(Source).filter(
        Source.active == True,
        Source.type != "youtube",
    ).all()
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
