import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

def _build_url():
    database_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if database_url:
        return re.sub(r"^mysql://", "mysql+pymysql://", database_url)

    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "railway")
    return (
        f"mysql+pymysql://{user}:{password}"
        f"@{host}:{port}/{database}?charset=utf8mb4"
    )

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_build_url(), pool_pre_ping=True)
    return _engine

class Base(DeclarativeBase):
    pass

def get_session():
    return sessionmaker(bind=get_engine())()


def run_migrations():
    from sqlalchemy import text
    engine = get_engine()
    with engine.connect() as conn:
        # Adiciona coluna transcript se não existir
        exists = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'articles' "
            "AND COLUMN_NAME = 'transcript'"
        )).scalar()
        if not exists:
            conn.execute(text("ALTER TABLE articles ADD COLUMN transcript LONGTEXT NULL"))
            conn.commit()
            print("Migration: coluna transcript adicionada.")

        # Corrige URLs de canais YouTube de @handle para /channel/ID
        youtube_fixes = [
            ("https://www.youtube.com/channel/UCH_iB5NZNUDT3BITtcFPFQw",
             "https://www.youtube.com/feeds/videos.xml?channel_id=UCH_iB5NZNUDT3BITtcFPFQw",
             "https://www.youtube.com/@PortaldoHolandaTV"),
            ("https://www.youtube.com/channel/UCIZiuY6rbu3myUQ39vYsqRw",
             "https://www.youtube.com/feeds/videos.xml?channel_id=UCIZiuY6rbu3myUQ39vYsqRw",
             "https://www.youtube.com/@redeamazonicaoficial"),
            ("https://www.youtube.com/channel/UC880szznksA04nYdg2G-3eQ",
             "https://www.youtube.com/feeds/videos.xml?channel_id=UC880szznksA04nYdg2G-3eQ",
             "https://www.youtube.com/c/TVCM7"),
            ("https://www.youtube.com/channel/UClpkHFE0rwJOsA_Rzk7OK8A",
             "https://www.youtube.com/feeds/videos.xml?channel_id=UClpkHFE0rwJOsA_Rzk7OK8A",
             "https://www.youtube.com/@RecordManaus"),
            ("https://www.youtube.com/channel/UCJVYVZTlMgiytKA9hjZ3ioA",
             "https://www.youtube.com/feeds/videos.xml?channel_id=UCJVYVZTlMgiytKA9hjZ3ioA",
             "https://www.youtube.com/@AmazonasBand"),
            ("https://www.youtube.com/channel/UCg8t9F8LXjaOURUBnMZgb5g",
             "https://www.youtube.com/feeds/videos.xml?channel_id=UCg8t9F8LXjaOURUBnMZgb5g",
             "https://www.youtube.com/@amazonasatual1125"),
        ]
        for new_url, new_rss, old_url in youtube_fixes:
            conn.execute(text(
                "UPDATE sources SET url = :new_url, rss_url = :new_rss "
                "WHERE url = :old_url"
            ), {"new_url": new_url, "new_rss": new_rss, "old_url": old_url})

        # Desativa AM POST YouTube (handle inválido)
        conn.execute(text(
            "UPDATE sources SET active = 0 WHERE url = 'https://www.youtube.com/@portalampost'"
        ))

        # Adiciona coluna content se não existir
        has_content = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'articles' "
            "AND COLUMN_NAME = 'content'"
        )).scalar()
        if not has_content:
            conn.execute(text("ALTER TABLE articles ADD COLUMN content LONGTEXT NULL"))
            conn.commit()
            print("Migration: coluna content adicionada.")

        # Adiciona coluna is_local se não existir
        has_is_local = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'articles' "
            "AND COLUMN_NAME = 'is_local'"
        )).scalar()
        if not has_is_local:
            conn.execute(text("ALTER TABLE articles ADD COLUMN is_local TINYINT(1) NULL"))
            print("Migration: coluna is_local adicionada.")

        # Adiciona coluna image_data em daily_summaries se não existir
        has_image_data = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'daily_summaries' "
            "AND COLUMN_NAME = 'image_data'"
        )).scalar()
        if not has_image_data:
            conn.execute(text("ALTER TABLE daily_summaries ADD COLUMN image_data LONGBLOB NULL"))
            print("Migration: coluna image_data adicionada em daily_summaries.")

        conn.commit()
