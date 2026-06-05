#!/usr/bin/env python3
"""Reclassifica o campo is_local de artigos já gravados.

Necessário após remover keywords de nlp/local_classifier.py: o pipeline normal
(`run_local_classification`) só processa is_local IS NULL e NUNCA reverte
True->False. Logo, falsos positivos antigos (marcados local por uma keyword que
foi removida) ficam presos como is_local=True. Este script os corrige.

Estratégia (segura quanto a custo/limite do Groq):
  - is_local=True que AINDA casa alguma keyword  -> mantém True (sem LLM).
  - is_local=True que NÃO casa mais nenhuma keyword -> reavalia via LLM:
        LLM "não" -> False ; LLM "sim" -> mantém True.
        Em erro/429 do Groq, PARA com segurança (artigo intacto) e reporta;
        basta re-rodar depois para continuar de onde parou.
  - --max-llm limita as chamadas por execução para não estourar o budget diário.

Uso (dentro do Railway):
  railway ssh --service coletor -- python scripts/reclassify_is_local.py --dry-run
  railway ssh --service coletor -- python scripts/reclassify_is_local.py --apply --recent 30
  railway ssh --service coletor -- python scripts/reclassify_is_local.py --apply --max-llm 400
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from db.connection import get_session
from db.models import Article
from nlp.local_classifier import _keyword_match


def _article_text(a) -> str:
    return f"{a.title or ''} {a.summary or ''} {a.transcript or ''}"


def _llm_is_local(text: str) -> bool:
    """Reavalia via LLM (mesmo modelo/prompt do pipeline). Levanta em erro."""
    from groq import Groq
    from nlp.prompts import render
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    prompt = render("is_local", text=text[:500])
    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0,
    )
    return resp.choices[0].message.content.strip().lower().startswith("sim")


def reclassify_is_local(recent_days=None, apply=False, batch_size=500, max_llm=500):
    session = get_session()
    try:
        q = session.query(Article.id).filter(Article.is_local.is_(True))
        if recent_days:
            cutoff = datetime.utcnow() - timedelta(days=recent_days)
            q = q.filter(Article.published_at >= cutoff)
        ids = [i for (i,) in q.all()]
        total = len(ids)
        escopo = f"últimos {recent_days} dias" if recent_days else "todos"
        print(f"Artigos is_local=True no escopo ({escopo}): {total}")
        if total == 0:
            return

        kept_kw = 0        # ainda casam keyword -> seguem local
        llm_calls = 0      # reavaliações via LLM feitas
        set_false = 0      # rebaixados para não-local
        kept_llm = 0       # LLM confirmou local
        candidates = 0     # km=None (precisariam de LLM); usado no dry-run
        examples_false = []
        stopped = None

        for start in range(0, total, batch_size):
            batch = session.query(Article).filter(
                Article.id.in_(ids[start:start + batch_size])
            ).all()
            for a in batch:
                if _keyword_match(_article_text(a)) is not None:
                    kept_kw += 1
                    continue
                candidates += 1
                if not apply:
                    continue
                if llm_calls >= max_llm:
                    stopped = f"limite de {max_llm} chamadas LLM atingido"
                    break
                try:
                    local = _llm_is_local(_article_text(a))
                except Exception as e:
                    stopped = f"erro/limite do Groq ({e})"
                    break
                llm_calls += 1
                if local:
                    kept_llm += 1
                else:
                    set_false += 1
                    a.is_local = False
                    if len(examples_false) < 15:
                        examples_false.append((a.title or "(sem título)")[:90])
            if apply:
                session.commit()
            done = min(start + batch_size, total)
            print(f"  processados {done}/{total} | keyword-mantidos {kept_kw} | "
                  f"LLM {llm_calls} (→False {set_false}, →True {kept_llm})")
            if stopped:
                break

        if apply:
            session.commit()

        print(f"\nRESULTADO ({'APLICADO' if apply else 'DRY-RUN'}):")
        print(f"  Mantidos local por keyword: {kept_kw}")
        if apply:
            print(f"  Reavaliados via LLM: {llm_calls}")
            print(f"    -> rebaixados para não-local (False): {set_false}")
            print(f"    -> confirmados local (True): {kept_llm}")
            if stopped:
                restantes = candidates - llm_calls
                print(f"  PAROU: {stopped}.")
                print(f"  ~{restantes} candidatos ainda por reavaliar — re-rode para continuar.")
        else:
            print(f"  Candidatos a reavaliar via LLM (não casam mais keyword): {candidates}")
            print(f"  -> um --apply faria até {candidates} chamadas ao Groq "
                  f"(use --max-llm para fracionar).")
        if examples_false:
            print("  Exemplos rebaixados para não-local:")
            for t in examples_false:
                print(f"    • {t}")
        if not apply:
            print("\n  DRY-RUN — nada foi alterado. Use --apply para aplicar.")
    finally:
        session.close()


def main():
    p = argparse.ArgumentParser(description="Reclassifica is_local de artigos gravados")
    p.add_argument("--recent", type=int, default=None, help="só artigos dos últimos N dias")
    p.add_argument("--apply", action="store_true", help="aplica de fato (padrão é dry-run)")
    p.add_argument("--dry-run", action="store_true", help="apenas simula (padrão)")
    p.add_argument("--batch-size", type=int, default=500, help="tamanho do batch de commit")
    p.add_argument("--max-llm", type=int, default=500, help="máx. de chamadas LLM por execução")
    args = p.parse_args()
    reclassify_is_local(
        recent_days=args.recent, apply=args.apply,
        batch_size=args.batch_size, max_llm=args.max_llm,
    )


if __name__ == "__main__":
    main()
