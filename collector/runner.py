import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import schedule
from db.connection import get_engine, Base, run_migrations
from db.seeds import seed_all
from collector.rss_collector import run_collection
from collector.youtube_collector import run_youtube_collection
from nlp.classifier import run_classification
from scripts.backfill_transcripts import backfill

Base.metadata.create_all(get_engine())
run_migrations()
seed_all()


def job():
    print("\n--- Iniciando coleta ---")
    run_collection()
    n_yt = run_youtube_collection()
    print(f"YouTube: {n_yt} novos vídeos")
    n = run_classification()
    print(f"Classificados: {n} artigos")

print("Observatório do Amazonas — Coletor iniciado")
print("Preenchendo transcrições pendentes...")
backfill()
job()

schedule.every(30).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
