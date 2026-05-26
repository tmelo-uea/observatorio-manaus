#!/usr/bin/env python3
"""Teste simples da API do Brevo - sem dependências externas."""

import urllib.request
import urllib.error
import json
import os
import sys
import time

print("\n" + "="*70)
print("🧪 TESTE SIMPLES - API DO BREVO")
print("="*70)

api_key = os.getenv("BREVO_API_KEY")
sender_email = os.getenv("BREVO_SENDER_EMAIL")
test_email = "tiagoeugeniodemelo@gmail.com"

print("\n📧 CONFIGURAÇÃO:")
print(f"  API Key: {api_key[:20] + '...' if api_key else '❌ NÃO configurada'}")
print(f"  Sender Email: {sender_email if sender_email else '❌ NÃO configurada'}")
print(f"  Test Email: {test_email}")

if not api_key or not sender_email:
    print("\n❌ ERRO: Configure BREVO_API_KEY e BREVO_SENDER_EMAIL")
    sys.exit(1)

# Preparar payload
payload = {
    "to": [{"email": test_email}],
    "sender": {"name": "Observatório de Manaus", "email": sender_email},
    "subject": "🧪 Teste Brevo",
    "htmlContent": "<h1>Teste</h1><p>Se recebeu, API funciona!</p>",
}

headers = {
    "api-key": api_key,
    "Content-Type": "application/json",
}

print("\n📤 ENVIANDO EMAIL DE TESTE...")
print(f"  URL: https://api.brevo.com/v3/smtp/email")
print(f"  Timeout: 30 segundos\n")

max_retries = 3
for attempt in range(1, max_retries + 1):
    try:
        print(f"⏳ Tentativa {attempt}/{max_retries}...")

        start = time.time()
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        # Adicionar timeout
        import socket
        socket.setdefaulttimeout(30)

        with urllib.request.urlopen(req) as response:
            elapsed = time.time() - start
            status = response.status
            body = response.read().decode('utf-8')

            print(f"   Status: {status}")
            print(f"   Tempo: {elapsed:.2f}s")
            print(f"   Resposta: {body}\n")

            if status == 201:
                print("✅ SUCESSO! Email foi enviado.")
                print("   Verifique sua caixa de email.")
                sys.exit(0)
            else:
                print(f"❌ Status inesperado: {status}")
                sys.exit(1)

    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        print(f"   HTTP Error {e.code}: {e.reason}")
        print(f"   Tempo: {elapsed:.2f}s")
        print(f"   Resposta: {e.read().decode('utf-8')}\n")

        if attempt < max_retries:
            wait = 2 ** attempt
            print(f"   Aguardando {wait}s para retry...\n")
            time.sleep(wait)
        else:
            print(f"❌ Falha após {max_retries} tentativas")
            sys.exit(1)

    except urllib.error.URLError as e:
        elapsed = time.time() - start
        print(f"   URL Error: {e.reason}")
        print(f"   Tempo: {elapsed:.2f}s\n")

        if "timed out" in str(e.reason).lower():
            print("   ⏱️  TIMEOUT detectado")
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"   Aguardando {wait}s para retry...\n")
                time.sleep(wait)
            else:
                print(f"❌ Timeout após {max_retries} tentativas")
                print("\n💡 SUGESTÃO:")
                print("   A API do Brevo está muito lenta ou inacessível.")
                print("   Considere migrar para Sendgrid (mais rápido).")
                sys.exit(1)
        else:
            print(f"❌ Erro de conexão: {e.reason}")
            sys.exit(1)

    except Exception as e:
        print(f"   ❌ Erro: {type(e).__name__}: {e}")
        sys.exit(1)

print("\n" + "="*70)
