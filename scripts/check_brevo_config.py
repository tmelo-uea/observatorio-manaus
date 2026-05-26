#!/usr/bin/env python3
"""Verificar configuração do Brevo."""

import os
import sys

print("\n" + "="*70)
print("🔍 VERIFICAÇÃO - CONFIGURAÇÃO DO BREVO")
print("="*70)

api_key = os.getenv("BREVO_API_KEY", "")
sender_email = os.getenv("BREVO_SENDER_EMAIL", "")
sender_name = os.getenv("BREVO_SENDER_NAME", "Observatório de Manaus")

print("\n1️⃣  VARIÁVEIS DE AMBIENTE:")
print(f"  BREVO_API_KEY: {'✓ Configurada' if api_key else '❌ NÃO configurada'}")
print(f"    Primeiros 20 chars: {api_key[:20] if api_key else 'N/A'}")
print(f"    Últimos 10 chars: ...{api_key[-10:] if api_key else 'N/A'}")
print(f"    Comprimento: {len(api_key) if api_key else 0} caracteres")

print(f"\n  BREVO_SENDER_EMAIL: {sender_email if sender_email else '❌ NÃO configurada'}")
print(f"  BREVO_SENDER_NAME: {sender_name}")

if not api_key or not sender_email:
    print("\n❌ ERRO CRÍTICO: Faltam variáveis de ambiente!")
    sys.exit(1)

print("\n2️⃣  VALIDAÇÃO DE EMAIL:")
# Validar formato do email
if "@" not in sender_email or "." not in sender_email.split("@")[1]:
    print(f"  ❌ Email inválido: {sender_email}")
    sys.exit(1)
else:
    print(f"  ✓ Email válido: {sender_email}")

print("\n3️⃣  VERIFICAÇÕES COMUNS NO BREVO:")
print(f"""
  ⚠️  Para o Brevo funcionar, verifique:

  1. Email remetente VERIFICADO:
     - Acesse: https://app.brevo.com/setting/account/sender
     - O email '{sender_email}' está verificado?
     - Se não, verifique clicando no link que Brevo enviou

  2. Remetente AUTORIZADO:
     - Acesse: https://app.brevo.com/setting/account/sender
     - O email '{sender_email}' está marcado como "Verificado"?

  3. Domínio VERIFICADO (se tiver):
     - Se usar domínio customizado (ex: noreply@seu-dominio.com)
     - Verifique SPF/DKIM em: https://app.brevo.com/setting/account/authentication

  4. LIMITE DE REQUISIÇÕES:
     - Seu plano Brevo tem limite de emails/dia?
     - Verificar em: https://app.brevo.com/setting/account/billing

  5. RATE LIMITING:
     - Brevo pode estar bloqueando por muitas requisições rápidas
     - Tente esperar alguns minutos entre testes

  6. VERIFICAR LOGS NO BREVO:
     - Acesse: https://app.brevo.com/activity
     - Há emails com status "Bounced", "Rejected" ou "Failed"?
""")

print("\n4️⃣  TESTAR MANUALMENTE NO BREVO:")
print("""
  1. Acesse: https://app.brevo.com
  2. Vá para: Marketing → Transactional
  3. Clique em: "Send a test email"
  4. Escolha template ou crie um teste simples
  5. Envie para: tiagoeugeniodemelo@gmail.com
  6. Se funcionar manualmente, o problema é na nossa integração
  7. Se não funcionar, o problema é na configuração do Brevo
""")

print("\n" + "="*70)
print("\n💡 PRÓXIMO PASSO:")
print("  1. Verifique se o email está verificado no Brevo")
print("  2. Se sim, considere MIGRAR PARA SENDGRID (mais confiável)")
print("  3. Se não, verifique o email de confirmação do Brevo")
print("="*70 + "\n")
