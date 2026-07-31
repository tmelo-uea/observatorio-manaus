"""Zera a extração de cobertura criminal para reprocessar tudo do zero.

Por que existe: as correções do extrator NÃO retroagem. Cada mudança de prompt,
taxonomia ou guarda vale só para o que for extraído depois — então a base
acumula registros de várias versões do classificador ao mesmo tempo. Uma
auditoria feita sobre essa mistura não consegue medir o classificador ATUAL, e
volta a reencontrar defeitos já corrigidos.

Zerar e reextrair resolve isso: a base inteira passa a ter uma versão só.

O que apaga:
  - crime_events    (camada derivada, recalculável)
  - crime_mentions  (a série primária)
  - articles.crime_processed_at → NULL, inclusive dos artigos avaliados como
    NÃO sendo crime, porque essa decisão também mudou (balanço estatístico,
    referência histórica, mandado sem crime informado).

⚠️ Exporte o CSV pela página ANTES de rodar com --apply, se quiser comparar a
classificação antiga com a nova. Depois disto não há como recuperá-la.

Depois de zerar, reextraia de uma vez em vez de esperar 20 por ciclo:
    python scripts/backfill_crimes.py --apply --max-llm 500 --cluster

Uso:
    python scripts/reprocess_crimes.py            # dry-run: só dimensiona
    python scripts/reprocess_crimes.py --apply
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse

from sqlalchemy import text

from db.connection import get_session
from nlp.crime_extractor import EXTRACT_MODEL, MAX_CONTENT_CHARS


def dimensionar(session) -> dict:
    q = lambda sql: session.execute(text(sql)).scalar() or 0
    return {
        "mencoes": q("SELECT COUNT(*) FROM crime_mentions"),
        "casos": q("SELECT COUNT(*) FROM crime_events"),
        "avaliados": q("SELECT COUNT(*) FROM articles WHERE crime_processed_at IS NOT NULL"),
        "com_crime": q("SELECT COUNT(DISTINCT article_id) FROM crime_mentions"),
    }


def main():
    p = argparse.ArgumentParser(description="Zera a extração criminal para reprocessar")
    p.add_argument("--apply", action="store_true",
                   help="executa de fato (padrão é dry-run)")
    args = p.parse_args()

    session = get_session()
    try:
        st = dimensionar(session)
        sem_crime = st["avaliados"] - st["com_crime"]

        print("\nEstado atual da extração criminal")
        print(f"  menções gravadas ............ {st['mencoes']}")
        print(f"  casos agrupados ............. {st['casos']}")
        print(f"  artigos já avaliados ........ {st['avaliados']}")
        print(f"    dos quais COM crime ....... {st['com_crime']}")
        print(f"    dos quais SEM crime ....... {sem_crime}")

        custo = st["avaliados"] * (5400 + MAX_CONTENT_CHARS * 0.5) / 4
        print(f"\nReextração completa: {st['avaliados']} chamadas ao {EXTRACT_MODEL}")
        print(f"  ~{custo/1_000_000:.2f}M tokens de entrada estimados")

        if not args.apply:
            print("\n(dry-run — nada apagado. Exporte o CSV antes e use --apply.)\n")
            return

        # Ordem importa: crime_mentions.event_id referencia crime_events.id, então
        # apagar os casos primeiro esbarra na chave estrangeira (erro 1451).
        session.execute(text("DELETE FROM crime_mentions"))
        session.execute(text("DELETE FROM crime_events"))
        n = session.execute(text(
            "UPDATE articles SET crime_processed_at = NULL "
            "WHERE crime_processed_at IS NOT NULL"
        )).rowcount
        session.commit()

        print(f"\nZerado. {n} artigos voltaram para a fila.")
        print("Reextraia de uma vez com:")
        print("  python scripts/backfill_crimes.py --apply --max-llm 500 --cluster\n")
    finally:
        session.close()


if __name__ == "__main__":
    main()
