import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import schedule
from db.connection import get_engine, Base, run_migrations
from db.seeds import seed_all
from collector.rss_collector import run_collection
from collector.youtube_collector import run_youtube_collection
from nlp.classifier import run_classification, reclassify_outros
from nlp.local_classifier import run_local_classification, backfill_local_keywords
from nlp.summarizer import run_daily_summary, run_topic_summaries
from nlp.prompts import seed_prompts
from scripts.backfill_transcripts import backfill
from collector.content_fetcher import backfill_content
from notifications.email_sender import run_digest
from nlp.adjective_extractor import run_adjective_extraction

Base.metadata.create_all(get_engine())
run_migrations()
seed_all()
seed_prompts()


def job():
    print("\n--- Iniciando coleta ---")
    run_collection()
    n_yt = run_youtube_collection()
    print(f"YouTube: {n_yt} novos vídeos")
    n = run_classification()
    print(f"Classificados: {n} artigos")
    n_local = run_local_classification()
    print(f"Localidade classificada: {n_local} artigos")
    backfill(limit=50)  # processa até 50 vídeos, respeitando limite de 20 min
    backfill_content(limit=30)  # busca texto completo dos 30 artigos mais recentes sem content
    reclassify_outros(batch_size=200)  # reclassifica vídeos que ganharam transcript
    run_daily_summary()
    run_topic_summaries(min_articles=5)
    run_digest()
    run_adjective_extraction()

print("Observatório do Amazonas — Coletor iniciado")
print("Reclassificando artigos em 'Outros'...")
reclassify_outros(batch_size=2000)
print("Classificando localidade de artigos históricos (keywords)...")
n_backfill = backfill_local_keywords(batch_size=10000)
print(f"  Backfill is_local: {n_backfill} artigos classificados")
print("Gerando resumos iniciais...")
run_daily_summary()
run_topic_summaries(min_articles=5)
job()

schedule.every(30).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
