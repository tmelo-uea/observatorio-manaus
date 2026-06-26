import os
import unicodedata
from datetime import date, datetime, timedelta
from db.connection import get_session
from db.models import DailySummary, Topic, WhatsAppSubscription

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

# Mapeamento de comandos do usuário → slug do tema no banco
TOPIC_ALIASES = {
    "saude": "saude",
    "saúde": "saude",
    "seguranca": "seguranca-publica",
    "segurança": "seguranca-publica",
    "meio ambiente": "meio-ambiente",
    "ambiente": "meio-ambiente",
    "politica": "politica-e-governo",
    "política": "politica-e-governo",
    "governo": "politica-e-governo",
    "economia": "economia-e-negocios",
    "negocios": "economia-e-negocios",
    "negócios": "economia-e-negocios",
    "educacao": "educacao",
    "educação": "educacao",
    "infraestrutura": "infraestrutura-e-mobilidade",
    "mobilidade": "infraestrutura-e-mobilidade",
    "transporte": "infraestrutura-e-mobilidade",
    "cultura": "cultura-e-lazer",
    "lazer": "cultura-e-lazer",
    "esporte": "esporte",
    "esportes": "esporte",
    "tecnologia": "tecnologia-e-inovacao",
    "inovacao": "tecnologia-e-inovacao",
    "inovação": "tecnologia-e-inovacao",
    "justica": "justica-e-direito",
    "justiça": "justica-e-direito",
    "direito": "justica-e-direito",
    "social": "social-e-cidadania",
    "cidadania": "social-e-cidadania",
}

HELP_COMMANDS = {"ajuda", "menu", "oi", "olá", "ola", "hello", "hi", "start", "inicio", "início"}
STOP_COMMANDS = {"parar", "sair", "cancelar", "stop", "unsubscribe"}
DIGEST_COMMANDS = {"resumo", "noticias", "notícias", "hoje", "news"}

APP_URL = os.getenv("APP_URL", "https://www.observatorio.manaus.br")


def _manaus_today() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date()


