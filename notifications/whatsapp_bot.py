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
    "politica": "politica-governo",
    "política": "politica-governo",
    "governo": "politica-governo",
    "economia": "economia-negocios",
    "negocios": "economia-negocios",
    "negócios": "economia-negocios",
    "educacao": "educacao",
    "educação": "educacao",
    "infraestrutura": "infraestrutura-mobilidade",
    "mobilidade": "infraestrutura-mobilidade",
    "transporte": "infraestrutura-mobilidade",
    "cultura": "cultura-lazer",
    "lazer": "cultura-lazer",
    "esporte": "esporte",
    "esportes": "esporte",
    "tecnologia": "tecnologia-inovacao",
    "inovacao": "tecnologia-inovacao",
    "inovação": "tecnologia-inovacao",
    "justica": "justica-direito",
    "justiça": "justica-direito",
    "direito": "justica-direito",
    "social": "social-cidadania",
    "cidadania": "social-cidadania",
}

# Ordem canônica do menu (número → tema). Fonte única de verdade para o menu
# numerado e para os atalhos por número. Cada item: (slug, rótulo curto, ícone).
TOPIC_MENU = [
    ("saude",                       "Saúde",          "🏥"),
    ("seguranca-publica",           "Segurança",      "🚔"),
    ("meio-ambiente",               "Meio Ambiente",  "🌿"),
    ("politica-governo",          "Política",       "🏛️"),
    ("economia-negocios",         "Economia",       "💼"),
    ("educacao",                    "Educação",       "🎓"),
    ("infraestrutura-mobilidade", "Infraestrutura", "🚌"),
    ("cultura-lazer",             "Cultura",        "🎭"),
    ("esporte",                     "Esporte",        "⚽"),
    ("tecnologia-inovacao",       "Tecnologia",     "💡"),
    ("justica-direito",           "Justiça",        "⚖️"),
    ("social-cidadania",          "Social",         "🤝"),
]

# Atalho por número: "1" → slug de Saúde, etc.
NUMBER_ALIASES = {str(i): slug for i, (slug, _, _) in enumerate(TOPIC_MENU, start=1)}

_DIVIDER = "━━━━━━━━━━━━━━━━"

HELP_COMMANDS = {"ajuda", "menu", "oi", "olá", "ola", "hello", "hi", "start", "inicio", "início"}
STOP_COMMANDS = {"parar", "sair", "cancelar", "stop", "unsubscribe"}
DIGEST_COMMANDS: set = set()  # desativado temporariamente — limite de chars do TwiML

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
    """Índice de temas do dia — lista compacta para caber no limite de 1600 chars do WhatsApp.
    O usuário digita o nome do tema para ver o resumo completo.
    """
    if not summaries:
        return (
            f"📭 Ainda não há resumos para hoje ({target_date.strftime('%d/%m/%Y')}).\n"
            f"Tente mais tarde ou acesse {APP_URL}"
        )

    date_str = target_date.strftime("%d/%m/%Y")
    lines = [f"🔭 *Observatório de Manaus — {date_str}*\n"]

    for summary_text, topic_name, article_count in summaries:
        icon = TOPIC_ICONS.get(topic_name, "📰")
        lines.append(f"{icon} {topic_name} ({article_count} artigos)")

    lines.append(f"\n_Digite o tema para o resumo completo:_")
    lines.append("saude • seguranca • ambiente • politica\neconomia • educacao • infraestrutura\ncultura • esporte • tecnologia • justica • social")
    lines.append(f"\n🔗 {APP_URL}")
    return "\n".join(lines)


def _format_topic_summary(summary_text: str, topic_name: str, article_count: int, target_date: date) -> str:
    icon = TOPIC_ICONS.get(topic_name, "📰")
    date_str = target_date.strftime("%d/%m/%Y")
    domain = APP_URL.replace("https://", "").replace("http://", "")
    return (
        f"{icon} *{topic_name.upper()}*\n"
        f"_{date_str} · {article_count} artigos locais_\n"
        f"{_DIVIDER}\n\n"
        f"{summary_text}\n\n"
        f"{_DIVIDER}\n"
        "↩️ *menu* para ver outros temas\n"
        f"🔗 {domain}"
    )


def _format_help() -> str:
    rows = "\n".join(
        f"{i:>2} · {icon} {label}"
        for i, (_, label, icon) in enumerate(TOPIC_MENU, start=1)
    )
    domain = APP_URL.replace("https://", "").replace("http://", "")
    return (
        "🔭 *OBSERVATÓRIO DE MANAUS*\n"
        "_Notícias de Manaus e do Amazonas_\n"
        f"{_DIVIDER}\n\n"
        "📋 *TEMAS DE HOJE*\n"
        "Digite o número ou o nome:\n\n"
        f"{rows}\n\n"
        f"{_DIVIDER}\n"
        "ℹ️ *ajuda*   ❌ *parar*\n"
        f"🔗 {domain}"
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

    # Tema específico — aceita número (1-12) ou nome do tema
    slug = NUMBER_ALIASES.get(normalized) or TOPIC_ALIASES.get(normalized)
    if slug:
        result = _get_topic_summary_by_slug(slug, today)
        if result:
            return _format_topic_summary(*result, target_date=today)
        # Nome do tema para a mensagem de "sem resumo"
        label = next((lbl for s, lbl, _ in TOPIC_MENU if s == slug), "este tema")
        return (
            f"📭 Ainda não há resumo de *{label}* hoje.\n\n"
            "Digite *menu* para ver os temas já disponíveis."
        )

    # Comando não reconhecido
    return (
        "🤔 Não entendi.\n\n"
        "Digite *menu* para ver os temas, ou o número/nome de um tema (ex: *1* ou *saude*)."
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
