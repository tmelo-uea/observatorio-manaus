import os
import time
from datetime import date, datetime, timedelta
from sqlalchemy.exc import IntegrityError
from db.connection import get_session
from db.models import Article, Source, Topic, DailySummary, DailySummaryVersion
from nlp.prompts import render, get_template

def _manaus_today() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date()

def _manaus_day_utc_range(d: date):
    """Retorna (start_utc, end_utc) para um dia no horário de Manaus (UTC-4)."""
    start = datetime(d.year, d.month, d.day, 4, 0, 0)      # meia-noite Manaus = 04:00 UTC
    end   = start + timedelta(days=1)
    return start, end


SUMMARY_MODEL = "gpt-4o-mini"


def _call_llm(prompt: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  [OpenAI summarizer] OPENAI_API_KEY não configurada — resumo não gerado.")
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.4,
        )
        text = response.choices[0].message.content.strip()
        usage = response.usage
        tokens = (f"{usage.prompt_tokens}+{usage.completion_tokens} tokens"
                  if usage else "tokens n/d")
        print(f"  [OpenAI summarizer] OK — {SUMMARY_MODEL}, {len(text)} chars, {tokens}")
        return text
    except Exception as e:
        print(f"  [OpenAI summarizer] Erro na API: {e}")
        return None


def _format_article(article) -> str:
    """Título para RSS; título + trecho do transcript para YouTube."""
    is_youtube = getattr(article.source, "type", None) == "youtube"
    if is_youtube and article.transcript:
        trecho = article.transcript[:500].strip()
        return f"- [{article.source.name}] {article.title}\n  Trecho: {trecho}"
    return f"- [{article.source.name}] {article.title}"


def _build_prompt(articles, topic_name: str | None, context: str = "dashboard",
                  ref_date: date | None = None) -> str:
    """Constrói o prompt de resumo.

    context="dashboard" → resumo do dia em curso, visível na página principal.
    context="email"     → balanço do dia anterior, enviado por e-mail na manhã seguinte.
    ref_date            → data das notícias resumidas (usada para ancorar o tempo verbal).
    """
    youtube = [a for a in articles if getattr(a.source, "type", None) == "youtube" and a.transcript]
    rss = [a for a in articles if a not in youtube]
    selected = youtube[:10] + rss[:30]
    headlines = "\n".join(_format_article(a) for a in selected)

    date_str = ref_date.strftime("%d/%m/%Y") if ref_date else ""

    if topic_name:
        topic_filter = render("summary.topic_filter", topic_name=topic_name)
        about = f"sobre o tema '{topic_name}' na cidade de Manaus"
    else:
        topic_filter = ""
        about = "sobre a cidade de Manaus"

    temporal = render(f"summary.temporal.{context}", date_str=date_str)
    regras_comuns = get_template("summary.common_rules")

    return render(
        "summary.intro",
        about=about,
        topic_filter=topic_filter,
        temporal=temporal,
        regras_comuns=regras_comuns,
        headlines=headlines,
    )


def generate_summary(topic_id: int | None = None, force: bool = False) -> DailySummary | None:
    session = get_session()
    today = _manaus_today()
    try:
        # Verifica se já existe resumo para hoje
        existing = session.query(DailySummary).filter_by(
            date=today, topic_id=topic_id
        ).first()
        if existing and not force:
            return existing

        start_utc, end_utc = _manaus_day_utc_range(today)
        query = session.query(Article).join(Source).filter(
            Article.published_at >= start_utc,
            Article.published_at < end_utc,
            Source.active == True,
            Article.is_local == True,
        )
        if topic_id:
            query = query.filter(Article.topic_id == topic_id)

        articles = query.order_by(Article.published_at.desc()).all()

        if len(articles) < 3:
            return None

        topic_name = None
        if topic_id:
            topic = session.query(Topic).filter_by(id=topic_id).first()
            topic_name = topic.name if topic else None

        prompt = _build_prompt(articles, topic_name, context="dashboard", ref_date=today)
        text = _call_llm(prompt)
        if not text:
            return None

        source_names = list({a.source.name for a in articles})
        article_ids = [a.id for a in articles]
        now = datetime.utcnow()

        summary = DailySummary(
            date=today,
            topic_id=topic_id,
            summary=text,
            article_ids=article_ids,
            article_count=len(articles),
            generated_at=now,
        )

        # Registra a versão no log append-only (mantém histórico para estudos)
        version = DailySummaryVersion(
            date=today,
            topic_id=topic_id,
            summary=text,
            article_ids=article_ids,
            article_count=len(articles),
            generated_at=now,
        )

        if existing:
            session.delete(existing)
            session.flush()

        session.add(summary)
        session.add(version)
        session.commit()
        session.refresh(summary)
        return summary

    except IntegrityError:
        session.rollback()
        return session.query(DailySummary).filter_by(date=today, topic_id=topic_id).first()
    finally:
        session.close()


