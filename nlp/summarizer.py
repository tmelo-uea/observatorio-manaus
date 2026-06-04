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


def _format_article(article) -> str:
    """Título para RSS; título + trecho do transcript para YouTube."""
    is_youtube = getattr(article.source, "type", None) == "youtube"
    if is_youtube and article.transcript:
        trecho = article.transcript[:500].strip()
        return f"- [{article.source.name}] {article.title}\n  Trecho: {trecho}"
    return f"- [{article.source.name}] {article.title}"


def _build_prompt(articles, topic_name: str | None) -> str:
    # YouTube com transcript primeiro (mais conteúdo), depois RSS — limites para não estourar contexto
    youtube = [a for a in articles if getattr(a.source, "type", None) == "youtube" and a.transcript]
    rss = [a for a in articles if a not in youtube]
    selected = youtube[:10] + rss[:30]

    headlines = "\n".join(_format_article(a) for a in selected)

    if topic_name:
        topic_filter = (
            f"FOCO EXCLUSIVO NO TEMA '{topic_name}': inclua APENAS conteúdo diretamente "
            f"relacionado a {topic_name}. Conteúdo sobre outros temas pode ter sido classificado "
            f"erroneamente — IGNORE esses itens mesmo que estejam na lista. "
            f"Se não houver conteúdo suficiente sobre {topic_name}, "
            f"escreva apenas sobre o que realmente pertence ao tema. "
        )
        context = f"sobre o tema '{topic_name}' na cidade de Manaus"
    else:
        topic_filter = ""
        context = "sobre a cidade de Manaus"

    return (
        f"Você é um jornalista que escreve resumos diários de notícias {context}. "
        f"Com base nas manchetes e trechos de vídeos abaixo, escreva um parágrafo conciso (4 a 6 frases) "
        f"resumindo os principais acontecimentos do dia anterior. "
        f"{topic_filter}"
        f"Inclua apenas fatos que dizem respeito à cidade de Manaus — ignore notícias "
        f"de outros municípios do Amazonas ou de outros estados. "
        f"Preserve os nomes completos de pessoas, órgãos e locais mencionados. "
        f"Ao mencionar pessoas, use apenas o nome e o cargo exatamente como aparecem nas fontes — "
        f"não atribua, infira ou complete cargos, títulos ou funções que não estejam explicitamente escritos. "
        f"Ao mencionar instituições (hospitais, escolas, órgãos), sempre identifique o nome completo — "
        f"nunca escreva apenas 'o hospital' ou 'a escola' sem nomear qual. "
        f"Inclua apenas fatos com contexto suficiente para o leitor entender — "
        f"ignore manchetes que pareçam fragmentos sem contexto claro (gírias, referências internas, disputas políticas menores). "
        f"IMPORTANTE: use o tempo verbal adequado ao contexto de cada notícia. "
        f"Para eventos já concluídos ontem, use passado ('realizou', 'prendeu'). "
        f"Para serviços ou situações que continuam no presente ou foram anunciados para o futuro, "
        f"use presente ou futuro ('mantém', 'vai manter', 'está previsto'). "
        f"Nunca use a palavra 'hoje' — prefira 'ontem', 'neste feriado', 'durante o período' ou o contexto adequado. "
        f"PROIBIDO usar frases de encerramento genéricas como 'Esses foram alguns dos principais acontecimentos', "
        f"'Esses são os destaques', 'Assim foi o dia em Manaus' ou similares — termine no último fato relevante. "
        f"Não use frases de abertura genéricas como 'Ontem foi um dia movimentado em Manaus' — "
        f"comece direto com o fato mais relevante do dia. "
        f"Escreva em português, de forma clara e objetiva, sem usar bullet points.\n\n"
        f"Fontes:\n{headlines}"
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