def _normalize(text: str) -> str:
    """Remove acentos e converte para minúsculas para comparação de comandos."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _get_topic_summaries(target_date: date) -> list[tuple[str, str, int]]:
    """Busca resumos do banco para a data alvo. Retorna (summary, topic_name, article_count)."""
    session = get_session()
    try:
        rows = (
            session.query(DailySummary, Topic)
            .join(Topic, DailySummary.topic_id == Topic.id)
            .filter(DailySummary.date == target_date)
            .order_by(Topic.display_order)
            .all()
        )
        return [(ds.summary, t.name, ds.article_count) for ds, t in rows]
    finally:
        session.close()


def _get_topic_summary_by_slug(slug: str, target_date: date) -> tuple[str, str, int] | None:
    """Busca resumo de um tema específico pelo slug."""
    session = get_session()
    try:
        result = (
            session.query(DailySummary, Topic)
            .join(Topic, DailySummary.topic_id == Topic.id)
            .filter(DailySummary.date == target_date, Topic.slug == slug)
            .first()
        )
        if result:
            ds, t = result
            return (ds.summary, t.name, ds.article_count)
        return None
    finally:
        session.close()


def _format_full_digest(summaries: list[tuple[str, str, int]], target_date: date) -> str:
    """Versão compacta do digest — uma linha por tema para caber no limite do WhatsApp.
    O usuário pode detalhar cada tema enviando seu nome (ex: saude, politica).
    """
    if not summaries:
        return (
            f"📭 Ainda não há resumos disponíveis para hoje ({target_date.strftime('%d/%m/%Y')}).\n\n"
            f"Tente novamente mais tarde ou acesse {APP_URL}"
        )

    date_str = target_date.strftime("%d/%m/%Y")
    lines = [f"🔭 *Observatório de Manaus — {date_str}*\n"]

    for summary_text, topic_name, article_count in summaries:
        icon = TOPIC_ICONS.get(topic_name, "📰")
        # Primeira frase do resumo como prévia
        first_sentence = summary_text.split(".")[0].strip() + "."
        lines.append(f"{icon} *{topic_name}* ({article_count})\n{first_sentence}")

    lines.append(f"\n_Digite o nome do tema para o resumo completo._")
    lines.append(f"🔗 {APP_URL}")
    return "\n\n".join(lines)


def _format_topic_summary(summary_text: str, topic_name: str, article_count: int, target_date: date) -> str:
    icon = TOPIC_ICONS.get(topic_name, "📰")
    date_str = target_date.strftime("%d/%m/%Y")
    return (
        f"{icon} *{topic_name} — {date_str}*\n\n"
        f"{summary_text}\n\n"
        f"_({article_count} artigos locais)_\n\n"
        f"🔗 {APP_URL}"
    )


def _format_help() -> str:
    topic_list = "\n".join(
        f"  • {_normalize(name).split()[0]} → resumo de {name}"
        for name in TOPIC_ICONS
    )
    return (
        "👋 *Olá! Sou o bot do Observatório de Manaus.*\n\n"
        "Monitoro notícias de Manaus e Amazonas organizadas por tema.\n\n"
        "*Comandos disponíveis:*\n"
        "  • *resumo* → boletim completo do dia\n"
        "  • *saude*, *seguranca*, *politica*... → tema específico\n"
        "  • *parar* → cancelar recebimento de mensagens\n"
        "  • *ajuda* → exibir esta mensagem\n\n"
        "*Temas disponíveis:*\n"
        "saude, seguranca, ambiente, politica, economia,\n"
        "educacao, infraestrutura, cultura, esporte,\n"
        "tecnologia, justica, social\n\n"
        f"🔗 {APP_URL}"
    )


def _register(phone: str) -> None:
    """Registra o número se ainda não existir."""
    session = get_session()
    try:
        existing = session.query(WhatsAppSubscription).filter_by(phone=phone).first()
        if existing:
            if not existing.active:
                existing.active = True
                session.commit()
        else:
            session.add(WhatsAppSubscription(phone=phone))
            session.commit()
    finally:
        session.close()


def _deactivate(phone: str) -> None:
    session = get_session()
    try:
        sub = session.query(WhatsAppSubscription).filter_by(phone=phone).first()
        if sub:
            sub.active = False
            session.commit()
    finally:
        session.close()


def handle_message(from_phone: str, body: str) -> str:
    """Processa mensagem recebida e retorna texto de resposta."""
    normalized = _normalize(body)
    today = _manaus_today()

    # Opt-out
    if normalized in STOP_COMMANDS:
        _deactivate(from_phone)
        return (
            "✅ Você foi removido da nossa lista.\n\n"
            "Para voltar a usar o bot, basta enviar qualquer mensagem.\n"
            f"🔗 {APP_URL}"
        )

    # Registra/reativa o número em qualquer interação
    _register(from_phone)

    # Ajuda / boas-vindas
    if normalized in HELP_COMMANDS:
        return _format_help()

    # Resumo completo
    if normalized in DIGEST_COMMANDS:
        summaries = _get_topic_summaries(today)
        return _format_full_digest(summaries, today)

    # Tema específico
    slug = TOPIC_ALIASES.get(normalized)
    if slug:
        result = _get_topic_summary_by_slug(slug, today)
        if result:
            return _format_topic_summary(*result, target_date=today)
        return (
            f"📭 Ainda não há resumo disponível para este tema hoje.\n\n"
            f"Tente mais tarde ou veja todos os temas em {APP_URL}"
        )

    # Comando não reconhecido
    return (
        "🤔 Não entendi o comando.\n\n"
        "Digite *ajuda* para ver os comandos disponíveis."
    )


def send_whatsapp(to_phone: str, message: str) -> tuple[bool, str]:
    """Envia mensagem via Twilio WhatsApp. Retorna (sucesso, erro)."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")

    if not all([account_sid, auth_token, from_number]):
        return False, "Credenciais Twilio não configuradas."

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            from_=from_number,
            to=f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone,
            body=message,
        )
        print(f"  [WhatsApp] ✓ Enviado para {to_phone} — SID {msg.sid}")
        return True, ""
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        print(f"  [WhatsApp] ✗ {err}")
        return False, err
