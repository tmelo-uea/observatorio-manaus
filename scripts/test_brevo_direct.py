#!/usr/bin/env python3
"""Teste direto da API do Brevo com retry."""

import os
import sys
import requests
import time

api_key = os.getenv("BREVO_API_KEY")
sender_email = os.getenv("BREVO_SENDER_EMAIL")

print("\n" + "="*70)
print("🔍 TESTE DIRETO - BREVO API")
print("="*70)

if not api_key:
    print("❌ BREVO_API_KEY não configurada!")
    sys.exit(1)

if not sender_email:
    print("❌ BREVO_SENDER_EMAIL não configurada!")
    sys.exit(1)

print(f"✓ API Key: {api_key[:20]}...{api_key[-10:]}")
print(f"✓ Remetente: {sender_email}")

# Email de teste
test_email = "tiagoeugeniodemelo@gmail.com"
print(f"\n📧 Enviando email de teste para: {test_email}")

headers = {
    "api-key": api_key,
    "Content-Type": "application/json",
}

payload = {
    "to": [{"email": test_email}],
    "sender": {"name": "Observatório de Manaus", "email": sender_email},
    "subject": "🧪 Teste Brevo - Observatório de Manaus",
    "htmlContent": "<h1>Teste</h1><p>Se você recebeu este email, a API do Brevo está funcionando!</p>",
}

max_retries = 3
timeout_sec = 30

for attempt in range(1, max_retries + 1):
    try:
        print(f"\n⏳ Tentativa {attempt}/{max_retries} (timeout: {timeout_sec}s)...")
        start = time.time()

        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers=headers,
            timeout=timeout_sec,
        )

        elapsed = time.time() - start
        print(f"  Resposta em {elapsed:.2f}s")
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 201:
            print(f"\n✅ SUCESSO! Email enviado.")
            print(f"   Resposta: {resp.json()}")
            sys.exit(0)
        else:
            print(f"  Erro: {resp.text}")
            if attempt < max_retries:
                wait_sec = 2 ** attempt
                print(f"  Aguardando {wait_sec}s...")
                time.sleep(wait_sec)
            else:
                print(f"\n❌ Falha após {max_retries} tentativas")
                sys.exit(1)

    except requests.Timeout:
        print(f"  ⏱️  TIMEOUT após {timeout_sec}s")
        if attempt < max_retries:
            wait_sec = 2 ** attempt
            print(f"  Aguardando {wait_sec}s para retry...")
            time.sleep(wait_sec)
        else:
            print(f"\n❌ Timeout após {max_retries} tentativas")
            sys.exit(1)

    except Exception as e:
        print(f"  ❌ Erro: {type(e).__name__}: {e}")
        sys.exit(1)

print("\n❌ Erro inesperado")
sys.exit(1)
