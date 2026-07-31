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

        # Adiciona coluna crime_processed_at se não existir. Marca os artigos já
        # avaliados pelo extrator de cobertura criminal — inclusive os que NÃO
        # tinham crime, para não reprocessá-los a cada ciclo. Deixar NULL em caso
        # de falha é o que torna a etapa retomável sozinha.
        has_crime_processed = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'articles' "
            "AND COLUMN_NAME = 'crime_processed_at'"
        )).scalar()
        if not has_crime_processed:
            conn.execute(text("ALTER TABLE articles ADD COLUMN crime_processed_at DATETIME NULL"))
            conn.execute(text(
                "CREATE INDEX ix_articles_crime_processed ON articles (crime_processed_at)"
            ))
            conn.commit()
            print("Migration: coluna crime_processed_at adicionada em articles.")

        # Adiciona coluna tentativa em crime_mentions se a tabela já existir.
        # Distingue crime tentado de consumado (CP art. 14, II) — sem ela,
        # "tentativa de feminicídio" e feminicídio consumado ficavam idênticos.
        tem_tabela_crimes = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'crime_mentions'"
        )).scalar()
        if tem_tabela_crimes:
            has_tentativa = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'crime_mentions' "
                "AND COLUMN_NAME = 'tentativa'"
            )).scalar()
            if not has_tentativa:
                conn.execute(text("ALTER TABLE crime_mentions ADD COLUMN tentativa TINYINT(1) NULL"))
                conn.commit()
                print("Migration: coluna tentativa adicionada em crime_mentions.")

            # Separa vítimas de suspeitos. O campo único count_people misturava
            # as duas contagens e ficava sem significado analítico.
            for coluna in ("count_victims", "count_suspects"):
                existe = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'crime_mentions' "
                    "AND COLUMN_NAME = :col"
                ), {"col": coluna}).scalar()
                if not existe:
                    conn.execute(text(f"ALTER TABLE crime_mentions ADD COLUMN {coluna} INT NULL"))
                    conn.commit()
                    print(f"Migration: coluna {coluna} adicionada em crime_mentions.")

        # Corrige tamanho da coluna phone em whatsapp_subscriptions (VARCHAR(20) → 35)
        phone_size = conn.execute(text(
            "SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'whatsapp_subscriptions' "
            "AND COLUMN_NAME = 'phone'"
        )).scalar()
        if phone_size is not None and phone_size < 35:
            conn.execute(text(
                "ALTER TABLE whatsapp_subscriptions MODIFY COLUMN phone VARCHAR(35) NOT NULL"
            ))
            print("Migration: coluna phone de whatsapp_subscriptions ampliada para 35.")

        conn.commit()