def get_today_summary(topic_id: int | None = None) -> DailySummary | None:
    session = get_session()
    try:
        return session.query(DailySummary).filter_by(
            date=date.today(), topic_id=topic_id
        ).first()
    finally:
        session.close()


def _should_regenerate(existing: DailySummary, current_count: int) -> bool:
    """Critério 4: volume dobrou E passaram pelo menos 2 horas."""
    if existing.article_count == 0:
        return current_count >= 3
    volume_doubled = current_count >= existing.article_count * 2
    hours_elapsed = (datetime.utcnow() - existing.generated_at).total_seconds() / 3600
    return volume_doubled and hours_elapsed >= 2


def run_topic_summaries(min_articles: int = 10):
    """Gera resumos automáticos para temas com artigos suficientes hoje."""
    session = get_session()
    today = _manaus_today()
    start_utc, end_utc = _manaus_day_utc_range(today)
    print(f"  [Resumos por tema] Data Manaus: {today} | UTC range: {start_utc} → {end_utc}")
    try:
        topics = session.query(Topic).filter(Topic.slug != "outros").all()
        for topic in topics:
            count = session.query(Article).join(Source).filter(
                Article.published_at >= start_utc,
                Article.published_at < end_utc,
                Article.topic_id == topic.id,
                Source.active == True,
                Article.is_local == True,
            ).count()
            print(f"  [Resumos por tema] '{topic.name}': {count} artigos hoje")
            if count < min_articles:
                continue
            existing = session.query(DailySummary).filter_by(
                date=today, topic_id=topic.id
            ).first()
            if existing and not _should_regenerate(existing, count):
                print(f"  [Resumos por tema] '{topic.name}': resumo já existe, sem regeneração.")
                continue
            print(f"  [Resumos por tema] Gerando resumo para '{topic.name}' ({count} artigos)...")
            result = generate_summary(topic_id=topic.id, force=bool(existing))
            if result:
                print(f"  [Resumos por tema] '{topic.name}': resumo salvo com {result.article_count} artigos.")
            else:
                print(f"  [Resumos por tema] '{topic.name}': falha ao gerar resumo.")
            time.sleep(2)  # evita rate limit do provedor entre chamadas consecutivas
    finally:
        session.close()


def run_daily_summary():
    """Gera ou regenera o resumo do dia com base no Critério 4."""
    session = get_session()
    today = _manaus_today()
    try:
        start_utc, end_utc = _manaus_day_utc_range(today)
        current_count = session.query(Article).join(Source).filter(
            Article.published_at >= start_utc,
            Article.published_at < end_utc,
            Source.active == True,
        ).count()

        existing = session.query(DailySummary).filter_by(
            date=today, topic_id=None
        ).first()

        if existing and not _should_regenerate(existing, current_count):
            print(f"  Resumo do dia já existe ({existing.article_count} artigos, {current_count} disponíveis hoje). Sem regeneração.")
            return

        print(f"  Gerando resumo diário ({current_count} artigos publicados hoje)...")
        result = generate_summary(topic_id=None, force=True)
        if result:
            print(f"  Resumo gerado: {result.article_count} artigos.")
        else:
            print("  Artigos insuficientes para resumo.")
    finally:
        session.close()


def generate_email_summaries(target_date: date) -> list[tuple[str, str, int]]:
    """Gera resumos frescos com contexto 'email' (ontem) para o boletim diário.

    Retorna lista de (summary_text, topic_name, article_count) ordenada por tema.
    Não armazena no banco — usado diretamente pelo email sender.
    """
    session = get_session()
    results = []
    try:
        start_utc, end_utc = _manaus_day_utc_range(target_date)
        topics = session.query(Topic).filter(Topic.slug != "outros").order_by(Topic.display_order).all()

        for topic in topics:
            articles = (
                session.query(Article).join(Source)
                .filter(
                    Article.published_at >= start_utc,
                    Article.published_at < end_utc,
                    Article.topic_id == topic.id,
                    Source.active == True,
                    Article.is_local == True,
                )
                .order_by(Article.published_at.desc())
                .all()
            )
            if len(articles) < 5:
                continue
            prompt = _build_prompt(articles, topic.name, context="email", ref_date=target_date)
            text = _call_llm(prompt)
            if text:
                results.append((text, topic.name, len(articles)))
                print(f"  [Email resumo] '{topic.name}': OK ({len(articles)} artigos)")
            time.sleep(2)
    finally:
        session.close()
    return results
