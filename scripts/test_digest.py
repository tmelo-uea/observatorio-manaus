"""Script de teste — força envio do digest ignorando horário e DigestLog."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta, date
from db.connection import get_session
from db.models import DailySummary, Topic, EmailSubscription
from notifications.email_sender import _build_html, _send_brevo, APP_URL

def _manaus_today():
    return (datetime.utcnow() - timedelta(hours=4)).date()

def test_send():
    today = _manaus_today()
    yesterday = today - timedelta(days=1)

    session = get_session()
    try:
        # Tenta ontem primeiro, depois hoje
        for target_date in [yesterday, today]:
            rows = (
                session.query(DailySummary.summary, Topic.name, DailySummary.article_count)
                .join(Topic, DailySummary.topic_id == Topic.id)
                .filter(DailySummary.date == target_date)
                .order_by(Topic.display_order)
                .all()
            )
            if rows:
                print(f"Usando resumos de {target_date} ({len(rows)} temas)")
                break
        else:
            print("Nenhum resumo encontrado. Execute o coletor primeiro.")
            return

        subscribers = session.query(EmailSubscription).filter_by(active=True).all()
        print(f"Assinantes ativos: {len(subscribers)}")

        subject = f"[TESTE] 🔭 Observatório de Manaus — {target_date.strftime('%d/%m/%Y')}"
        for sub in subscribers:
            unsubscribe_url = f"{APP_URL}/?token={sub.unsubscribe_token}"
            html = _build_html(list(rows), target_date, unsubscribe_url)
            ok, err = _send_brevo(sub.email, subject, html)
            status = "✓" if ok else "✗"
            error_msg = f" ({err})" if not ok and err else ""
            print(f"  {status} {sub.email}{error_msg}")
    finally:
        session.close()

test_send()
