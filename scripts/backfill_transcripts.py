import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_session
from db.models import Article, Source
from collector.youtube_collector import _get_transcript, _video_id_from_url

MAX_SECONDS = 20 * 60  # nunca ultrapassa 20 min para não atrasar o próximo ciclo


def backfill(limit: int = 50):
    session = get_session()
    start = time.time()
    try:
        query = (
            session.query(Article)
            .join(Source)
            .filter(Source.type == "youtube", Article.transcript.is_(None))
        )
        total_pending = query.count()
        if total_pending == 0:
            return

        articles = query.limit(limit).all()
        batch = len(articles)
        print(f"Transcrições pendentes: {total_pending} | Processando até: {batch}")

        done = 0
        for i, article in enumerate(articles, 1):
            if time.time() - start > MAX_SECONDS:
                print(f"  [backfill] Limite de tempo atingido após {done} transcrições")
                break

            video_id = _video_id_from_url(article.url)
            if not video_id:
                continue

            transcript = _get_transcript(video_id, article.url)
            if transcript:
                article.transcript = transcript
                session.commit()
                done += 1
                elapsed = int(time.time() - start)
                print(f"[{i}/{batch}] OK ({elapsed}s): {article.title[:60]}")
            else:
                print(f"[{i}/{batch}] Sem transcrição: {article.title[:60]}")

    finally:
        session.close()


if __name__ == "__main__":
    backfill()
