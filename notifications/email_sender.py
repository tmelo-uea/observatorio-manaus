import os
import requests
from datetime import datetime, timedelta, date
from sqlalchemy.exc import IntegrityError
from db.connection import get_session
from db.models import EmailSubscription, DigestLog, DailySummary, Topic

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
APP_URL = "https://observatorio-manaus-production.up.railway.app"

TOPIC_ICONS = {
    "Saúde": "🏥",
    "Segurança Pública": "🚔",
    "Meio Ambiente": "🌿",
    "Política e Governo": "🏛️",
    "Economia e Negócios": "💼",
    "Educação": "🎓",
    "Infraestrutura e Mobilidade": "🚌",
    "Cultura e Lazer": "🎭",
    "Esporte": "⚽",
    "Tecnologia e Inovação": "💡",
    "Justiça e Direito": "⚖️",
    "Social e Cidadania": "🤝",
}

TOPIC_COLORS = {
    "Saúde": "#e74c3c",
    "Segurança Pública": "#c0392b",
    "Meio Ambiente": "#27ae60",
    "Política e Governo": "#2980b9",
    "Economia e Negócios": "#f39c12",
    "Educação": "#8e44ad",
    "Infraestrutura e Mobilidade": "#7f8c8d",
    "Cultura e Lazer": "#e67e22",
    "Esporte": "#1abc9c",
    "Tecnologia e Inovação": "#3498db",
    "Justiça e Direito": "#6c3483",
    "Social e Cidadania": "#e91e63",
}


def _manaus_today() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date()


def subscribe(email: str) -> tuple[bool, str]:
    session = get_session()
    try:
        sub = EmailSubscription(email=email.lower().strip())
        session.add(sub)
        session.commit()
        return True, "Inscrição realizada! Você receberá o digest diário no seu e-mail."
    except IntegrityError:
        session.rollback()
        existing = session.query(EmailSubscription).filter_by(email=email.lower().strip()).first()
        if existing and not existing.active:
            existing.active = True
            session.commit()
            return True, "Inscrição reativada com sucesso!"
        return False, "Este e-mail já está inscrito."
    finally:
        session.close()


def unsubscribe_by_token(token: str) -> tuple[bool, str]:
    session = get_session()
    try:
        sub = session.query(EmailSubscription).filter_by(unsubscribe_token=token).first()
        if not sub:
            return False, "Link inválido ou expirado."
        if not sub.active:
            return True, "Você já havia cancelado a inscrição anteriormente."
        sub.active = False
        session.commit()
        return True, "Inscrição cancelada. Você não receberá mais o digest."
    finally:
        session.close()


def _build_html(summaries: list[tuple[str, str, str]], today: date, unsubscribe_url: str) -> str:
    date_str = today.strftime("%d/%m/%Y")
    sections = ""
    for summary_text, topic_name, article_count in summaries:
        icon = TOPIC_ICONS.get(topic_name, "📰")
        color = TOPIC_COLORS.get(topic_name, "#2980b9")
        sections += f"""
        <div style="margin-bottom:20px;padding:18px 20px;background:#f8fafc;
                    border-radius:12px;border-left:4px solid {color};">
          <div style="font-size:0.85rem;font-weight:700;color:{color};
                      text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">
            {icon} {topic_name}
          </div>
          <p style="margin:0;color:#334155;line-height:1.75;font-size:0.95rem;">{summary_text}</p>
          <div style="margin-top:8px;font-size:0.78rem;color:#9ca3af;">
            Baseado em {article_count} artigos locais
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:sans-serif;">
  <div style="max-width:620px;margin:32px auto;background:#ffffff;
              border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

    <div style="background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);
                padding:28px 32px;text-align:center;">
      <div style="font-size:2rem;margin-bottom:8px;">🔭</div>
      <h1 style="margin:0;color:#ffffff;font-size:1.4rem;font-weight:800;">
        Observatório de Manaus
      </h1>
      <p style="margin:6px 0 0;color:#bfdbfe;font-size:0.9rem;">
        Digest diário — {date_str}
      </p>
    </div>

    <div style="padding:28px 32px;">
      <p style="margin:0 0 24px;color:#475569;font-size:0.95rem;line-height:1.6;">
        Veja os principais acontecimentos do dia em Manaus, organizados por tema:
      </p>

      {sections}

      <div style="margin-top:28px;text-align:center;">
        <a href="{APP_URL}" style="display:inline-block;padding:12px 28px;
           background:#2563eb;color:#ffffff;border-radius:8px;
           text-decoration:none;font-weight:700;font-size:0.9rem;">
          Acessar o Observatório
        </a>
      </div>
    </div>

    <div style="padding:20px 32px;border-top:1px solid #e5e7eb;
                text-align:center;font-size:0.78rem;color:#9ca3af;">
      <p style="margin:0 0 6px;">
        Você recebe este e-mail porque se inscreveu no Observatório de Manaus.
      </p>
      <p style="margin:0;">
        <a href="{unsubscribe_url}" style="color:#9ca3af;">Cancelar inscrição</a>
      </p>
    </div>
  </div>
</body>
</html>"""


