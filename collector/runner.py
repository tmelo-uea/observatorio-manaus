import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import logging
import schedule

# Configura o logging do pipeline para que as mensagens INFO dos módulos
# (classificador, resumos, adjetivos, métricas de escrita...) apareçam nos
# logs do Railway. Sem isto, INFO é descartado e só os print() são visíveis.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# Silencia bibliotecas HTTP muito verbosas (cada requisição Groq/OpenAI logaria).
for _noisy in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

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
from nlp.writing_metrics import run_writing_metrics, run_writing_insight
from nlp.crime_extractor import run_crime_extraction
from nlp.crime_clusterer import run_crime_clustering

Base.metadata.create_all(get_engine())
run_migrations()
seed_all()
seed_prompts()


def _safe(step_name, fn, *args, **kwargs):
    """Roda uma etapa do pipeline isolada: uma exceção aqui não pode derrubar
    o processo inteiro, senão a coleta de RSS das ~60 fontes fica bloqueada
    até alguém notar e reiniciar manualmente (caso real: run_digest() estourou
    RuntimeError quando o Sendgrid ficou sem créditos, e como job() não isolava
    as etapas, isso matou o container e a coleta ficou parada por 11h)."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"[ERRO] Etapa '{step_name}' falhou: {e}")
        return None


def job():
    print("\n--- Iniciando coleta ---")
    _safe("run_collection", run_collection)
    n_yt = _safe("run_youtube_collection", run_youtube_collection)
    print(f"YouTube: {n_yt} novos vídeos")
    n = _safe("run_classification", run_classification)
    print(f"Classificados: {n} artigos")
    n_local = _safe("run_local_classification", run_local_classification)
    print(f"Localidade classificada: {n_local} artigos")
    # Ordem importa: as etapas baratas e determinísticas vêm primeiro. A
    # transcrição do YouTube é a mais lenta e a mais instável — quando o YouTube
    # bloqueia o IP do datacenter ela consome os 20 min de teto sem entregar nada,
    # e tudo que estivesse atrás dela ficava com o que sobrasse da janela (em
    # geral, nada). Cobertura criminal depende só do backfill_content, então sobe.
    _safe("backfill_content", backfill_content, limit=30)  # busca texto completo dos 30 artigos mais recentes sem content
    _safe("run_crime_extraction", run_crime_extraction, limit=20)
    _safe("run_crime_clustering", run_crime_clustering, limit=200)
    _safe("backfill", backfill, limit=50)  # transcrições: até 50 vídeos, teto de 20 min, com disjuntor
    _safe("reclassify_outros", reclassify_outros, batch_size=200)  # reclassifica vídeos que ganharam transcript
    _safe("run_daily_summary", run_daily_summary)
    _safe("run_topic_summaries", run_topic_summaries, min_articles=5)
    _safe("run_digest", run_digest)
    _safe("run_adjective_extraction", run_adjective_extraction)
    _safe("run_writing_metrics", run_writing_metrics)
    _safe("run_writing_insight_source", run_writing_insight, "source")
    _safe("run_writing_insight_topic", run_writing_insight, "topic")

print("Observatório do Amazonas — Coletor iniciado")
print("Reclassificando artigos em 'Outros'...")
_safe("reclassify_outros_inicial", reclassify_outros, batch_size=2000)
print("Classificando localidade de artigos históricos (keywords)...")
n_backfill = _safe("backfill_local_keywords", backfill_local_keywords, batch_size=10000)
print(f"  Backfill is_local: {n_backfill} artigos classificados")
print("Gerando resumos iniciais...")
_safe("run_daily_summary_inicial", run_daily_summary)
_safe("run_topic_summaries_inicial", run_topic_summaries, min_articles=5)
job()

schedule.every(30).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
