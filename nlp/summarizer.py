import os
from datetime import date, datetime, timedelta
from sqlalchemy.exc import IntegrityError
from db.connection import get_session
from db.models import Article, Source, Topic, DailySummary

def _manaus_today() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date()


def _call_groq(prompt: str) -> str | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [Groq summarizer] Erro: {e}")
        return None


def _build_prompt(articles, topic_name: str | None) -> str:
    headlines = "\n".join(
        f"- [{a.source.name}] {a.title}" for a in articles[:40]
    )
    if topic_name:
        context = f"sobre o tema '{topic_name}' em Manaus e no Amazonas"
    else:
        context = "sobre Manaus e o estado do Amazonas"

    return (
        f"Você é um jornalista que escreve resumos diários de notícias {context}. "
        f"Com base nas manchetes abaixo, escreva um parágrafo conciso (4 a 6 frases) "
        f"resumindo os principais acontecimentos do dia. Escreva em português, "
        f"de forma clara e objetiva, sem usar bullet points.\n\n"
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

        # Busca artigos do dia (ou dos últimos 2 dias se poucos artigos hoje)
        from sqlalchemy import func
        query = session.query(Article).join(Source).filter(
            func.date(func.convert_tz(Article.published_at, '+00:00', '-04:00')) == today,
            Source.active == True,
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


def run_daily_summary():
    """Gera ou regenera o resumo do dia com base no Critério 4."""
    session = get_session()
    today = _manaus_today()
    try:
        from sqlalchemy import func
        current_count = session.query(Article).join(Source).filter(
            func.date(Article.published_at) == today,
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
