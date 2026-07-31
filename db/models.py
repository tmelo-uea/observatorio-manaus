import secrets
from datetime import datetime, date
from sqlalchemy import String, Text, DateTime, Integer, Float, ForeignKey, UniqueConstraint, JSON, Date, Boolean, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.connection import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    rss_url: Mapped[str] = mapped_column(String(500), nullable=True)
    type: Mapped[str] = mapped_column(String(50), default="portal")  # portal | blog
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    articles: Mapped[list["Article"]] = relationship(back_populates="source")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    keywords: Mapped[dict] = mapped_column(JSON, nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="#95a5a6")
    display_order: Mapped[int] = mapped_column(Integer, default=99)

    articles: Mapped[list["Article"]] = relationship(back_populates="topic")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("url", name="uq_article_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(767), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=True)
    topic_score: Mapped[float] = mapped_column(Float, nullable=True)
    transcript: Mapped[str] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    is_local: Mapped[bool] = mapped_column(default=None, nullable=True)
    crime_processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, index=True)

    source: Mapped["Source"] = relationship(back_populates="articles")
    topic: Mapped["Topic"] = relationship(back_populates="articles")


class EmailSubscription(Base):
    __tablename__ = "email_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, default=lambda: secrets.token_urlsafe(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WhatsAppSubscription(Base):
    __tablename__ = "whatsapp_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(35), nullable=False, unique=True)  # whatsapp:+5592999999999
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DigestLog(Base):
    __tablename__ = "digest_logs"
    __table_args__ = (UniqueConstraint("date", name="uq_digest_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailySummary(Base):
    __tablename__ = "daily_summaries"
    __table_args__ = (UniqueConstraint("date", "topic_id", name="uq_summary_date_topic"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    article_ids: Mapped[dict] = mapped_column(JSON, nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)

    topic: Mapped["Topic"] = relationship()


class Prompt(Base):
    """Prompt ativo (editável) usado pelo sistema. Uma linha por nome."""
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromptVersion(Base):
    """Histórico append-only de todas as versões de cada prompt."""
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TopicAdjective(Base):
    __tablename__ = "topic_adjectives"

    id:            Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id:      Mapped[int]   = mapped_column(Integer, ForeignKey("topics.id"), nullable=False, index=True)
    word:          Mapped[str]   = mapped_column(String(100), nullable=False)
    tfidf_score:   Mapped[float] = mapped_column(Float, nullable=False)
    frequency:     Mapped[int]   = mapped_column(Integer, nullable=False)
    computed_date: Mapped[date]  = mapped_column(Date, nullable=False, index=True)

    topic: Mapped["Topic"] = relationship()


class WritingMetric(Base):
    """Métricas de escrita agregadas por fonte ou tema, computadas 1x/dia.

    Cada linha é o valor de uma métrica para um grupo (fonte ou tema), medido
    sobre o pool de título+resumo das notícias locais dos 30 dias anteriores a
    computed_date. Guardar um snapshot diário acumula a série temporal que
    alimentará a lente de evolução no tempo.

    group_type: "source" | "topic"
    metric:     "lexical_sophistication" | "nominalization_rate" | "word_length"
    """
    __tablename__ = "writing_metrics"

    id:            Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    computed_date: Mapped[date]  = mapped_column(Date, nullable=False, index=True)
    group_type:    Mapped[str]   = mapped_column(String(20), nullable=False)
    group_id:      Mapped[int]   = mapped_column(Integer, nullable=False, index=True)
    metric:        Mapped[str]   = mapped_column(String(40), nullable=False)
    value:         Mapped[float] = mapped_column(Float, nullable=False)
    n_articles:    Mapped[int]   = mapped_column(Integer, nullable=False)
    n_tokens:      Mapped[int]   = mapped_column(Integer, nullable=False)


class WritingInsight(Base):
    """Análise interpretativa (gerada por IA) das métricas de escrita, 1x/dia.

    Um texto curto, descritivo (não avaliativo), por lente (group_type) e data.
    A página exibe o texto mais recente abaixo do gráfico.
    """
    __tablename__ = "writing_insights"

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    computed_date: Mapped[date]     = mapped_column(Date, nullable=False, index=True)
    group_type:    Mapped[str]      = mapped_column(String(20), nullable=False)
    text:          Mapped[str]      = mapped_column(Text, nullable=False)
    model:         Mapped[str]      = mapped_column(String(40), nullable=False)
    created_at:    Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WhatsAppPushLog(Base):
    __tablename__ = "whatsapp_push_logs"
    __table_args__ = (UniqueConstraint("date", name="uq_wa_push_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CrimeMention(Base):
    """Um crime noticiado por um artigo. É a UNIDADE PRIMÁRIA da série.

    O objeto de estudo é a cobertura da imprensa, não a criminalidade real —
    só sabemos o que foi noticiado. Por isso uma linha aqui representa o ato de
    NOTICIAR um crime, e nunca é fundida com outra: se cinco veículos cobrem o
    mesmo latrocínio, são cinco menções. O agrupamento por caso vive em
    CrimeEvent, que é camada derivada e recomputável (event_id é anulável).

    Uma matéria só gera mais de uma menção se noticiar crimes de TIPOS
    diferentes — uma operação com 12 prisões por tráfico é uma menção só, com
    count_people=12. A UniqueConstraint abaixo é o que garante essa regra e
    torna a extração idempotente se o artigo for reprocessado.
    """
    __tablename__ = "crime_mentions"
    __table_args__ = (
        UniqueConstraint("article_id", "crime_type", name="uq_mention_article_type"),
    )

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    event_id:   Mapped[int] = mapped_column(ForeignKey("crime_events.id"), nullable=True, index=True)

    # crime_type é a FIGURA PENAL (nível 2, ~50 valores, preciso mas esparso).
    # crime_group é o bem jurídico tutelado (nível 1, ~13 valores) — é a série
    # densa que vai ao gráfico. Ambos vêm de nlp/crime_types.py; o grupo é
    # derivado do tipo, gravado aqui só para simplificar o GROUP BY do painel.
    crime_type:  Mapped[str]  = mapped_column(String(40), nullable=False, index=True)
    crime_group: Mapped[str]  = mapped_column(String(40), nullable=False, index=True)
    crime_types: Mapped[dict] = mapped_column(JSON, nullable=True)   # figuras secundárias do mesmo fato
    stage:       Mapped[str]  = mapped_column(String(20), nullable=False)  # fato|investigacao|prisao|julgamento|condenacao

    # Tentado x consumado (CP art. 14, II). Ortogonal a `stage`, que é o momento
    # processual: cabe "tentativa de homicídio" em etapa de julgamento. Sem este
    # campo, homicídio tentado e consumado viravam o mesmo registro — e numa
    # série sobre crime isso muda o significado do número, não é detalhe.
    tentativa: Mapped[bool] = mapped_column(Boolean, nullable=True)

    # Duas datas: um release de hoje sobre condenação de um crime de 2023 é
    # cobertura de hoje sobre fato antigo. Misturar as duas cria pico falso.
    occurred_on: Mapped[date] = mapped_column(Date, nullable=True, index=True)
    reported_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Até onde a matéria permite datar o fato: dia | mes | ano | desconhecida.
    # Existe porque o modelo não admite ignorar o dia — proibido de inventar, ele
    # respondia 2023-01-01 e depois 2023-06-01 para o mesmo caso. Perguntando a
    # precisão em separado, o código descarta occurred_on quando não for 'dia'.
    # De quebra vira dado de pesquisa: com que precisão a imprensa data os fatos.
    occurred_precision: Mapped[str] = mapped_column(String(12), nullable=True)

    municipio:     Mapped[str] = mapped_column(String(80), nullable=True, index=True)
    zona:          Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    bairro:        Mapped[str] = mapped_column(String(80), nullable=True, index=True)
    location_text: Mapped[str] = mapped_column(String(255), nullable=True)

    count_people: Mapped[int] = mapped_column(Integer, nullable=True)  # presos, vítimas, apreensões
    description:  Mapped[str] = mapped_column(Text, nullable=False)    # 1-2 frases, SEM nomes próprios

    # legal_ref NÃO vem do LLM: é consultado em nlp/crime_types.py a partir de
    # crime_type, portanto determinístico. Gravado aqui (e não só derivado em
    # consulta) para preservar a tipificação vigente à época da extração, caso
    # a taxonomia mude depois.
    legal_ref: Mapped[str] = mapped_column(String(60), nullable=True)

    # Já isto é observação sobre a MATÉRIA: ela própria citou o enquadramento
    # jurídico, ou apenas narrou o fato? É dado sobre a imprensa — permite
    # perguntar quais veículos tipificam e quais só descrevem.
    legal_cited_by_source: Mapped[bool] = mapped_column(Boolean, nullable=True)
    legal_text_source:     Mapped[str]  = mapped_column(String(255), nullable=True)

    # Nomes próprios: uso interno para agrupar menções do mesmo caso. Não vão
    # para a interface — description nasce sem nomes, o que mantém barata uma
    # eventual anonimização futura (UPDATE nesta coluna, sem reprocessar).
    entities: Mapped[dict] = mapped_column(JSON, nullable=True)

    confidence:   Mapped[float]    = mapped_column(Float, nullable=True)
    model:        Mapped[str]      = mapped_column(String(40), nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    article: Mapped["Article"] = relationship()


class CrimeEvent(Base):
    """Caso distinto, agrupando as menções que falam dele. CAMADA DERIVADA.

    Existe para responder o que a série de menções sozinha não responde: 20
    matérias são 20 crimes diferentes ou 1 crime repercutido 20 vezes? A razão
    mention_count/caso varia de 1x a 5x conforme o tipo de crime, e essa razão
    é um achado sobre prioridade editorial.

    Pode ser recalculada inteira sem tocar em crime_mentions — se o limiar de
    agrupamento estiver errado, reprocessa-se esta tabela e a série primária
    permanece intacta.
    """
    __tablename__ = "crime_events"

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    crime_type:  Mapped[str]  = mapped_column(String(40), nullable=False, index=True)
    crime_group: Mapped[str]  = mapped_column(String(40), nullable=False, index=True)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=True, index=True)

    municipio: Mapped[str] = mapped_column(String(80), nullable=True)
    zona:      Mapped[str] = mapped_column(String(20), nullable=True)
    bairro:    Mapped[str] = mapped_column(String(80), nullable=True)

    mention_count: Mapped[int] = mapped_column(Integer, default=1)  # repercussão
    source_count:  Mapped[int] = mapped_column(Integer, default=1)  # veículos distintos

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cluster_score: Mapped[float]    = mapped_column(Float, nullable=True)  # auditável


class DailySummaryVersion(Base):
    """Log append-only de todas as versões geradas de cada resumo do dia.

    Diferente de DailySummary (uma versão 'atual' por date/topic_id), aqui cada
    regeneração vira uma nova linha — preserva o histórico para estudos futuros.
    """
    __tablename__ = "daily_summary_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    article_ids: Mapped[dict] = mapped_column(JSON, nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    topic: Mapped["Topic"] = relationship()
