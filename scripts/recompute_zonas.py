"""Recalcula bairro normalizado e zona das menções e casos já gravados.

A zona é derivada do bairro por um mapa estático (nlp/manaus_geo.py). Quando o
mapa muda — correção de erro, bairro novo oficializado — as linhas antigas ficam
com a derivação velha. Este script refaz a derivação sobre o que já está no banco.

Não usa LLM e não altera nada além de bairro/zona: é barato e idempotente.
Padrão é dry-run.

    railway ssh --service coletor -- python scripts/recompute_zonas.py
    railway ssh --service coletor -- python scripts/recompute_zonas.py --apply
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from collections import Counter

from db.connection import get_session
from db.models import CrimeEvent, CrimeMention
from nlp.manaus_geo import resolve


def recompute(apply: bool = False):
    session = get_session()
    mudancas = Counter()
    try:
        for modelo, nome in ((CrimeMention, "menções"), (CrimeEvent, "casos")):
            linhas = session.query(modelo).filter(modelo.bairro.isnot(None)).all()
            alteradas = 0
            for linha in linhas:
                bairro, zona = resolve(linha.bairro)
                if bairro == linha.bairro and zona == linha.zona:
                    continue
                alteradas += 1
                mudancas[f"{linha.zona or 'nenhuma'} → {zona or 'nenhuma'}"] += 1
                if apply:
                    linha.bairro, linha.zona = bairro, zona
            print(f"{nome}: {len(linhas)} com bairro, {alteradas} a corrigir")

        if mudancas:
            print("\nmudanças de zona:")
            for k, v in mudancas.most_common():
                print(f"  {k:34s} {v}")

        if apply:
            session.commit()
            print("\nAplicado.")
        else:
            print("\n(dry-run — nada gravado. Use --apply.)")
    finally:
        session.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Recalcula zona a partir do bairro")
    p.add_argument("--apply", action="store_true", help="grava (padrão é dry-run)")
    recompute(p.parse_args().apply)
