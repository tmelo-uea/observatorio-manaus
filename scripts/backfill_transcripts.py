import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_session
from db.models import Article, Source
from collector.youtube_collector import _get_transcript, _video_id_from_url


def backfill(limit: int | None = None):
    session = get_session()
    try:
        query = (
            session.query(Article)
            .join(Source)
            .filter(Source.type == "youtube", Article.transcript.is_(None))
        )
        total_pending = query.count()
        if total_pending == 0:
            return

        articles = query.limit(limit).all() if limit else query.all()
        batch = len(articles)
        print(f"Transcrições pendentes: {total_pending} | Processando: {batch}")

        for i, article in enumerate(articles, 1):
            video_id = _video_id_from_url(article.url)
            if not video_id:
                continue

            transcript = _get_transcript(video_id, article.url)
            if transcript:
                article.transcript = transcript
                session.commit()
                print(f"[{i}/{batch}] OK: {article.title[:60]}")
            else:
                print(f"[{i}/{batch}] Sem transcrição: {article.title[:60]}")

    finally:
        session.close()


if __name__ == "__main__":
    backfill()
