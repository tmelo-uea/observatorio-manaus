import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import schedule
from db.connection import get_engine, Base
from db.seeds import seed_all
from collector.rss_collector import run_collection
from nlp.classifier import run_classification

Base.metadata.create_all(get_engine())
seed_all()

def reset_classification():
    from db.connection import get_session
    from db.models import Article
    session = get_session()
    try:
        session.query(Article).update({"topic_id": None, "topic_score": None})
        session.commit()
        print("Classificação resetada — todos os artigos serão reclassificados.")
    finally:
        session.close()

reset_classification()

def job():
    print("\n--- Iniciando coleta ---")
    run_collection()
    n = run_classification()
    print(f"Classificados: {n} artigos")

print("Observatório do Amazonas — Coletor iniciado")
job()

schedule.every(30).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
