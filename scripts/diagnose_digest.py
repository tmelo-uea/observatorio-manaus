#!/usr/bin/env python3
"""Script para diagnosticar problemas no envio de digest."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, date
from db.connection import get_session
from db.models import EmailSubscription, DailySummary, Topic, DigestLog, Article

def manaus_today():
    return (datetime.utcnow() - timedelta(hours=4)).date()

print("\n" + "="*70)
print("🔍 DIAGNÓSTICO - SISTEMA DE DIGEST")
print("="*70)

# 1. Configuração
print("\n📧 1. CONFIGURAÇÃO DE EMAIL:")
sendgrid_key = os.getenv("SENDGRID_API_KEY", "")
brevo_key = os.getenv("BREVO_API_KEY", "")
brevo_email = os.getenv("BREVO_SENDER_EMAIL", "")
admin_pwd = os.getenv("ADMIN_PASSWORD", "")

print(f"  ✓ SENDGRID_API_KEY: {'✓ Configurada' if sendgrid_key else '✗ NÃO configurada'}")
print(f"  ✓ BREVO_API_KEY: {'✓ Configurada' if brevo_key else '✗ NÃO configurada'}")
print(f"  ✓ BREVO_SENDER_EMAIL: {brevo_email if brevo_email else '✗ NÃO configurada'}")
print(f"  ✓ ADMIN_PASSWORD: {'✓ Configurada' if admin_pwd else '✗ NÃO configurada'}")

if not (sendgrid_key or brevo_key):
    print("\n❌ ERRO CRÍTICO: Nenhum provedor de email configurado!")
    sys.exit(1)

provider = "Sendgrid" if sendgrid_key else "Brevo"
print(f"\n  📌 Usando: {provider}")

# 2. Assinantes
print("\n📋 2. ASSINANTES DE EMAIL:")
session = get_session()
try:
    total_subs = session.query(EmailSubscription).count()
    active_subs = session.query(EmailSubscription).filter_by(active=True).count()
    print(f"  ✓ Total: {total_subs}")
    print(f"  ✓ Ativos: {active_subs}")

    if active_subs == 0:
        print("  ⚠️  AVISO: Nenhum assinante ativo!")
    else:
        subs = session.query(EmailSubscription).filter_by(active=True).all()
        print(f"\n  Assinantes ativos:")
        for sub in subs:
            print(f"    - {sub.email}")
except Exception as e:
    print(f"  ❌ Erro ao consultar assinantes: {e}")
finally:
    session.close()

# 3. Resumos gerados
print("\n📝 3. RESUMOS GERADOS:")
session = get_session()
try:
    today = manaus_today()
    yesterday = today - timedelta(days=1)

    today_summaries = session.query(DailySummary).filter_by(date=today).count()
    yesterday_summaries = session.query(DailySummary).filter_by(date=yesterday).count()

    print(f"  ✓ Hoje ({today}): {today_summaries} resumos")
    print(f"  ✓ Ontem ({yesterday}): {yesterday_summaries} resumos")

    if today_summaries > 0:
        print(f"\n  Resumos de hoje:")
        summaries = session.query(DailySummary, Topic.name).join(Topic).filter_by(date=today).all()
        for summary, topic_name in summaries:
            print(f"    - {topic_name}: {summary.article_count} artigos")

    if yesterday_summaries > 0:
        print(f"\n  Resumos de ontem:")
        summaries = session.query(DailySummary, Topic.name).join(Topic).filter_by(date=yesterday).all()
        for summary, topic_name in summaries:
            print(f"    - {topic_name}: {summary.article_count} artigos")

except Exception as e:
    print(f"  ❌ Erro ao consultar resumos: {e}")
finally:
    session.close()

# 4. Histórico de envios
print("\n📊 4. HISTÓRICO DE ENVIOS:")
session = get_session()
try:
    logs = session.query(DigestLog).order_by(DigestLog.sent_at.desc()).limit(5).all()
    if logs:
        for log in logs:
            print(f"  ✓ {log.date}: {log.recipients} assinante(s)")
    else:
        print("  ℹ️  Nenhum envio registrado ainda")
except Exception as e:
    print(f"  ❌ Erro ao consultar histórico: {e}")
finally:
    session.close()

# 5. Artigos coletados
print("\n📰 5. ARTIGOS COLETADOS:")
session = get_session()
try:
    total_articles = session.query(Article).count()
    today_articles = session.query(Article).filter(
        Article.published_at >= datetime.utcnow() - timedelta(days=1)
    ).count()

    print(f"  ✓ Total coletado: {total_articles}")
    print(f"  ✓ Últimas 24h: {today_articles}")
except Exception as e:
    print(f"  ❌ Erro ao consultar artigos: {e}")
finally:
    session.close()

# 6. Testar envio
print("\n🚀 6. TESTAR ENVIO:")
print("\n  Para testar o envio, execute:")
print("  python scripts/test_digest.py")
print("\n  Ou clique no botão no dashboard:")
print("  1. Abra: https://observatorio-manaus-production.up.railway.app")
print("  2. Clique em ⚙️ Admin (sidebar)")
print("  3. Informe a senha")
print("  4. Clique em 📤 Disparar digest agora (teste)")

print("\n" + "="*70)
print("✓ Diagnóstico concluído")
print("="*70 + "\n")
