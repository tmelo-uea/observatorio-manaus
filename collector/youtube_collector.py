import re
import feedparser
import requests
from datetime import datetime

from db.connection import get_session
from db.models import Article, Source


def _resolve_rss_url(channel_url: str) -> str | None:
    """Converte uma URL de canal do YouTube para a URL do RSS feed."""
    if "feeds/videos.xml" in channel_url:
        return channel_url
    try:
        resp = requests.get(
            channel_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', resp.text)
        if not match:
            return None
        channel_id = match.group(1)
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    except Exception:
        return None


def _get_transcript(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["pt", "pt-BR", "en"])
        return " ".join(t["text"] for t in transcript)
    except Exception:
        return None


def _video_id_from_url(url: str) -> str | None:
    match = re.search(r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None


def _collect_channel(source: Source, session) -> int:
    rss_url = _resolve_rss_url(source.rss_url)
    if not rss_url:
        print(f"  [{source.name}] Não foi possível resolver o RSS.")
        return 0

    # Atualiza rss_url no banco se foi resolvido agora
    if rss_url != source.rss_url:
        source.rss_url = rss_url
        session.flush()

    feed = feedparser.parse(rss_url)
    collected = 0

    for entry in feed.entries:
        url = entry.get("link", "")
        if not url or session.query(Article).filter_by(url=url).first():
            continue

        video_id = _video_id_from_url(url)
        transcript = _get_transcript(video_id) if video_id else None

        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6])

        summary = entry.get("summary", "") or ""
        # O RSS do YouTube inclui HTML no summary; remove tags básicas
        summary = re.sub(r"<[^>]+>", "", summary).strip()

        article = Article(
            title=(entry.get("title", "") or "")[:500],
            url=url[:767],
            summary=summary or None,
            published_at=published,
            source_id=source.id,
            transcript=transcript,
        )
        session.add(article)
        collected += 1

    session.commit()
    return collected


def run_youtube_collection() -> int:
    session = get_session()
    total = 0
    try:
        sources = session.query(Source).filter_by(type="youtube", active=True).all()
        for source in sources:
            n = _collect_channel(source, session)
            if n:
                print(f"  {source.name}: {n} novos vídeos")
            total += n
    finally:
        session.close()
    return total
