import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_session
from db.models import Article, Source
from collector.youtube_collector import _get_transcript, _video_id_from_url


def backfill():
    session = get_session()
    try:
        articles = (
            session.query(Article)
            .join(Source)
            .filter(Source.type == "youtube", Article.transcript.is_(None))
            .all()
        )
        total = len(articles)
        print(f"Vídeos sem transcrição: {total}")

        for i, article in enumerate(articles, 1):
            video_id = _video_id_from_url(article.url)
            if not video_id:
                print(f"[{i}/{total}] Sem video_id: {article.url}")
                continue

            transcript = _get_transcript(video_id, article.url)
            if transcript:
                article.transcript = transcript
                session.commit()
                print(f"[{i}/{total}] OK: {article.title[:60]}")
            else:
                print(f"[{i}/{total}] Sem transcrição: {article.title[:60]}")

    finally:
        session.close()


if __name__ == "__main__":
    backfill()
