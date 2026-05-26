#!/usr/bin/env python3
"""Reclassifica artigos no banco usando o classificador atual.

Estratégias disponíveis:
  --low-score        Reclassifica artigos com topic_score < threshold (default: 0.05)
  --recent N         Reclassifica artigos dos últimos N dias
  --all              Reclassifica TODOS os artigos (cuidado: lento)
  --dry-run          Mostra o que seria reclassificado sem aplicar
  --topic SLUG       Reclassifica apenas artigos do tema (ex: --topic tecnologia-inovacao)

Exemplos:
  python scripts/reclassify_articles.py --low-score --recent 7
  python scripts/reclassify_articles.py --topic tecnologia-inovacao --dry-run
  python scripts/reclassify_articles.py --all
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from db.connection import get_session
from db.models import Article, Topic
from nlp.classifier import classify_article


def main():
    parser = argparse.ArgumentParser(description="Reclassifica artigos no banco")
    parser.add_argument("--low-score", action="store_true",
                        help="Apenas artigos com topic_score abaixo do threshold")
    parser.add_argument("--score-threshold", type=float, default=0.05,
                        help="Threshold de score (default: 0.05)")
    parser.add_argument("--recent", type=int, default=None,
                        help="Apenas artigos dos últimos N dias")
    parser.add_argument("--all", action="store_true",
                        help="Reclassifica todos os artigos (cuidado!)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra o que seria mudado sem aplicar")
    parser.add_argument("--topic", type=str, default=None,
                        help="Slug do tema específico (ex: tecnologia-inovacao)")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Tamanho do batch para commit")
    args = parser.parse_args()

    if not any([args.low_score, args.recent, args.all, args.topic]):
        print("❌ Especifique pelo menos uma estratégia: --low-score, --recent N, --all ou --topic SLUG")
        parser.print_help()
        sys.exit(1)

    session = get_session()
    try:
        topics = session.query(Topic).all()
        topics_by_id = {t.id: t for t in topics}

        query = session.query(Article)

        if args.topic:
            topic = next((t for t in topics if t.slug == args.topic), None)
            if not topic:
                print(f"❌ Tema '{args.topic}' não encontrado")
                sys.exit(1)
            query = query.filter(Article.topic_id == topic.id)
            print(f"🎯 Filtrando por tema: {topic.name}")

        if args.low_score:
            query = query.filter(Article.topic_score < args.score_threshold)
            print(f"🎯 Filtrando por score < {args.score_threshold}")

        if args.recent is not None:
            cutoff = datetime.utcnow() - timedelta(days=args.recent)
            query = query.filter(Article.published_at >= cutoff)
            print(f"🎯 Filtrando últimos {args.recent} dias (desde {cutoff.date()})")

        total = query.count()
        print(f"\n📊 Total a reclassificar: {total} artigo(s)")

        if total == 0:
            print("Nada a fazer.")
            return

        if args.dry_run:
            print("\n🔍 DRY RUN — não vai aplicar mudanças\n")

        changes = {"same": 0, "changed": 0}
        change_examples = []
        processed = 0

        articles = query.yield_per(args.batch_size)
        for article in articles:
            text = f"{article.title or ''} {article.summary or ''} {article.transcript or ''}"
            new_topic_id, new_score = classify_article(text, topics)

            old_topic_id = article.topic_id
            old_topic = topics_by_id.get(old_topic_id)
            new_topic = topics_by_id.get(new_topic_id)

            if old_topic_id != new_topic_id:
                changes["changed"] += 1
                if len(change_examples) < 10:
                    change_examples.append({
                        "title": article.title[:80] if article.title else "(sem título)",
                        "from": old_topic.name if old_topic else "(nenhum)",
                        "to": new_topic.name if new_topic else "(nenhum)",
                        "score": new_score,
                    })

                if not args.dry_run:
                    article.topic_id = new_topic_id
                    article.topic_score = new_score
            else:
                changes["same"] += 1
                if not args.dry_run and article.topic_score != new_score:
                    article.topic_score = new_score

            processed += 1
            if processed % args.batch_size == 0:
                if not args.dry_run:
                    session.commit()
                print(f"  Processados: {processed}/{total} ({changes['changed']} mudaram)")

        if not args.dry_run:
            session.commit()

        print(f"\n📊 RESULTADO:")
        print(f"   Total processado: {processed}")
        print(f"   Mantidos no mesmo tema: {changes['same']}")
        print(f"   Reclassificados: {changes['changed']}")

        if change_examples:
            print(f"\n🔄 Exemplos de mudanças:")
            for ex in change_examples:
                print(f"   • {ex['title']}")
                print(f"     {ex['from']} → {ex['to']} (score: {ex['score']})")

        if args.dry_run:
            print("\n⚠️  DRY RUN — nenhuma mudança aplicada. Rode sem --dry-run para aplicar.")

    finally:
        session.close()


if __name__ == "__main__":
    main()
