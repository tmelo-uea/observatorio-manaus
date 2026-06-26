import os
import hmac
import hashlib
from fastapi import FastAPI, Form, Request, HTTPException, Response
from notifications.whatsapp_bot import handle_message, send_whatsapp

app = FastAPI(title="Observatório Manaus — WhatsApp Bot")


def _validate_twilio_signature(request: Request, body: bytes) -> bool:
    """Valida que a requisição veio do Twilio (usando X-Twilio-Signature)."""
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)

    # Twilio assina com HMAC-SHA1 sobre a URL + parâmetros ordenados
    # Para simplicidade em sandbox, aceita sem validação se TWILIO_VALIDATE=false
    if os.getenv("TWILIO_VALIDATE", "true").lower() == "false":
        return True

    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(auth_token)
        # Precisa do body como dict de form fields — obtido via form data
        return validator.validate(url, {}, signature)
    except Exception:
        return False


@app.get("/health")
async def health():
    return {"status": "ok", "service": "whatsapp-bot"}


@app.post("/webhook")
async def webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(default=""),
):
    """Recebe mensagem do Twilio e responde ao usuário."""
    # Valida assinatura do Twilio em produção
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if auth_token and os.getenv("TWILIO_VALIDATE", "true").lower() != "false":
        try:
            from twilio.request_validator import RequestValidator
            raw_body = await request.body()
            form_data = await request.form()
            params = dict(form_data)
            validator = RequestValidator(auth_token)
            signature = request.headers.get("X-Twilio-Signature", "")
            url = str(request.url)
            if not validator.validate(url, params, signature):
                raise HTTPException(status_code=403, detail="Assinatura Twilio inválida")
        except ImportError:
            pass  # twilio não instalado ainda — pula validação

    print(f"  [WhatsApp webhook] Mensagem de {From}: {Body!r}")

    # Processa e obtém resposta
    reply = handle_message(From, Body)

    # Responde usando TwiML (XML que o Twilio interpreta)
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{_escape_xml(reply)}</Message>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


def _escape_xml(text: str) -> str:
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("bot.main:app", host="0.0.0.0", port=port, reload=False)
