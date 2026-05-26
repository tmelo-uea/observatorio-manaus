#!/usr/bin/env python3
"""Teste simples da API do Sendgrid - sem dependências externas."""

import urllib.request
import urllib.error
import json
import os
import sys
import time
import socket

print("\n" + "="*70)
print("🧪 TESTE SIMPLES - API DO SENDGRID")
print("="*70)

api_key = os.getenv("SENDGRID_API_KEY")
from_email = os.getenv("SENDGRID_FROM_EMAIL")
from_name = os.getenv("SENDGRID_FROM_NAME", "Observatório de Manaus")
test_email = "tiagoeugeniodemelo@gmail.com"

print("\n📧 CONFIGURAÇÃO:")
print(f"  API Key: {api_key[:20] + '...' if api_key else '❌ NÃO configurada'}")
print(f"  From Email: {from_email if from_email else '❌ NÃO configurada'}")
print(f"  From Name: {from_name}")
print(f"  Test Email: {test_email}")

if not api_key:
    print("\n❌ ERRO: SENDGRID_API_KEY não configurada")
    print("   Configure no Railway ou exporte como variável de ambiente")
    sys.exit(1)

if not from_email:
    print("\n❌ ERRO: SENDGRID_FROM_EMAIL não configurada")
    sys.exit(1)

payload = {
    "personalizations": [{"to": [{"email": test_email}]}],
    "from": {"email": from_email, "name": from_name},
    "subject": "🧪 Teste Sendgrid - Observatório de Manaus",
    "content": [{"type": "text/html", "value": "<h1>Teste Sendgrid</h1><p>Se você recebeu este email, a API do Sendgrid está funcionando!</p>"}],
}

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

print("\n📤 ENVIANDO EMAIL DE TESTE...")
print(f"  URL: https://api.sendgrid.com/v3/mail/send")
print(f"  Timeout: 20 segundos\n")

socket.setdefaulttimeout(20)

try:
    print(f"⏳ Enviando...")
    start = time.time()

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )

    with urllib.request.urlopen(req) as response:
        elapsed = time.time() - start
        status = response.status
        body = response.read().decode('utf-8')

        print(f"   Status: {status}")
        print(f"   Tempo: {elapsed:.2f}s")

        if status == 202:
            print(f"\n✅ SUCESSO! Email enviado em {elapsed:.2f}s")
            print("   Verifique sua caixa de email em alguns segundos.")
            sys.exit(0)
        else:
            print(f"\n❌ Status inesperado: {status}")
            print(f"   Resposta: {body}")
            sys.exit(1)

except urllib.error.HTTPError as e:
    elapsed = time.time() - start
    error_body = e.read().decode('utf-8')
    print(f"\n❌ HTTP Error {e.code}: {e.reason}")
    print(f"   Tempo: {elapsed:.2f}s")
    print(f"   Resposta: {error_body}")

    if e.code == 401:
        print("\n💡 Chave API inválida. Gere uma nova em:")
        print("   https://app.sendgrid.com/settings/api_keys")
    elif e.code == 403:
        print("\n💡 Sender não verificado. Configure em:")
        print("   https://app.sendgrid.com/settings/sender_auth/senders")
    sys.exit(1)

except urllib.error.URLError as e:
    elapsed = time.time() - start
    print(f"\n❌ URL Error: {e.reason}")
    print(f"   Tempo: {elapsed:.2f}s")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ Erro: {type(e).__name__}: {e}")
    sys.exit(1)