def _send_brevo(to_email: str, subject: str, html: str) -> bool:
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "tmelo@uea.edu.br")
    sender_name = os.getenv("BREVO_SENDER_NAME", "Observatório de Manaus")

    if not api_key:
        print("  [Digest] BREVO_API_KEY não configurada — envio ignorado.")
        return False

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html,
    }
    headers = {"api-key": api_key, "Content-Type": "application/json"}

    try:
        resp = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=15)
        if resp.status_code not in (200, 201):
            print(f"  [Digest] Brevo erro {resp.status_code}: {resp.text[:200]}")
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"  [Digest] Erro ao enviar para {to_email}: {e}")
        return False


def run_digest(min_summaries: int = 3, send_after_hour: int = 7, force: bool = False) -> int:
    """Envia o digest diário com os resumos do dia anterior.

    Só dispara uma vez por dia, após `send_after_hour` no horário de Manaus.
    Use force=True para ignorar verificações de horário e DigestLog (testes).
    Retorna o número de e-mails enviados.
    """
    manaus_now = datetime.utcnow() - timedelta(hours=4)
    if not force and manaus_now.hour < send_after_hour:
        return 0

    today = _manaus_today()
    yesterday = today - timedelta(days=1)
    session = get_session()
    try:
        if not force and session.query(DigestLog).filter_by(date=today).first():
            print("  [Digest] Já enviado hoje.")
            return 0

        rows = (
            session.query(DailySummary.summary, Topic.name, DailySummary.article_count)
            .join(Topic, DailySummary.topic_id == Topic.id)
            .filter(DailySummary.date == yesterday)
            .order_by(Topic.display_order)
            .all()
        )

        if len(rows) < min_summaries:
            print(f"  [Digest] Apenas {len(rows)} resumos de {yesterday} — sem envio.")
            return 0

        subscribers = session.query(EmailSubscription).filter_by(active=True).all()
        if not subscribers:
            print("  [Digest] Nenhum assinante ativo.")
            _log_send(session, today, 0)
            return 0

        subject = f"🔭 Observatório de Manaus — {yesterday.strftime('%d/%m/%Y')}"
        sent = 0
        for sub in subscribers:
            unsubscribe_url = f"{APP_URL}/?token={sub.unsubscribe_token}"
            html = _build_html(list(rows), yesterday, unsubscribe_url)
            if _send_brevo(sub.email, subject, html):
                sent += 1

        _log_send(session, today, sent)
        print(f"  [Digest] Enviado para {sent}/{len(subscribers)} assinantes.")
        return sent
    finally:
        session.close()


def _log_send(session, today: date, recipients: int):
    from sqlalchemy.exc import IntegrityError as IE
    try:
        session.add(DigestLog(date=today, recipients=recipients))
        session.commit()
    except IE:
        session.rollback()
