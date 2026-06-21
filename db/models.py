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

    source: Mapped["Source"] = relationship(back_populates="articles")
    topic: Mapped["Topic"] = relationship(back_populates="articles")


class EmailSubscription(Base):
    __tablename__ = "email_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, default=lambda: secrets.token_urlsafe(32))
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
