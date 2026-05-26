#!/usr/bin/env python3
"""Teste completo do digest - simula exatamente o que o botão faz."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, date
from db.connection import get_session
from db.models import EmailSubscription, DailySummary, Topic, Article
from notifications.email_sender import run_digest

print("\n" + "="*70)
print("🧪 TESTE COMPLETO - DIGEST")
print("="*70)

def manaus_today():
    return (datetime.utcnow() - timedelta(hours=4)).date()

# 1. Verificar assinantes
print("\n1️⃣  VERIFICANDO ASSINANTES:")
session = get_session()
try:
    active_subs = session.query(EmailSubscription).filter_by(active=True).all()
    print(f"   Assinantes ativos: {len(active_subs)}")

    if len(active_subs) == 0:
        print("   ⚠️  AVISO: Sem assinantes! Digest não será enviado.")
        print("   Adicione assinantes pelo dashboard.")
        sys.exit(1)

    for sub in active_subs:
        print(f"   - {sub.email}")
except Exception as e:
    print(f"   ❌ Erro: {e}")
    sys.exit(1)
finally:
    session.close()

# 2. Verificar resumos
print("\n2️⃣  VERIFICANDO RESUMOS:")
session = get_session()
try:
    today = manaus_today()
    yesterday = today - timedelta(days=1)

    today_summaries = session.query(DailySummary).filter_by(date=today).count()
    yesterday_summaries = session.query(DailySummary).filter_by(date=yesterday).count()

    print(f"   Hoje ({today}): {today_summaries} resumos")
    print(f"   Ontem ({yesterday}): {yesterday_summaries} resumos")

    if today_summaries == 0 and yesterday_summaries == 0:
        print("   ⚠️  AVISO: Sem resumos! Rodando coletor primeiro...")
        # Não rodamos o coletor aqui para não complicar
        sys.exit(1)

    if yesterday_summaries > 0:
        print(f"\n   Resumos de ontem:")
        summaries = session.query(DailySummary, Topic.name).join(Topic).filter_by(date=yesterday).all()
        for summary, topic_name in summaries:
            print(f"   - {topic_name}: {summary.article_count} artigos")
except Exception as e:
    print(f"   ❌ Erro: {e}")
    sys.exit(1)
finally:
    session.close()

# 3. Configuração de email
print("\n3️⃣  CONFIGURAÇÃO DE EMAIL:")
sendgrid_key = os.getenv("SENDGRID_API_KEY", "")
brevo_key = os.getenv("BREVO_API_KEY", "")
brevo_email = os.getenv("BREVO_SENDER_EMAIL", "")

print(f"   Sendgrid: {'✓ Configurada' if sendgrid_key else '✗ Não'}")
print(f"   Brevo API Key: {'✓ Configurada' if brevo_key else '✗ Não'}")
print(f"   Brevo Sender Email: {brevo_email if brevo_email else '✗ Não'}")

if not (sendgrid_key or brevo_key):
    print("   ❌ Nenhum provedor configurado!")
    sys.exit(1)

provider = "Sendgrid" if sendgrid_key else "Brevo"
print(f"   → Usando: {provider}")

# 4. TESTAR ENVIO
print("\n4️⃣  TESTANDO ENVIO (force=True, min_summaries=1):")
print("   Aguarde... (pode levar até 2 minutos se houver retry)")
print()

try:
    sent = run_digest(force=True, min_summaries=1)
    print()
    print(f"✅ SUCESSO! {sent} email(s) enviado(s)")
    print("\n   Verifique seu email em alguns segundos.")
except Exception as e:
    print()
    print(f"❌ ERRO: {e}")
    print("\n   Detalhes:")
    print(f"   - Tipo: {type(e).__name__}")
    print(f"   - Mensagem: {str(e)}")

    if "timeout" in str(e).lower():
        print("\n   💡 SUGESTÃO:")
        print("   A API do Brevo está muito lenta ou há problema de conectividade.")
        print("   Considere migrar para Sendgrid (mais rápido e confiável).")
        print("\n   Para migrar:")
        print("   1. Crie conta em https://sendgrid.com")
        print("   2. Obtenha API key e email remetente")
        print("   3. Configure em Railway: SENDGRID_API_KEY + SENDGRID_FROM_EMAIL")
        print("   4. Código automaticamente usará Sendgrid")

    sys.exit(1)

print("\n" + "="*70)
