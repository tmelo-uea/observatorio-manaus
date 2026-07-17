import os
import time
import threading
import hmac
import hashlib
import schedule as _schedule
from fastapi import FastAPI, Form, Request, HTTPException, Response
from notifications.whatsapp_bot import handle_message, send_whatsapp, run_whatsapp_push

app = FastAPI(title="Observatório Manaus — WhatsApp Bot")


def _push_scheduler_loop():
    _schedule.every().day.at("11:00").do(run_whatsapp_push)  # 07:00 Manaus (UTC-4)
    while True:
        _schedule.run_pending()
        time.sleep(60)


@app.on_event("startup")
def startup():
    from db.connection import get_engine, Base, run_migrations
    Base.metadata.create_all(get_engine())
    run_migrations()
    threading.Thread(target=_push_scheduler_loop, daemon=True).start()
    print("  [WhatsApp push] Agendado para 07:00 Manaus (11:00 UTC)")


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

    # Processa e obtém a(s) mensagem(ns) de resposta
    replies = handle_message(From, Body)

    # Caso comum (1 mensagem): responde via TwiML — rápido e sem depender da API.
    if len(replies) <= 1:
        body = _escape_xml(replies[0]) if replies else ""
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f"<Response>\n    <Message>{body}</Message>\n</Response>"
        )
        return Response(content=twiml, media_type="application/xml")

    # Digest (várias mensagens): envia via API do Twilio e responde TwiML vazio
    # para não duplicar. O usuário acabou de escrever, então estamos na janela de 24h.
    print(f"  [WhatsApp webhook] Enviando digest em {len(replies)} mensagens via API...")
    for i, msg in enumerate(replies, start=1):
        ok, err = send_whatsapp(From, msg)
        if not ok:
            print(f"  [WhatsApp webhook] Falha na parte {i}/{len(replies)}: {err}")
    empty = '<?xml version="1.0" encoding="UTF-8"?>\n<Response></Response>'
    return Response(content=empty, media_type="application/xml")


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
