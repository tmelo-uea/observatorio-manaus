"""Busca e armazena o texto completo dos artigos via scraping da URL.

O campo `content` é para histórico e futura análise — não é usado nos resumos.
Estratégia por ciclo: processa os N artigos mais recentes sem content,
do mais novo para o mais antigo. Em falha, grava "" para não retentar
indefinidamente.

Portais com JavaScript obrigatório ou paywall resultarão em content="".
URLs do YouTube são ignoradas (conteúdo já vem via transcript).
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from db.connection import get_session
from db.models import Article

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _fetch_text(url: str, timeout: int = 10) -> str:
    """Retorna o texto extraído da URL, ou "" em qualquer falha."""
    try:
        import trafilatura
        resp = requests.get(url, headers=_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
        return text or ""
    except Exception:
        return ""


def backfill_content(limit: int = 30) -> int:
    """Preenche `content` dos artigos mais recentes que ainda não têm.

    Retorna o número de artigos processados (incluindo falhas).
    """
    try:
        import trafilatura  # noqa: F401
    except ImportError:
        print("  [content] trafilatura não instalado — backfill ignorado.")
        return 0

    session = get_session()
    try:
        articles = (
            session.query(Article)
            .filter(Article.content.is_(None))
            .filter(~Article.url.contains("youtube.com"))
            .order_by(Article.collected_at.desc())
            .limit(limit)
            .all()
        )
        if not articles:
            return 0

        fetched = 0
        failed = 0
        for a in articles:
            text = _fetch_text(a.url)
            a.content = text
            if text:
                fetched += 1
            else:
                failed += 1

        session.commit()
        print(f"  [content] backfill: {fetched} extraídos, {failed} sem conteúdo")
        return fetched + failed
    finally:
        session.close()
