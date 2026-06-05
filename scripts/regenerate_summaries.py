#!/usr/bin/env python3
"""Regenera os resumos diários para uma data específica.

Uso:
  python3 scripts/regenerate_summaries.py              # ontem (Manaus)
  python3 scripts/regenerate_summaries.py 2026-05-25   # data específica
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime, timedelta, date
from db.connection import get_session
from db.models import Article, Source, Topic, DailySummary
from nlp.summarizer import _build_prompt, _call_llm


def _manaus_day_utc_range(d: date):
    start = datetime(d.year, d.month, d.day, 4, 0, 0)
    return start, start + timedelta(days=1)


def regenerate_for_date(target_date: date):
    session = get_session()
    try:
        start_utc, end_utc = _manaus_day_utc_range(target_date)
        topics = session.query(Topic).filter(Topic.slug != "outros").all()

        print(f"\n📅 Regenerando resumos para {target_date}")
        print(f"   UTC range: {start_utc} → {end_utc}")
        print("="*70)

        for topic in topics:
            articles = (
                session.query(Article).join(Source).filter(
                    Article.published_at >= start_utc,
                    Article.published_at < end_utc,
                    Article.topic_id == topic.id,
                    Source.active == True,
                    Article.is_local == True,
                )
                .order_by(Article.published_at.desc())
                .all()
            )

            if len(articles) < 3:
                print(f"  ⏭️  {topic.name}: {len(articles)} artigos — pulando")
                continue

            print(f"\n  📝 {topic.name}: {len(articles)} artigos")
            prompt = _build_prompt(articles, topic.name)
            text = _call_llm(prompt)

            if not text:
                print(f"     ❌ Falha ao gerar resumo")
                continue

            existing = session.query(DailySummary).filter_by(
                date=target_date, topic_id=topic.id
            ).first()

            article_ids = [a.id for a in articles]

            if existing:
                existing.summary = text
                existing.article_ids = article_ids
                existing.article_count = len(articles)
                existing.generated_at = datetime.utcnow()
            else:
                new_summary = DailySummary(
                    date=target_date,
                    topic_id=topic.id,
                    summary=text,
                    article_ids=article_ids,
                    article_count=len(articles),
                    generated_at=datetime.utcnow(),
                )
                session.add(new_summary)

            session.commit()
            print(f"     ✓ Resumo salvo ({len(text)} chars)")
            time.sleep(2)  # Evita rate limit do provedor

        # Resumo geral (sem topic_id)
        print(f"\n  📝 Resumo geral do dia")
        articles = (
            session.query(Article).join(Source).filter(
                Article.published_at >= start_utc,
                Article.published_at < end_utc,
                Source.active == True,
            ).all()
        )

        if len(articles) >= 3:
            prompt = _build_prompt(articles, None)
            text = _call_llm(prompt)

            if text:
                existing = session.query(DailySummary).filter_by(
                    date=target_date, topic_id=None
                ).first()
                article_ids = [a.id for a in articles]

                if existing:
                    existing.summary = text
                    existing.article_ids = article_ids
                    existing.article_count = len(articles)
                    existing.generated_at = datetime.utcnow()
                else:
                    session.add(DailySummary(
                        date=target_date,
                        topic_id=None,
                        summary=text,
                        article_ids=article_ids,
                        article_count=len(articles),
                        generated_at=datetime.utcnow(),
                    ))
                session.commit()
                print(f"     ✓ Resumo geral salvo ({len(text)} chars)")

        print("\n" + "="*70)
        print("✅ Regeneração concluída!")
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    else:
        target = (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=1)

    regenerate_for_date(target)
