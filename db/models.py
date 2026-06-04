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
