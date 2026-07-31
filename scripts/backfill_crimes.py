"""Backfill da extração de cobertura criminal sobre artigos já coletados.

Processa artigos locais dos temas Segurança Pública e Justiça e Direito que
ainda não passaram pelo extrator, dos mais recentes para os mais antigos.

Padrão é DRY-RUN e não gasta nada: apenas dimensiona a fila, distribui por mês
e estima o consumo de tokens. Use --apply para executar de fato.

Uso típico (fase 1 do plano — 90 dias):
    python scripts/backfill_crimes.py --days 90                 # dimensiona
    python scripts/backfill_crimes.py --days 90 --apply --max-llm 500

Dentro do Railway (o MySQL só tem endpoint interno):
    railway ssh --service coletor -- python scripts/backfill_crimes.py --days 90
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
from datetime import datetime, timedelta

from sqlalchemy import bindparam, text

from db.connection import get_session
from db.models import Article, Topic
from nlp.crime_extractor import (
    MAX_CONTENT_CHARS,
    TARGET_TOPICS,
    extract_from_article,
)

# Estimativas para o dry-run. O prompt fixo (instruções + vocabulário de 61
# figuras penais) mede ~5.400 caracteres; o texto do artigo entra truncado.
# Divide-se por 4 para aproximar caracteres → tokens em português.
PROMPT_FIXO_CHARS = 5400
SAIDA_TOKENS_EST = 300


def _pool(session, days: int | None):
    topic_ids = [
        t.id for t in session.query(Topic).filter(Topic.name.in_(TARGET_TOPICS)).all()
    ]
    if not topic_ids:
        return None
    q = session.query(Article).filter(
        Article.is_local.is_(True),
        Article.topic_id.in_(topic_ids),
        Article.crime_processed_at.is_(None),
    )
    if days:
        corte = datetime.utcnow() - timedelta(days=days)
        q = q.filter(Article.published_at >= corte)
    # MySQL não aceita NULLS LAST; em DESC ele já ordena os NULL por último.
    return q.order_by(Article.published_at.desc(), Article.id.desc())


def dimensionar(days: int | None):
    """Dry-run: conta a fila, distribui por mês e estima tokens. Não chama LLM."""
    session = get_session()
    try:
        q = _pool(session, days)
        if q is None:
            print("Nenhum tema encontrado entre", TARGET_TOPICS)
            return
        total = q.count()
        print(f"\nFila de backfill{f' (últimos {days} dias)' if days else ' (histórico completo)'}")
        print(f"  artigos a processar: {total}")
        if not total:
            return

        stmt = text("""
            SELECT DATE_FORMAT(a.published_at, '%Y-%m') AS mes, COUNT(*)
            FROM articles a
            JOIN topics t ON a.topic_id = t.id
            WHERE a.is_local = 1
              AND a.crime_processed_at IS NULL
              AND t.name IN :nomes
              AND (:corte IS NULL OR a.published_at >= :corte)
            GROUP BY mes ORDER BY mes DESC
        """).bindparams(bindparam("nomes", expanding=True))
        rows = session.execute(stmt, {
            "nomes": list(TARGET_TOPICS),
            "corte": (datetime.utcnow() - timedelta(days=days)) if days else None,
        }).fetchall()

        print("\n  distribuição por mês:")
        for mes, cnt in rows:
            barra = "█" * min(40, max(1, cnt // 20))
            print(f"    {mes or 'sem data'}  {cnt:5d}  {barra}")

        # amostra o tamanho real do texto para estimar tokens de entrada
        amostra = q.limit(200).all()
        if amostra:
            chars = sum(
                len(a.title or "")
                + min(len(a.summary or ""), 1500)
                + min(len(a.content or a.transcript or ""), MAX_CONTENT_CHARS)
                for a in amostra
            ) / len(amostra)
        else:
            chars = 0
        entrada = (PROMPT_FIXO_CHARS + chars) / 4
        print(f"\n  estimativa por chamada: ~{entrada:,.0f} tokens de entrada, "
              f"~{SAIDA_TOKENS_EST} de saída".replace(",", "."))
        print(f"  estimativa total: ~{entrada * total / 1_000_000:.2f}M tokens de entrada, "
              f"~{SAIDA_TOKENS_EST * total / 1_000_000:.2f}M de saída")
        print("\n  (dry-run — nada foi gravado. Use --apply para executar.)\n")
    finally:
        session.close()


def executar(days: int | None, max_llm: int, sleep: float, batch: int):
    session = get_session()
    processados = com_crime = mencoes = falhas_seguidas = 0
    inicio = time.time()
    try:
        q = _pool(session, days)
        if q is None:
            print("Nenhum tema encontrado entre", TARGET_TOPICS)
            return
        artigos = q.limit(max_llm).all()
        total = len(artigos)
        print(f"Processando {total} artigos (teto de {max_llm} chamadas)...\n")

        for i, article in enumerate(artigos, start=1):
            n = extract_from_article(session, article)

            if n < 0:
                falhas_seguidas += 1
                print(f"  [{i}/{total}] falha de API (seguidas: {falhas_seguidas})")
                if falhas_seguidas >= 5:
                    print("\n5 falhas seguidas — interrompendo para não queimar a fila "
                          "contra um provedor indisponível. Os artigos ficam pendentes "
                          "e serão retomados na próxima execução.")
                    break
                time.sleep(min(30, 2 ** falhas_seguidas))
                continue

            falhas_seguidas = 0
            processados += 1
            if n > 0:
                com_crime += 1
                mencoes += n

            if i % batch == 0:
                session.commit()
                decorrido = time.time() - inicio
                ritmo = i / decorrido if decorrido else 0
                restante = (total - i) / ritmo if ritmo else 0
                print(f"  [{i}/{total}] {com_crime} com crime, {mencoes} menções "
                      f"— {ritmo:.1f} art/s, ~{restante/60:.0f} min restantes")

            if sleep:
                time.sleep(sleep)

        session.commit()
        print(f"\nConcluído: {processados} artigos avaliados, {com_crime} com crime, "
              f"{mencoes} menções gravadas em {(time.time()-inicio)/60:.1f} min.")
        if processados:
            print(f"Taxa de artigos com crime: {100*com_crime/processados:.1f}%")
    finally:
        session.close()


def main():
    p = argparse.ArgumentParser(
        description="Backfill da extração de cobertura criminal")
    p.add_argument("--days", type=int, default=90,
                   help="janela em dias (padrão 90; use 0 para histórico completo)")
    p.add_argument("--apply", action="store_true",
                   help="executa de fato (padrão é dry-run, que não gasta nada)")
    p.add_argument("--max-llm", type=int, default=500,
                   help="teto de chamadas ao LLM nesta execução (padrão 500)")
    p.add_argument("--sleep", type=float, default=0.3,
                   help="pausa em segundos entre chamadas (padrão 0.3)")
    p.add_argument("--batch", type=int, default=25,
                   help="commit e relatório a cada N artigos (padrão 25)")
    p.add_argument("--cluster", action="store_true",
                   help="roda o agrupamento em eventos ao final")
    args = p.parse_args()

    days = args.days if args.days and args.days > 0 else None

    if not args.apply:
        dimensionar(days)
        return

    executar(days, args.max_llm, args.sleep, args.batch)

    if args.cluster:
        from nlp.crime_clusterer import run_crime_clustering
        print("\nAgrupando menções em casos...")
        total = 0
        while True:
            stats = run_crime_clustering(limit=500)
            total += stats["processadas"]
            if stats["processadas"] == 0:
                break
        print(f"Agrupamento concluído: {total} menções processadas.")


if __name__ == "__main__":
    main()
