# 🔧 Troubleshooting - Erro de Timeout do Brevo

## Sintoma

```
Erro Brevo: Brevo: timed out
```

Ao clicar no botão "📤 Disparar digest agora (teste)" no painel admin.

## Causa Raiz

**Railway está bloqueando conexões outbound na porta 587** (SMTP padrão).

## Soluções

### Opção 1: Usar Sendgrid (Recomendado para Railway)

Sendgrid é nativo no Railway e não precisa de porta 587 aberta.

1. **Criar conta Sendgrid:**
   - Acesse https://sendgrid.com
   - Crie conta grátis
   - Vá para Settings → API Keys → Create API Key
   - Copie a chave

2. **Atualizar código `email_sender.py`:**

```python
def _send_sendgrid(to_email: str, subject: str, html: str) -> tuple[bool, str]:
    """Envia email via Sendgrid API."""
    import requests
    
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        return False, "SENDGRID_API_KEY não configurada"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": os.getenv("SENDGRID_FROM_EMAIL")},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 202:
            return True, ""
        return False, f"Sendgrid {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, str(e)
```

3. **Configurar Railway:**
   - Adicione `SENDGRID_API_KEY=sua_chave`
   - Adicione `SENDGRID_FROM_EMAIL=seu@email.com`

4. **Atualizar `run_digest()` para usar Sendgrid:**
   - Trocar chamada de `_send_brevo()` para `_send_sendgrid()`

### Opção 2: Usar Mailgun (Alternativa)

Mailgun também funciona bem com Railway e tem plano gratuito.

1. Criar conta em https://mailgun.com
2. Obter domínio e API key
3. Implementar similar ao Sendgrid

### Opção 3: Contactar Railway Support

Se quiser continuar com Brevo:
1. Abra ticket em https://railway.app/support
2. Peça para desbloquear porta 587 (SMTP outbound)
3. Pode levar 24-48h

## Recomendação

**Use Sendgrid** — é gratuito, confiável e funciona nativamente no Railway sem bloqueios de porta.

## Configuração Rápida Sendgrid

```bash
# Em Railway, adicione estas variáveis:
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=noreply@observatorio-manaus.com
SENDGRID_FROM_NAME=Observatório de Manaus
```

Quer que eu implemente o Sendgrid?
