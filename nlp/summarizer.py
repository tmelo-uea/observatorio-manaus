import os
import time
from datetime import date, datetime, timedelta
from sqlalchemy.exc import IntegrityError
from db.connection import get_session
from db.models import Article, Source, Topic, DailySummary, DailySummaryVersion

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
        topic_filter = (
            f"FOCO EXCLUSIVO NO TEMA '{topic_name}': inclua APENAS conteúdo diretamente "
            f"relacionado a {topic_name}. Conteúdo sobre outros temas pode ter sido classificado "
            f"erroneamente — IGNORE esses itens mesmo que estejam na lista. "
            f"Se não houver conteúdo suficiente sobre {topic_name}, "
            f"escreva apenas sobre o que realmente pertence ao tema. "
        )
        about = f"sobre o tema '{topic_name}' na cidade de Manaus"
    else:
        topic_filter = ""
        about = "sobre a cidade de Manaus"

    # O tempo verbal acompanha o momento REAL de cada evento, não a data de publicação da notícia.
    if context == "email":
        temporal = (
            f"Este é um boletim enviado na manhã seguinte, recapitulando as notícias publicadas ontem ({date_str}). "
            f"Descreva cada acontecimento com o tempo verbal que corresponde ao momento REAL do evento, "
            f"e não à data de publicação da notícia: passado para o que já ocorreu, "
            f"presente para serviços ou situações contínuas, e FUTURO para o que foi apenas anunciado "
            f"e ainda vai acontecer depois daquela data — por exemplo, um feriado, evento ou serviço "
            f"programado para os dias seguintes (use 'vai manter', 'ocorrerá', 'está previsto'). "
            f"Não force tudo para o passado nem use 'ontem' em fatos que se referem ao futuro. "
            f"Não use frases de abertura genéricas como 'Ontem foi um dia movimentado' — "
            f"comece direto com o fato mais relevante. "
            f"IMPORTANTE: NÃO inicie o parágrafo com a palavra 'Ontem'. Comece pelo sujeito da notícia "
            f"(o órgão, a pessoa, o evento) — por exemplo 'A Prefeitura de Manaus inaugurou...' ou "
            f"'Uma operação da Polícia Civil resultou em...'. O contexto temporal (ontem) deve aparecer "
            f"naturalmente ao longo do texto quando necessário, não como primeira palavra. "
        )
    else:  # dashboard
        temporal = (
            f"Este resumo é exibido em tempo real e reúne as notícias coletadas hoje ({date_str}), "
            f"mas atenção: uma notícia coletada hoje pode relatar um evento que ocorreu ONTEM ou antes. "
            f"Descreva cada acontecimento com o tempo verbal que corresponde ao momento REAL do evento, "
            f"e não à data de publicação da notícia: passado para o que já ocorreu, "
            f"presente para o que está em andamento, e futuro para o que foi anunciado e ainda vai acontecer. "
            f"NÃO assuma que o evento aconteceu hoje só porque a notícia é de hoje — "
            f"use 'ontem' e o passado quando a notícia indicar que o fato já ocorreu, e não force 'hoje' nem 'nesta manhã'. "
            f"Não use frases de abertura genéricas como 'Hoje foi um dia movimentado' — "
            f"comece direto com o fato mais relevante. "
        )

    regras_comuns = (
        f"Inclua apenas fatos que dizem respeito à cidade de Manaus — ignore notícias "
        f"de outros municípios do Amazonas ou de outros estados. "
        f"Preserve os nomes completos de pessoas, órgãos e locais mencionados. "
        f"Ao mencionar pessoas, use apenas o nome e o cargo exatamente como aparecem nas fontes. "
        f"Ao mencionar instituições (hospitais, escolas, órgãos), sempre identifique o nome completo. "
        f"Inclua apenas fatos com contexto suficiente para o leitor entender — "
        f"ignore manchetes que pareçam fragmentos sem contexto claro. "
        f"DEDUPLICAÇÃO: várias manchetes podem cobrir o MESMO acontecimento (de fontes diferentes). "
        f"Trate cada acontecimento UMA ÚNICA VEZ — nunca escreva duas frases sobre o mesmo evento, "
        f"mesmo que apareça repetido em várias fontes. Reúna as informações e mencione o fato apenas uma vez. "
        f"NÃO invente precisão temporal: só diga 'pela manhã', 'à tarde', 'à noite' ou um horário "
        f"se isso estiver EXPLÍCITO nas fontes. Se as fontes não indicam a hora do evento, não a mencione. "
        f"Da mesma forma, não afirme que algo aconteceu hoje se as fontes não confirmam a data — "
        f"uma notícia publicada hoje pode relatar um evento de um dia anterior. Na dúvida, não atribua data nem hora. "
        f"PROIBIDO usar frases de encerramento genéricas como 'Esses foram alguns dos principais acontecimentos', "
        f"'Esses são os destaques' ou similares — termine no último fato relevante. "
        f"Escreva em português, de forma clara e objetiva, sem usar bullet points."
    )

    return (
        f"Você é um jornalista que escreve resumos diários de notícias {about}. "
        f"Com base nas manchetes e trechos de vídeos abaixo, escreva um parágrafo conciso (4 a 6 frases) "
        f"resumindo os principais acontecimentos. "
        f"{topic_filter}"
        f"{temporal}"
        f"{regras_comuns}\n\n"
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

        prompt = _build_prompt(articles, topic_name, context="dashboard", ref_date=today)
        text = _call_groq(prompt)
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
            text = _call_groq(prompt)
            if text:
                results.append((text, topic.name, len(articles)))
                print(f"  [Email resumo] '{topic.name}': OK ({len(articles)} artigos)")
            time.sleep(2)
    finally:
        session.close()
    return results
