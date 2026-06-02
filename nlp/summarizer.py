import os
import time
from datetime import date, datetime, timedelta
from sqlalchemy.exc import IntegrityError
from db.connection import get_session
from db.models import Article, Source, Topic, DailySummary

def _manaus_today() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date()

def _manaus_day_utc_range(d: date):
    """Retorna (start_utc, end_utc) para um dia no horário de Manaus (UTC-4)."""
    start = datetime(d.year, d.month, d.day, 4, 0, 0)      # meia-noite Manaus = 04:00 UTC
    end   = start + timedelta(days=1)
    return start, end


def _call_groq(prompt: str) -> str | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("  [Groq summarizer] GROQ_API_KEY não configurada — resumo não gerado.")
        return None
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [Groq summarizer] Erro na API: {e}")
        return None


def _build_prompt(articles, topic_name: str | None) -> str:
    headlines = "\n".join(
        f"- [{a.source.name}] {a.title}" for a in articles[:40]
    )

    if topic_name:
        topic_filter = (
            f"FOCO EXCLUSIVO NO TEMA '{topic_name}': inclua APENAS manchetes diretamente "
            f"relacionadas a {topic_name}. Manchetes sobre outros temas (acidentes de trânsito, "
            f"crimes, política, saúde, etc.) podem ter sido classificadas erroneamente — "
            f"IGNORE essas manchetes mesmo que estejam na lista. "
            f"Se não houver manchetes suficientes sobre {topic_name}, "
            f"escreva apenas sobre as que realmente pertencem ao tema. "
        )
        context = f"sobre o tema '{topic_name}' na cidade de Manaus"
    else:
        topic_filter = ""
        context = "sobre a cidade de Manaus"

    return (
        f"Você é um jornalista que escreve resumos diários de notícias {context}. "
        f"Com base nas manchetes abaixo, escreva um parágrafo conciso (4 a 6 frases) "
        f"resumindo os principais acontecimentos do dia anterior. "
        f"{topic_filter}"
        f"Inclua apenas fatos que dizem respeito à cidade de Manaus — ignore notícias "
        f"de outros municípios do Amazonas ou de outros estados. "
        f"Preserve os nomes completos de pessoas, órgãos e locais mencionados nas manchetes. "
        f"Ao mencionar pessoas, use apenas o nome e o cargo exatamente como aparecem nas manchetes — "
        f"não atribua, infira ou complete cargos, títulos ou funções que não estejam explicitamente escritos. "
        f"IMPORTANTE: nunca use a palavra 'hoje' — use 'ontem' ou o contexto temporal adequado. "
        f"Não use frases genéricas como 'Ontem foi um dia movimentado em Manaus' — "
        f"comece direto com os fatos mais relevantes. "
        f"Escreva em português, de forma clara e objetiva, sem usar bullet points.\n\n"
        f"Manchetes:\n{headlines}"
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

        prompt = _build_prompt(articles, topic_name)
        text = _call_groq(prompt)
        if not text:
            return None

        source_names = list({a.source.name for a in articles})
        article_ids = [a.id for a in articles]

        summary = DailySummary(
            date=today,
            topic_id=topic_id,
            summary=text,
            article_ids=article_ids,
            article_count=len(articles),
            generated_at=datetime.utcnow(),
        )

        if existing:
            session.delete(existing)
            session.flush()

        session.add(summary)
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
            time.sleep(2)  # evita rate limit do Groq entre chamadas consecutivas
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
